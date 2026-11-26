# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin contract common to every plugin kind."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.context import SettingsContext


class IPlugin(abc.ABC):
    """The plugin contract: a name and the context of the settings class.

    Two plugin kinds share this contract, and each kind is marked by its own
    interface. A storage backend (``ISettingsPlugin``) registers setting
    attributes and serializers, and an extension (``IExtensionPlugin``) adds
    its own operations over one settings class. Both kinds register the same
    way, and user code reaches both through ``Settings.get_plugin(...)``.

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


PluginT = TypeVar("PluginT", bound=IPlugin)
"""The plugin class a ``get_plugin`` call requests; the call returns its instance."""
