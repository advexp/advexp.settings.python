# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The neutral member of a settings class."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings._internal.settings_attribute import SettingsAttribute
from advexp.settings_base.required import REQUIRED


class Setting(SettingsAttribute):
    """The attribute of a member that the own source binding of the class resolves.

    The attribute names the setting, not the storage. A member declared through
    it has no backend of its own: it reads the one source that the class
    declares through ``options=``. Both the plain declaration (``token: str``)
    and the rich one (:func:`setting`) produce this attribute. The family of
    the binding builds the address of the member by its own rules (the
    environment prefix and case, the JSON key pattern), so the member is
    addressed according to the storage that it actually reads. A declared
    ``name=`` is a full literal address in that storage.
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
    """Declare a member that the own source binding of the class resolves. This is
    the type-checker-friendly spelling of :class:`Setting`.

    It is the rich form of the plain declaration: the member reads the one
    source that its class declares through ``options=``, and the family of the
    binding builds its address. If ``default=`` is omitted (or is ``REQUIRED``),
    the member is required: the source must provide its value, or the load
    aborts.

    ``name=`` is the full literal address in the storage of the member: the
    environment prefix, the case, and the file key pattern never change it.
    ``aliases=`` are full literal addresses in the same way. A load tries the
    primary address first, then the aliases in their order.

    The keyword parameters after ``aliases`` are the declared value
    constraints: ``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, and ``when``. They are applied to whatever the source
    provides, and they are the same constraints that every member factory of
    the family applies.
    """
    return Setting(
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
