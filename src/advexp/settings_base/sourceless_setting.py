# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The family-wide factory of a member that no source or storage ever serves."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED


class SourcelessSetting(BaseAttribute):
    """The attribute of a member that no source or storage ever serves.

    The member's value is its declared default, and nothing else arrives
    from outside: the load pass serves the default without asking any
    source, the load overrides skip the member, and the write passes of the
    writable package leave it alone. The value still reaches the member the
    in-memory ways of its package: an assignment on a settings class, and
    the bulk updates that set members. This is a member that the
    application states about itself — a schema version pinned in code, a
    feature flag the sources must not control, a working value that lives
    in memory alone until the next load.
    """

    SOURCELESS = True
    """The load machinery's mark: no source is ever asked for this member,
    and the load overrides skip it. See
    :attr:`BaseAttribute.SOURCELESS` for the machinery's reading of it."""

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
                "sourceless_setting() declares a member that no source or storage "
                "ever serves, so it needs a value: pass default="
            )
        # a sourceless member has no address: no name and no aliases reach
        # any storage, so the declaration carries none
        super().__init__(
            name=None,
            default=default,
            metadata=metadata,
            aliases=None,
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


def sourceless_setting(
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
    """Declare a member that no source or storage ever serves.

    The member lives outside every source: its value is the declared
    ``default=``, every load serves exactly that value, and the load
    overrides (``load_configuration(overrides={...})``) skip the member with
    a debug record. The value goes through the same declared-default
    machinery as any other member: it is converted to the member's
    annotation at the ``class`` statement, so a value in storage form
    (``"0:30:00"`` for a ``timedelta`` member) works as it does for any
    other member. ``default=`` is required: a sourceless member without a
    value could never be served, so the factory refuses it outright.

    On the writable side the member keeps the in-memory channels: an
    assignment sets it, ``update_from_dict`` and ``update_from_object`` set
    it like any other member, and ``to_dict`` includes it. A load, a
    delete, and a reset all return it to the declared value, and the write
    passes skip it — a save has nowhere to go, and ``contains_setting``
    reports ``False``, the answer of a storage that holds nothing.

    The factory builds the family-wide attribute, which belongs to no
    distribution: it works in the body of a settings class of either
    package and in a declaration base
    (:class:`~advexp.settings_base.setting_declarations.SettingDeclarations`)
    that the settings and configuration classes inherit. The packages
    re-export the factory from their roots, so the import may name either
    one — it is the same function.

    The keyword parameters after ``metadata`` are the declared value
    constraints (``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, ``when``). A comparison bound may name a sibling member:
    the attribute object of a member that was declared earlier in the same
    class body, or — in a class that inherits a declaration base — the same
    object reached through the base (``ge=Declarations.low``). They are the
    same constraints that every member factory applies, and they run
    wherever a value reaches the member: the declared default, an
    assignment, a load, a bulk update, and a save.
    """
    return SourcelessSetting(
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
