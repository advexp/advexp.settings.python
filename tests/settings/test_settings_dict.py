"""Snapshot contract: ``to_dict`` and ``update_from_dict`` on the settings
class.

The settings class is the singleton storage, so a snapshot must be an
independent object. These tests pin three things:

- the copy semantics (a deep copy, with effective defaults);
- the apply semantics (type conversion, and patching instead of replacing);
- the failure modes (unknown keys, and values that cannot be converted).
"""

from __future__ import annotations

import enum
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from advexp.settings import Settings

# noinspection PyProtectedMember
from advexp.settings._internal.non_storage_setting import non_storage_setting


class Color(enum.Enum):
    RED = 1
    GREEN = 2


class SnapshotSettings(Settings):
    flag: bool = non_storage_setting(default=False)
    count: int = non_storage_setting(default=1)
    text: str = non_storage_setting(default="fallback")
    shade: Optional[Color] = non_storage_setting(default=None)
    tags: List[str] = non_storage_setting(name="tags", default=[])


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
        member: int = non_storage_setting(default=7)

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
        base_flag: bool = non_storage_setting(default=False)

    class DerivedSnap(BaseSnap):
        derived_count: int = non_storage_setting(default=3)

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
