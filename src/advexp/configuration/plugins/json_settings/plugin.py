# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the JSON file source.

Importing the package (which imports this module) enables the source, so no
explicit registration call is needed. See the package docstring for a usage
example.
"""

from __future__ import annotations

from advexp.configuration.plugin_api import (
    PACKAGE_NAME,
    AttributeSerializerBinding,
    LibraryConfiguration,
    SettingsBasePlugin,
)
from advexp.configuration.plugins.json_settings.serializer import JSONSettingsSerializer
from advexp.settings_base.json_setting import JSONSetting


class JSONSettingsPlugin(SettingsBasePlugin):
    """Plugin object for the JSON file source."""

    family = PACKAGE_NAME

    # the module-default spelling of the family reads through this
    # registration: the family slot keeps the shared member class free
    # of the other distribution's serializer
    binding = AttributeSerializerBinding(
        JSONSetting,
        JSONSettingsSerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "JSONSettings"


LibraryConfiguration.register_settings_plugin(JSONSettingsPlugin)
