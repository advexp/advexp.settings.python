"""The settings class of the several-sources scenario.

One class reads four sources at once: the process environment (two
members), a JSON file, a dotenv file, and a TOML file. The scenario breaks
each source in its own way: a missing variable, a value that cannot be
converted, and two empty files. The TOML source serves its member. One run
therefore shows every source reporting in its own words, next to a healthy
load.
"""

from settings_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.settings.plugins.environment.variables import environment_variable_setting
from advexp.settings.plugins.json_settings import json_setting, json_source
from advexp.settings.plugins.toml_settings import toml_setting, toml_source

MULTI_JSON_FILE = STORAGE_DIR / "multi.json"
MULTI_TOML_FILE = STORAGE_DIR / "multi.toml"
MULTI_DOTENV_FILE = STORAGE_DIR / "multi.env"


class MultiSourceSettings(
    Settings,
    options=(
        json_source(file=MULTI_JSON_FILE),
        toml_source(file=MULTI_TOML_FILE),
        dotenv_source(file=MULTI_DOTENV_FILE),
    ),
):
    """Four sources on one class; the test breaks each in its own way."""

    env_answer: int = environment_variable_setting(name="EMX_ENV_ANSWER", default=REQUIRED)
    env_known: int = environment_variable_setting(name="EMX_ENV_KNOWN", default=7)
    json_plain: int = json_setting(name="json_plain", default=NO_DEFAULT)
    dotenv_extra: int = dotenv_setting(name="EMX_DOTENV_EXTRA", default=5)
    toml_control: int = toml_setting(name="toml_control", default=REQUIRED)
