# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the TOML file source.

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
from advexp.configuration.plugins.toml_settings.serializer import TOMLSettingsSerializer
from advexp.settings_base.toml_setting import TOMLSetting


class TOMLSettingsPlugin(SettingsBasePlugin):
    """Plugin object for the TOML file source."""

    family = PACKAGE_NAME

    # the module-default spelling of the family reads through this
    # registration: the family slot keeps the shared member class free
    # of the other distribution's serializer
    binding = AttributeSerializerBinding(
        TOMLSetting,
        TOMLSettingsSerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "TOMLSettings"


LibraryConfiguration.register_settings_plugin(TOMLSettingsPlugin)
