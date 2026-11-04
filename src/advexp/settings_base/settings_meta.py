# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The metaclass of settings classes.

Gives every settings class its own members registry, value storage and
context, and routes setting-name assignments on the class into the storage
— after the declared value constraints have their say.
"""

from __future__ import annotations

import collections.abc
import inspect
import typing
from typing import Any, Dict, Sequence, Set, cast

from advexp.settings_base.constraints import check_value
from advexp.settings_base.context import (
    CLASS_METADATA_NAME,
    SETTINGS_CONTEXT_ATTR,
    SettingsContext,
)
from advexp.settings_base.cross_validation import effective_values, validate_member_references
from advexp.settings_base.default_validation import validate_declared_defaults
from advexp.settings_base.family_boundaries import (
    class_family,
    settle_options,
    validate_attribute_families,
)
from advexp.settings_base.library_configuration import member_term
from advexp.settings_base.setting_descriptor import (
    SettingDescriptor,
    wrap_attribute_members,
)
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.sources import FILE_SEAT_SOURCES

_MEMBERS_ATTR = "__settings_members__"
_VALUES_ATTR = "__settings_values__"


def _collect_setting_members(cls: type) -> Dict[str, SettingMember]:
    """Collect declared settings walking the MRO from base to derived.

    Inheritance composes: a subclass loads the settings of its bases too,
    into its own storage.
    """
    members: Dict[str, SettingMember] = {}
    for klass in reversed(inspect.getmro(cls)):
        for name, value in vars(klass).items():
            if isinstance(value, SettingDescriptor):
                members[name] = SettingMember(name, value.attribute, value)

    hints = _resolve_annotations(cls)
    for member in members.values():
        member.annotation = hints.get(member.name)
    return members


def _resolve_annotations(cls: type) -> Dict[str, Any]:
    # (a user annotation may raise anything when evaluated)
    # noinspection PyBroadException
    try:
        return dict(typing.get_type_hints(cls))
    except Exception:  # noqa: BLE001 - unresolvable forward refs fall back to raw
        raw: Dict[str, Any] = {}
        for klass in reversed(inspect.getmro(cls)):
            raw.update(getattr(klass, "__annotations__", {}) or {})
        return raw


def _merge_options_entries(entries: Sequence[Any], class_name: str) -> Dict[str, Any]:
    """Combine the sequence form of ``options=`` into one mapping, from left to
    right.

    Every entry must be a mapping. If a name is declared by two entries, the
    ``class`` statement fails and names every shared name. This is the same loud
    rule that the keyword and the ``class_metadata`` of the body follow between
    themselves.
    """
    combined: Dict[str, Any] = {}
    shared: Set[str] = set()
    for entry in entries:
        if not isinstance(entry, collections.abc.Mapping):
            raise TypeError(
                f"{class_name}: every options= entry must be a mapping "
                f"of metadata names to values, got {type(entry).__name__}"
            )
        shared |= set(combined) & set(entry)
        combined.update(entry)
    if shared:
        names = ", ".join(repr(metadata_name) for metadata_name in sorted(shared))
        raise TypeError(
            f"{class_name} declares the metadata name(s) {names} more than once "
            f"in options=. Declare each name only once"
        )
    return combined


class SettingsMeta(type):
    """The metaclass that gives every settings class its own members, storage, and
    context.

    The ``class`` statement accepts one keyword of its own: ``options=`` is the
    readable spelling of the ``class_metadata`` declaration of the class
    (``class AppSettings(Settings, options=...)``). The keyword takes one
    mapping, or a sequence (a tuple or a list) of mappings. The helpers of
    several families and free keys can therefore fit in one keyword, combined
    from left to right, with every name declared once across the entries.

    The two spellings share one class. ``options=`` (the entry that the helper
    of a source family built) and the ``class_metadata`` of the body (the own
    keys of the application) are merged, and each name is declared once on one
    of the two sides. The key of a source family is a long distinctive name
    that the family chose for itself, so the two sides do not collide.

    A name that is declared on both sides makes the ``class`` statement fail.
    The error names the class and the shared names. A silent last write would
    overwrite one side with no indication of the failure.
    """

    # Injected per class by __new__ below (annotation only; the same
    # declarations sit on Settings for its own layer). An instance of
    # SettingsMeta is a settings class, so the base code addresses the
    # per-class state through the metaclass type.
    __settings_members__: Dict[str, SettingMember]
    __settings_values__: Dict[str, Any]

    def __new__(mcs, name, bases, namespace, options=None, **kwargs):
        # ``options=`` is the readable spelling of the class's class_metadata
        # declaration — ``class AppSettings(Settings, options=...)`` — landed
        # in the namespace under the reserved name, so everything downstream
        # (validation, the MRO merge, the runtime channel) sees one channel.
        # A body declaration is carried along as well: the two merge per
        # name, and a name shared by the two fails the class statement (a
        # silent last-write here would clobber one side with no indication
        # of the failure).
        # A malformed declaration (either side not a mapping) is left for
        # the context's declaration check, which fails the class statement
        # naming the offender
        #
        # the distribution boundary comes first: the family the bases carry
        # settles every ``options=`` spelling — a helper-built entry of
        # another distribution fails the class statement here — and the
        # members are checked right after the class exists
        family = class_family(bases, name)
        if isinstance(options, (list, tuple)):
            options = [settle_options(entry, family, name) for entry in options]
        elif options is not None:
            options = settle_options(options, family, name)
        declared = namespace.get(CLASS_METADATA_NAME)
        if declared is not None:
            namespace[CLASS_METADATA_NAME] = settle_options(declared, family, name)
        if options is not None:
            # the sequence form — several option mappings in one keyword —
            # combines into one mapping here, so everything downstream sees
            # the one shared merge of the keyword and the body below
            if isinstance(options, (list, tuple)):
                options = _merge_options_entries(options, name)
            if not isinstance(options, collections.abc.Mapping):
                # stored as the declaration whatever the body said: the
                # context's check fails the class statement naming it
                namespace[CLASS_METADATA_NAME] = options
            elif declared is None:
                namespace[CLASS_METADATA_NAME] = options
            elif isinstance(declared, collections.abc.Mapping):
                shared = sorted(set(declared) & set(options))
                if shared:
                    names = ", ".join(repr(metadata_name) for metadata_name in shared)
                    raise TypeError(
                        f"{name} declares the metadata name(s) {names} in both "
                        f"{CLASS_METADATA_NAME} and options=. Declare each name only once"
                    )
                namespace[CLASS_METADATA_NAME] = {**declared, **options}
            # a malformed body declaration stays put: the context's check
            # fails the class statement naming it
        # a family's file seat beside its own source binding names one
        # storage twice — the file belongs on the bound family's builder,
        # whatever side of the declaration spelled it
        declared_options = namespace.get(CLASS_METADATA_NAME)
        if isinstance(declared_options, collections.abc.Mapping):
            for seat, source in FILE_SEAT_SOURCES.items():
                if seat in declared_options and source in declared_options:
                    raise TypeError(
                        f"{name} declares the family's file seat {seat!r} alongside "
                        f"its source binding {source!r}. For a bound family, the "
                        f"file must be given on its source builder"
                    )
        # turn assigned setting attributes into descriptors before the class
        # exists, so __set_name__ fires for them during class creation
        wrap_attribute_members(namespace)
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        # per-class state; subclasses never share these with their bases
        setattr(cls, _VALUES_ATTR, {})
        members = _collect_setting_members(cls)
        setattr(cls, _MEMBERS_ATTR, members)
        # every class built here has Settings in its bases: to the type
        # checker a settings class is an instance of the metaclass
        settings_class = cast("SettingsMeta", cls)
        # a member the body declared with another distribution's attribute
        # fails the class statement here, before any validation reads it
        validate_attribute_families(settings_class)
        # member references of the declared constraints must name members
        # of this class and form no cycles, before anything resolves them
        validate_member_references(settings_class, members)
        # defaults are validated and converted before the class becomes
        # usable: an invalid default fails the class statement itself
        validate_declared_defaults(settings_class, members)
        setattr(cls, SETTINGS_CONTEXT_ATTR, SettingsContext(settings_class))
        return cls

    def __setattr__(cls, name, value):
        # assignments to setting names go to the class storage, keeping the
        # descriptor intact; the declared constraints get their say first
        members = cls.__dict__.get(_MEMBERS_ATTR)
        if members is not None and name in members:
            check_value(
                members[name].attribute,
                value,
                f"invalid value for {member_term(cls)} '{name}' of {cls.__name__}",
                siblings=effective_values(cast("SettingsMeta", cls)),
            )
            getattr(cls, _VALUES_ATTR)[name] = value
        else:
            super().__setattr__(name, value)

    def __delattr__(cls, name):
        members = cls.__dict__.get(_MEMBERS_ATTR)
        if members is not None and name in members:
            raise TypeError(
                f"'{name}' is a setting of {cls.__name__}; "
                f"use {cls.__name__}.delete_setting('{name}') instead of del"
            )
        super().__delattr__(name)
