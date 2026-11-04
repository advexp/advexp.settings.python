"""The configuration classes of the conditional-constraint scenarios.

Every class belongs to exactly one test. A configuration class keeps the
values that an earlier load gave it, so a class is never shared between
tests.

``when=`` references a sibling member: while the referenced member is
falsy, none of the constraints of the member apply. The two classes have the
same shape, and their storages differ only in the value of the condition.
"""

from configuration_validation_storage_paths import STORAGE_DIR

from advexp.configuration import Configuration
from advexp.configuration.plugins.json_settings import json_setting, json_source

WHEN_OFF_JSON_FILE = STORAGE_DIR / "when-off.json"
WHEN_ON_JSON_FILE = STORAGE_DIR / "when-on.json"


class WhenConditionOffConfiguration(
    Configuration,
    options=json_source(file=WHEN_OFF_JSON_FILE),
):
    """The condition is off: the ``le`` bound does not apply."""

    enabled: bool = json_setting(name="enabled", default=False)
    retries: int = json_setting(name="retries", default=3, le=5, when=enabled)


class WhenConditionOnConfiguration(
    Configuration,
    options=json_source(file=WHEN_ON_JSON_FILE),
):
    """The condition is on: the ``le`` bound applies."""

    enabled: bool = json_setting(name="enabled", default=False)
    retries: int = json_setting(name="retries", default=3, le=5, when=enabled)
