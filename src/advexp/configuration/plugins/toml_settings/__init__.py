# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""TOML file configuration source.

Importing this package enables the source; no explicit registration call
is needed::

    import advexp.configuration as adv_config
    import advexp.configuration.plugins.toml_settings as ts

    class AppConfig(adv_config.Configuration, options=ts.toml_source("app.toml")):
        # reads the dotted addresses of app.toml
        session_ttl: timedelta = ts.toml_setting(default="0:30:00")

    AppConfig.load_configuration()

    # datetime.timedelta(seconds=5400) — parsed, not a string
    print(repr(AppConfig.session_ttl))

Declare members through the ``toml_setting`` factory so that the
assignments pass type checking. Assigning a ``TOMLSetting`` instance does
the same thing at runtime, but type checkers report a type mismatch for it
(see ``toml_setting``).

The link that a class declares names the file that it reads. It can also
anchor its keys inside a subtree of the document and set the key pattern;
see ``toml_source``. On Python 3.10 and older, the source depends on the
tomli package: install it with the extra of the distribution
(``pip install "advexp-configuration[toml]"``). This module contains the
whole source (the builder, the factory and the serializer), and importing
it enables the source.
"""

from advexp.configuration.plugins.toml_settings.options import toml_source
from advexp.configuration.plugins.toml_settings.plugin import TOMLSettingsPlugin
from advexp.configuration.plugins.toml_settings.serializer import TOMLSettingsSerializer
from advexp.configuration.plugins.toml_settings.setting import TOMLSetting, toml_setting

__all__ = [
    "TOMLSetting",
    "TOMLSettingsPlugin",
    "TOMLSettingsSerializer",
    "toml_setting",
    "toml_source",
]
