# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The setting attribute base of this package's sources."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings._internal.package_name import PACKAGE_NAME
from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.no_default import NO_DEFAULT


class SettingsAttribute(BaseAttribute):
    """The setting attribute base of the sources of the settings package.

    This is the family base with the defaults of this package spelled out: if
    ``default=`` is omitted (or is
    :data:`~advexp.settings_base.no_default.NO_DEFAULT`), the member is
    optional, and ``None`` stands in when the storage has nothing. Source
    authors derive their attribute classes from this one, through
    ``advexp.settings.plugin_api``. The family base itself carries no default
    values for parameters, so the base of each package is the one place where
    the defaults of that package live.
    """

    FAMILY_NAME = PACKAGE_NAME
    """The distribution every attribute derived from this base belongs to;
    the settings machinery words its distribution boundary with it."""

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = NO_DEFAULT,
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
