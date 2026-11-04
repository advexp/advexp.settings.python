"""The settings classes of the dynamic-collection scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

Each class binds the static file backend and the dynamic collection of the
same format to one file: one static member, plus the name-value pairs that
appear at runtime.

There are two groups of scenarios for each format:

- The file is corrupt. The own load of the plugin aborts on the error of the
  parser.
- The collection fails on its own: a name that it does not hold, a value
  that the type of the default cannot take, and a save of a name that was
  never set.
"""

from settings_storage_paths import STORAGE_DIR

from advexp.settings import Settings
from advexp.settings.plugins.json_settings import json_setting, json_source
from advexp.settings.plugins.toml_settings import toml_setting, toml_source

DYNAMIC_CORRUPT_JSON_FILE = STORAGE_DIR / "dynamic-corrupt.json"
DYNAMIC_CORRUPT_TOML_FILE = STORAGE_DIR / "dynamic-corrupt.toml"

DYNAMIC_NAMES_JSON_FILE = STORAGE_DIR / "dynamic-names.json"
DYNAMIC_NAMES_TOML_FILE = STORAGE_DIR / "dynamic-names.toml"


class DynamicCorruptJsonSettings(
    Settings,
    options=(json_source(file=DYNAMIC_CORRUPT_JSON_FILE, dynamic_file=DYNAMIC_CORRUPT_JSON_FILE)),
):
    """One static member and the dynamic collection on a corrupt JSON
    file."""

    member: int = json_setting(name="member", default=1)


class DynamicCorruptTomlSettings(
    Settings,
    options=(toml_source(file=DYNAMIC_CORRUPT_TOML_FILE, dynamic_file=DYNAMIC_CORRUPT_TOML_FILE)),
):
    """One static member and the dynamic collection on a corrupt TOML
    file."""

    member: int = toml_setting(name="member", default=1)


class DynamicNamesJsonSettings(
    Settings,
    options=(json_source(file=DYNAMIC_NAMES_JSON_FILE, dynamic_file=DYNAMIC_NAMES_JSON_FILE)),
):
    """One static member and the dynamic collection the test drives through
    the plugin."""

    member: int = json_setting(name="member", default=1)


class DynamicNamesTomlSettings(
    Settings,
    options=(toml_source(file=DYNAMIC_NAMES_TOML_FILE, dynamic_file=DYNAMIC_NAMES_TOML_FILE)),
):
    """One static member and the dynamic collection the test drives through
    the plugin."""

    member: int = toml_setting(name="member", default=1)
