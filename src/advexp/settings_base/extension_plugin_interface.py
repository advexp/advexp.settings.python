# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The extension plugin contract: the plugin kind that adds operations."""

from __future__ import annotations

from advexp.settings_base.plugin_interface import IPlugin


class IExtensionPlugin(IPlugin):
    """The contract of the extension plugin kind.

    An extension adds its own operations to one settings class: it
    registers no setting attributes and no serializers, and it holds no
    storage. This is what keeps ecosystem-oriented functionality (a bridge
    to another library's models, and similar) out of the settings class
    API: the functionality rides a plugin instead of growing the class.

    What an extension offers is entirely its own API, so the contract adds
    no members of its own: it only carries the common
    :class:`~advexp.settings_base.plugin_interface.IPlugin` members — a
    name and the bound context of the class it serves.

    An extension registers like any plugin (a
    ``LibraryConfiguration.register_settings_plugin(...)`` call when its
    module is imported), and user code reaches it through
    ``Settings.get_plugin(...)``; the class of that call is the one and
    only class the returned instance works with.
    """
