# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Reading dynamic settings from the YAML file source.

Dynamic settings are name-value pairs that have no declared class member:
their names appear at runtime on the writing side. This package is the
reading half. A class declares the group key of the writing class next to
its YAML source binding, and the collection (reached through the plugin)
reads the entries that this group holds, as a snapshot that an explicit
``load_configuration()`` call refreshes. Importing this package enables the
reader:

```python
from datetime import timedelta
from pathlib import Path

import advexp.configuration as adv_config
import advexp.configuration.plugins.yaml_dynamic_settings as yds
import advexp.configuration.plugins.yaml_settings as ys

# the writing side (the advexp.settings package) stores its dynamic
# entries of the class "app.LocalSettings" in app-settings.yaml


class DashboardConfig(
    adv_config.Configuration,
    options=ys.yaml_source(
        file="app-settings.yaml",
        dynamic_of="app.LocalSettings",
    ),
):
    # a declared member, read from the same file as always
    session_ttl: timedelta = ys.yaml_setting(default="0:30:00")


dashboard = DashboardConfig.get_plugin(yds.YAMLDynamicSettingsPlugin)
dashboard.load_configuration()  # this group's dynamic entries from the file
dark_mode = dashboard.get_setting("dark_mode", default=False)
sorted(dashboard)  # the entry names, the class metadata order first
dashboard.to_dict()  # the snapshot
```

The collection is read-only: every write (saving, deleting, setting a
value, or changing the setting metadata) is refused with a ``TypeError``,
the same guard that this package applies to its members. The writing side
of the entries is the dynamic plugin of the settings package; this package
reads what that plugin stored.

The group key of the writer is the name under which its entries are stored
in the document. It is ``"app.LocalSettings"`` for a class ``LocalSettings``
of the module ``app`` with the default name pattern (the key is the class
part of the writer's pattern after expansion, whatever pattern the writer
declared). The entries are stored in the section that the writer laid out,
which by default is the ``"dynamic"`` mapping, with one nested mapping per
writing class:

```yaml
app.LocalSettings.session_ttl: 0:30:00
dynamic:
  app.LocalSettings:
    dark_mode: true
```

A writer that disabled the section (``dynamic_settings_section_name = None``
on its plugin) is read in the same way. The section parameters that the
reader inherits mirror those of the writer. If the writer moved the section
or switched to the flat layout, set the same parameters on the reading
plugin before calling ``load_configuration()``.

The shared file is the default, not a rule. The
``yaml_source(dynamic_file=...)`` binding of the class, or the module-wide
``YAMLDynamicSettingsConfiguration.file_path``, points the reader at the
dynamic file of the writer, separate from the file of the declared members.
"""

from advexp.configuration.plugins.yaml_dynamic_settings.plugin import (
    YAMLDynamicSettingsPlugin,
)
from advexp.configuration.plugins.yaml_settings import (
    YAMLSetting,
    YAMLSettingsPlugin,
    yaml_setting,
    yaml_source,
)
from advexp.configuration.plugins.yaml_settings.dynamic_configuration import (
    YAMLDynamicSettingsConfiguration,
)

__all__ = [
    "YAMLDynamicSettingsConfiguration",
    "YAMLDynamicSettingsPlugin",
    "YAMLSetting",
    "YAMLSettingsPlugin",
    "yaml_setting",
    "yaml_source",
]
