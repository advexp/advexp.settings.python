# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The constant member: a value that the sources never touch."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from advexp.configuration._internal.configuration_attribute import ConfigurationAttribute
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED


class ConstantSetting(ConfigurationAttribute):
    """The attribute of a member outside the source chain.

    The member's value is its declared default, and nothing else: no link of
    the chain is asked for it, the load overrides skip it, and a reload serves
    the same declared value again. Examples are a schema version pinned in
    code, or a feature flag that the sources must not control. This is a member
    that the application states about itself, rather than reads from its
    environment. The declaration requires a value: a constant member without
    one could never be loaded, so the factory refuses it outright.
    """

    SOURCELESS = True
    """The load machinery's mark: no source is ever asked for this member,
    and the load overrides skip it."""

    def __init__(
        self,
        *,
        default: Any = REQUIRED,
        metadata: Optional[Mapping[str, Any]] = None,
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
        if default is REQUIRED or default is NO_DEFAULT:
            raise TypeError(
                "constant_setting() declares a member that no source ever loads, so "
                "it needs a value: pass default= (the value becomes the "
                "member's constant)"
            )
        super().__init__(
            name=None,
            default=default,
            metadata=metadata,
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


def constant_setting(
    *,
    default: Any = REQUIRED,
    metadata: Optional[Mapping[str, Any]] = None,
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
    """Declare a constant member. This is the type-checker-friendly spelling of
    :class:`ConstantSetting`.

    The member lives outside the source chain: its value is the declared
    ``default=``, every load serves exactly that value, and the load overrides
    (``load_configuration(overrides={...})``) skip the member and write a debug
    record. The value goes through the same declared-default machinery as any
    other member: it is converted to the member's annotation at the ``class``
    statement, so a value in storage form (``"0:30:00"`` for a ``timedelta``
    member) works as it does for any other member. ``default=`` is required: a
    constant without a value could never be loaded, so the factory refuses it.

    The keyword parameters after ``metadata`` are the declared value
    constraints. ``gt/ge/lt/le/eq/ne`` compare the value, ``min_length`` and
    ``max_length`` bound ``len(value)``, ``regex`` is an unanchored pattern
    that a ``str`` value must match, and ``validator`` is a callable that
    receives the value and returns whether it passes. ``when=`` names another
    member: while that member's value is falsy, the whole set of constraints is
    switched off. The constraints check the declared value in the same way as
    for any other member: a constant is immune to the sources, but not to its
    own declaration.
    """
    return ConstantSetting(
        default=default,
        metadata=metadata,
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
