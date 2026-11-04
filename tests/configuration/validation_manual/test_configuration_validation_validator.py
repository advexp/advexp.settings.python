"""The custom validator constraint.

``validator=`` takes a predicate. ``True`` passes, and ``False`` is a
violation whose message names the validator. An exception that the
validator raises propagates as it is, because a bug in the validator is not
a property of the value.

The message carries the ``repr`` of the validator, so the expected string
in the tests interpolates the very function that is declared in the module
of the classes.
"""

import pytest
from configuration_validation_storage_paths import prepare_storage_dir
from configuration_validation_validator_classes import (
    EXPLODING_VALIDATOR_JSON_FILE,
    PARITY_JSON_FILE,
    ExplodingValidatorConfiguration,
    ParityConfiguration,
    is_even,
)


def test_failing_validator_on_load():
    """The stored value fails the predicate: the report names the validator."""
    prepare_storage_dir()
    PARITY_JSON_FILE.write_text('{"retries": 7}', encoding="utf-8")

    report = ParityConfiguration.load_configuration()

    assert [str(entry) for entry in report] == [
        f"member 'retries' (key 'retries' in the JSON file {PARITY_JSON_FILE}) "
        "of 'ParityConfiguration' fell back to its default: the value violates its "
        f"constraints (value 7 failed the validator {is_even!r})"
    ]
    assert ParityConfiguration.retries == 2


def test_validator_exception_propagates_as_is():
    """A validator that raises: the exception leaves the load unchanged —
    it is a bug in the validator, not a violation to report."""
    prepare_storage_dir()
    EXPLODING_VALIDATOR_JSON_FILE.write_text(
        '{"enabled": true, "retries": 7}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="validator bug"):
        ExplodingValidatorConfiguration.load_configuration()
