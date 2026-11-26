# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the environment variables backend.

Importing the package (which imports this module) enables the backend — no
explicit registration call is needed; see the package docstring for a usage
example.
"""

from __future__ import annotations

from advexp.settings.plugin_api import (
    PACKAGE_NAME,
    AttributeSerializerBinding,
    LibraryConfiguration,
    SettingsBasePlugin,
)
from advexp.settings.plugins.environment.variables.serializer import (
    EnvironmentVariablesSerializer,
)
from advexp.settings_base.environment_variable_setting import EnvironmentVariableSetting


class EnvironmentVariablesPlugin(SettingsBasePlugin):
    """Plugin object for the environment variables backend."""

    family = PACKAGE_NAME

    # the module-default spelling of the family reads through this
    # registration: the family slot keeps the shared member class free
    # of the other distribution's serializer
    binding = AttributeSerializerBinding(
        EnvironmentVariableSetting,
        EnvironmentVariablesSerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "EnvironmentVariables"


LibraryConfiguration.register_settings_plugin(EnvironmentVariablesPlugin)
