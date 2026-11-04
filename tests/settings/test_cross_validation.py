"""Cross-member validation: member references, ``when=``, and the class hook.

A comparison bound may reference a sibling member (``ge=min_port``). The
``when=`` parameter gates the constraints of a member on the truthiness of a
sibling. The ``__validate__`` hook carries the rules that a comparison
cannot state.

The checks run where all values are known at once:

- Class creation, against the defaults.
- A load, which is lenient: the members of a violated rule fall back to
  their defaults, and a violation that no reset can settle aborts the pass.
- ``update_from_dict`` and ``update_from_object``, and a save, which are
  strict.
- ``validate_settings()``, which is the manual check, with the per-member
  report that the error carries.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import pytest

from advexp.settings import (
    AggregateLoadError,
    ConstraintViolationError,
    MissingValueError,
    Settings,
    SettingValidationError,
)

# noinspection PyProtectedMember
from advexp.settings._internal.non_storage_setting import non_storage_setting
from advexp.settings.plugins.environment.variables import environment_variable_setting

# noinspection PyProtectedMember
from advexp.settings_base import cross_validation
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.secret_str import SecretStr

LOGGER = "advexp.settings"


def _names(*suffixes: str) -> dict:
    """Unique environment variable names for one test's members."""
    return {suffix: f"ADVEXP_CV_{suffix.upper()}" for suffix in suffixes}


# ---------------------------------------------------------------------------
# level 1: a comparison bound referencing a sibling member


def test_member_reference_compares_with_the_actual_value():
    class Ranges(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

    assert Ranges.high == 10  # the all-default state is consistent
    Ranges.validate_settings()

    Ranges.low = 5
    Ranges.validate_settings()  # 10 >= 5 still holds

    Ranges.high = 4
    with pytest.raises(SettingValidationError) as info:
        Ranges.validate_settings()
    assert info.value.problems == {
        "high": ["value 4 must be greater than or equal to the value of 'low' (5)"]
    }


def test_single_assignment_never_runs_the_cross_member_checks():
    # changing a pair of related members one by one passes the intermediate
    # state through; the check is the user's to run afterwards
    class Ranges(Settings):
        low: int = non_storage_setting(default=100)
        high: int = non_storage_setting(default=200, ge=low)

    Ranges.low = 3000  # no cross-member complaint here
    assert Ranges.low == 3000
    with pytest.raises(SettingValidationError) as info:
        Ranges.validate_settings()
    assert "high" in info.value.problems

    Ranges.high = 4000
    Ranges.validate_settings()  # the pair is consistent again


def test_declared_defaults_of_a_violated_rule_fail_the_class_statement():
    with pytest.raises(TypeError) as info:

        class BadRanges(Settings):
            low: int = non_storage_setting(default=100)
            high: int = non_storage_setting(default=10, ge=low)

    text = str(info.value)
    assert "invalid defaults in BadRanges" in text
    assert "high" in text
    assert "must be greater than or equal to the value of 'low' (100)" in text


def test_all_member_reference_findings_are_listed_at_once():
    class Triangle(Settings):
        a: int = non_storage_setting(default=1)
        b: int = non_storage_setting(default=2, ge=a)
        c: int = non_storage_setting(default=3, ge=b)

    Triangle.__settings_values__.update({"a": 30, "b": 20, "c": 10})
    with pytest.raises(SettingValidationError) as info:
        Triangle.validate_settings()
    assert set(info.value.problems) == {"b", "c"}


def test_none_of_an_optional_neighbor_takes_part_in_eq_and_ne():
    class OptionalRef(Settings):
        token: Optional[str] = non_storage_setting(default=None)
        same: Optional[str] = non_storage_setting(default=None, eq=token)

    OptionalRef.validate_settings()  # None == None holds
    OptionalRef.same = "x"
    with pytest.raises(SettingValidationError) as info:
        OptionalRef.validate_settings()
    assert "must be equal to the value of 'token' (None)" in str(info.value)


def test_a_rule_whose_neighbor_holds_no_value_does_not_apply():
    # a member without a default holds no value until assigned or loaded;
    # there is nothing to compare with, so the rule waits
    class Waiting(Settings):
        low: int = environment_variable_setting(name="XV_WAITING_LOW")
        high: int = non_storage_setting(default=10, ge=low)

    Waiting.validate_settings()  # low has no value: the rule does not apply
    Waiting.low = 5
    Waiting.validate_settings()
    Waiting.low = 50
    with pytest.raises(SettingValidationError):
        Waiting.validate_settings()


def test_incomparable_neighbor_value_is_a_violation_not_a_crash():
    # int vs str never compares: the class statement reports the rule as
    # violated instead of crashing the check
    with pytest.raises(TypeError) as info:

        class Mixed(Settings):
            tag: str = non_storage_setting(default="a")
            count: int = non_storage_setting(default=1, gt=tag)

    assert "is not comparable with the gt bound, the value of 'tag'" in str(info.value)


def test_secret_neighbor_value_stays_masked_in_messages():
    class WithSecret(Settings):
        token: SecretStr = non_storage_setting(default=SecretStr("s3cr3t"))
        echo: str = non_storage_setting(default="s3cr3t", eq=token)

    WithSecret.__settings_values__["echo"] = "leak"  # the pair breaks
    with pytest.raises(SettingValidationError) as info:
        WithSecret.validate_settings()
    message = str(info.value)
    assert "s3cr3t" not in message
    assert "**********" in message


def test_subclass_inherits_the_rule_and_redeclaration_resolves_by_name():
    class Base(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

    class Sub(Base):
        low: int = non_storage_setting(default=5)  # redeclared: the rule sees this value

    Sub.validate_settings()  # 10 >= 5

    with pytest.raises(TypeError):
        # the redeclaration breaks the rule against the inherited high
        class Broken(Base):
            low: int = non_storage_setting(default=50)


# ---------------------------------------------------------------------------
# when=: the member's constraints gated on a sibling's truthiness


def test_when_gates_all_constraints_of_the_member():
    class Secure(Settings):
        ssl: bool = non_storage_setting(default=False)
        port: int = non_storage_setting(default=80, eq=443, when=ssl)

    assert Secure.port == 80  # ssl off: the default passes the creation check
    Secure.port = 8080  # ...and an assignment too
    Secure.validate_settings()

    Secure.ssl = True  # the constraint wakes up
    with pytest.raises(SettingValidationError) as info:
        Secure.validate_settings()
    assert info.value.problems == {"port": ["value 8080 must be equal to 443"]}
    with pytest.raises(SettingValidationError, match="must be equal to 443"):
        Secure.port = 8081  # the assignment boundary resolves when= as well

    Secure.port = 443
    Secure.validate_settings()


def test_when_resolves_against_the_actual_value_after_the_fallbacks():
    names = _names("ssl", "port")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(names["ssl"], "1")

        class Conditional(Settings):
            ssl: bool = environment_variable_setting(name=names["ssl"], default=False)
            port: int = environment_variable_setting(
                name=names["port"], default=80, eq=443, when=ssl
            )

        Conditional.load_settings()
    # ssl loaded as True, port stayed at its default: the rule fires and the
    # members of the rule fall back to their (consistent) defaults
    assert Conditional.ssl is False
    assert Conditional.port == 80


def test_a_late_neighbor_change_reactivates_the_dormant_rule():
    class Dormant(Settings):
        ssl: bool = non_storage_setting(default=False)
        port: int = non_storage_setting(default=80, eq=443, when=ssl)

    Dormant.ssl = True  # the dormant rule now judges the stored value
    with pytest.raises(SettingValidationError) as info:
        Dormant.validate_settings()
    assert "port" in info.value.problems


# ---------------------------------------------------------------------------
# level 2: the __validate__ hook


def test_hook_findings_join_the_report_of_every_check():
    class Hooked(Settings):
        mode: str = non_storage_setting(default="dev")
        ssl: Optional[str] = non_storage_setting(default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    Hooked.validate_settings()

    Hooked.mode = "prod"
    with pytest.raises(SettingValidationError) as info:
        Hooked.validate_settings()
    assert info.value.problems == {"ssl": ["ssl is required when mode is 'prod'"]}
    assert Hooked.mode == "prod"  # the check changes nothing


def test_hook_and_declarative_rules_share_one_report():
    class Both(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

        def __validate__(self) -> dict:
            return {"high": "hook disagrees too"}

    Both.__settings_values__["high"] = 0
    with pytest.raises(SettingValidationError) as info:
        Both.validate_settings()
    assert info.value.problems == {
        "high": [
            "value 0 must be greater than or equal to the value of 'low' (1)",
            "hook disagrees too",
        ]
    }


def test_hook_runs_on_a_fully_built_snapshot_and_cannot_touch_the_class():
    class Guarded(Settings):
        low: int = non_storage_setting(default=1)

        def __validate__(self) -> dict:
            self.low = 999  # a violating hook: mutation must not stick
            return {"low": "still reports"}

    with pytest.raises(SettingValidationError):
        Guarded.validate_settings()
    assert Guarded.low == 1


def test_hook_must_return_a_mapping():
    class BadHook(Settings):
        value: int = non_storage_setting(default=1)

        def __validate__(self) -> dict:
            return "nope"  # type: ignore[return-value]  # the negative scenario under test

    with pytest.raises(TypeError, match="must return a dict"):
        BadHook.validate_settings()


def test_hook_exception_propagates_as_is():
    def boom(context):
        raise RuntimeError("bug in the hook")

    class Raising(Settings):
        value: int = non_storage_setting(default=1)
        __validate__ = boom

    with pytest.raises(RuntimeError, match="bug in the hook"):
        Raising.validate_settings()


# ---------------------------------------------------------------------------
# declaration errors: references that name no member, cycles


def test_when_literal_fails_the_declaration():
    with pytest.raises(TypeError, match="when must reference a member"):

        class Literal(Settings):
            value: int = non_storage_setting(default=1, when=True)


def test_reference_to_an_attribute_bound_to_no_member_fails():
    orphan = non_storage_setting(default=1)
    with pytest.raises(TypeError) as info:

        class Orphan(Settings):
            value: int = non_storage_setting(default=2, ge=orphan)

    assert "references an attribute that is not declared as a member by any settings class" in str(
        info.value
    )


def test_a_descriptor_bound_fails_the_declaration():
    class Other(Settings):
        member: int = non_storage_setting(default=1)

    with pytest.raises(TypeError, match="member of another"):
        # reading a settings class's member through the class yields its
        # value, so the common misspelling is invisible; a descriptor
        # passed directly (the storage form of that misspelling) fails
        # loudly instead of becoming a bound nobody meant
        class ThroughClass(Settings):
            value: int = non_storage_setting(
                default=2, ge=Other.__settings_members__["member"].descriptor
            )


def test_reference_cycles_are_named_in_full():
    # the factories cannot build a cycle (a bound must exist before the
    # attribute referencing it), but an attribute subclass can; the guard
    # is the class statement's, so the detector is probed directly
    assert cross_validation._find_cycle({"a": ["b"], "b": ["a"]}) == ["a", "b", "a"]
    assert cross_validation._find_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}) == [
        "a",
        "b",
        "c",
        "a",
    ]
    assert cross_validation._find_cycle({"a": ["b"], "b": [], "c": ["c"]}) == ["c", "c"]
    assert cross_validation._find_cycle({"a": ["b"], "b": ["a"], "x": []}) is not None


# ---------------------------------------------------------------------------
# the load pass: soft — the violated rule's members fall back to defaults


def test_load_resets_the_members_of_a_violated_rule(caplog, monkeypatch):
    names = _names("lo", "hi")
    monkeypatch.setenv(names["lo"], "2000")
    monkeypatch.setenv(names["hi"], "1500")

    class Net(Settings):
        lo: int = environment_variable_setting(name=names["lo"], default=1024)
        hi: int = environment_variable_setting(name=names["hi"], default=65535, ge=lo)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        Net.load_settings()

    assert Net.lo == 1024  # both members of the violated rule are reset
    assert Net.hi == 65535
    reports = [r for r in caplog.records if "cross-member constraint violations" in r.getMessage()]
    assert len(reports) == 1
    assert "resetting the members to their defaults: lo, hi" in reports[0].getMessage()


def test_load_without_violations_stays_silent_and_keeps_values(monkeypatch, caplog):
    names = _names("lo2", "hi2")
    monkeypatch.setenv(names["lo2"], "2000")
    monkeypatch.setenv(names["hi2"], "9000")

    class Net(Settings):
        lo: int = environment_variable_setting(name=names["lo2"], default=1024)
        hi: int = environment_variable_setting(name=names["hi2"], default=65535, ge=lo)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        Net.load_settings()

    assert (Net.lo, Net.hi) == (2000, 9000)
    assert not [r for r in caplog.records if "cross-member" in r.getMessage()]


def test_a_hook_finding_the_reset_cannot_settle_aborts_the_load(caplog, monkeypatch):
    names = _names("mode3", "ssl3")
    monkeypatch.setenv(names["mode3"], "prod")
    monkeypatch.setenv(names["ssl3"], "on")

    class Hooked(Settings):
        mode: str = environment_variable_setting(name=names["mode3"], default="dev")
        ssl: Optional[str] = environment_variable_setting(name=names["ssl3"], default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod":
                return {"ssl": "ssl is judged by other rules"}
            return {}

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(AggregateLoadError) as info:
            Hooked.load_settings()

    # the hook names ssl, and the reset takes the members the finding
    # involves: ssl alone (a hook declares no references); the finding
    # itself stays — mode is nobody the hook named — so the pass aborts
    # and the class keeps the state it had
    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error).endswith("no reset to the declared defaults settles it")
    assert Hooked.mode == "dev"
    assert Hooked.ssl is None
    reports = [r for r in caplog.records if "cross-member" in r.getMessage()]
    assert len(reports) == 2
    assert "resetting the members to their defaults: ssl" in reports[0].getMessage()
    assert "the pass is aborted" in reports[1].getMessage()


def test_a_when_active_violation_falls_back_to_the_members_default(caplog, monkeypatch):
    names = _names("flag4", "tag4")
    monkeypatch.setenv(names["flag4"], "1")
    monkeypatch.setenv(names["tag4"], "q")

    class Chained(Settings):
        flag: bool = environment_variable_setting(name=names["flag4"], default=False)
        tag: str = environment_variable_setting(
            name=names["tag4"], default="xx", min_length=2, when=flag
        )

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        Chained.load_settings()

    # the load pass resolved when= against the loaded flag, found the field
    # violation and fell back to the member's own default — the soft field
    # policy of a single member, condition included
    assert Chained.flag is True
    assert Chained.tag == "xx"
    field_reports = [r for r in caplog.records if "violates its constraints" in r.getMessage()]
    assert len(field_reports) == 1
    assert not [r for r in caplog.records if "cross-member" in r.getMessage()]


def test_a_hook_that_rejects_every_state_aborts_the_load(caplog, monkeypatch):
    # the hook disagrees with the all-default state itself: no reset can
    # settle the finding, so the pass aborts instead of completing into
    # a state the class rejects
    names = _names("steady5")
    monkeypatch.setenv(names["steady5"], "2")

    class Steady(Settings):
        value: int = environment_variable_setting(name=names["steady5"], default=1)

        def __validate__(self) -> dict:
            return {"value": "the hook is never happy"}

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(AggregateLoadError) as info:
            Steady.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert "the hook is never happy" in str(error)
    assert Steady.value == 1
    reports = [r for r in caplog.records if "cross-member" in r.getMessage()]
    assert reports
    assert "the pass is aborted" in reports[-1].getMessage()


def test_a_violation_a_required_participant_keeps_aborts_the_load(caplog, monkeypatch):
    names = _names("floor6", "ceil6")
    monkeypatch.setenv(names["floor6"], "5000")
    monkeypatch.setenv(names["ceil6"], "100")

    class Required(Settings):
        floor: int = environment_variable_setting(name=names["floor6"], default=REQUIRED)
        ceil: int = environment_variable_setting(name=names["ceil6"], default=100, ge=floor)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(AggregateLoadError) as info:
            Required.load_settings()

    # the rule wants ceil >= floor; floor is required, holds its loaded
    # value and has no default to reset to, and ceil already stands at
    # its default — no reset can settle the rule, so the pass aborts
    # and the class keeps the state it had (floor holds nothing at all,
    # for no load ever completed)
    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error).startswith("setting 'ceil' of 'Required' violates its constraints")
    assert "no reset to the declared defaults settles it" in str(error)
    assert any("has no default to reset to" in r.getMessage() for r in caplog.records)


def test_a_required_neighbor_that_found_nothing_aborts_the_load_once():
    names = _names("ceil7")

    class Waiting(Settings):
        floor: int = environment_variable_setting(default=REQUIRED)
        ceil: int = environment_variable_setting(name=names["ceil7"], default=100, ge=floor)

    with pytest.raises(AggregateLoadError) as info:
        Waiting.load_settings()

    # the neighbor holds no value: its own miss is the one entry, and the
    # rule referencing it does not pile a second error on top
    assert [type(entry) for entry in info.value.errors] == [MissingValueError]


# ---------------------------------------------------------------------------
# update_from_dict / update_from_object: strict — the whole update applies or
# nothing does


def test_update_rejects_a_cross_member_violation_and_applies_nothing():
    class Ranges(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

    with pytest.raises(SettingValidationError) as info:
        Ranges.update_from_dict({"low": 100, "high": 50})
    assert "high" in info.value.problems
    assert (Ranges.low, Ranges.high) == (1, 10)  # nothing was applied


def test_update_checks_the_new_values_beside_the_current_ones():
    class Ranges(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

    Ranges.update_from_dict({"low": 5})  # 10 >= 5: the pair stays consistent
    assert Ranges.low == 5
    with pytest.raises(SettingValidationError):
        Ranges.update_from_dict({"low": 50})  # 10 >= 50 would not hold
    assert Ranges.low == 5


def test_update_rejects_a_hook_finding_too():
    class Hooked(Settings):
        mode: str = non_storage_setting(default="dev")
        ssl: Optional[str] = non_storage_setting(default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    with pytest.raises(SettingValidationError) as info:
        Hooked.update_from_dict({"mode": "prod"})
    assert "ssl" in info.value.problems
    assert Hooked.mode == "dev"

    Hooked.update_from_dict({"mode": "prod", "ssl": "on"})  # the pair passes
    assert Hooked.ssl == "on"


def test_update_resolves_when_against_the_merged_state():
    class Conditional(Settings):
        ssl: bool = non_storage_setting(default=False)
        port: int = non_storage_setting(default=80, eq=443, when=ssl)

    with pytest.raises(SettingValidationError) as info:
        Conditional.update_from_dict({"ssl": True})  # port=80 stays: eq wakes up
    assert "port" in info.value.problems

    Conditional.update_from_dict({"ssl": True, "port": 443})
    assert Conditional.port == 443


def test_update_from_object_shares_the_rules_of_update_from_dict():
    class Ranges(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

    snapshot = Ranges.to_object()
    snapshot.low = 100
    snapshot.high = 50
    with pytest.raises(SettingValidationError):
        Ranges.update_from_object(snapshot)
    assert (Ranges.low, Ranges.high) == (1, 10)


# ---------------------------------------------------------------------------
# save: strict — a class in violation saves nothing


def test_save_raises_on_a_violation_and_writes_nothing(monkeypatch):
    names = _names("lo8", "hi8")
    monkeypatch.setenv(names["lo8"], "2000")

    class Net(Settings):
        lo: int = environment_variable_setting(name=names["lo8"], default=1024)
        hi: int = environment_variable_setting(name=names["hi8"], default=65535, ge=lo)

    Net.load_settings()
    Net.__settings_values__["hi"] = 1000  # 1000 < 2000: the pair is broken
    with pytest.raises(SettingValidationError) as info:
        Net.save_settings()

    assert "hi" in info.value.problems
    assert names["hi8"] not in os.environ  # nothing was written


# ---------------------------------------------------------------------------
# validate_settings: strict, read-only, the report carried as data


def test_validate_settings_passes_quietly_on_a_consistent_class():
    class Fine(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

        def __validate__(self) -> dict:
            return {}

    assert Fine.validate_settings() is None


def test_validate_settings_changes_nothing():
    class Touched(Settings):
        value: int = non_storage_setting(default=1, gt=0)

    Touched.__settings_values__["value"] = -1
    with pytest.raises(SettingValidationError):
        Touched.validate_settings()
    assert Touched.value == -1


def test_validate_settings_message_lists_every_finding():
    class Pair(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)
        empty: str = non_storage_setting(default="xx", min_length=2)

    Pair.__settings_values__.update({"high": 0, "empty": ""})
    with pytest.raises(SettingValidationError) as info:
        Pair.validate_settings()

    assert str(info.value) == (
        "invalid settings in Pair:\n"
        "  - high: value 0 must be greater than or equal to the value of 'low' (1)\n"
        "  - empty: length 0 must be at least 2"
    )


def test_load_settles_a_broken_chain_in_rounds(caplog, monkeypatch):
    names = _names("a9", "b9", "c9")
    monkeypatch.setenv(names["a9"], "5")
    monkeypatch.setenv(names["b9"], "1")
    monkeypatch.setenv(names["c9"], "2")

    class Chain(Settings):
        a: int = environment_variable_setting(name=names["a9"], default=0)
        b: int = environment_variable_setting(name=names["b9"], default=10, ge=a)
        c: int = environment_variable_setting(name=names["c9"], default=20, ge=b)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        Chain.load_settings()

    # round one: b >= a is violated, the reset puts a and b at their
    # defaults; round two: c=2 now stands below the restored b=10, so c
    # resets too — the all-default state closes the chain
    assert (Chain.a, Chain.b, Chain.c) == (0, 10, 20)
    reports = [r for r in caplog.records if "resetting the members" in r.getMessage()]
    assert len(reports) == 2


def test_a_hook_may_name_a_member_the_class_does_not_declare():
    class Stranger(Settings):
        value: int = non_storage_setting(default=1)

        def __validate__(self) -> dict:
            return {"elsewhere": "not a member"}

    with pytest.raises(SettingValidationError) as info:
        Stranger.validate_settings()
    assert "elsewhere" in info.value.problems  # reported as named, nothing resets


def test_the_error_stays_a_plain_value_error():
    class Ranges(Settings):
        low: int = non_storage_setting(default=1)
        high: int = non_storage_setting(default=10, ge=low)

    Ranges.high = 0
    try:
        Ranges.validate_settings()
    except ValueError as exc:
        assert isinstance(exc, SettingValidationError)
        assert exc.problems is not None
    else:
        pytest.fail("validate_settings did not raise")
