"""The configuration classes of the broken-serializer scenarios.

Every class belongs to exactly one test. A configuration class keeps the
values that an earlier load gave it, so a class is never shared between
tests.

The shape of the members is the matrix of ``configuration_healthy_classes``:
``answer`` is declared bare (``REQUIRED``, the own default of the package),
``control`` spells ``REQUIRED`` out, ``plain`` carries ``NO_DEFAULT``, and
``known`` declares 7.

The test replaces the ``load`` of the backend serializer with a function
that raises an error. The storage files that are bound below therefore never
materialize, and their content is never read.
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

BROKEN_SERIALIZER_DOTENV_FILE = STORAGE_DIR / "broken-serializer.env"
BROKEN_SERIALIZER_JSON_FILE = STORAGE_DIR / "broken-serializer.json"
BROKEN_SERIALIZER_TOML_FILE = STORAGE_DIR / "broken-serializer.toml"


class BrokenSerializerEnvConfiguration(
    Configuration,
    options=env_source(),
):
    """The matrix shape reading the process environment; the test breaks the
    environment serializer itself."""

    answer: int = environment_variable_setting(name="EMC_ANSWER")
    plain: int = environment_variable_setting(name="EMC_PLAIN", default=NO_DEFAULT)
    known: int = environment_variable_setting(name="EMC_KNOWN", default=7)
    control: int = environment_variable_setting(name="EMC_CONTROL", default=REQUIRED)


class BrokenSerializerDotenvConfiguration(
    Configuration,
    options=dotenv_source(file=BROKEN_SERIALIZER_DOTENV_FILE),
):
    """The matrix shape reading a dotenv file; the test breaks the dotenv
    serializer itself."""

    answer: int = dotenv_setting(name="EMC_ANSWER")
    plain: int = dotenv_setting(name="EMC_PLAIN", default=NO_DEFAULT)
    known: int = dotenv_setting(name="EMC_KNOWN", default=7)
    control: int = dotenv_setting(name="EMC_CONTROL", default=REQUIRED)


class BrokenSerializerJsonConfiguration(
    Configuration,
    options=json_source(file=BROKEN_SERIALIZER_JSON_FILE),
):
    """The matrix shape reading a JSON file; the test breaks the JSON
    serializer itself."""

    answer: int = json_setting(name="answer")
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)


class BrokenSerializerTomlConfiguration(
    Configuration,
    options=toml_source(file=BROKEN_SERIALIZER_TOML_FILE),
):
    """The matrix shape reading a TOML file; the test breaks the TOML
    serializer itself."""

    answer: int = toml_setting(name="answer")
    plain: int = toml_setting(name="plain", default=NO_DEFAULT)
    known: int = toml_setting(name="known", default=7)
    control: int = toml_setting(name="control", default=REQUIRED)
