"""The configuration class of the read-only-contract scenario.

The package never writes a value back. Assigning to a member or deleting a
member meets the read-only contract, and the error names the reload call that
stands in for the write. The class never touches its file: the contract
holds over the members themselves, whether they are loaded or not.
"""

from configuration_storage_paths import STORAGE_DIR

from advexp.configuration import REQUIRED, Configuration
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.json_settings import json_setting, json_source

READ_ONLY_JSON_FILE = STORAGE_DIR / "read-only.json"


class ReadOnlyConfiguration(
    Configuration,
    options=json_source(file=READ_ONLY_JSON_FILE),
):
    """The full matrix shape; the test tries to write to its members."""

    answer: int = json_setting(name="answer")
    plain: int = json_setting(name="plain", default=NO_DEFAULT)
    known: int = json_setting(name="known", default=7)
    control: int = json_setting(name="control", default=REQUIRED)
