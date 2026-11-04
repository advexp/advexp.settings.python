"""The configuration classes of the broken-storage scenarios.

Every class belongs to exactly one test. A configuration class keeps the
values that an earlier load gave it, so a class is never shared between
tests.

The classes cover the shapes that a broken storage needs:

- Required members only. A corrupt file collects one source error for each
  member, and an unreadable path does the same.
- The full matrix shape. A corrupt file, with an optional member present,
  raises the error of the parser unchanged, because a served default must
  not hide it.
- A JSON file that parses into an array.
- A dotenv file that holds a line that python-dotenv skips.

This package is read-only, so there is no save pass to break. The write
paths meet the read-only contract instead (a category of its own).
"""

from configuration_storage_paths import STORAGE_DIR

from advexp.configuration import REQUIRED, Configuration
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.configuration.plugins.json_settings import json_setting, json_source
from advexp.configuration.plugins.toml_settings import toml_setting, toml_source
from advexp.configuration.plugins.yaml_settings import yaml_setting, yaml_source

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


class CorruptRequiredJsonConfiguration(
    Configuration,
    options=json_source(file=CORRUPT_REQUIRED_JSON_FILE),
):
    """Two required members reading a file the JSON parser refuses."""

    answer: int = json_setting(name="answer")
    control: int = json_setting(name="control", default=REQUIRED)


class CorruptRequiredTomlConfiguration(
    Configuration,
    options=toml_source(file=CORRUPT_REQUIRED_TOML_FILE),
):
    """Two required members reading a file the TOML parser refuses."""

    answer: int = toml_setting(name="answer")
    control: int = toml_setting(name="control", default=REQUIRED)


class CorruptOptionalJsonConfiguration(
    Configuration,
    options=json_source(file=CORRUPT_OPTIONAL_JSON_FILE),
):
    """The full matrix shape on a corrupt JSON file: because of the optional
    members, the error of the parser leaves the load pass unchanged.
    """

    answer: int = json_setting(name="answer")
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class CorruptOptionalTomlConfiguration(
    Configuration,
    options=toml_source(file=CORRUPT_OPTIONAL_TOML_FILE),
):
    """The full matrix shape on a corrupt TOML file: because of the optional
    members, the error of the parser leaves the load pass unchanged.
    """

    answer: int = toml_setting(name="answer")
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)


class UnreadableDotenvConfiguration(
    Configuration,
    options=dotenv_source(file=UNREADABLE_DOTENV_FILE),
):
    """Two required members whose dotenv path is a directory."""

    answer: int = dotenv_setting(name="EMC_ANSWER")
    control: int = dotenv_setting(name="EMC_CONTROL", default=REQUIRED)


class UnreadableJsonConfiguration(
    Configuration,
    options=json_source(file=UNREADABLE_JSON_FILE),
):
    """Two required members whose JSON path is a directory."""

    answer: int = json_setting(name="answer")
    control: int = json_setting(name="control", default=REQUIRED)


class UnreadableTomlConfiguration(
    Configuration,
    options=toml_source(file=UNREADABLE_TOML_FILE),
):
    """Two required members whose TOML path is a directory."""

    answer: int = toml_setting(name="answer")
    control: int = toml_setting(name="control", default=REQUIRED)


class TopLevelArrayJsonConfiguration(
    Configuration,
    options=json_source(file=TOP_LEVEL_ARRAY_JSON_FILE),
):
    """The full matrix shape that reads a JSON file with an array in the place
    where the configuration object should be.
    """

    answer: int = json_setting(name="answer")
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class BrokenLineDotenvConfiguration(
    Configuration,
    options=dotenv_source(file=BROKEN_LINE_DOTENV_FILE),
):
    """Two required members reading a dotenv file whose first line
    python-dotenv skips."""

    answer: int = dotenv_setting(name="EMC_ANSWER")
    control: int = dotenv_setting(name="EMC_CONTROL", default=REQUIRED)


class CorruptRequiredYamlConfiguration(
    Configuration,
    options=yaml_source(file=CORRUPT_REQUIRED_YAML_FILE),
):
    """Two required members reading a file the YAML parser refuses."""

    answer: int = yaml_setting(name="answer")
    control: int = yaml_setting(name="control", default=REQUIRED)


class CorruptOptionalYamlConfiguration(
    Configuration,
    options=yaml_source(file=CORRUPT_OPTIONAL_YAML_FILE),
):
    """The full matrix shape on a corrupt YAML file: because of the optional
    members, the error of the parser leaves the load pass unchanged.
    """

    answer: int = yaml_setting(name="answer")
    plain: int = yaml_setting(name="plain", default=NO_DEFAULT)
    known: int = yaml_setting(name="known", default=7)
    control: int = yaml_setting(name="control", default=REQUIRED)


class UnreadableYamlConfiguration(
    Configuration,
    options=yaml_source(file=UNREADABLE_YAML_FILE),
):
    """Two required members whose YAML path is a directory."""

    answer: int = yaml_setting(name="answer")
    control: int = yaml_setting(name="control", default=REQUIRED)
