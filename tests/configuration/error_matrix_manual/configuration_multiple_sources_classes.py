"""The configuration classes of the several-sources scenarios.

One class reads four sources at once: the process environment (two
members), a JSON file, a dotenv file, and a TOML file. The scenario breaks
each source in its own way: a missing variable, a value that cannot be
converted, and two empty files. The TOML source serves its member. One run
therefore shows every source reporting in its own words, next to a healthy
load.

The other class holds members of no family, so they walk the whole chain:
the scenario empties every link and reads the miss that names one storage
address per line.
"""

from configuration_storage_paths import STORAGE_DIR

from advexp.configuration import REQUIRED, Configuration, Sources
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.environment.dotenv import dotenv_source
from advexp.configuration.plugins.environment.variables import (
    env_source,
)
from advexp.configuration.plugins.json_settings import json_source
from advexp.configuration.plugins.toml_settings import toml_source
from advexp.settings_base.dotenv_setting import dotenv_setting
from advexp.settings_base.environment_variable_setting import (
    environment_variable_setting,
)
from advexp.settings_base.json_setting import json_setting
from advexp.settings_base.setting import setting
from advexp.settings_base.toml_setting import toml_setting

MULTI_JSON_FILE = STORAGE_DIR / "multi.json"
MULTI_TOML_FILE = STORAGE_DIR / "multi.toml"
MULTI_DOTENV_FILE = STORAGE_DIR / "multi.env"
CHAIN_JSON_FILE = STORAGE_DIR / "chain.json"
CHAIN_DOTENV_FILE = STORAGE_DIR / "chain.env"


class MultiSourceConfiguration(
    Configuration,
    options=Sources(
        env_source(),
        json_source(file=MULTI_JSON_FILE),
        toml_source(file=MULTI_TOML_FILE),
        dotenv_source(file=MULTI_DOTENV_FILE),
    ),
):
    """Four sources on one class; the test breaks each in its own way."""

    env_answer: int = environment_variable_setting(name="EMC_ENV_ANSWER")
    env_known: int = environment_variable_setting(name="EMC_ENV_KNOWN", default=7)
    json_plain: int = json_setting(name="json_plain", default=NO_DEFAULT)
    dotenv_extra: int = dotenv_setting(name="EMC_DOTENV_EXTRA", default=5)
    toml_control: int = toml_setting(name="toml_control", default=REQUIRED)


class ChainMissConfiguration(
    Configuration,
    options=Sources(
        env_source(),
        dotenv_source(file=CHAIN_DOTENV_FILE),
        json_source(file=CHAIN_JSON_FILE),
    ),
):
    """Members of no family walk the whole chain; the test empties every link."""

    token: str = setting(name="chain_token")
    retries: int = setting(name="chain_retries", default=3)
