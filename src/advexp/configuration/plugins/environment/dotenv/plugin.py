# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the dotenv file source.

Importing the package (which imports this module) enables the source — no
explicit registration call is needed; see the package docstring for a usage
example.
"""

from __future__ import annotations

from advexp.configuration.plugin_api import (
    PACKAGE_NAME,
    AttributeSerializerBinding,
    LibraryConfiguration,
    SettingsBasePlugin,
)
from advexp.configuration.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.settings_base.dotenv_setting import DotenvSetting


class DotenvPlugin(SettingsBasePlugin):
    """Plugin object for the dotenv file source."""

    family = PACKAGE_NAME

    # the module-default spelling of the family reads through this
    # registration: the family slot keeps the shared member class free
    # of the other distribution's serializer
    binding = AttributeSerializerBinding(
        DotenvSetting,
        DotenvSerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "Dotenv"


LibraryConfiguration.register_settings_plugin(DotenvPlugin)
