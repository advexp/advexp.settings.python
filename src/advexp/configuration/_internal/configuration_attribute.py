# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The setting attribute base of this package's sources."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.configuration._internal.package_name import PACKAGE_NAME
from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.required import REQUIRED


class ConfigurationAttribute(BaseAttribute):
    """The setting attribute base of the configuration package's sources.

    This is the family base with one difference, which reflects the philosophy
    of the package: if ``default=`` is omitted (or is ``REQUIRED``), the member
    is required, so its value must come from a source. For an optional member,
    declare :data:`~advexp.settings_base.no_default.NO_DEFAULT` or a value.
    Source authors derive their attribute classes from this one, so their
    members behave like the members of the bundled sources out of the box:
    required by default, with no explicit sentinel to remember.
    """

    FAMILY_NAME = PACKAGE_NAME
    """The distribution every attribute derived from this base belongs to;
    the settings machinery words its distribution boundary with it."""

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
