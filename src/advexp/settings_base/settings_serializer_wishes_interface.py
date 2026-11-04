# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Optional serializer wishes: storage-name formatting and context injection.

``set_serializer_params`` (context injection) is part of the same contract.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from advexp.settings_base.context import SettingsContext


class ISettingsSerializerWishes(abc.ABC):
    """Optional wishes: storage-name formatting and context injection."""

    @abc.abstractmethod
    def delimiter(self) -> str:
        """Name-part separator wish: ``'.'`` or ``'_'``.

        Any other value is replaced with ``'.'`` and reported through a
        library log warning (once per serializer class).
        """

    @abc.abstractmethod
    def remove_inappropriate_symbols(self, text: str) -> str:
        """Sanitize a name fragment before it is used in storage names."""

    @abc.abstractmethod
    def set_serializer_params(self, context: SettingsContext) -> None:
        """Called once after construction with the settings context."""
