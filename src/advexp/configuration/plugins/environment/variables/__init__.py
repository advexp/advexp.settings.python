# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Environment variables configuration source.

Importing this package enables the source; no explicit registration call
is needed. The module contains everything that the source needs: the
``environment_variable_setting`` factory and the chain builder of the
namespace of the family::

    import advexp.configuration.plugins.environment.variables as env
    import advexp.configuration as adv_config

    class AppConfig(adv_config.Configuration, options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER,
    )):
        # APP_SESSION_TTL, required
        session_ttl: timedelta = env.environment_variable_setting(default="0:30:00")

    # APP_SESSION_TTL=1:30:00 in the environment
    AppConfig.load_configuration()

    # datetime.timedelta(seconds=5400) — parsed, not a string
    print(repr(AppConfig.session_ttl))

Declare members through the ``environment_variable_setting`` factory so
that the assignments pass type checking. Assigning an
``EnvironmentVariableSetting`` instance does the same thing at runtime, but
type checkers report a type mismatch for it (see
``environment_variable_setting``).

This module contains the whole source (its factory and the naming
vocabulary of the family), and importing it enables only this source: the
dotenv sibling is not enabled until its own module is imported. The root of
the family, ``advexp.configuration.plugins.environment``, holds the chain
builder of the namespace of the family and enables no source.
"""

from advexp.configuration.plugins.environment.variables.options import env_source
from advexp.configuration.plugins.environment.variables.plugin import (
    EnvironmentVariablesPlugin,
)
from advexp.configuration.plugins.environment.variables.serializer import (
    EnvironmentVariablesSerializer,
)
from advexp.configuration.plugins.environment.variables.setting import (
    EnvironmentVariableSetting,
    environment_variable_setting,
)
from advexp.settings_base.environment import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NESTED_DELIMITER,
    NameCase,
)

__all__ = [
    "ENVIRONMENT_METADATA_OPTIONS",
    "EnvironmentVariableSetting",
    "EnvironmentVariablesPlugin",
    "EnvironmentVariablesSerializer",
    "NAME_CASE",
    "NAME_PREFIX",
    "NESTED_DELIMITER",
    "NameCase",
    "env_source",
    "environment_variable_setting",
]
