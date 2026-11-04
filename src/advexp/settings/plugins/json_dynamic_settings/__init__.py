# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Dynamic settings in the JSON file backend.

Dynamic settings are name-value pairs that have no declared class member:
their names appear at runtime (window layouts, dashboards added by users,
plugin configurations). Importing this package enables the backend. The
collection is reached through the plugin that is bound to the settings
class:

```python
from datetime import timedelta
from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.json_dynamic_settings as jds

jds.JSONSettingsConfiguration.file_path = Path("app-settings.json")


class LocalSettings(adv_settings.Settings):
    # a declared (static) setting
    session_ttl: timedelta = timedelta(minutes=30)


dynamic_settings_plugin = LocalSettings.get_plugin(jds.JSONDynamicSettingsPlugin)
dynamic_settings_plugin.load_settings()  # this class's dynamic entries from the same file
dark_mode = dynamic_settings_plugin.get_setting("dark_mode", default=False)
dynamic_settings_plugin.set_setting("dark_mode", True)
dynamic_settings_plugin.save_settings()
```

This module contains the whole scenario on its own. The dynamic collection
builds on the JSON file backend, so importing this package has already
brought that backend in. The module also re-exports the application names
of that backend (``json_setting``, ``json_source``,
``JSONSettingsConfiguration``, ``JSONSettingsPlugin``) next to its own, so
nothing else is needed to serve a class that has both static and dynamic
settings.

Static and dynamic settings share one file. The static members are stored
under their full names at the document root. The dynamic entries are stored
in their own section: the ``"dynamic"`` object, with one nested object per
settings class:

```json
{
  "app.LocalSettings.session_ttl": "0:30:00",
  "dynamic": {"app.LocalSettings": {"dark_mode": true}}
}
```

The section is a layout choice of this backend. It is controlled by two
parameters that mirror ``name=`` and ``path=`` of ``JSONSetting``:

- :attr:`JSONDynamicSettingsPlugin.dynamic_settings_section_name` is the key
  of the section. Assign another key to relocate the section, or ``None``
  for the flat layout (``D``-prefixed full-name keys at the document root).
- The optional :attr:`JSONDynamicSettingsPlugin.dynamic_settings_section_path`
  locates the section deeper in the document tree (``"/config"`` nests it
  inside the ``config`` object).

Both parameters follow the MRO of the settings class, each independently.

The shared file is the default, not a rule:
``JSONDynamicSettingsConfiguration.file_path`` gives the dynamic entries a
file of their own, separate from the static one:

```python
import advexp.settings.plugins.json_dynamic_settings as jds

jds.JSONDynamicSettingsConfiguration.file_path = Path("dynamic-settings.json")
```

The dynamic side of a single class can be moved separately with the
``dynamic_file=`` parameter of the ``json_source(...)`` binding of the
class. It wins over the module default:

```python
import advexp.settings.plugins.json_dynamic_settings as jds


class LocalSettings(
    Settings,
    options=jds.json_source(
        file="window-settings.json",
        dynamic_file="window-dynamic-settings.json",
    ),
):
    session_ttl: timedelta = timedelta(minutes=30)
```

The ``file_path`` property of the plugin instance is the imperative
spelling of the same binding.

If both are unset (the default), the dynamic entries go into the static
file. This is the file of the own ``json_source(file=...)`` binding of the
class, or of its ``json_file(...)`` seat, or the file set module-wide
through ``JSONSettingsConfiguration.file_path``.
"""

from advexp.settings.plugins.json_dynamic_settings.plugin import JSONDynamicSettingsPlugin
from advexp.settings.plugins.json_settings import (
    JSONSettingsConfiguration,
    JSONSettingsPlugin,
    json_setting,
    json_source,
)
from advexp.settings.plugins.json_settings.dynamic_configuration import (
    JSONDynamicSettingsConfiguration,
)
from advexp.settings_base.json_file import JSON_DYNAMIC_FILE_METADATA
from advexp.settings_base.names import DEFAULT_SETTINGS_NAME_PATTERN

__all__ = [
    "DEFAULT_SETTINGS_NAME_PATTERN",
    "JSON_DYNAMIC_FILE_METADATA",
    "JSONDynamicSettingsConfiguration",
    "JSONDynamicSettingsPlugin",
    "JSONSettingsConfiguration",
    "JSONSettingsPlugin",
    "json_setting",
    "json_source",
]
