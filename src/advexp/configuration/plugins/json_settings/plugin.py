# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the JSON file source.

Importing the package (which imports this module) enables the source, so no
explicit registration call is needed. See the package docstring for a usage
example.
"""

from __future__ import annotations

from advexp.configuration.plugin_api import (
    AttributeSerializerBinding,
    LibraryConfiguration,
    SettingsBasePlugin,
)
from advexp.configuration.plugins.json_settings.serializer import JSONSettingsSerializer
from advexp.configuration.plugins.json_settings.setting import JSONSetting


class JSONSettingsPlugin(SettingsBasePlugin):
    """Plugin object for the JSON file source."""

    # the declarative binding; the plugin base setup() registers
    # it at import of this package
    binding = AttributeSerializerBinding(JSONSetting, JSONSettingsSerializer)

    @property
    def plugin_name(self) -> str:
        return "JSONSettings"


LibraryConfiguration.register_settings_plugin(JSONSettingsPlugin)
