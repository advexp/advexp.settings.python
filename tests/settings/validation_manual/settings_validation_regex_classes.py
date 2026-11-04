"""The settings classes of the regex-constraint scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

``regex=`` runs an unanchored ``re.search`` over the value. ``None`` passes
silently, and a value that is not a string is a violation with its own
wording. The pattern is compiled at the ``class`` statement: a pattern that
does not compile makes the declaration fail (the declaration category pins
this).
"""

from typing import Union

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.json_settings import json_setting, json_source

REGEX_CODE_JSON_FILE = STORAGE_DIR / "regex-code.json"
NON_STRING_JSON_FILE = STORAGE_DIR / "regex-non-string.json"


class RegexCodeSettings(
    Settings,
    options=json_source(file=REGEX_CODE_JSON_FILE),
):
    """A member whose stored value misses the pattern."""

    code: str = json_setting(name="code", default=NO_DEFAULT, regex="^[a-z]+$")


class NonStringDigitSettings(
    Settings,
    options=json_source(file=NON_STRING_JSON_FILE),
):
    """A non-string value where the constraint asks for a pattern match."""

    digit: Union[int, str] = json_setting(name="digit", default=NO_DEFAULT, regex="^[a-z]+$")
