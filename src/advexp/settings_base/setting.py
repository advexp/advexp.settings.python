# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The family-wide factory of a member that the own source of the class resolves."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.required import REQUIRED


def setting(
    *,
    name: Optional[str] = None,
    default: Any = REQUIRED,
    metadata: Optional[Mapping[str, Any]] = None,
    aliases: Optional[Sequence[str]] = None,
    gt: Any = None,
    ge: Any = None,
    lt: Any = None,
    le: Any = None,
    eq: Any = None,
    ne: Any = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    regex: Optional[str] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    when: Any = None,
) -> Any:
    """Declare a member that the own source of the class resolves.

    This is the rich form of the plain declaration: the member has no family
    of its own, and it reads the source that its class declares — the one
    source binding of a settings class, or the chain of a configuration
    class. The family of that source builds the address of the member by its
    own rules (the environment prefix and case, the file key pattern), so the
    member is addressed according to the storage that it actually reads. A
    declared ``name=`` is a full literal address in that storage, and
    ``aliases=`` are full literal addresses in the same way.

    If ``default=`` is omitted (or is :data:`REQUIRED`), the member is
    required: a source must provide its value, or the load aborts. An
    optional member says so explicitly with ``default=None`` — or with any
    other value it wants served when no source has one.

    The factory builds the family-wide attribute, which belongs to no
    distribution: it works in the body of a settings class of either package
    and in a declaration base (:class:`~advexp.settings_base.setting_declarations.SettingDeclarations`)
    that the settings and configuration classes inherit. The packages
    re-export the factory from their roots, so the import may name either
    one — it is the same function.

    The keyword parameters after ``aliases=`` are the declared value
    constraints (``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, ``when``). A comparison bound may name a sibling member:
    the attribute object of a member that was declared earlier in the same
    class body, or — in a class that inherits a declaration base — the same
    object reached through the base (``ge=Declarations.low``). They are the
    same constraints that every member factory applies, and they run wherever
    a value reaches the member.
    """
    return BaseAttribute(
        name=name,
        default=default,
        metadata=metadata,
        aliases=aliases,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        eq=eq,
        ne=ne,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        validator=validator,
        when=when,
    )


def plain_member(default: Any) -> BaseAttribute:
    """The family-wide plain member for one default: the attribute that the
    plain declarations of a class body and the poured plain declarations of a
    declaration base both land as.

    This is the machinery's builder behind the plain declaration style; the
    applications spell :func:`setting` instead.
    """
    return BaseAttribute(
        name=None,
        default=default,
        metadata=None,
        aliases=None,
        gt=None,
        ge=None,
        lt=None,
        le=None,
        eq=None,
        ne=None,
        min_length=None,
        max_length=None,
        regex=None,
        validator=None,
        when=None,
    )
