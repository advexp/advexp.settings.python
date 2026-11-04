"""Snapshot contract: ``to_object`` and ``update_from_object`` on the settings
class.

The object form of a snapshot is a detached instance of the settings class.
Its fields are the declared member names, so a renamed setting shows up as a
stale attribute on snapshots. Its reads and writes touch only the own
storage of the instance.

These tests pin three things:

- the copy semantics (an instance of the class, a deep copy, and effective
  defaults);
- the apply semantics that are shared with ``update_from_dict`` (type
  conversion, and patching instead of replacing for partial objects);
- the failure modes (unknown fields, and values that cannot be converted).

One more contract is tested: ordinary instances keep sharing the class
storage.
"""

from __future__ import annotations

import enum
from types import SimpleNamespace
from typing import Any, List, Optional

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
# to_object
# ---------------------------------------------------------------------------


def test_to_object_returns_detached_instance_of_the_settings_class():
    SnapshotSettings.flag = True

    snapshot = SnapshotSettings.to_object()

    assert type(snapshot) is SnapshotSettings
    assert snapshot.flag is True
    assert snapshot.count == 1
    assert snapshot.text == "fallback"
    assert snapshot.shade is None
    assert snapshot.tags == []


def test_to_object_fields_carry_the_member_names():
    # the rename-safety contract: a field the class no longer declares is a
    # loud AttributeError, not a silent dict miss
    class FreshSettings(Settings):
        member: int = non_storage_setting(default=7)

    snapshot = FreshSettings.to_object()

    assert snapshot.member == 7
    with pytest.raises(AttributeError):
        _ = getattr(snapshot, "renamed")


def test_to_object_reports_effective_defaults_before_any_load():
    class FreshSettings(Settings):
        member: int = non_storage_setting(default=7)

    assert FreshSettings.to_object().member == 7


def test_to_object_is_independent_of_later_class_writes():
    snapshot = SnapshotSettings.to_object()

    SnapshotSettings.flag = True
    SnapshotSettings.count = 99

    assert snapshot.flag is False
    assert snapshot.count == 1


def test_snapshot_writes_stay_on_the_instance():
    snapshot = SnapshotSettings.to_object()

    snapshot.flag = True
    snapshot.tags.append("local")

    assert SnapshotSettings.flag is False
    assert SnapshotSettings.tags == []


def test_to_object_deep_copies_mutable_values():
    SnapshotSettings.tags = ["primary"]

    snapshot = SnapshotSettings.to_object()
    snapshot.tags.append("mutated")

    assert SnapshotSettings.tags == ["primary"]

    SnapshotSettings.tags.append("later")
    assert snapshot.tags == ["primary", "mutated"]


def test_to_object_of_unset_member_does_not_corrupt_the_declared_default():
    snapshot = SnapshotSettings.to_object()  # tags never set: the default
    snapshot.tags.append("mutated")

    assert SnapshotSettings.tags == []

    SnapshotSettings.reset_settings()
    assert SnapshotSettings.tags == []


def test_to_object_includes_inherited_members():
    class BaseSnap(Settings):
        base_flag: bool = non_storage_setting(default=False)

    class DerivedSnap(BaseSnap):
        derived_count: int = non_storage_setting(default=3)

    snapshot = DerivedSnap.to_object()

    assert type(snapshot) is DerivedSnap
    assert snapshot.base_flag is False
    assert snapshot.derived_count == 3


def test_ordinary_instances_still_share_the_class_storage():
    instance = SnapshotSettings()

    instance.flag = True

    assert SnapshotSettings.flag is True
    assert SnapshotSettings().flag is True


# ---------------------------------------------------------------------------
# update_from_object
# ---------------------------------------------------------------------------


def test_update_from_object_sets_values_in_class_storage():
    snapshot = SnapshotSettings.to_object()
    snapshot.flag = True
    snapshot.count = 42

    SnapshotSettings.update_from_object(snapshot)

    assert SnapshotSettings.flag is True
    assert SnapshotSettings.count == 42
    assert SnapshotSettings.__settings_values__["flag"] is True


def test_update_from_object_converts_to_annotated_types_like_load():
    # (deliberately wrong-typed field values: conversion is the subject, so
    # the snapshot is read as Any here)
    snapshot: Any = SnapshotSettings.to_object()
    snapshot.count = "8080"
    snapshot.flag = "yes"
    snapshot.shade = "GREEN"
    snapshot.text = 5

    SnapshotSettings.update_from_object(snapshot)

    assert SnapshotSettings.count == 8080
    assert SnapshotSettings.count.__class__ is int
    assert SnapshotSettings.flag is True
    assert SnapshotSettings.shade is Color.GREEN
    assert SnapshotSettings.text == "5"


def test_update_from_object_accepts_any_attribute_namespace():
    SnapshotSettings.update_from_object(SimpleNamespace(flag=True))

    assert SnapshotSettings.flag is True
    assert SnapshotSettings.text == "fallback"  # fields the object lacks stay untouched


def test_update_from_object_unknown_fields_raise_key_error():
    with pytest.raises(KeyError, match="not a setting"):
        SnapshotSettings.update_from_object(SimpleNamespace(flag=True, mystery=1))


def test_update_from_object_rejects_a_foreign_snapshot():
    class OtherSettings(Settings):
        other_flag: bool = non_storage_setting(default=True)

    with pytest.raises(KeyError, match="not a setting"):
        SnapshotSettings.update_from_object(OtherSettings.to_object())


def test_update_from_object_applies_nothing_when_a_value_fails_to_convert():
    snapshot: Any = SnapshotSettings.to_object()
    snapshot.flag = True
    snapshot.count = "not-a-number"

    with pytest.raises(ValueError):
        SnapshotSettings.update_from_object(snapshot)

    assert SnapshotSettings.flag is False  # nothing applied, not even the valid part


def test_update_from_object_copies_mutable_values():
    snapshot = SnapshotSettings.to_object()
    snapshot.tags = ["a", "b"]

    SnapshotSettings.update_from_object(snapshot)
    snapshot.tags.append("c")  # mutating the snapshot after the update

    assert SnapshotSettings.tags == ["a", "b"]  # storage never shares mutable state


def test_update_from_object_without_attribute_namespace_raises_type_error():
    with pytest.raises(TypeError):
        SnapshotSettings.update_from_object(("flag", True))


def test_round_trip_snapshot_apply_restores_values():
    snapshot = SnapshotSettings.to_object()

    SnapshotSettings.flag = True
    SnapshotSettings.tags = ["changed"]
    SnapshotSettings.update_from_object(snapshot)

    assert SnapshotSettings.flag is False
    assert SnapshotSettings.tags == []
