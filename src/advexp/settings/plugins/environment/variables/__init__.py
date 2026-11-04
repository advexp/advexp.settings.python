# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Environment variables settings backend.

Importing this package enables the backend; no explicit registration call
is needed. The package contains everything that the backend needs: the
``environment_variable_setting`` factory and the ``env_source`` binding of
the backend:

```python
import advexp.settings.plugins.environment.variables as env
import advexp.settings as adv_settings

class AppSettings(adv_settings.Settings, options=env.env_source(
    name_prefix="APP_", name_case=env.NameCase.UPPER,
)):
    # APP_SESSION_TTL
    session_ttl: timedelta = timedelta(minutes=30)

# APP_SESSION_TTL=1:30:00 in the environment
AppSettings.load_settings()

# datetime.timedelta(seconds=5400) — parsed, not a string
print(repr(AppSettings.session_ttl))
```

Declare members through the ``environment_variable_setting`` factory so
that the assignments pass type checking. Assigning an
``EnvironmentVariableSetting`` instance does the same thing at runtime, but
type checkers report a type mismatch for it (see
``environment_variable_setting``).

This module contains the whole backend (its factory and its source
builder), and importing it enables only this backend: the dotenv sibling is
not enabled until its own module is imported. The root of the family,
``advexp.settings.plugins.environment``, contains only the naming
vocabulary and enables no backend.
"""

from advexp.settings.plugins.environment.variables.options import env_source
from advexp.settings.plugins.environment.variables.plugin import (
    EnvironmentVariablesPlugin,
)
from advexp.settings.plugins.environment.variables.serializer import (
    EnvironmentVariablesSerializer,
)
from advexp.settings.plugins.environment.variables.setting import (
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
