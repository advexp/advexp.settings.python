# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""
Advexp.Settings — typed application settings with pluggable backends.

Define typed settings once, then load and save them through pluggable
backends (local files, environment variables, cloud secret storages).
Members are plain annotations; the source binding of the class reads them::

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

A bare annotation declares a required member. An annotated assignment
declares a member with that value as its default. The rich spelling of the
same member (with constraints or an explicit address) is
:func:`advexp.settings.setting`. A member that belongs to a single backend
is declared with the factory of that backend (``json_setting`` and the
others). A member that no storage ever serves is declared with the
``non_storage_setting`` factory of the core::

    from datetime import timedelta

    import advexp.settings as adv_settings

    class Limits(adv_settings.Settings):
        timeout: timedelta = adv_settings.non_storage_setting(default="0:30:00")

    # datetime.timedelta(seconds=1800) — converted, kept in memory
    print(repr(Limits.timeout))

The file of a file binding can be written as a template that is filled in
from an environment variable. This gives one file per environment: for
example, ``APP_ENV`` selects ``settings-dev.json`` or
``settings-prod.json``::

    from advexp.settings import env_parameter
    import advexp.settings.plugins.json_settings as js

    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

    class EnvSettings(
        adv_settings.Settings,
        options=js.json_source(file="settings-{APP_ENV}.json", parameters=app_env),
    ):
        token: str

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
    Setting,
    Settings,
    SettingValidationError,
    SourceLoadError,
    __version__,
    declared_module_defaults,
    env_parameter,
    for_this_module,
    non_storage_setting,
    setting,
)

__all__ = [
    "REQUIRED",
    "AggregateLoadError",
    "ConstraintViolationError",
    "ConversionError",
    "MemberLoadError",
    "MissingValueError",
    "PluginNotEnabledError",
    "SecretBytes",
    "SecretStr",
    "Setting",
    "SettingValidationError",
    "Settings",
    "LibraryConfiguration",
    "SourceLoadError",
    "__version__",
    "declared_module_defaults",
    "env_parameter",
    "for_this_module",
    "non_storage_setting",
    "setting",
]
