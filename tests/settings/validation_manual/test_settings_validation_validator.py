"""The custom validator constraint.

``validator=`` takes a predicate. ``True`` passes, and ``False`` is a
violation whose message names the validator. An exception that the
validator raises propagates as it is, because that is a bug in the
validator, not a property of the value.

A validator that raises is also checked against the declared defaults at the
``class`` statement. The class below therefore gates it behind a ``when=``
condition that is off in the state in which every member has its default.
Without the gate, the ``class`` statement itself would fail.

On a load, the crash leaves an ERROR record in the log channel of the
package before it propagates, so the bug stays visible even where the
traceback is swallowed.
"""

import logging

import pytest
from settings_validation_storage_paths import prepare_storage_dir
from settings_validation_validator_classes import (
    EXPLODING_VALIDATOR_JSON_FILE,
    PARITY_JSON_FILE,
    ExplodingValidatorSettings,
    ParitySettings,
    is_even,
)


def test_failing_validator_on_load():
    """The stored value fails the predicate: the report names the validator."""
    prepare_storage_dir()
    PARITY_JSON_FILE.write_text('{"retries": 7}', encoding="utf-8")

    report = ParitySettings.load_settings()

    assert [str(entry) for entry in report] == [
        f"setting 'retries' (key 'retries' in the JSON file {PARITY_JSON_FILE}) "
        "of 'ParitySettings' fell back to its default: the value violates its "
        f"constraints (value 7 failed the validator {is_even!r})"
    ]
    assert ParitySettings.retries == 2


def test_validator_exception_propagates_as_is(caplog):
    """A validator that raises an exception: the exception leaves the load
    unchanged. It is a bug in the validator, not a violation to report, and the
    ERROR record keeps the crash visible in the log.
    """
    prepare_storage_dir()
    EXPLODING_VALIDATOR_JSON_FILE.write_text(
        '{"enabled": true, "retries": 7}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        with pytest.raises(ValueError, match="validator bug"):
            ExplodingValidatorSettings.load_settings()

    assert [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ] == ["validation exception for setting 'retries': validator bug"]
