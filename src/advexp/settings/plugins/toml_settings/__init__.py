# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""TOML file settings backend.

Importing this package enables the backend; no explicit registration call
is needed:

```python
from datetime import timedelta
from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.toml_settings as ts

ts.TOMLSettingsConfiguration.file_path = Path("app-settings.toml")

class AppSettings(adv_settings.Settings):
    session_ttl: timedelta = timedelta(minutes=30)

AppSettings.load_settings()
```

Classes are bound to their own files through the source builder of the
backend:

```python
class WindowSettings(
    adv_settings.Settings,
    options=ts.toml_source(file="window-settings.toml"),
):
    width: int = 800
```

Declare members through plain annotations (the binding of the class reads
them) or through the ``toml_setting`` factory, so that the assignments pass
type checking. Assigning a ``TOMLSetting`` instance does the same thing at
runtime, but type checkers report a type mismatch for it (see
``toml_setting``).
"""

from advexp.settings.plugins.toml_settings.configuration import TOMLSettingsConfiguration
from advexp.settings.plugins.toml_settings.options import toml_file, toml_source
from advexp.settings.plugins.toml_settings.plugin import TOMLSettingsPlugin
from advexp.settings.plugins.toml_settings.serializer import TOMLSettingsSerializer
from advexp.settings.plugins.toml_settings.setting import TOMLSetting, toml_setting
from advexp.settings_base.toml_file import TOML_FILE_METADATA
from advexp.settings_base.toml_options import NAME_PATTERN, TOML_METADATA_OPTIONS

__all__ = [
    "NAME_PATTERN",
    "TOMLSetting",
    "TOMLSettingsConfiguration",
    "TOMLSettingsPlugin",
    "TOMLSettingsSerializer",
    "TOML_METADATA_OPTIONS",
    "TOML_FILE_METADATA",
    "toml_file",
    "toml_setting",
    "toml_source",
]
