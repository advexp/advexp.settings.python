# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""JSON file configuration source.

Importing this package enables the source; no explicit registration call
is needed:

```python
import advexp.configuration as adv_config
import advexp.configuration.plugins.json_settings as js

class AppConfig(adv_config.Configuration, options=js.json_source("app.json")):
    # reads the full-name keys of app.json
    session_ttl: timedelta = js.json_setting(default="0:30:00")

AppConfig.load_configuration()

# datetime.timedelta(seconds=5400) — parsed, not a string
print(repr(AppConfig.session_ttl))
```

Declare members through the ``json_setting`` factory so that the
assignments pass type checking. Assigning a ``JSONSetting`` instance does
the same thing at runtime, but type checkers report a type mismatch for it
(see ``json_setting``).

The link that a class declares names the file that it reads. It can also
anchor its keys inside a subtree of the document and set the key pattern;
see ``json_source``. This module contains the whole source (the builder,
the factory and the serializer), and importing it enables the source.
"""

from advexp.configuration.plugins.json_settings.options import json_source
from advexp.configuration.plugins.json_settings.plugin import JSONSettingsPlugin
from advexp.configuration.plugins.json_settings.serializer import JSONSettingsSerializer
from advexp.configuration.plugins.json_settings.setting import JSONSetting, json_setting

__all__ = [
    "JSONSetting",
    "JSONSettingsPlugin",
    "JSONSettingsSerializer",
    "json_setting",
    "json_source",
]
