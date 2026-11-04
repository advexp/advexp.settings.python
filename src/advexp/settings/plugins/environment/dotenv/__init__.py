# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Dotenv file settings backend.

Importing this package enables the backend; no explicit registration call
is needed. The package contains everything that the backend needs: the
``dotenv_source`` binding, the ``dotenv_setting`` factory, and the naming
constants of the family:

```python
import advexp.settings.plugins.environment.dotenv as env
import advexp.settings as adv_settings

class AppSettings(adv_settings.Settings, options=env.dotenv_source("app.env")):
    # SESSION_TTL in app.env
    session_ttl: timedelta = timedelta(minutes=30)

# SESSION_TTL=1:30:00 in the .env file
AppSettings.load_settings()

# datetime.timedelta(seconds=5400) — parsed, not a string
print(repr(AppSettings.session_ttl))
```

The file of a class is the one that its ``dotenv_source(...)`` binding
names. Otherwise, the module default of
:class:`~advexp.settings.plugins.environment.dotenv.configuration.DotenvConfiguration`
is used: ``.env`` in the working directory.

Names are built by the shared rules of the environment family: the naming
parameters of the binding apply, an explicit ``name=`` is the full address,
and the nested delimiter of the family addresses the fields of a dataclass
member. As a result, a variable that this backend writes resolves in
exactly the same way in the process environment backend. The backend
depends on the python-dotenv package: install it with the extra of the
distribution (``pip install "advexp-settings[dotenv]"``).

Declare members through the ``dotenv_setting`` factory so that the
assignments pass type checking. Assigning a ``DotenvSetting`` instance does
the same thing at runtime, but type checkers report a type mismatch for it
(see ``dotenv_setting``).

This module contains the whole backend (its factory and its source
builder), and importing it enables only this backend: the sibling backend
for the process environment is not enabled until its own module is
imported. The root of the family, ``advexp.settings.plugins.environment``,
contains only the naming vocabulary and enables no backend.
"""

from advexp.settings.plugins.environment.dotenv.configuration import DotenvConfiguration
from advexp.settings.plugins.environment.dotenv.options import dotenv_file, dotenv_source
from advexp.settings.plugins.environment.dotenv.plugin import DotenvPlugin
from advexp.settings.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.settings.plugins.environment.dotenv.setting import DotenvSetting, dotenv_setting
from advexp.settings_base.dotenv_file import DOTENV_FILE_METADATA
from advexp.settings_base.environment import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NESTED_DELIMITER,
    NameCase,
)

__all__ = [
    "DOTENV_FILE_METADATA",
    "DotenvConfiguration",
    "DotenvPlugin",
    "DotenvSerializer",
    "DotenvSetting",
    "ENVIRONMENT_METADATA_OPTIONS",
    "NAME_CASE",
    "NAME_PREFIX",
    "NESTED_DELIMITER",
    "NameCase",
    "dotenv_file",
    "dotenv_setting",
    "dotenv_source",
]
