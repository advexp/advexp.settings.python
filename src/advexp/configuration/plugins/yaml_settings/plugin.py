# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the YAML file source.

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
from advexp.configuration.plugins.yaml_settings.serializer import YAMLSettingsSerializer
from advexp.settings_base.yaml_setting import YAMLSetting


class YAMLSettingsPlugin(SettingsBasePlugin):
    """Plugin object for the YAML file source."""

    family = PACKAGE_NAME

    # the module-default spelling of the family reads through this
    # registration: the family slot keeps the shared member class free
    # of the other distribution's serializer
    binding = AttributeSerializerBinding(
        YAMLSetting,
        YAMLSettingsSerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "YAMLSettings"


LibraryConfiguration.register_settings_plugin(YAMLSettingsPlugin)
