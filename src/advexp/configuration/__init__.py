# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""
Advexp.Configuration — layered, read-only application configuration.

Define typed configuration once, then load it through a chain of
pluggable sources (environment variables, JSON files, a dictionary
declared in code). The chain resolves each member from top to bottom:
the first source that provides a value wins, and the declared default is
the implicit last layer. Sources are only ever read: the package never
writes a value back. This is the main difference between this package and
Advexp.Settings, the read-write package of the same family.

Quick start:

```python
from datetime import timedelta

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment as env

class AppConfig(
    adv_config.Configuration,
    options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER,
    ),
):
    session_ttl: timedelta = timedelta(minutes=30)

# APP_SESSION_TTL=1:30:00 in the environment
AppConfig.load_configuration()

# datetime.timedelta(seconds=5400) — parsed, not a string
print(repr(AppConfig.session_ttl))
```

A bare annotation declares a required member that the chain must provide.
An annotated assignment declares a member with that value as its default.
To add constraints or aliases, use
:func:`advexp.configuration.setting`. To declare a member that lives
outside the chain (a value that the sources never change), use
:func:`advexp.configuration.sourceless_setting`:

```python
import advexp.configuration as adv_config

class Endpoints(adv_config.Configuration):
    url: str = adv_config.sourceless_setting(default="https://api.example")

Endpoints.load_configuration()
print(Endpoints.url)  # https://api.example — the declared value
```

The file of a file link can be written as a template that is filled in
from an environment variable. This gives one file per environment: for
example, ``APP_ENV`` selects ``settings-dev.json`` or
``settings-prod.json``:

```python
from advexp.configuration import settings_profile, json_source, Sources

profile = settings_profile("APP_ENV", choices=("dev", "test", "prod"))

class AppConfig(adv_config.Configuration, options=Sources(
    json_source(file="app.json"),
    json_source(file="settings-{APP_ENV}.json", settings_profile=profile),
)):
    token: str
```

This module is the application-level API. Source (plugin) authors use
:mod:`advexp.configuration.plugin_api`.

The public API is under development and may change before the first
stable release.
"""

# (the facade's one sanctioned import of the internals; the ruff TID251 ban
# keeps everyone else out of _internal)
# noinspection PyProtectedMember
from advexp.configuration._internal.facade_sources import (
    MISSING_NONE,
    MISSING_RAISE,
    MISSING_SKIP,
    REQUIRED,
    AggregateLoadError,
    Configuration,
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
    SourcelessSetting,
    SourceLoadError,
    Sources,
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
    "Configuration",
    "SourcelessSetting",
    "ConstraintViolationError",
    "ConversionError",
    "MissingValueError",
    "MISSING_NONE",
    "MISSING_RAISE",
    "MISSING_SKIP",
    "PluginNotEnabledError",
    "MemberLoadError",
    "SecretBytes",
    "SecretStr",
    "SettingDeclarations",
    "SettingRef",
    "LibraryConfiguration",
    "SourceLoadError",
    "Sources",
    "__version__",
    "sourceless_setting",
    "declared_module_defaults",
    "settings_profile",
    "for_this_module",
    "setting",
]
