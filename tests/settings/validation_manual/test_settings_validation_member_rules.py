"""Member-reference rules: a comparison bound that names a sibling.

``ge=min_port`` compares the member with the value that its sibling
actually holds. The rules run where all values are known at once.

On a load, the channel is the finding of the violating member. Unlike a
field violation, it has no storage address. The finding is fatal for a
required member. For an optional member, it is a fallback that resets every
member that takes part in the violated rule to its declared default.

A single assignment never runs the rules. The last test breaks the pair
through two assignments, each of which passes its own checks, and the strict
validation catches it.
"""

import logging

import pytest
from settings_validation_member_rules_classes import (
    RULE_FINE_JSON_FILE,
    RULE_OPTIONAL_JSON_FILE,
    RULE_REQUIRED_JSON_FILE,
    AssignmentRuleSettings,
    RuleFinePortsSettings,
    RuleOptionalPortsSettings,
    RuleRequiredPortsSettings,
)
from settings_validation_storage_paths import prepare_storage_dir

from advexp.settings import AggregateLoadError, ConstraintViolationError, SettingValidationError


def test_violated_rule_on_optional_members_resets_on_load(caplog):
    """max_port below min_port: the finding rides the report, and both
    members of the rule stand at their defaults again."""
    prepare_storage_dir()
    RULE_OPTIONAL_JSON_FILE.write_text(
        '{"min_port": 2000, "max_port": 1500}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = RuleOptionalPortsSettings.load_settings()

    assert [str(entry) for entry in report] == [
        "setting 'max_port' of 'RuleOptionalPortsSettings' violates its constraints "
        "(value 1500 must be greater than or equal to the value of 'min_port' (2000))"
    ]
    # both members of the violated rule are reset to their defaults
    assert RuleOptionalPortsSettings.min_port == 1024
    assert RuleOptionalPortsSettings.max_port == 65535
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        "found cross-member constraint violations after load (max_port: value 1500 must be "
        "greater than or equal to the value of 'min_port' (2000)); "
        "resetting the members to their defaults: min_port, max_port"
    ) in warning_messages


def test_violated_rule_on_a_required_member_aborts_the_load():
    """The same pair with a required max_port: the finding is fatal."""
    prepare_storage_dir()
    RULE_REQUIRED_JSON_FILE.write_text(
        '{"min_port": 2000, "max_port": 1500}',
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        RuleRequiredPortsSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        "setting 'max_port' of 'RuleRequiredPortsSettings' violates its constraints "
        "(value 1500 must be greater than or equal to the value of 'min_port' (2000))"
    )


def test_satisfied_rule_loads_cleanly():
    """The passing side: a pair in order loads without a word."""
    prepare_storage_dir()
    RULE_FINE_JSON_FILE.write_text(
        '{"min_port": 2000, "max_port": 9000}',
        encoding="utf-8",
    )

    report = RuleFinePortsSettings.load_settings()

    assert report == ()
    assert RuleFinePortsSettings.min_port == 2000
    assert RuleFinePortsSettings.max_port == 9000


def test_single_assignments_skip_the_rules_until_a_strict_check():
    """Two assignments, each of them fine alone, break the pair. Nothing objects
    until the strict validation collects the finding.
    """
    AssignmentRuleSettings.hi = 9000  # its own constraints say nothing about lo
    AssignmentRuleSettings.lo = 9500  # its own constraints say nothing about hi

    with pytest.raises(SettingValidationError) as info:
        AssignmentRuleSettings.validate_settings()

    assert str(info.value) == (
        "invalid settings in AssignmentRuleSettings:\n"
        "  - hi: value 9000 must be greater than or equal to the value of 'lo' (9500)"
    )
    assert info.value.problems == {
        "hi": ["value 9000 must be greater than or equal to the value of 'lo' (9500)"]
    }
    # the validation changed nothing
    assert AssignmentRuleSettings.lo == 9500
    assert AssignmentRuleSettings.hi == 9000
