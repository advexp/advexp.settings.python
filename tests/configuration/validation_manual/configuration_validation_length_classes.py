"""The configuration classes of the length-constraint scenarios.

Every class belongs to exactly one test. A configuration class keeps the
values that an earlier load gave it, so a class is never shared between
tests.

``min_length`` and ``max_length`` check ``len(value)``, and ``None`` passes
silently. A value that has no length at all (an ``int`` under a length
bound) is a violation with its own wording, not a crash.
"""

from typing import Union

from configuration_validation_storage_paths import STORAGE_DIR

from advexp.configuration import Configuration
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.json_settings import json_setting, json_source

LENGTH_BOUNDS_JSON_FILE = STORAGE_DIR / "length-bounds.json"
NO_LENGTH_JSON_FILE = STORAGE_DIR / "length-no-length.json"


class LengthBoundsConfiguration(
    Configuration,
    options=json_source(file=LENGTH_BOUNDS_JSON_FILE),
):
    """A too-short member and a too-long member, one bound each."""

    short: str = json_setting(name="short", default=NO_DEFAULT, min_length=3)
    long: str = json_setting(name="long", default=NO_DEFAULT, max_length=5)


class NoLengthNumberConfiguration(
    Configuration,
    options=json_source(file=NO_LENGTH_JSON_FILE),
):
    """An ``int`` value where the constraint asks for a length."""

    number: Union[int, str] = json_setting(name="number", default=NO_DEFAULT, min_length=2)
