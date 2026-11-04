"""The settings classes of the length-constraint scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

``min_length`` and ``max_length`` check ``len(value)``, and ``None`` passes
silently. A value that has no length at all is a violation, not a crash. The
``Union[int, str]`` member below carries an ``int`` value into that case.
"""

from typing import Union

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.json_settings import json_setting, json_source

LENGTH_BOUNDS_JSON_FILE = STORAGE_DIR / "length-bounds.json"
NO_LENGTH_JSON_FILE = STORAGE_DIR / "length-no-length.json"


class LengthBoundsSettings(
    Settings,
    options=json_source(file=LENGTH_BOUNDS_JSON_FILE),
):
    """A too-short member and a too-long member, one bound each."""

    short: str = json_setting(name="short", default=NO_DEFAULT, min_length=3)
    long: str = json_setting(name="long", default=NO_DEFAULT, max_length=5)


class NoLengthNumberSettings(
    Settings,
    options=json_source(file=NO_LENGTH_JSON_FILE),
):
    """An ``int`` value where the constraint asks for a length."""

    number: Union[int, str] = json_setting(name="number", default=NO_DEFAULT, min_length=2)
