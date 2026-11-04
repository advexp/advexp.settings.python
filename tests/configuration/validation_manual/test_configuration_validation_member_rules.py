"""Member-reference rules: a comparison bound that names a sibling.

``ge=min_port`` compares the member with the value that its sibling
actually holds.

On a load, the channel is the finding of the violating member. Unlike a
field violation, it has no storage address. The finding is fatal for a
required member. For an optional member, it is a fallback that resets every
member that takes part in the violated rule to its declared default.

A satisfied pair closes the category with the passing side.
"""

import logging

import pytest
from configuration_validation_member_rules_classes import (
    RULE_FINE_JSON_FILE,
    RULE_OPTIONAL_JSON_FILE,
    RULE_REQUIRED_JSON_FILE,
    RuleFinePortsConfiguration,
    RuleOptionalPortsConfiguration,
    RuleRequiredPortsConfiguration,
)
from configuration_validation_storage_paths import prepare_storage_dir

from advexp.configuration import AggregateLoadError, ConstraintViolationError


def test_violated_rule_on_optional_members_resets_on_load(caplog):
    """max_port below min_port: the finding rides the report, and both
    members of the rule stand at their defaults again."""
    prepare_storage_dir()
    RULE_OPTIONAL_JSON_FILE.write_text(
        '{"min_port": 2000, "max_port": 1500}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = RuleOptionalPortsConfiguration.load_configuration()

    assert [str(entry) for entry in report] == [
        "member 'max_port' of 'RuleOptionalPortsConfiguration' violates its constraints "
        "(value 1500 must be greater than or equal to the value of 'min_port' (2000))"
    ]
    # both members of the violated rule are reset to their defaults
    assert RuleOptionalPortsConfiguration.min_port == 1024
    assert RuleOptionalPortsConfiguration.max_port == 65535
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
        RuleRequiredPortsConfiguration.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        "member 'max_port' of 'RuleRequiredPortsConfiguration' violates its constraints "
        "(value 1500 must be greater than or equal to the value of 'min_port' (2000))"
    )


def test_satisfied_rule_loads_cleanly():
    """The passing side: a pair in order loads without a word."""
    prepare_storage_dir()
    RULE_FINE_JSON_FILE.write_text(
        '{"min_port": 2000, "max_port": 9000}',
        encoding="utf-8",
    )

    report = RuleFinePortsConfiguration.load_configuration()

    assert report == ()
    assert RuleFinePortsConfiguration.min_port == 2000
    assert RuleFinePortsConfiguration.max_port == 9000
