"""The settings classes of the custom-validator scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

``validator=`` takes a predicate. ``True`` passes, and ``False`` is a
violation whose message names the validator. An exception that the
validator raises propagates as it is, because that is a bug in the
validator, not a property of the value.

A validator that raises is also checked against the declared defaults at the
``class`` statement. The class below therefore gates it behind a ``when=``
condition that is off in the state in which every member has its default.
Without the gate, the ``class`` statement itself would fail.
"""

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import Settings
from advexp.settings.plugins.json_settings import json_setting, json_source

PARITY_JSON_FILE = STORAGE_DIR / "validator-parity.json"
EXPLODING_VALIDATOR_JSON_FILE = STORAGE_DIR / "validator-exploding.json"


def is_even(value):
    """The custom validator of the parity scenario: ``True`` when the value passes."""
    return value % 2 == 0


def reject_everything(value):
    """A validator that breaks instead of answering."""
    raise ValueError("validator bug")


class ParitySettings(
    Settings,
    options=json_source(file=PARITY_JSON_FILE),
):
    """The ``retries`` member must pass the ``is_even`` predicate."""

    retries: int = json_setting(name="retries", default=2, validator=is_even)


class ExplodingValidatorSettings(
    Settings,
    options=json_source(file=EXPLODING_VALIDATOR_JSON_FILE),
):
    """A validator that raises, gated behind a ``when=`` condition: the
    class statement survives the all-default state, and the load that
    switches the condition on meets the exception."""

    enabled: bool = json_setting(name="enabled", default=False)
    retries: int = json_setting(
        name="retries", default=2, validator=reject_everything, when=enabled
    )
