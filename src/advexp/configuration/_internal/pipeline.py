# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The loading pass of configuration classes.

The pass itself is the shared one of the family
(:func:`advexp.settings_base.loading.load_settings_class`). It walks the
members declared on a configuration class and resolves each of them
through the class's source chain: the first link that provides a value
wins, and the declared default is the implicit last layer. It then applies
type conversion and constraints, and reports each member's load problem
through the channel that the member's declaration selects. Loading is the
only storage operation of this package: nothing here writes a source back.
"""

from __future__ import annotations

from typing import Mapping, Optional, Tuple

from advexp.settings_base.context import SettingsContext
from advexp.settings_base.loading import load_settings_class
from advexp.settings_base.member_load_error import MemberLoadError


def load_configuration(
    context: SettingsContext, overrides: Optional[Mapping[str, object]] = None
) -> Tuple[MemberLoadError, ...]:
    """Load every member of the class from its sources.

    This is the shared load pass of the family: see
    :func:`advexp.settings_base.loading.load_settings_class`. The returned
    report holds the errors of the members that fell back to their defaults. A
    required member that got nothing usable aborts the load with
    :class:`~advexp.configuration.AggregateLoadError`. If the caller passed a
    mapping as ``overrides``, it is applied above the whole chain as the top
    layer of the pass, not as a declared link.
    """
    return load_settings_class(context, overrides)
