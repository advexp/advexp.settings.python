# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""
Advexp.Settings — typed application settings with pluggable backends.

Define typed settings once, then load and save them through pluggable
backends (local files, environment variables, cloud secret storages).
Members are plain annotations; the source binding of the class reads them:

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js

class AppSettings(
    adv_settings.Settings,
    options=js.json_source(file="app-settings.json"),
):
    token: str  # REQUIRED: the storage or the load's abort
    session_ttl: timedelta = timedelta(minutes=30)

# "AppSettings.session_ttl": "1:30:00" in the file
AppSettings.load_settings()

# datetime.timedelta(seconds=5400) — parsed, not a string
print(repr(AppSettings.session_ttl))
```

A bare annotation declares a required member. An annotated assignment
declares a member with that value as its default. The rich spelling of the
same member (with constraints or an explicit address) is
:func:`advexp.settings.setting`. A member that belongs to a single backend
is declared with the factory of that backend's package — ``json_setting``
of the JSON plugin package, and the like; importing the package is what
enables the backend, so the factory and the backend always arrive
together. A member that no source or storage ever serves is declared with
the ``sourceless_setting`` factory of the core:

```python
from datetime import timedelta

import advexp.settings as adv_settings

class Limits(adv_settings.Settings):
    timeout: timedelta = adv_settings.sourceless_setting(default="0:30:00")

# datetime.timedelta(seconds=1800) — converted, no storage asked
print(repr(Limits.timeout))
```

The file of a file binding can be written as a template that is filled in
from an environment variable. This gives one file per environment: for
example, ``APP_ENV`` selects ``settings-dev.json`` or
``settings-prod.json``:

```python
from advexp.settings import settings_profile
import advexp.settings.plugins.json_settings as js

profile = settings_profile("APP_ENV", choices=("dev", "test", "prod"))

class EnvSettings(
    adv_settings.Settings,
    options=js.json_source(file="settings-{APP_ENV}.json", settings_profile=profile),
):
    token: str
```

This module is the application-level API. Backend (plugin) authors use
:mod:`advexp.settings.plugin_api`; ``samples/settings/custom_backend.py``
builds a backend in a single file on top of it.

The public API is under development and may change before the first
stable release.
"""

# (the facade's one sanctioned import of the internals; the ruff TID251 ban
# keeps everyone else out of _internal)
# noinspection PyProtectedMember
from advexp.settings._internal.facade_sources import (
    MISSING_NONE,
    MISSING_RAISE,
    MISSING_SKIP,
    REQUIRED,
    AggregateLoadError,
    ConstraintViolationError,
    ConversionError,
    LibraryConfiguration,
    MemberLoadError,
    MissingValueError,
    PluginNotEnabledError,
    SecretBytes,
    SecretStr,
    SettingDeclarations,
    SettingRef,
    Settings,
    SettingValidationError,
    SourcelessSetting,
    SourceLoadError,
    __version__,
    declared_module_defaults,
    for_this_module,
    setting,
    settings_profile,
    sourceless_setting,
)

__all__ = [
    "REQUIRED",
    "AggregateLoadError",
    "SourcelessSetting",
    "ConstraintViolationError",
    "ConversionError",
    "MemberLoadError",
    "MissingValueError",
    "MISSING_NONE",
    "MISSING_RAISE",
    "MISSING_SKIP",
    "PluginNotEnabledError",
    "SecretBytes",
    "SecretStr",
    "SettingDeclarations",
    "SettingRef",
    "SettingValidationError",
    "Settings",
    "LibraryConfiguration",
    "SourceLoadError",
    "__version__",
    "declared_module_defaults",
    "settings_profile",
    "for_this_module",
    "sourceless_setting",
    "setting",
]
