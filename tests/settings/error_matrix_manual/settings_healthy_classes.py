"""The settings classes of the healthy-load scenarios.

Every class in this suite belongs to exactly one test. A settings class
keeps the values that an earlier load gave it (a failed load does not clear
them), so a class is never shared between tests.

The four members cover the declaration states that a member can be in:

* ``answer`` is ``REQUIRED`` (no default). The failure scenarios break this
  member.
* ``plain`` is ``NO_DEFAULT``. A bare member serves ``None`` when nothing is
  stored.
* ``known`` has a declared default (7).
* ``control`` is ``REQUIRED`` and is always stored, so a broken run still
  shows a healthy load next to the failures.
"""

from settings_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.settings.plugins.environment.variables import environment_variable_setting
from advexp.settings.plugins.json_settings import json_setting, json_source
from advexp.settings.plugins.toml_settings import toml_setting, toml_source

HEALTHY_DOTENV_FILE = STORAGE_DIR / "healthy.env"
HEALTHY_JSON_FILE = STORAGE_DIR / "healthy.json"
HEALTHY_TOML_FILE = STORAGE_DIR / "healthy.toml"


class HealthyEnvSettings(Settings):
    """The matrix shape reading the process environment."""

    answer: int = environment_variable_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = environment_variable_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMX_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMX_CONTROL", default=REQUIRED)


class HealthyDotenvSettings(
    Settings,
    options=dotenv_source(file=HEALTHY_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file."""

    answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
    plain: int = dotenv_setting(name="EMX_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMX_KNOWN", default=7)
    control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)


class HealthyJsonSettings(
    Settings,
    options=json_source(file=HEALTHY_JSON_FILE),
):
    """The matrix shape reading a JSON file."""

    answer: int = json_setting(name="answer", default=REQUIRED)
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class HealthyTomlSettings(
    Settings,
    options=toml_source(file=HEALTHY_TOML_FILE),
):
    """The matrix shape reading a TOML file."""

    answer: int = toml_setting(name="answer", default=REQUIRED)
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)
