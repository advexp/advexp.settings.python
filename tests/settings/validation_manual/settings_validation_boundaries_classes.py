"""The settings classes of the boundary scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

The constraints apply on every boundary, and each boundary has its own
policy:

- A load falls back to the default, with a logged warning (see the load
  categories above).
- An assignment rejects the value that it is handed.
- An update collects every finding of the merged state and applies nothing.
- A save of a class in violation writes nothing.
- The manual ``validate_settings()`` reports the same findings without
  touching anything.
"""

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import Settings, non_storage_setting
from advexp.settings.plugins.json_settings import json_setting, json_source

SAVE_STRICT_JSON_FILE = STORAGE_DIR / "boundaries-save.json"


class AssignmentPortSettings(Settings):
    """One member in memory: the assignment boundary."""

    port: int = non_storage_setting(default=8080, le=65535)


class UpdateRejectSettings(Settings):
    """Two members in memory: the update boundary with two bad values."""

    port: int = non_storage_setting(default=8080, le=65535)
    tag: str = non_storage_setting(default="xx", min_length=2)


class SaveStrictSettings(
    Settings,
    options=json_source(file=SAVE_STRICT_JSON_FILE),
):
    """The port pair on a file: the save boundary over a broken rule."""

    lo: int = json_setting(name="lo", default=1024, ge=1024)
    hi: int = json_setting(name="hi", default=65535, le=65535, ge=lo)


class ValidateListSettings(Settings):
    """The pair in memory: the manual validation over a broken rule."""

    low: int = non_storage_setting(default=1)
    high: int = non_storage_setting(default=10, ge=low)


class ValidateQuietSettings(Settings):
    """A consistent class with a hook: the manual validation passes
    quietly."""

    value: int = non_storage_setting(default=5, gt=0)
    lo: int = non_storage_setting(default=1)
    hi: int = non_storage_setting(default=10, ge=lo)

    def __validate__(self) -> dict:
        return {}
