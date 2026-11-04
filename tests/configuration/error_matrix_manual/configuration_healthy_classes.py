"""The configuration classes of the healthy-load scenarios.

Every class in this suite belongs to exactly one test. A configuration class
keeps the values that an earlier load gave it (a failed load does not clear
them), so a class is never shared between tests.

The four members cover the declaration states that a member can be in. Here
this package differs from the settings package: a member that is declared
bare, without ``default=``, is ``REQUIRED`` (the own default of the
package), and ``NO_DEFAULT`` is the opt-out that makes the member optional
and serves ``None``.

* ``answer`` is declared bare: ``REQUIRED``, no default. The failure
  scenarios break this member.
* ``plain`` is ``NO_DEFAULT`` (the opt-out). It serves ``None`` when nothing
  is stored.
* ``known`` has a declared default (7).
* ``control`` is the explicit ``REQUIRED`` spelling. It is always stored, so
  a broken run still shows a healthy load next to the failures.
"""

from configuration_storage_paths import STORAGE_DIR

from advexp.configuration import REQUIRED, Configuration
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.configuration.plugins.environment.variables import (
    env_source,
    environment_variable_setting,
)
from advexp.configuration.plugins.json_settings import json_setting, json_source
from advexp.configuration.plugins.toml_settings import toml_setting, toml_source

HEALTHY_DOTENV_FILE = STORAGE_DIR / "healthy.env"
HEALTHY_JSON_FILE = STORAGE_DIR / "healthy.json"
HEALTHY_TOML_FILE = STORAGE_DIR / "healthy.toml"


class HealthyEnvConfiguration(
    Configuration,
    options=env_source(),
):
    """The matrix shape reading the process environment."""

    answer: int = environment_variable_setting(name="EMC_ANSWER")
    plain: int = environment_variable_setting(name="EMC_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMC_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMC_CONTROL", default=REQUIRED)


class HealthyDotenvConfiguration(
    Configuration,
    options=dotenv_source(file=HEALTHY_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file."""

    answer: int = dotenv_setting(name="EMC_ANSWER")
    plain: int = dotenv_setting(name="EMC_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMC_KNOWN", default=7)
    control: int = dotenv_setting(name="EMC_CONTROL", default=REQUIRED)


class HealthyJsonConfiguration(
    Configuration,
    options=json_source(file=HEALTHY_JSON_FILE),
):
    """The matrix shape reading a JSON file."""

    answer: int = json_setting(name="answer")
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class HealthyTomlConfiguration(
    Configuration,
    options=toml_source(file=HEALTHY_TOML_FILE),
):
    """The matrix shape reading a TOML file."""

    answer: int = toml_setting(name="answer")
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)
