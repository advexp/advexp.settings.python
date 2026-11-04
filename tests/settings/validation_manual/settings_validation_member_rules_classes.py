"""The settings classes of the member-reference rule scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

A comparison bound may reference a sibling member instead of a literal:
``ge=min_port`` compares with the value that the member ``min_port``
actually holds at the moment of the check.

The rules run where all values are known at once: a load, an update, a
save, and the manual validation. They never run on a single assignment. The
assignment test below breaks the pair through two assignments, each of which
passes its own checks.
"""

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings, non_storage_setting
from advexp.settings.plugins.json_settings import json_setting, json_source

RULE_OPTIONAL_JSON_FILE = STORAGE_DIR / "member-rules-optional.json"
RULE_REQUIRED_JSON_FILE = STORAGE_DIR / "member-rules-required.json"
RULE_FINE_JSON_FILE = STORAGE_DIR / "member-rules-fine.json"


class RuleOptionalPortsSettings(
    Settings,
    options=json_source(file=RULE_OPTIONAL_JSON_FILE),
):
    """The port pair on optional members: a violated rule falls back to the
    defaults of every member taking part in it."""

    min_port: int = json_setting(name="min_port", default=1024, ge=1024)
    max_port: int = json_setting(name="max_port", default=65535, le=65535, ge=min_port)


class RuleRequiredPortsSettings(
    Settings,
    options=json_source(file=RULE_REQUIRED_JSON_FILE),
):
    """The port pair with a required ``max_port``: a violated rule aborts
    the load."""

    min_port: int = json_setting(name="min_port", default=1024, ge=1024)
    max_port: int = json_setting(name="max_port", default=REQUIRED, le=65535, ge=min_port)


class RuleFinePortsSettings(
    Settings,
    options=json_source(file=RULE_FINE_JSON_FILE),
):
    """The port pair satisfied: the passing side of the rule story."""

    min_port: int = json_setting(name="min_port", default=1024, ge=1024)
    max_port: int = json_setting(name="max_port", default=65535, le=65535, ge=min_port)


class AssignmentRuleSettings(Settings):
    """The port pair in memory, broken by two single assignments that each
    pass their own checks."""

    lo: int = non_storage_setting(default=1024)
    hi: int = non_storage_setting(default=65535, ge=lo)
