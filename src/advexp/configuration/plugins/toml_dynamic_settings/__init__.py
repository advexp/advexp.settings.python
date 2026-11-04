# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Reading dynamic settings from the TOML file source.

Dynamic settings are name-value pairs that have no declared class member:
their names appear at runtime on the writing side. This package is the
reading half. A class declares the group key of the writing class next to
its TOML source binding, and the collection (reached through the plugin)
reads the entries that this group holds, as a snapshot that an explicit
``load_configuration()`` call refreshes. Importing this package enables the
reader. See :mod:`advexp.configuration.plugins.json_dynamic_settings` for
the full usage example of the JSON counterpart. The TOML side is spelled in
exactly the same way, with ``toml_source(dynamic_of=...)`` and the plugin of
this package::

    import advexp.configuration.plugins.toml_dynamic_settings as tds

    dashboard = AppConfig.get_plugin(tds.TOMLDynamicSettingsPlugin)
    dashboard.load_configuration()  # the writer's group from the TOML file

The collection is read-only: every write (saving, deleting, setting a
value, or changing the setting metadata) is refused with a ``TypeError``,
the same guard that this package applies to its members. The writing side
of the entries is the dynamic plugin of the settings package; this package
reads what that plugin stored.

The entries are stored in the section that the writer laid out, which by
default is the ``"dynamic"`` table. The part of the writing class is nested
by its dots, and the name of an entry is a plain literal key::

    [dynamic."app.LocalSettings"]
    dark_mode = true

A writer that disabled the section (``dynamic_settings_section_name = None``
on its plugin) is read in the same way. The section parameters that the
reader inherits mirror those of the writer. If the writer moved the section
or switched to the flat layout, set the same parameters on the reading
plugin before calling ``load_configuration()``.

The shared file is the default, not a rule. The
``toml_source(dynamic_file=...)`` binding of the class, or the module-wide
``TOMLDynamicSettingsConfiguration.file_path``, points the reader at the
dynamic file of the writer, separate from the file of the declared members.
"""

from advexp.configuration.plugins.toml_dynamic_settings.plugin import (
    TOMLDynamicSettingsPlugin,
)
from advexp.configuration.plugins.toml_settings import (
    TOMLSetting,
    TOMLSettingsPlugin,
    toml_setting,
    toml_source,
)
from advexp.configuration.plugins.toml_settings.dynamic_configuration import (
    TOMLDynamicSettingsConfiguration,
)

__all__ = [
    "TOMLDynamicSettingsConfiguration",
    "TOMLDynamicSettingsPlugin",
    "TOMLSetting",
    "TOMLSettingsPlugin",
    "toml_setting",
    "toml_source",
]
