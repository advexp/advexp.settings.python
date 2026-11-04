"""The settings classes of the missing-value scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

The shape of the members is the matrix of ``settings_healthy_classes``:
``answer`` and ``control`` are ``REQUIRED``, ``plain`` carries
``NO_DEFAULT``, and ``known`` declares 7.

The classes come in three groups of scenarios:

- The storage holds only ``control``.
- The storage holds nothing at all.
- The storage is full, but under addresses that the class never asks for.

The last class covers the naming options of the environment family: the name
of the member is built from the options of the class (the prefix plus the
case), and it is not spelled in the declaration.
"""

from settings_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment import NameCase
from advexp.settings.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.settings.plugins.environment.variables import env_source, environment_variable_setting
from advexp.settings.plugins.json_settings import json_setting, json_source
from advexp.settings.plugins.toml_settings import toml_setting, toml_source

ONLY_CONTROL_DOTENV_FILE = STORAGE_DIR / "only-control.env"
ONLY_CONTROL_JSON_FILE = STORAGE_DIR / "only-control.json"
ONLY_CONTROL_TOML_FILE = STORAGE_DIR / "only-control.toml"

NOTHING_STORED_DOTENV_FILE = STORAGE_DIR / "nothing-stored.env"
NOTHING_STORED_JSON_FILE = STORAGE_DIR / "nothing-stored.json"
NOTHING_STORED_TOML_FILE = STORAGE_DIR / "nothing-stored.toml"

WRONG_ADDRESSES_DOTENV_FILE = STORAGE_DIR / "wrong-addresses.env"
WRONG_ADDRESSES_JSON_FILE = STORAGE_DIR / "wrong-addresses.json"
WRONG_ADDRESSES_TOML_FILE = STORAGE_DIR / "wrong-addresses.toml"


class OnlyControlStoredEnvSettings(Settings):
    """The matrix shape reading the process environment; only ``control``
    will be set."""

    answer: int = environment_variable_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = environment_variable_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMX_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMX_CONTROL", default=REQUIRED)


class OnlyControlStoredDotenvSettings(
    Settings,
    options=dotenv_source(file=ONLY_CONTROL_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file; only ``control`` will be
    stored."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = dotenv_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMX_KNOWN", default=7)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class OnlyControlStoredJsonSettings(
    Settings,
    options=json_source(file=ONLY_CONTROL_JSON_FILE),
):
    """The matrix shape reading a JSON file; only ``control`` will be
    stored."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class OnlyControlStoredTomlSettings(
    Settings,
    options=toml_source(file=ONLY_CONTROL_TOML_FILE),
):
    """The matrix shape reading a TOML file; only ``control`` will be
    stored."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)


class NothingStoredEnvSettings(Settings):
    """The matrix shape reading the process environment; nothing will be
    set."""

    answer: int = environment_variable_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = environment_variable_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMX_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMX_CONTROL", default=REQUIRED)


class NothingStoredDotenvSettings(
    Settings,
    options=dotenv_source(file=NOTHING_STORED_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file that will not exist."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = dotenv_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMX_KNOWN", default=7)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class NothingStoredJsonSettings(
    Settings,
    options=json_source(file=NOTHING_STORED_JSON_FILE),
):
    """The matrix shape reading a JSON file that will not exist."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class NothingStoredTomlSettings(
    Settings,
    options=toml_source(file=NOTHING_STORED_TOML_FILE),
):
    """The matrix shape reading a TOML file that will not exist."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)


class WrongAddressesEnvSettings(Settings):
    """The matrix shape reading the process environment; the variables set
    will carry names the class never asks for."""

    answer: int = environment_variable_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = environment_variable_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMX_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMX_CONTROL", default=REQUIRED)


class WrongAddressesDotenvSettings(
    Settings,
    options=dotenv_source(file=WRONG_ADDRESSES_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file; the lines stored will carry
    names the class never asks for."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = dotenv_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMX_KNOWN", default=7)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class WrongAddressesJsonSettings(
    Settings,
    options=json_source(file=WRONG_ADDRESSES_JSON_FILE),
):
    """The matrix shape reading a JSON file; the keys stored are ones the
    class never asks for."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class WrongAddressesTomlSettings(
    Settings,
    options=toml_source(file=WRONG_ADDRESSES_TOML_FILE),
):
    """The matrix shape reading a TOML file; the keys stored are ones the
    class never asks for."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)


class EnvNamePatternSettings(
    Settings,
    options=env_source(name_prefix="EMX_", name_case=NameCase.UPPER),
):
    """An environment member whose storage name is built from the options of the
    class: the prefix ``EMX_`` plus the upper case, so the member ``mode`` reads
    the variable ``EMX_MODE``.
    """

    mode: str = environment_variable_setting(default="production")
