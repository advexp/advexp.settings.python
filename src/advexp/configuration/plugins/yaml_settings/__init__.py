# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""YAML file configuration source.

Importing this package enables the source; no explicit registration call
is needed::

    import advexp.configuration as adv_config
    import advexp.configuration.plugins.yaml_settings as ys

    class AppConfig(adv_config.Configuration, options=ys.yaml_source("app.yaml")):
        # reads the full-name keys of app.yaml
        session_ttl: timedelta = ys.yaml_setting(default="0:30:00")

    AppConfig.load_configuration()

    # datetime.timedelta(seconds=5400) — parsed, not a string
    print(repr(AppConfig.session_ttl))

Declare members through the ``yaml_setting`` factory so that the
assignments pass type checking. Assigning a ``YAMLSetting`` instance does
the same thing at runtime, but type checkers report a type mismatch for it
(see ``yaml_setting``).

The link that a class declares names the file that it reads. It can also
anchor its keys inside a subtree of the document and set the key pattern;
see ``yaml_source``. This module contains the whole source (the builder,
the factory and the serializer), and importing it enables the source.
"""

from advexp.configuration.plugins.yaml_settings.options import yaml_source
from advexp.configuration.plugins.yaml_settings.plugin import YAMLSettingsPlugin
from advexp.configuration.plugins.yaml_settings.serializer import YAMLSettingsSerializer
from advexp.configuration.plugins.yaml_settings.setting import YAMLSetting, yaml_setting

__all__ = [
    "YAMLSetting",
    "YAMLSettingsPlugin",
    "YAMLSettingsSerializer",
    "yaml_setting",
    "yaml_source",
]
