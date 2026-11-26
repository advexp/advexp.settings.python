# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The metaclass of configuration classes."""

from __future__ import annotations

from typing import Any, Dict, cast

from advexp.settings_base.context import SETTINGS_CONTEXT_ATTR, SettingsContext
from advexp.settings_base.family_boundaries import class_family, settings_family
from advexp.settings_base.family_members import FAMILY_MEMBER_CLASSES
from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.setting_declarations import expand_base_declarations
from advexp.settings_base.setting_descriptor import expand_plain_members
from advexp.settings_base.settings_meta import SettingsMeta
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.sources import SOURCE_CHAIN_METADATA, Sources, chain_options_entries


def _validate_chain_membership(settings_class: type, context: SettingsContext) -> None:
    """Make the ``class`` statement fail for a member that its chain cannot resolve.

    A neutral member (a plain declaration or ``setting``) reads the
    class's chain, so a class without a chain cannot load it. The ``class``
    statement then fails with an error that names the member, instead of
    letting the load miss every address. A member declared through a family's
    factory reads the links of that family in the chain, so a chain that has no
    such link fails in the same way, naming the member and the family. Members
    outside the chain (a sourceless member) ask nothing of the chain and pass whatever
    the chain holds.
    """
    chain = context.get_class_metadata(SOURCE_CHAIN_METADATA, default=None)
    members: Dict[str, Any] = cast("SettingsMeta", settings_class).__settings_members__
    for name, member in members.items():
        attribute = member.attribute
        if getattr(type(attribute), "SOURCELESS", False):
            continue
        if isinstance(attribute, FAMILY_MEMBER_CLASSES):
            # a member of a shared family reads the links of that family in
            # the chain, the same pass a member of a printed family takes
            if chain is None or not any(link.serves(attribute) for link in chain):
                raise TypeError(
                    f"{settings_class.__name__}.{name} is declared with "
                    f"{type(attribute).__name__}, but the class's source chain has "
                    "no link of that family. Add one to options=, and the member "
                    "will read from it"
                )
            continue
        if getattr(type(attribute), "FAMILY_NAME", None) is not None:
            if chain is None or not any(link.serves(attribute) for link in chain):
                raise TypeError(
                    f"{settings_class.__name__}.{name} is declared with "
                    f"{type(attribute).__name__}, but the class's source chain has no "
                    f"link of that family. Add one to options=, and the member will read from it"
                )
            continue
        if (
            LibraryConfiguration._get_serializer_factory(
                type(attribute), settings_family(settings_class)
            )
            is not None
        ):
            # a member of its own serializer (a custom backend) reads its own
            # way; the chain does not name its storage
            continue
        # a neutral member (a plain declaration or the family-wide rich
        # spelling): every link of the chain may serve it, so the chain itself
        # is what the member cannot do without
        if chain is None:
            raise TypeError(
                f"{settings_class.__name__}.{name} is a neutral member, but the "
                "class declares no source chain. Declare the chain in the "
                "class statement (options=Sources(...)), or bind a source "
                "directly, for example options=json_source(...) or "
                "options=env_source(...) (or a source builder from another "
                "family)"
            )


class ConfigurationMeta(SettingsMeta):
    """Metaclass of configuration classes: it handles plain members, the chain,
    and the read-only guard on writes.

    The plain annotations in the class body are members. A bare annotation
    declares a required member that the chain must provide. An annotated
    assignment declares a member with that value as its default. A ``ClassVar``
    annotation stays an ordinary class attribute. Once the class exists, every
    member must be resolvable (a neutral member needs a chain, and a member of
    a family factory needs a link of that family), and the ``class`` statement
    rejects the members that are not.

    Assigning to or deleting a declared member on the class raises an error.
    The only permitted way to write is the load pass, which fills the value
    storage directly. Required members are not the work of this metaclass: the
    attribute itself carries the requirement, as the ``REQUIRED`` sentinel that
    this package's attribute base declares as the value of its ``default``
    parameter.
    """

    def __new__(mcs, name, bases, namespace, options=None, **kwargs):
        # a source chain — the layered spelling of ``options=``: laid out
        # into the chain's metadata entry plus the links' side entries (the
        # environment naming, when a link declares it), so everything
        # downstream sees the one shared channel. A lone link is the
        # one-link chain of the same shape; a link inside the options=
        # sequence is neither and fails here, for the order of a chain
        # read out of two shapes is order the reader cannot see
        family = class_family(bases, name)
        if isinstance(options, (Sources, SourceBinding)):
            options = chain_options_entries(options, family, name)
        elif isinstance(options, (list, tuple)):
            for entry in options:
                if isinstance(entry, (Sources, SourceBinding)):
                    raise TypeError(
                        f"{name}: a source builder was passed inside the options= "
                        "sequence. The chain counts as a single entry: pass "
                        "Sources(...) containing the builders to options= instead"
                    )
        expand_plain_members(namespace)
        # the declarations of the marked bases pour in after the body's own
        # plain members: a name the body declares wins over the pour
        expand_base_declarations(namespace, bases, name)
        cls = super().__new__(mcs, name, bases, namespace, options=options, **kwargs)
        context: SettingsContext = getattr(cls, SETTINGS_CONTEXT_ATTR)
        _validate_chain_membership(cls, context)
        return cls

    def __setattr__(cls, name, value):
        # the members registry sits in every class this metaclass builds;
        # cls.__dict__ (not getattr) limits the check to the class's own
        # registry, the same lookup SettingsMeta.__setattr__ applies
        members = cls.__dict__.get("__settings_members__")
        if members is not None and name in members:
            raise TypeError(
                f"'{name}' is a read-only member of {cls.__name__}: configuration "
                "values are loaded from their sources and cannot be assigned. "
                "Call load_configuration() to reload them"
            )
        super().__setattr__(name, value)

    def __delattr__(cls, name):
        # the deletion twin of the write guard: the base class's advice
        # names the settings package's API, which this package does not
        # carry — a member of a configuration class is never deletable
        members = cls.__dict__.get("__settings_members__")
        if members is not None and name in members:
            raise TypeError(
                f"'{name}' is a read-only member of {cls.__name__}: configuration "
                "values are loaded from their sources and cannot be assigned. "
                "Call load_configuration() to reload them"
            )
        super().__delattr__(name)
