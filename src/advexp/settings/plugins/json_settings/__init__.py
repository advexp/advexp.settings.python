# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""JSON file settings backend.

Importing this package enables the backend; no explicit registration call
is needed::

    from datetime import timedelta
    from pathlib import Path

    import advexp.settings as adv_settings
    import advexp.settings.plugins.json_settings as js

    js.JSONSettingsConfiguration.file_path = Path("app-settings.json")

    class AppSettings(adv_settings.Settings):
        session_ttl: timedelta = timedelta(minutes=30)

    AppSettings.load_settings()

Classes are bound to their own files through the source builder of the
backend::

    class WindowSettings(
        adv_settings.Settings,
        options=js.json_source(file="window-settings.json"),
    ):
        width: int = 800

Declare members through plain annotations (the binding of the class reads
them) or through the ``json_setting`` factory, so that the assignments pass
type checking. Assigning a ``JSONSetting`` instance does the same thing at
runtime, but type checkers report a type mismatch for it (see
``json_setting``).
"""

from advexp.settings.plugins.json_settings.configuration import JSONSettingsConfiguration
from advexp.settings.plugins.json_settings.options import json_file, json_source
from advexp.settings.plugins.json_settings.plugin import JSONSettingsPlugin
from advexp.settings.plugins.json_settings.serializer import JSONSettingsSerializer
from advexp.settings.plugins.json_settings.setting import JSONSetting, json_setting
from advexp.settings_base.json_file import JSON_FILE_METADATA
from advexp.settings_base.json_options import JSON_METADATA_OPTIONS, NAME_PATTERN

__all__ = [
    "JSON_FILE_METADATA",
    "JSON_METADATA_OPTIONS",
    "JSONSetting",
    "JSONSettingsConfiguration",
    "JSONSettingsPlugin",
    "JSONSettingsSerializer",
    "NAME_PATTERN",
    "json_file",
    "json_setting",
    "json_source",
]
