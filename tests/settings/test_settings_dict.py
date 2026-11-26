"""Snapshot contract: ``to_dict`` and ``update_from_dict`` on the settings
class.

The settings class is the singleton storage, so a snapshot must be an
independent object. These tests pin four things:

- the copy semantics (a deep copy, with effective defaults);
- the apply semantics (type conversion, and patching instead of replacing);
- the failure modes (unknown keys, and values that cannot be converted);
- the ``missing=`` modes of ``to_dict`` for a required member without a
  value, and the warning that a ``None`` into a member that cannot hold it
  records.
"""

from __future__ import annotations

import enum
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from advexp.settings import MISSING_NONE, MISSING_RAISE, MISSING_SKIP, Settings
from advexp.settings.plugins.environment.variables import env_source
from advexp.settings_base.environment_variable_setting import environment_variable_setting
from advexp.settings_base.member_load_error import MemberLoadError

# noinspection PyProtectedMember
from advexp.settings_base.sourceless_setting import sourceless_setting


class Color(enum.Enum):
    RED = 1
    GREEN = 2


class SnapshotSettings(Settings):
    flag: bool = sourceless_setting(default=False)
    count: int = sourceless_setting(default=1)
    text: str = sourceless_setting(default="fallback")
    shade: Optional[Color] = sourceless_setting(default=None)
    tags: List[str] = sourceless_setting(default=[])


@pytest.fixture(autouse=True)
def reset_settings():
    SnapshotSettings.reset_settings()
    yield
    SnapshotSettings.reset_settings()


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------


def test_to_dict_returns_current_values_keyed_by_member_name():
    SnapshotSettings.flag = True
    SnapshotSettings.text = "custom"

    snapshot = SnapshotSettings.to_dict()

    assert snapshot == {
        "flag": True,
        "count": 1,
        "text": "custom",
        "shade": None,
        "tags": [],
    }


def test_to_dict_reports_effective_defaults_before_any_load():
    class FreshSettings(Settings):
        member: int = sourceless_setting(default=7)

    assert FreshSettings.to_dict() == {"member": 7}


def test_to_dict_deep_copies_mutable_values():
    SnapshotSettings.tags = ["primary"]

    snapshot = SnapshotSettings.to_dict()
    snapshot["tags"].append("mutated")

    assert SnapshotSettings.tags == ["primary"]

    SnapshotSettings.tags.append("later")
    assert snapshot["tags"] == ["primary", "mutated"]


def test_to_dict_includes_inherited_members():
    class BaseSnap(Settings):
        base_flag: bool = sourceless_setting(default=False)

    class DerivedSnap(BaseSnap):
        derived_count: int = sourceless_setting(default=3)

    assert DerivedSnap.to_dict() == {"base_flag": False, "derived_count": 3}


# ---------------------------------------------------------------------------
# update_from_dict
# ---------------------------------------------------------------------------


def test_update_from_dict_sets_values_in_class_storage():
    SnapshotSettings.update_from_dict({"flag": True, "count": 42})

    assert SnapshotSettings.flag is True
    assert SnapshotSettings.count == 42
    assert SnapshotSettings.__settings_values__["flag"] is True


def test_update_from_dict_converts_to_annotated_types_like_load():
    SnapshotSettings.update_from_dict({"count": "8080", "flag": "yes", "shade": "GREEN", "text": 5})

    assert SnapshotSettings.count == 8080
    assert SnapshotSettings.count.__class__ is int
    assert SnapshotSettings.flag is True
    assert SnapshotSettings.shade is Color.GREEN
    assert SnapshotSettings.text == "5"


def test_update_from_dict_is_patch_not_replace():
    SnapshotSettings.text = "keep-me"

    SnapshotSettings.update_from_dict({"flag": True})

    assert SnapshotSettings.flag is True
    assert SnapshotSettings.text == "keep-me"


def test_update_from_dict_unknown_keys_raise_key_error():
    with pytest.raises(KeyError, match="not a setting"):
        SnapshotSettings.update_from_dict({"flag": True, "mystery": 1, "another": 2})


def test_update_from_dict_applies_nothing_when_a_value_fails_to_convert():
    SnapshotSettings.flag = False

    with pytest.raises(ValueError):
        SnapshotSettings.update_from_dict({"flag": True, "count": "not-a-number"})

    assert SnapshotSettings.flag is False  # nothing applied, not even the valid part


def test_update_from_dict_copies_mutable_values():
    tags = ["a", "b"]
    SnapshotSettings.update_from_dict({"tags": tags})

    tags.append("c")  # mutating the source mapping after the update

    assert SnapshotSettings.tags == ["a", "b"]  # storage never shares mutable state


def test_round_trip_snapshot_apply_restores_values():
    snapshot: Dict[str, Any] = SnapshotSettings.to_dict()

    SnapshotSettings.flag = True
    SnapshotSettings.tags = ["changed"]
    SnapshotSettings.update_from_dict(snapshot)

    assert SnapshotSettings.flag is False
    assert SnapshotSettings.tags == []


def test_simple_namespace_snapshot_round_trip():
    SnapshotSettings.flag = True
    instance = SimpleNamespace(**SnapshotSettings.to_dict())

    assert instance.flag is True
    instance.flag = False
    assert SnapshotSettings.flag is True  # instance is independent

    SnapshotSettings.update_from_dict(vars(instance))
    assert SnapshotSettings.flag is False


# ---------------------------------------------------------------------------
# the missing= modes of to_dict (#90)
# ---------------------------------------------------------------------------


class UnloadedSettings(
    Settings,
    options=env_source(),
):
    token: str = environment_variable_setting(name="TEST_SDM_TOKEN")
    width: int = sourceless_setting(default=800)


@pytest.fixture(autouse=True)
def reset_unloaded_settings():
    yield
    UnloadedSettings.reset_settings()


def test_to_dict_fails_on_a_required_member_without_a_value():
    # the default mode keeps the read honest: a required member that never
    # got a value fails the snapshot with that member's read error
    with pytest.raises(MemberLoadError, match="no value was loaded"):
        UnloadedSettings.to_dict()


def test_to_dict_missing_none_stands_none_in():
    snapshot = UnloadedSettings.to_dict(missing=MISSING_NONE)

    assert snapshot == {"token": None, "width": 800}


def test_to_dict_missing_none_serves_loaded_values():
    # a required member that holds a value reads as the value, not as None
    UnloadedSettings.token = "loaded"

    assert UnloadedSettings.to_dict(missing=MISSING_NONE)["token"] == "loaded"


def test_to_dict_missing_skip_leaves_the_member_out():
    snapshot = UnloadedSettings.to_dict(missing=MISSING_SKIP)

    assert snapshot == {"width": 800}


def test_to_dict_missing_mode_is_validated():
    with pytest.raises(ValueError, match="is not one of") as info:
        UnloadedSettings.to_dict(missing="bogus")

    text = str(info.value)
    assert repr(MISSING_RAISE) in text
    assert repr(MISSING_NONE) in text
    assert repr(MISSING_SKIP) in text


# ---------------------------------------------------------------------------
# None into a member that cannot hold it (#128)
# ---------------------------------------------------------------------------


def test_update_from_dict_none_into_a_non_optional_member_warns(caplog):
    # the None is stored — it is a value like any other at this boundary —
    # and the warning names the member, so a mistaken key surfaces in the
    # log instead of passing silently
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        SnapshotSettings.update_from_dict({"count": None, "shade": None})

    assert SnapshotSettings.count is None
    assert SnapshotSettings.shade is None
    records = [record for record in caplog.records if "'count'" in record.getMessage()]
    assert len(records) == 1
    assert "int" in records[0].getMessage()
    assert not [record for record in caplog.records if "'shade'" in record.getMessage()]


def test_update_from_object_none_into_a_non_optional_member_warns(caplog):
    # the object form goes through the same boundary and records the same
    # warning
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        SnapshotSettings.update_from_object(SimpleNamespace(count=None))

    assert SnapshotSettings.count is None
    assert any(
        "'count'" in record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    )
