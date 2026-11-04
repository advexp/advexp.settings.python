# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the dotenv file source.

Importing the package (which imports this module) enables the source — no
explicit registration call is needed; see the package docstring for a usage
example.
"""

from __future__ import annotations

from advexp.configuration.plugin_api import (
    AttributeSerializerBinding,
    LibraryConfiguration,
    SettingsBasePlugin,
)
from advexp.configuration.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.configuration.plugins.environment.dotenv.setting import DotenvSetting


class DotenvPlugin(SettingsBasePlugin):
    """Plugin object for the dotenv file source."""

    # the declarative binding; the plugin base setup() registers
    # it at import of this package
    binding = AttributeSerializerBinding(DotenvSetting, DotenvSerializer)

    @property
    def plugin_name(self) -> str:
        return "Dotenv"


LibraryConfiguration.register_settings_plugin(DotenvPlugin)
