# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The settings plugin contract."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.context import SettingsContext


class ISettingsPlugin(abc.ABC):
    """The plugin contract: a name and the context of the settings class.

    A plugin bundles a storage backend behind this contract. It registers its
    setting attributes and serializers (conventionally from a ``setup()`` class
    method that is called at registration), and it exposes plugin-specific
    operations that user code reaches through ``Settings.get_plugin(...)``.

    The binding consists of two members. :meth:`bind_context` receives the
    context of the settings class once, right after construction, and
    ``context`` returns it afterward. Where the context is kept is up to the
    implementation: the contract says nothing about it.
    """

    @property
    @abc.abstractmethod
    def plugin_name(self) -> str:
        """Human-readable plugin name."""

    @property
    @abc.abstractmethod
    def context(self) -> SettingsContext:
        """The settings class context this plugin instance is bound to."""

    @abc.abstractmethod
    def bind_context(self, context: SettingsContext) -> None:
        """Receive the context of the settings class this instance serves.

        Called once by ``Settings.get_plugin``, right after construction;
        an implementation stores the context where its ``context``
        property reads it.
        """
