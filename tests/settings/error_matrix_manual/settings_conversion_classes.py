"""The settings classes of the conversion-failure scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

The shape of the members is the matrix of ``settings_healthy_classes``:
``answer`` and ``control`` are ``REQUIRED``, ``plain`` carries
``NO_DEFAULT``, and ``known`` declares 7.

There are three groups of scenarios:

- The required member holds a value that no conversion can take (``"abc"``
  for an ``int``).
- The two optional members hold such values.
- Both required members hold such values at once.

A failed pass applies nothing to the class. A completed pass serves every
member its value or its default.
"""

from settings_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.settings.plugins.environment.variables import environment_variable_setting
from advexp.settings.plugins.json_settings import json_setting, json_source
from advexp.settings.plugins.toml_settings import toml_setting, toml_source

BAD_REQUIRED_VALUE_DOTENV_FILE = STORAGE_DIR / "bad-required-value.env"
BAD_REQUIRED_VALUE_JSON_FILE = STORAGE_DIR / "bad-required-value.json"
BAD_REQUIRED_VALUE_TOML_FILE = STORAGE_DIR / "bad-required-value.toml"

BAD_REQUIRED_VALUES_DOTENV_FILE = STORAGE_DIR / "bad-required-values.env"
BAD_REQUIRED_VALUES_JSON_FILE = STORAGE_DIR / "bad-required-values.json"
BAD_REQUIRED_VALUES_TOML_FILE = STORAGE_DIR / "bad-required-values.toml"

BAD_OPTIONAL_VALUE_DOTENV_FILE = STORAGE_DIR / "bad-optional-value.env"
BAD_OPTIONAL_VALUE_JSON_FILE = STORAGE_DIR / "bad-optional-value.json"
BAD_OPTIONAL_VALUE_TOML_FILE = STORAGE_DIR / "bad-optional-value.toml"


class BadRequiredValueEnvSettings(Settings):
    """The matrix shape reading the process environment; ``answer`` will
    hold a value no conversion can take."""

    answer: int = environment_variable_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = environment_variable_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMX_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMX_CONTROL", default=REQUIRED)


class BadRequiredValueDotenvSettings(
    Settings,
    options=dotenv_source(file=BAD_REQUIRED_VALUE_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file; ``answer`` will hold a value
    no conversion can take."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = dotenv_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMX_KNOWN", default=7)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class BadRequiredValueJsonSettings(
    Settings,
    options=json_source(file=BAD_REQUIRED_VALUE_JSON_FILE),
):
    """The matrix shape reading a JSON file; ``answer`` will hold a value no
    conversion can take."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class BadRequiredValueTomlSettings(
    Settings,
    options=toml_source(file=BAD_REQUIRED_VALUE_TOML_FILE),
):
    """The matrix shape reading a TOML file; ``answer`` will hold a value no
    conversion can take."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)


class BadOptionalValueEnvSettings(Settings):
    """The matrix shape reading the process environment; ``plain`` and
    ``known`` will hold values no conversion can take."""

    answer: int = environment_variable_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = environment_variable_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMX_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMX_CONTROL", default=REQUIRED)


class BadOptionalValueDotenvSettings(
    Settings,
    options=dotenv_source(file=BAD_OPTIONAL_VALUE_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file; ``plain`` and ``known`` will
    hold values no conversion can take."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = dotenv_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMX_KNOWN", default=7)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class BadOptionalValueJsonSettings(
    Settings,
    options=json_source(file=BAD_OPTIONAL_VALUE_JSON_FILE),
):
    """The matrix shape reading a JSON file; ``plain`` and ``known`` will
    hold values no conversion can take."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class BadOptionalValueTomlSettings(
    Settings,
    options=toml_source(file=BAD_OPTIONAL_VALUE_TOML_FILE),
):
    """The matrix shape reading a TOML file; ``plain`` and ``known`` will
    hold values no conversion can take."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)


class BadRequiredValuesEnvSettings(Settings):
    """The matrix shape reading the process environment; ``answer`` and
    ``control`` will hold values no conversion can take."""

    answer: int = environment_variable_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = environment_variable_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMX_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMX_CONTROL", default=REQUIRED)


class BadRequiredValuesDotenvSettings(
    Settings,
    options=dotenv_source(file=BAD_REQUIRED_VALUES_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file; ``answer`` and ``control``
    will hold values no conversion can take."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = dotenv_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMX_KNOWN", default=7)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class BadRequiredValuesJsonSettings(
    Settings,
    options=json_source(file=BAD_REQUIRED_VALUES_JSON_FILE),
):
    """The matrix shape reading a JSON file; ``answer`` and ``control`` will
    hold values no conversion can take."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class BadRequiredValuesTomlSettings(
    Settings,
    options=toml_source(file=BAD_REQUIRED_VALUES_TOML_FILE),
):
    """The matrix shape reading a TOML file; ``answer`` and ``control`` will
    hold values no conversion can take."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)
