# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The metaclass of this distribution's settings classes."""

from __future__ import annotations

from typing import Any, Dict, cast

from advexp.settings_base.context import SETTINGS_CONTEXT_ATTR, SettingsContext
from advexp.settings_base.family_boundaries import settings_family
from advexp.settings_base.family_members import FAMILY_MEMBER_CLASSES
from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.setting_declarations import expand_base_declarations
from advexp.settings_base.setting_descriptor import expand_plain_members
from advexp.settings_base.settings_meta import SettingsMeta
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.sources import (
    _SOURCE_LINK_KEYS,
    EXCLUSIVE_SOURCE_SEATS,
    Sources,
    declared_source_links,
)


def _refuse_chains(options: Any, class_name: str) -> None:
    """Reject the source spellings of the other package at the ``class`` statement.

    A ``Sources(...)`` chain is a declaration of the layered package, and a
    bare :class:`~advexp.settings_base.source_binding.SourceBinding` is the
    result of its builder. Neither belongs in the ``options=`` of a settings
    class, where the sources are declared one family builder at a time. The
    ``class`` statement is where this mix surfaces, and the error names the
    spelling that the class received.
    """
    if isinstance(options, (Sources, SourceBinding)):
        raise TypeError(
            f"{class_name}: source chains are provided by advexp.configuration and "
            "are not supported here. Declare this class's sources one builder "
            "at a time (options=json_source(...), env_source(...), ...)"
        )
    if isinstance(options, (list, tuple)):
        for entry in options:
            _refuse_chains(entry, class_name)


def _anchor_listing(links: Any) -> str:
    # the anchors by their families, for the message naming them
    return ", ".join(
        link.attribute_class.__name__ for link in links if link.attribute_class is not None
    )


def _validate_anchor_membership(settings_class: type, context: SettingsContext) -> None:
    """Make the ``class`` statement fail for a member whose sources cannot name
    its storage.

    A member of a shared family (``json_setting`` and its siblings) reads the
    source link of that family, so the class must declare one, and the error
    names the member and the family it misses. A member of the family of its
    own (a third-party backend) reads through its own registered serializer
    and asks nothing of the anchors. A neutral member (a plain declaration or
    :func:`~advexp.settings_base.setting.setting`) reads the source binding of
    the class, and there must be exactly one binding. A class that declares
    none has no storage that the member could read, and a class that declares
    several leaves the storage of the member ambiguous. The error names the
    member and the way out: a family factory picks the storage of the member
    in the cases where a single binding cannot. A sourceless member reads
    nothing and passes this check whatever the class declares.
    """
    members: Dict[str, Any] = cast("SettingsMeta", settings_class).__settings_members__
    anchors = declared_source_links(context)
    for name, member in members.items():
        attribute = member.attribute
        if getattr(type(attribute), "SOURCELESS", False):
            continue
        if isinstance(attribute, FAMILY_MEMBER_CLASSES):
            if not any(link.serves(attribute) for link in anchors):
                if (
                    LibraryConfiguration._get_serializer_factory(
                        type(attribute), settings_family(settings_class)
                    )
                    is None
                ):
                    raise TypeError(
                        f"{settings_class.__name__}.{name} is declared with "
                        f"{type(attribute).__name__}, but the class declares no "
                        "source of that family. Declare one in the class statement "
                        "(options=json_source(...), for example), or import the "
                        "family's plugin module: its module default serves the "
                        "member without a binding"
                    )
                # the family's plugin is imported: its module default serves
                # the member, the spelling without a class binding
            continue
        if getattr(type(attribute), "FAMILY_NAME", None) is not None:
            # a member of a family of its own reads through the serializer
            # that its plugin registered; the anchors are not its storage
            continue
        if (
            LibraryConfiguration._get_serializer_factory(
                type(attribute), settings_family(settings_class)
            )
            is not None
        ):
            # a member of its own serializer (a custom backend) reads its own
            # way; the single binding of the class does not name its storage
            continue
        if not anchors:
            raise TypeError(
                f"{settings_class.__name__}.{name} is a plain member, but the class "
                "declares no source. Declare a source in the class statement, "
                "for example options=json_source(...) or env_source(...) "
                "(or a source builder from another family)"
            )
        if len(anchors) > 1:
            raise TypeError(
                f"{settings_class.__name__}.{name} is a plain member, but the class "
                f"declares {len(anchors)} sources ({_anchor_listing(anchors)}). "
                "To choose its storage, declare the member through a family "
                "factory, for example json_setting(...) or "
                "environment_variable_setting(...) (or a factory from "
                "another family)"
            )


def _validate_source_exclusivity(settings_class: type, context: SettingsContext) -> None:
    """Make the ``class`` statement fail when an exclusive seat is declared next to
    another seat.

    A storage that neutral members read (the mapping storage) cannot share a
    class with another source binding. There is no defined order between the
    bindings, so the storage that a plain member reads would depend on the
    internal registration of the seats, not on the declaration. The error
    names the class and both seats. It is raised for the class whose bindings
    hold the mix, including a subclass that declares a second seat over an
    inherited one. The members of a family lose nothing: their seats (the file
    seat of a family, or a factory member) are not source seats.
    """
    bound = [
        key
        for key in _SOURCE_LINK_KEYS
        if context.get_class_metadata(key, default=None) is not None
    ]
    for seat in EXCLUSIVE_SOURCE_SEATS:
        if seat not in bound:
            continue
        beside = [key for key in bound if key != seat]
        if beside:
            names = ", ".join(repr(key) for key in beside)
            raise TypeError(
                f"{settings_class.__name__} declares the seat {seat!r} alongside the "
                f"source {'seats' if len(beside) > 1 else 'seat'} {names}. The "
                "storage read by plain members is the class's only source "
                "binding, whereas the members of a family keep their own seats "
                "(a family file seat or a family factory member)"
            )


class PlainSettingsMeta(SettingsMeta):
    """Metaclass of the settings classes of this distribution: it handles plain
    members, the source seats, and the declaration bases.

    The plain annotations in the class body are members. A bare annotation
    declares a required member that the source of the class must provide. An
    annotated assignment declares a member with that value as its default. A
    ``ClassVar`` annotation stays an ordinary class attribute. Once the class
    exists, every member must have a source to read — one of the family of a
    family member, or the single binding of a neutral member — and the
    ``class`` statement rejects the members that have none or several.

    The declarations of a marked declaration base pour in as well, ahead of
    the wrapping: the members that a settings class shares with a
    configuration class land in its body as if it had spelled them.

    The ``options=`` keyword keeps its two spellings: one mapping, or a
    sequence of mappings. The source builders of the families
    (``json_source(...)``, ``env_source(...)``, ...) produce such mappings.
    The entry of each builder is stored under the own metadata key of the
    family: one builder per family, and several families side by side. A source
    chain (the declaration of the layered package) is rejected, because this
    package binds its storages one at a time.
    """

    def __new__(mcs, name, bases, namespace, options=None, **kwargs):
        # stamped entries of another family's helpers refuse in the base
        # metaclass's settle step; the chain spellings of the layered
        # package refuse here, naming the spelling itself
        _refuse_chains(options, name)
        expand_plain_members(namespace)
        # the declarations of the marked bases pour in after the body's own
        # plain members: a name the body declares wins over the pour
        expand_base_declarations(namespace, bases, name)
        cls = super().__new__(mcs, name, bases, namespace, options=options, **kwargs)
        context: SettingsContext = getattr(cls, SETTINGS_CONTEXT_ATTR)
        _validate_source_exclusivity(cls, context)
        _validate_anchor_membership(cls, context)
        return cls
