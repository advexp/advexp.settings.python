"""The settings classes of the conditional-constraint scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

``when=`` gates everything that is declared on the member: while the
referenced member is falsy, none of the constraints of the member apply. The
two classes have the same shape, and their storages differ only in the value
of the condition.
"""

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import Settings
from advexp.settings.plugins.json_settings import json_setting, json_source

WHEN_OFF_JSON_FILE = STORAGE_DIR / "when-off.json"
WHEN_ON_JSON_FILE = STORAGE_DIR / "when-on.json"


class WhenConditionOffSettings(
    Settings,
    options=json_source(file=WHEN_OFF_JSON_FILE),
):
    """The condition is off: the ``le`` bound does not apply."""

    enabled: bool = json_setting(name="enabled", default=False)
    retries: int = json_setting(name="retries", default=3, le=5, when=enabled)


class WhenConditionOnSettings(
    Settings,
    options=json_source(file=WHEN_ON_JSON_FILE),
):
    """The condition is on: the ``le`` bound applies."""

    enabled: bool = json_setting(name="enabled", default=False)
    retries: int = json_setting(name="retries", default=3, le=5, when=enabled)
