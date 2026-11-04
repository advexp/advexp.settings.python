"""The configuration classes of the member-reference rule scenarios.

Every class belongs to exactly one test. A configuration class keeps the
values that an earlier load gave it, so a class is never shared between
tests.

A comparison bound may reference a sibling member instead of a literal:
``ge=min_port`` compares with the value that the member ``min_port``
actually holds at the moment of the check.

In this read-only package, the rules run at the two points where the values
stand together:

- the ``class`` statement (against the declared defaults);
- the load. A violation is fatal for a required member. For an optional
  member, it is a fallback that resets every member that takes part in the
  violated rule to its declared default.
"""

from configuration_validation_storage_paths import STORAGE_DIR

from advexp.configuration import REQUIRED, Configuration
from advexp.configuration.plugins.json_settings import json_setting, json_source

RULE_OPTIONAL_JSON_FILE = STORAGE_DIR / "member-rules-optional.json"
RULE_REQUIRED_JSON_FILE = STORAGE_DIR / "member-rules-required.json"
RULE_FINE_JSON_FILE = STORAGE_DIR / "member-rules-fine.json"


class RuleOptionalPortsConfiguration(
    Configuration,
    options=json_source(file=RULE_OPTIONAL_JSON_FILE),
):
    """The port pair on optional members: a violated rule makes every member that
    takes part in it fall back to its default.
    """

    min_port: int = json_setting(name="min_port", default=1024, ge=1024)
    max_port: int = json_setting(name="max_port", default=65535, le=65535, ge=min_port)


class RuleRequiredPortsConfiguration(
    Configuration,
    options=json_source(file=RULE_REQUIRED_JSON_FILE),
):
    """The port pair with a required ``max_port``: a violated rule aborts
    the load."""

    min_port: int = json_setting(name="min_port", default=1024, ge=1024)
    max_port: int = json_setting(name="max_port", default=REQUIRED, le=65535, ge=min_port)


class RuleFinePortsConfiguration(
    Configuration,
    options=json_source(file=RULE_FINE_JSON_FILE),
):
    """The port pair satisfied: the passing side of the rule story."""

    min_port: int = json_setting(name="min_port", default=1024, ge=1024)
    max_port: int = json_setting(name="max_port", default=65535, le=65535, ge=min_port)
