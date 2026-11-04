# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""YAML file settings backend.

Importing this package enables the backend; no explicit registration call
is needed:

```python
from datetime import timedelta
from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.yaml_settings as ys

ys.YAMLSettingsConfiguration.file_path = Path("app-settings.yaml")

class AppSettings(adv_settings.Settings):
    session_ttl: timedelta = timedelta(minutes=30)

AppSettings.load_settings()
```

Classes are bound to their own files through the source builder of the
backend:

```python
class WindowSettings(
    adv_settings.Settings,
    options=ys.yaml_source(file="window-settings.yaml"),
):
    width: int = 800
```

Declare members through plain annotations (the binding of the class reads
them) or through the ``yaml_setting`` factory, so that the assignments pass
type checking. Assigning a ``YAMLSetting`` instance does the same thing at
runtime, but type checkers report a type mismatch for it (see
``yaml_setting``).
"""

from advexp.settings.plugins.yaml_settings.configuration import YAMLSettingsConfiguration
from advexp.settings.plugins.yaml_settings.options import yaml_file, yaml_source
from advexp.settings.plugins.yaml_settings.plugin import YAMLSettingsPlugin
from advexp.settings.plugins.yaml_settings.serializer import YAMLSettingsSerializer
from advexp.settings.plugins.yaml_settings.setting import YAMLSetting, yaml_setting
from advexp.settings_base.yaml_file import YAML_FILE_METADATA
from advexp.settings_base.yaml_options import NAME_PATTERN, YAML_METADATA_OPTIONS

__all__ = [
    "NAME_PATTERN",
    "YAML_FILE_METADATA",
    "YAML_METADATA_OPTIONS",
    "YAMLSetting",
    "YAMLSettingsConfiguration",
    "YAMLSettingsPlugin",
    "YAMLSettingsSerializer",
    "yaml_file",
    "yaml_setting",
    "yaml_source",
]
