"""The validation hook: ``__validate__``.

Everything that a comparison cannot express goes into the class hook. The
hook reads the whole configuration object and returns a dict that maps a
member name to a problem.

On a load, a finding is an entry of the member that it names:

- For a required member, the entry is fatal.
- For an optional member, the entry is a fallback that resets the members
  that the finding names. A hook declares no references, so only the named
  member is reset. If no reset can settle the finding, the pass aborts, and
  the class keeps the state that it had.

The other cases are as follows:

- A return value of the wrong kind makes the check of the load itself
  refuse it.
- A hook that reads a member that nothing has loaded reports through that
  member, next to its own miss.
- An exception that the body of the hook raises propagates as it is,
  because a bug in the code of the hook is not a property of the values.
"""

import logging

import pytest
from configuration_validation_hook_classes import (
    HOOK_FATAL_JSON_FILE,
    HOOK_UNSETTLED_JSON_FILE,
    HookBadReturnConfiguration,
    HookedFatalConfiguration,
    HookedUnsettledConfiguration,
    HookExplodingConfiguration,
    HookUnreadMemberConfiguration,
)
from configuration_validation_storage_paths import prepare_storage_dir

from advexp.configuration import AggregateLoadError, ConstraintViolationError


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

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            HookedUnsettledConfiguration.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        "member 'ssl' of 'HookedUnsettledConfiguration' violates its constraints "
        "(ssl must be 'on' in production mode); "
        "no reset to the declared defaults settles it"
    )
    # the failed pass touched nothing: both members keep the declared defaults
    assert HookedUnsettledConfiguration.mode == "dev"
    assert HookedUnsettledConfiguration.ssl == "none"
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
        HookedFatalConfiguration.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        "member 'ssl' of 'HookedFatalConfiguration' violates its constraints "
        "(ssl must be 'on' in production mode)"
    )


def test_hook_must_return_a_dict():
    """A hook that answers with a value of the wrong kind: the check of the load
    itself refuses the return value.
    """
    with pytest.raises(TypeError) as info:
        HookBadReturnConfiguration.load_configuration()

    assert str(info.value) == (
        "HookBadReturnConfiguration.__validate__() must return a dict mapping member names to "
        "problems, got str"
    )


def test_hook_reading_an_unset_member_reports_the_miss_beside_the_error():
    """A required in-memory member that nothing has loaded: the load reports the
    own miss of the member, and the read of it by the hook joins the abort.
    """
    with pytest.raises(AggregateLoadError) as info:
        HookUnreadMemberConfiguration.load_configuration()

    assert [str(error) for error in info.value.errors] == [
        "member 'missing' (environment variable 'missing') "
        "of 'HookUnreadMemberConfiguration' is required: "
        "the process environment provided no value",
        "member 'missing' of 'HookUnreadMemberConfiguration' violates its "
        "constraints (no loaded value to read; the __validate__ hook read the member)",
    ]


def test_hook_exception_propagates_as_is(caplog):
    """A hook that raises an exception instead of reporting a finding: after an
    ERROR record, the exception leaves the load unchanged. It is a bug in the
    code of the hook, not a finding to report.
    """
    with caplog.at_level(logging.ERROR, logger="advexp.configuration"):
        with pytest.raises(ZeroDivisionError, match="hook bug"):
            HookExplodingConfiguration.load_configuration()

    assert [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ] == [
        "validation exception in the cross-member checks of 'HookExplodingConfiguration': hook bug"
    ]
