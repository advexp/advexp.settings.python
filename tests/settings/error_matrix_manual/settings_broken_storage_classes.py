"""The settings classes of the broken-storage scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

The classes cover the shapes that a broken storage needs:

- Required members only. A corrupt file collects one source error for each
  member, and an unreadable path does the same.
- The full matrix shape. A corrupt file, with an optional member present,
  raises the error of the parser unchanged, because a served default must
  not hide it.
- A JSON file that parses into an array.
- A dotenv file that holds a line that python-dotenv skips.
- A class with one optional member, for the save pass over a corrupt file.
"""

from settings_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.settings.plugins.json_settings import json_setting, json_source
from advexp.settings.plugins.toml_settings import toml_setting, toml_source
from advexp.settings.plugins.yaml_settings import yaml_setting, yaml_source

CORRUPT_REQUIRED_JSON_FILE = STORAGE_DIR / "corrupt-required.json"
CORRUPT_REQUIRED_TOML_FILE = STORAGE_DIR / "corrupt-required.toml"
CORRUPT_REQUIRED_YAML_FILE = STORAGE_DIR / "corrupt-required.yaml"

CORRUPT_OPTIONAL_JSON_FILE = STORAGE_DIR / "corrupt-optional.json"
CORRUPT_OPTIONAL_TOML_FILE = STORAGE_DIR / "corrupt-optional.toml"
CORRUPT_OPTIONAL_YAML_FILE = STORAGE_DIR / "corrupt-optional.yaml"

UNREADABLE_DOTENV_FILE = STORAGE_DIR / "unreadable.env"
UNREADABLE_JSON_FILE = STORAGE_DIR / "unreadable.json"
UNREADABLE_TOML_FILE = STORAGE_DIR / "unreadable.toml"
UNREADABLE_YAML_FILE = STORAGE_DIR / "unreadable.yaml"

TOP_LEVEL_ARRAY_JSON_FILE = STORAGE_DIR / "top-level-array.json"

BROKEN_LINE_DOTENV_FILE = STORAGE_DIR / "broken-line.env"

SAVE_INTO_CORRUPT_JSON_FILE = STORAGE_DIR / "save-into-corrupt.json"
SAVE_INTO_CORRUPT_TOML_FILE = STORAGE_DIR / "save-into-corrupt.toml"
SAVE_INTO_CORRUPT_YAML_FILE = STORAGE_DIR / "save-into-corrupt.yaml"


class CorruptRequiredJsonSettings(
    Settings,
    options=json_source(file=CORRUPT_REQUIRED_JSON_FILE),
):
    """Two required members reading a file the JSON parser refuses."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    control: int = json_setting(name="control", default=REQUIRED)


class CorruptRequiredTomlSettings(
    Settings,
    options=toml_source(file=CORRUPT_REQUIRED_TOML_FILE),
):
    """Two required members reading a file the TOML parser refuses."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    control: int = toml_setting(name="control", default=REQUIRED)


class CorruptOptionalJsonSettings(
    Settings,
    options=json_source(file=CORRUPT_OPTIONAL_JSON_FILE),
):
    """The full matrix shape on a corrupt JSON file: the optional members
    make the parser's error leave the load pass unchanged."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class CorruptOptionalTomlSettings(
    Settings,
    options=toml_source(file=CORRUPT_OPTIONAL_TOML_FILE),
):
    """The full matrix shape on a corrupt TOML file: the optional members
    make the parser's error leave the load pass unchanged."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)


class UnreadableDotenvSettings(
    Settings,
    options=dotenv_source(file=UNREADABLE_DOTENV_FILE),
):
    """Two required members whose dotenv path is a directory."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class UnreadableJsonSettings(
    Settings,
    options=json_source(file=UNREADABLE_JSON_FILE),
):
    """Two required members whose JSON path is a directory."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    control: int = json_setting(name="control", default=REQUIRED)


class UnreadableTomlSettings(
    Settings,
    options=toml_source(file=UNREADABLE_TOML_FILE),
):
    """Two required members whose TOML path is a directory."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    control: int = toml_setting(name="control", default=REQUIRED)


class TopLevelArrayJsonSettings(
    Settings,
    options=json_source(file=TOP_LEVEL_ARRAY_JSON_FILE),
):
    """The full matrix shape that reads a JSON file with an array in the place
    where the settings object should be.
    """

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class BrokenLineDotenvSettings(
    Settings,
    options=dotenv_source(file=BROKEN_LINE_DOTENV_FILE),
):
    """Two required members reading a dotenv file whose first line
    python-dotenv skips."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class SaveIntoCorruptJsonSettings(
    Settings,
    options=json_source(file=SAVE_INTO_CORRUPT_JSON_FILE),
):
    """One optional member, so that the save pass, not the load pass, reads the
    corrupt file.
    """

    known: int = json_setting(name="known", default=7)


class SaveIntoCorruptTomlSettings(
    Settings,
    options=toml_source(file=SAVE_INTO_CORRUPT_TOML_FILE),
):
    """One optional member, so that the save pass, not the load pass, reads the
    corrupt file.
    """

    known: int = toml_setting(name="known", default=7)


class CorruptRequiredYamlSettings(
    Settings,
    options=yaml_source(file=CORRUPT_REQUIRED_YAML_FILE),
):
    """Two required members reading a file the YAML parser refuses."""

    answer: int = yaml_setting(name="answer", default=REQUIRED)
    control: int = yaml_setting(name="control", default=REQUIRED)


class CorruptOptionalYamlSettings(
    Settings,
    options=yaml_source(file=CORRUPT_OPTIONAL_YAML_FILE),
):
    """The full matrix shape on a corrupt YAML file: the optional members
    make the parser's error leave the load pass unchanged."""

    answer: int = yaml_setting(name="answer", default=REQUIRED)
    plain: int = yaml_setting(name="plain", default=NO_DEFAULT)
    known: int = yaml_setting(name="known", default=7)
    control: int = yaml_setting(name="control", default=REQUIRED)


class UnreadableYamlSettings(
    Settings,
    options=yaml_source(file=UNREADABLE_YAML_FILE),
):
    """Two required members whose YAML path is a directory."""

    answer: int = yaml_setting(name="answer", default=REQUIRED)
    control: int = yaml_setting(name="control", default=REQUIRED)


class SaveIntoCorruptYamlSettings(
    Settings,
    options=yaml_source(file=SAVE_INTO_CORRUPT_YAML_FILE),
):
    """One optional member, so that the save pass, not the load pass, reads the
    corrupt file.
    """

    known: int = yaml_setting(name="known", default=7)
