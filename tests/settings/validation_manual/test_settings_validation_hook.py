"""The validation hook: ``__validate__``.

Everything that a comparison cannot express goes into the class hook. The
hook reads the whole settings object and returns a dict that maps a member
name to a problem.

On a load, a finding is an entry of the member that it names:

- For a required member, the entry is fatal.
- For an optional member, the entry is a fallback that resets the members
  that the finding names. A hook declares no references, so only the named
  member is reset. If no reset can settle the finding, the pass aborts, and
  the class keeps the state that it had.

The other cases are as follows:

- A return value of the wrong kind makes the check refuse it.
- A hook that reads a member that nothing has loaded reports through that
  member, as a finding.
- An exception that the body of the hook raises propagates as it is,
  because a bug in the code of the hook is not a property of the values.
"""

import logging

import pytest
from settings_validation_hook_classes import (
    HOOK_FATAL_JSON_FILE,
    HOOK_UNSETTLED_JSON_FILE,
    HookBadReturnSettings,
    HookedFatalSettings,
    HookedUnsettledSettings,
    HookExplodingSettings,
    HookUnreadMemberLoadSettings,
    HookUnreadMemberSettings,
)
from settings_validation_storage_paths import prepare_storage_dir

from advexp.settings import (
    AggregateLoadError,
    ConstraintViolationError,
    SettingValidationError,
)


def test_a_hook_finding_the_reset_cannot_settle_aborts_the_load(caplog):
    """Production mode with a wrong ``ssl``: the finding names ``ssl``, and
    ``ssl`` is reset to its default. The finding then comes back, because the
    reset settled nothing. The pass aborts, and the class keeps the state that
    it had.
    """
    prepare_storage_dir()
    HOOK_UNSETTLED_JSON_FILE.write_text(
        '{"mode": "prod", "ssl": "maybe"}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            HookedUnsettledSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        "setting 'ssl' of 'HookedUnsettledSettings' violates its constraints "
        "(ssl must be 'on' in production mode); "
        "no reset to the declared defaults settles it"
    )
    # the failed pass touched nothing: both members keep the declared defaults
    assert HookedUnsettledSettings.mode == "dev"
    assert HookedUnsettledSettings.ssl == "none"
    log_messages = [record.getMessage() for record in caplog.records]
    assert (
        "found cross-member constraint violations after load (ssl: ssl must be 'on' in "
        "production mode); resetting the members to their defaults: ssl"
    ) in log_messages
    assert any(
        "cross-member constraint violations remain" in message and "the pass is aborted" in message
        for message in log_messages
    )


def test_hook_finding_on_a_required_member_aborts_the_load():
    """The same rule with a required ssl: the finding is fatal."""
    prepare_storage_dir()
    HOOK_FATAL_JSON_FILE.write_text(
        '{"mode": "prod", "ssl": "maybe"}',
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        HookedFatalSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        "setting 'ssl' of 'HookedFatalSettings' violates its constraints "
        "(ssl must be 'on' in production mode)"
    )


def test_hook_must_return_a_dict():
    """A hook that answers with a value of the wrong kind: the check itself
    refuses the return value.
    """
    with pytest.raises(TypeError) as info:
        HookBadReturnSettings.validate_settings()

    assert str(info.value) == (
        "HookBadReturnSettings.__validate__() must return a dict mapping member names "
        "to problems, got str"
    )


def test_hook_reading_an_unset_member_reports_the_reading_error():
    """A required member that nothing has loaded: the read of it by the hook is
    the finding of that member, and it appears in the report of the manual check
    like any other finding.
    """
    with pytest.raises(SettingValidationError) as info:
        HookUnreadMemberSettings.validate_settings()

    assert info.value.problems == {
        "missing": ["no loaded value to read; the __validate__ hook read the member"]
    }
    assert str(info.value) == (
        "invalid settings in HookUnreadMemberSettings:\n"
        "  - missing: no loaded value to read; the __validate__ hook read the member"
    )


def test_hook_reading_an_unset_member_reports_the_miss_beside_the_error():
    """The same member at a load: the load reports the own miss of the member, and
    the read of it by the hook joins the abort.
    """
    with pytest.raises(AggregateLoadError) as info:
        HookUnreadMemberLoadSettings.load_settings()

    assert [str(error) for error in info.value.errors] == [
        "setting 'missing' (environment variable 'ADVEXP_MANUAL_HOOK_MISSING') "
        "of 'HookUnreadMemberLoadSettings' is required: "
        "the process environment provided no value",
        "setting 'missing' of 'HookUnreadMemberLoadSettings' violates its "
        "constraints (no loaded value to read; the __validate__ hook read the member)",
    ]


def test_hook_exception_propagates_as_is():
    """A hook that raises an exception instead of reporting a finding: the
    exception leaves the check unchanged, and the class is untouched. It is a
    bug in the code of the hook, not a finding to report.
    """
    with pytest.raises(ZeroDivisionError, match="hook bug"):
        HookExplodingSettings.validate_settings()

    assert HookExplodingSettings.mode == "dev"
