# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The neutral member of a layered configuration class."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.configuration._internal.configuration_attribute import ConfigurationAttribute
from advexp.settings_base.required import REQUIRED


class ChainSetting(ConfigurationAttribute):
    """The attribute of a member that the whole source chain resolves.

    The attribute names the setting, not the storage. A member declared
    through it has no source of its own: it reads the class's chain from top
    to bottom, and the first link that provides a value wins. Both the plain
    declaration (``token: str``) and the rich one (:func:`chain_setting`)
    produce this attribute. Each named link builds the member's address by
    the rules of its own family (the environment prefix and case, the JSON
    key pattern), so the same member is addressed differently in different
    links. A declared ``aliases=`` entry is a full literal address in every
    named link.
    """

    def __init__(
        self,
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
    ) -> None:
        super().__init__(
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


def chain_setting(
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
    """Declare a member that the whole source chain resolves. This is the
    type-checker-friendly spelling of :class:`ChainSetting`.

    It is the rich form of the plain declaration: the member reads the class's
    chain from top to bottom, and every link builds its address by the rules
    of its own family. If ``default=`` is omitted (or is ``REQUIRED``), the
    member is required: the chain must provide its value, or the load aborts.

    ``name=`` is the full literal address in every named link: the prefix, the
    case, and the key pattern never change it. ``aliases=`` are full literal
    addresses in the same way. A load tries the primary address first, then
    the aliases in their declared order, in every named link of the chain. The
    mapping link is the exception: its dictionary knows only the member name.

    The keyword parameters after ``aliases`` are the declared value
    constraints: ``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, and ``when``. They are applied to whatever the chain
    provides, and they are the same constraints that every member factory of
    the family applies.
    """
    return ChainSetting(
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
