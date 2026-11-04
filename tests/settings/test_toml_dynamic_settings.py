"""TOMLDynamicSettings plugin tests (runtime-named settings in the TOML file).

The own machinery of the collection is the shared behavior of
``DynamicSettingsBasePlugin``, and it lives in the JSON dynamic tests. This
covers the iteration order, the snapshots, the suite of setting metadata,
and the contracts of the base plugin.

This file covers the surface that is specific to TOML:

- the round trips through the file;
- the document section, with its parameters and its reservation;
- the bindings of an own file;
- the name patterns that the entries spell into the document.
"""

from __future__ import annotations

import dataclasses
import enum
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Type

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import tomlkit

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import (
    DynamicSettingAttribute,
    DynamicSettingsBasePlugin,
)
from advexp.settings.plugins.toml_dynamic_settings import (
    TOML_DYNAMIC_FILE_METADATA,
    TOMLDynamicSettingsConfiguration,
    TOMLDynamicSettingsPlugin,
)
from advexp.settings.plugins.toml_settings import (
    NAME_PATTERN,
    TOMLSetting,
    TOMLSettingsConfiguration,
    TOMLSettingsSerializer,
    toml_setting,
    toml_source,
)
from advexp.settings_base.document_dynamic_settings_plugin import _UNSET_SECTION

# noinspection PyProtectedMember
from advexp.settings_base.names import (
    DEFAULT_SETTINGS_NAME_PATTERN,
    SettingNameMode,
    get_dynamic_settings_class_prefix,
    get_full_setting_name,
)
from advexp.settings_base.toml_options import TOML_TABLE_SEPARATOR


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


@dataclasses.dataclass
class Point:
    x: int
    y: int = 0


class DynSettings(Settings):
    """Mixed class: one declared member plus the dynamic collection."""

    airplane_mode: bool = toml_setting(default=False)


class OtherSettings(Settings):
    """A second class sharing the file: dynamic entries are kept apart."""


SECTION = TOMLDynamicSettingsPlugin.DEFAULT_SECTION


def dyn_full_name(settings_class: type, name: str) -> str:
    return get_full_setting_name(name, None, settings_class, mode=SettingNameMode.DYNAMIC)


def dyn_class_key(settings_class: type) -> str:
    prefix = get_dynamic_settings_class_prefix(settings_class)
    return prefix[:-1] if prefix else ""


def nested(key: str, value: Any) -> Any:
    """The value placed at the dotted address: a table per key level."""
    levels = key.split(TOML_TABLE_SEPARATOR)
    for level in reversed(levels[1:]):
        value = {level: value}
    return {levels[0]: value}


def dyn_section(settings_class: type, entries: Dict[str, Any]) -> Dict[str, Any]:
    """The section's table for one settings class: the class part nested."""
    return nested(dyn_class_key(settings_class), entries)


def dyn_document(settings_class: type, entries: Dict[str, Any]) -> Dict[str, Any]:
    """The document part holding one class's dynamic entries."""
    return {SECTION: dyn_section(settings_class, entries)}


def deep_merge(*parts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge documents into one. Two classes of one module share the leading levels
    of the class part and are nested side by side there.
    """
    merged: Dict[str, Any] = {}
    for part in parts:
        for key, value in part.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
    return merged


def static_full_name(settings_class: Type[Settings], member: str) -> str:
    attr = settings_class.__settings_members__[member].attribute
    return get_full_setting_name(member, attr, settings_class)


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.toml"
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", path)
    # the dynamic side's own file and name pattern are off unless a test
    # opts in
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(
        TOMLDynamicSettingsConfiguration, NAME_PATTERN, DEFAULT_SETTINGS_NAME_PATTERN
    )
    yield path


@pytest.fixture(autouse=True)
def clean_collections():
    # plugin instances and class metadata live as long as the settings class;
    # start each test with an empty dynamic collection, no declared order and
    # the default section binding
    for klass in (DynSettings, OtherSettings):
        plugin = klass.get_plugin(TOMLDynamicSettingsPlugin)
        # noinspection PyProtectedMember
        plugin._DynamicSettingsBasePlugin__values.clear()
        # noinspection PyProtectedMember
        plugin._DynamicSettingsBasePlugin__metadata.clear()
        # noinspection PyProtectedMember
        plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_name = _UNSET_SECTION
        # noinspection PyProtectedMember
        plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_path = _UNSET_SECTION
        # no own-file binding: the module default (or the static file) governs
        klass.delete_class_metadata(TOML_DYNAMIC_FILE_METADATA)
        klass.delete_class_metadata(TOMLDynamicSettingsPlugin.ITERATION_ORDER_METADATA)
    yield


def read_document(path: Path) -> Dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def write_document(path: Path, document: Dict[str, Any]) -> None:
    path.write_text(tomlkit.dumps(document), encoding="utf-8")


# -- registration -----------------------------------------------------------------


def test_import_enables_plugin_and_registers_pin_pair():
    assert TOMLDynamicSettingsPlugin in LibraryConfiguration.registered_plugin_classes()
    # the pin's own slot, registered by the base setup from the declared
    # binding: the dynamic side lives apart from the static
    # plugin's TOMLSetting binding, so the two registrations cannot clash
    pin = TOMLDynamicSettingsPlugin.binding.attribute_class
    assert pin is DynamicSettingAttribute[TOMLSetting]
    assert LibraryConfiguration._get_serializer_factory(pin) is TOMLSettingsSerializer


def test_plugin_instance_is_cached_per_class():
    assert DynSettings.get_plugin(TOMLDynamicSettingsPlugin) is DynSettings.get_plugin(
        TOMLDynamicSettingsPlugin
    )
    assert DynSettings.get_plugin(TOMLDynamicSettingsPlugin) is not OtherSettings.get_plugin(
        TOMLDynamicSettingsPlugin
    )


# -- save / load round trip ----------------------------------------------------------


def test_save_writes_dynamic_section_beside_static(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.set_setting("login", "alice")
    plugin.save_settings()

    # the same name as a declared member: static and dynamic entries coexist
    DynSettings.airplane_mode = True
    DynSettings.save_settings()

    document = read_document(configured_file)
    assert document == deep_merge(
        dyn_document(DynSettings, {"checkbox": True, "login": "alice"}),
        nested(static_full_name(DynSettings, "airplane_mode"), True),
    )
    assert not [key for key in document if key.startswith("D.")]


def test_save_pass_starts_a_blank_file_as_an_empty_document(configured_file):
    # a blank TOML file is the valid empty document: the dynamic side's
    # save enumerates the section over it and writes normally
    configured_file.write_text("", encoding="utf-8")
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = read_document(configured_file)
    assert document == dyn_document(DynSettings, {"checkbox": True})


def test_load_rebuilds_collection_from_storage(configured_file):
    write_document(
        configured_file,
        {
            **dyn_document(DynSettings, {"checkbox": True, "login": "alice", "edittext": 42}),
            "someone-elses-key": "kept",
        },
    )
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("stale", "dropped-by-load")  # load replaces the collection
    plugin.load_settings()

    assert list(plugin) == ["checkbox", "edittext", "login"]  # storage order (sorted)
    assert len(plugin) == 3
    assert plugin.get_setting("checkbox") is True
    assert plugin.get_setting("login") == "alice"
    assert plugin.get_setting("edittext") == 42
    assert "stale" not in plugin
    assert read_document(configured_file)["someone-elses-key"] == "kept"  # read-only pass


def test_load_picks_only_this_class_entries(configured_file):
    write_document(
        configured_file,
        deep_merge(
            dyn_document(DynSettings, {"checkbox": True}),
            dyn_document(OtherSettings, {"checkbox": False, "switch": False}),
        ),
    )
    mine = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    mine.load_settings()
    assert list(mine) == ["checkbox"]
    assert mine.get_setting("checkbox") is True

    other = OtherSettings.get_plugin(TOMLDynamicSettingsPlugin)
    other.load_settings()
    assert list(other) == ["checkbox", "switch"]
    assert other.get_setting("checkbox") is False


def test_values_round_trip_through_the_file(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("stamp", datetime(2026, 9, 13, 10, 0, 0))
    plugin.set_setting("color", Color.BLUE)
    plugin.set_setting("point", Point(3, 4))
    plugin.set_setting("tags", ["a", "b"])
    plugin.save_settings()

    plugin.load_settings()
    assert plugin.get_setting("stamp", default=datetime(2026, 1, 1)) == datetime(
        2026, 9, 13, 10, 0, 0
    )
    assert plugin.get_setting("color", default=Color.RED) is Color.BLUE
    assert plugin.get_setting("point", default=Point(0, 0)) == Point(3, 4)
    assert plugin.get_setting("tags", default=[]) == ["a", "b"]


def test_class_level_passes_do_not_touch_dynamic_collection(configured_file):
    write_document(configured_file, dyn_document(DynSettings, {"checkbox": True}))
    DynSettings.load_settings()  # the class pass loads the declared members only

    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    assert len(plugin) == 0


# -- single-setting operations ---------------------------------------------------------


def test_save_setting_writes_and_flushes_one_value(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_setting("checkbox")
    assert read_document(configured_file) == dyn_document(DynSettings, {"checkbox": True})


def test_save_setting_unknown_name_raises():
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    with pytest.raises(KeyError, match="no value to save"):
        plugin.save_setting("never-set")


def test_load_setting_refreshes_one_value(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")
    write_document(configured_file, dyn_document(DynSettings, {"login": "bob"}))
    plugin.load_setting("login")
    assert plugin.get_setting("login") == "bob"


def test_load_setting_drops_name_missing_from_storage(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")
    plugin.load_setting("login")  # the (fresh) file holds no such entry
    assert "login" not in plugin
    plugin.load_setting("never-known")  # a no-op, not an error


def test_delete_setting_removes_from_storage_and_collection(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.delete_setting("checkbox")

    assert "checkbox" not in plugin
    assert read_document(configured_file) == {}  # the emptied section is dropped too
    plugin.delete_setting("checkbox")  # deleting again is not an error


def test_saving_none_drops_the_entry(configured_file):
    # TOML has no null: a None value removes the entry, and the load that
    # comes back no longer knows the name — the JSON null distinction
    # between "stored None" and "missing" has no TOML form
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.set_setting("checkbox", None)
    plugin.save_settings()

    document = read_document(configured_file)
    assert document == {}
    plugin.load_settings()
    assert "checkbox" not in plugin
    with pytest.raises(KeyError):
        plugin.get_setting("checkbox")


# -- save_settings cleanup ----------------------------------------------------------


def test_save_settings_drops_orphaned_entries_of_this_class(configured_file):
    write_document(
        configured_file,
        deep_merge(
            dyn_document(DynSettings, {"orphan": "gone"}),
            dyn_document(OtherSettings, {"kept": "theirs"}),
            {"someone-elses-key": 42},
        ),
    )
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = read_document(configured_file)
    assert document == deep_merge(
        dyn_document(DynSettings, {"checkbox": True}),
        dyn_document(OtherSettings, {"kept": "theirs"}),
        {"someone-elses-key": 42},
    )


def test_delete_settings_clears_storage_and_collection(configured_file):
    write_document(
        configured_file,
        deep_merge(
            dyn_document(DynSettings, {"checkbox": True}),
            dyn_document(OtherSettings, {"kept": "theirs"}),
        ),
    )
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")  # never saved: deleted from storage anyway
    plugin.delete_settings()

    assert len(plugin) == 0
    assert read_document(configured_file) == dyn_document(OtherSettings, {"kept": "theirs"})


def test_bulk_save_logs_and_skips_values_without_a_toml_form(configured_file, caplog):
    import logging

    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("good", 1)
    plugin.set_setting("bad", object())  # no TOML form

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        plugin.save_settings()

    assert read_document(configured_file) == dyn_document(DynSettings, {"good": 1})
    assert any("dynamic setting 'bad'" in record.message for record in caplog.records)


def test_single_save_propagates_unconvertible_value():
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("bad", object())
    with pytest.raises(TypeError):
        plugin.save_setting("bad")


# -- user-facing storage errors --------------------------------------------------------


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("[not toml", encoding="utf-8")
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="cannot parse the TOML settings file"):
        plugin.load_settings()


def test_unset_file_path_raises_to_caller(monkeypatch):
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="file_path"):
        plugin.save_settings()


def test_section_holding_a_scalar_raises_to_caller(configured_file):
    write_document(configured_file, {SECTION: 42})
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="must hold an object"):
        plugin.load_settings()


# -- the document section ----------------------------------------------------------------


def test_section_can_be_renamed_and_disabled(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    assert plugin.dynamic_settings_section_name == "runtime"
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {
        "runtime": dyn_section(DynSettings, {"checkbox": True})
    }

    # None switches to the flat layout: D-prefixed full-name keys at the root
    plugin.dynamic_settings_section_name = None
    plugin.save_settings()
    assert read_document(configured_file)[dyn_full_name(DynSettings, "checkbox")] is True


def test_section_rejects_empty_and_non_string_names():
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="non-empty string"):
        plugin.dynamic_settings_section_name = ""
    with pytest.raises(ValueError, match="non-empty string"):
        plugin.dynamic_settings_section_name = 42
    # the path follows the path= rules of TOMLSetting: a JSON Pointer
    with pytest.raises(ValueError, match="must start with '/'"):
        plugin.dynamic_settings_section_path = "config/runtime"
    plugin.dynamic_settings_section_path = None  # back to the document root


def test_section_path_locates_the_section_in_the_tree(configured_file):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    plugin.dynamic_settings_section_path = "/config/advexp"
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {
        "config": {"advexp": {"runtime": dyn_section(DynSettings, {"checkbox": True})}}
    }

    # load, single ops and cleanup all follow the path
    plugin._DynamicSettingsBasePlugin__values.clear()
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True
    plugin.set_setting("login", "alice")
    plugin.save_setting("login")
    entries = read_document(configured_file)["config"]["advexp"]["runtime"]
    for level in dyn_class_key(DynSettings).split(TOML_TABLE_SEPARATOR):
        entries = entries[level]
    assert entries == {
        "checkbox": True,
        "login": "alice",
    }

    # deleting the last entry drops the emptied tables along the whole path
    plugin.delete_setting("checkbox")
    plugin.delete_setting("login")
    assert read_document(configured_file) == {}

    # a sibling subtree under the same root stays untouched
    write_document(configured_file, {"config": {"logs": {"level": 2}}})
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file)["config"]["logs"] == {"level": 2}


def test_section_path_binding_is_inherited_independently(configured_file):
    class Base(Settings):
        pass

    class Derived(Base):
        pass

    # the parameters inherit separately: the path from the base, the name set here
    Base.get_plugin(TOMLDynamicSettingsPlugin).dynamic_settings_section_path = "/config"
    derived = Derived.get_plugin(TOMLDynamicSettingsPlugin)
    derived.dynamic_settings_section_name = "runtime"
    derived.set_setting("checkbox", True)
    derived.save_settings()
    assert read_document(configured_file) == {
        "config": {"runtime": dyn_section(Derived, {"checkbox": True})}
    }

    # the flat layout (name None) ignores the path
    derived.dynamic_settings_section_name = None
    derived.save_settings()
    assert read_document(configured_file)[dyn_full_name(Derived, "checkbox")] is True


def test_section_name_binding_is_inherited_along_the_mro(configured_file):
    class Base(Settings):
        pass

    class Derived(Base):
        pass

    Base.get_plugin(TOMLDynamicSettingsPlugin).dynamic_settings_section_name = "runtime"
    derived = Derived.get_plugin(TOMLDynamicSettingsPlugin)
    # like file_path, the property shows the class's own binding: the base's
    # binding applies at storage time, through the MRO walk
    assert derived.dynamic_settings_section_name == TOMLDynamicSettingsPlugin.DEFAULT_SECTION
    derived.set_setting("checkbox", True)
    derived.save_settings()
    assert read_document(configured_file) == {"runtime": dyn_section(Derived, {"checkbox": True})}

    # the most derived explicit binding wins over the inherited one
    derived.dynamic_settings_section_name = None
    derived.save_settings()
    assert read_document(configured_file)[dyn_full_name(Derived, "checkbox")] is True


def test_static_key_of_the_section_name_is_rejected(configured_file):
    class GuardedSettings(Settings):
        plain: str = toml_setting(name=SECTION, default="x")  # would shadow the section
        nested: str = toml_setting(name="host", path=f"/{SECTION}", default="y")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_static_index_path_under_the_section_key_is_rejected(configured_file):
    class GuardedSettings(Settings):
        # would replace the section table with an array
        element: str = toml_setting(name="x", path=f"/{SECTION}/0", default="!")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_static_location_overlapping_a_pathed_section_is_rejected(configured_file):
    class GuardedSettings(Settings):
        inside: str = toml_setting(name="x", path="/config/advexp/runtime", default="!")
        at_node: str = toml_setting(name="advexp", path="/config", default="~")
        at_leaf: str = toml_setting(name="runtime", path="/config/advexp", default="=")
        root: str = toml_setting(name="config", default="*")
        sibling: str = toml_setting(name="y", path="/config/logs", default="ok")  # legal

    plugin = GuardedSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    plugin.dynamic_settings_section_path = "/config/advexp"

    # bulk pass errors surface as the inner exception, in member order
    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()
    GuardedSettings.save_setting("sibling")
    assert read_document(configured_file)["config"]["logs"] == {"y": "ok"}


def test_deleting_the_last_entry_drops_class_object_and_section(configured_file):
    write_document(
        configured_file,
        deep_merge(
            dyn_document(DynSettings, {"checkbox": True}),
            dyn_document(OtherSettings, {"switch": False}),
        ),
    )
    DynSettings.get_plugin(TOMLDynamicSettingsPlugin).delete_setting("checkbox")
    # this class's object left the section; the other class's entries stay
    assert read_document(configured_file) == dyn_document(OtherSettings, {"switch": False})

    OtherSettings.get_plugin(TOMLDynamicSettingsPlugin).delete_setting("switch")
    assert read_document(configured_file) == {}  # the emptied section is gone


# -- an own file for the dynamic entries ---------------------------------------------


def test_own_dynamic_file_separates_entries_from_static(tmp_path, configured_file, monkeypatch):
    runtime_file = tmp_path / "runtime.toml"
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", runtime_file)

    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    DynSettings.airplane_mode = True
    DynSettings.save_settings()

    assert read_document(runtime_file) == dyn_document(DynSettings, {"checkbox": True})
    assert read_document(configured_file) == nested(
        static_full_name(DynSettings, "airplane_mode"), True
    )


def test_load_reads_the_own_file_not_the_static_one(tmp_path, configured_file, monkeypatch):
    runtime_file = tmp_path / "runtime.toml"
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", runtime_file)
    write_document(runtime_file, dyn_document(DynSettings, {"checkbox": True}))
    # a section left in the static file (written before the own file was set)
    # is not this collection's storage anymore
    write_document(configured_file, dyn_document(DynSettings, {"checkbox": False}))

    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.load_settings()
    assert list(plugin) == ["checkbox"]
    assert plugin.get_setting("checkbox") is True


def test_per_class_static_binding_does_not_catch_the_dynamic_side(tmp_path, monkeypatch):
    runtime_file = tmp_path / "runtime.toml"
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", runtime_file)

    class WindowSettings(
        Settings,
        options=toml_source(file=tmp_path / "window.toml"),
    ):
        pass

    plugin = WindowSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(runtime_file) == dyn_document(WindowSettings, {"checkbox": True})
    # the dynamic pass never pulled the class's static file into existence
    assert not (tmp_path / "window.toml").exists()


def test_switching_to_the_own_file_keeps_old_entries_where_they_were(
    tmp_path, configured_file, monkeypatch
):
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    runtime_file = tmp_path / "runtime.toml"
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", runtime_file)
    plugin.save_settings()  # no migration: the entries were written where they live

    assert read_document(configured_file) == dyn_document(DynSettings, {"checkbox": True})
    assert read_document(runtime_file) == dyn_document(DynSettings, {"checkbox": True})


def test_static_keys_may_use_the_section_location_in_own_file_mode(
    tmp_path, configured_file, monkeypatch
):
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", tmp_path / "runtime.toml")

    class GuardedSettings(Settings):
        plain: str = toml_setting(name=SECTION, default="x")  # the section key, now free

    GuardedSettings.save_settings()
    assert read_document(configured_file)[SECTION] == "x"


def test_section_reservation_kept_when_the_own_file_names_the_static_file(
    configured_file, monkeypatch
):
    # one file named by both sides: one document, the section stays reserved
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", configured_file)

    class GuardedSettings(Settings):
        plain: str = toml_setting(name=SECTION, default="x")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_dynamic_passes_run_with_only_the_own_file_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)
    runtime_file = tmp_path / "runtime.toml"
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", runtime_file)

    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_no_file_configured_names_both_configurations(monkeypatch):
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="TOMLDynamicSettingsConfiguration.file_path"):
        plugin.save_settings()


# -- the per-class own-file binding ----------------------------------------------------


def test_per_class_binding_wins_over_the_module_default(tmp_path, monkeypatch):
    module_file = tmp_path / "module-dynamic.toml"
    class_file = tmp_path / "class-dynamic.toml"
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", module_file)

    class BoundSettings(
        Settings,
        options=toml_source(dynamic_file=class_file),
    ):
        pass

    bound = BoundSettings.get_plugin(TOMLDynamicSettingsPlugin)
    bound.set_setting("checkbox", True)
    bound.save_settings()

    # a class without the binding keeps the module default
    other = OtherSettings.get_plugin(TOMLDynamicSettingsPlugin)
    other.set_setting("switch", False)
    other.save_settings()

    assert read_document(class_file) == dyn_document(BoundSettings, {"checkbox": True})
    assert read_document(module_file) == dyn_document(OtherSettings, {"switch": False})


def test_file_path_binding_follows_the_class_mro(tmp_path, configured_file):
    own_file = tmp_path / "own-dynamic.toml"

    class BaseSettings(
        Settings,
        options=toml_source(dynamic_file=own_file),
    ):
        pass

    class DerivedSettings(BaseSettings):
        pass

    derived = DerivedSettings.get_plugin(TOMLDynamicSettingsPlugin)
    # like the static file_path, the property reads the chain: the base's
    # binding governs the derived class
    assert derived.file_path == own_file
    derived.set_setting("checkbox", True)
    derived.save_settings()
    assert read_document(own_file) == dyn_document(DerivedSettings, {"checkbox": True})

    # the most derived explicit binding wins over the inherited one; the
    # property setter re-binds the class itself
    nearer_file = tmp_path / "nearer-dynamic.toml"
    derived.file_path = nearer_file
    derived.save_settings()
    assert read_document(nearer_file) == dyn_document(DerivedSettings, {"checkbox": True})
    # no migration: the inherited file keeps what it already holds
    assert read_document(own_file) == dyn_document(DerivedSettings, {"checkbox": True})
    # and the base class keeps its own binding
    assert BaseSettings.get_plugin(TOMLDynamicSettingsPlugin).file_path == own_file


def test_per_class_binding_lifts_the_section_reservation(tmp_path, configured_file):
    class GuardedSettings(
        Settings,
        options=toml_source(dynamic_file=tmp_path / "own-dynamic.toml"),
    ):
        plain: str = toml_setting(name=SECTION, default="x")  # the section key, now free

    GuardedSettings.save_settings()
    assert read_document(configured_file)[SECTION] == "x"


def test_per_class_binding_naming_the_static_file_keeps_the_reservation(configured_file):
    # one file named by both sides: one document, the section stays reserved
    class GuardedSettings(
        Settings,
        options=toml_source(dynamic_file=configured_file),
    ):
        plain: str = toml_setting(name=SECTION, default="x")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_dynamic_passes_run_on_the_per_class_binding_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)
    own_file = tmp_path / "own-dynamic.toml"

    class OwnFileSettings(
        Settings,
        options=toml_source(dynamic_file=own_file),
    ):
        airplane_mode: bool = toml_setting(default=False)

    plugin = OwnFileSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_invalid_dynamic_binding_fails_class_statement():
    with pytest.raises(TypeError, match=f"{TOML_DYNAMIC_FILE_METADATA}.*must be a file path"):

        class BrokenSettings(
            Settings,
            options={TOML_DYNAMIC_FILE_METADATA: None},
        ):
            airplane_mode: bool = toml_setting(default=False)


def test_invalid_dynamic_path_fails_at_helper_call():
    with pytest.raises(TypeError, match="invalid TOML dynamic file"):
        toml_source(dynamic_file="")


# -- serializer enumeration -------------------------------------------------------------------


def test_flat_enumeration_lists_the_bound_class_entries(configured_file):
    # the flat layout keeps full names as the top-level keys; the
    # enumeration picks the bound class's names out of the document
    DynSettings.get_plugin(TOMLDynamicSettingsPlugin).dynamic_settings_section_name = None
    write_document(
        configured_file,
        {
            dyn_full_name(DynSettings, "zzz"): 1,
            dyn_full_name(DynSettings, "aaa"): 2,
            dyn_full_name(OtherSettings, "switch"): False,
            "plain-key": 3,
            # a value inside the document, not a top-level name
            "net": {"proxy": {dyn_full_name(DynSettings, "nested"): 4}},
        },
    )
    serializer = TOMLSettingsSerializer()
    serializer.set_serializer_params(DynSettings.__settings_context__)
    assert list(serializer.get_dynamic_settings_names()) == sorted(
        [dyn_full_name(DynSettings, "aaa"), dyn_full_name(DynSettings, "zzz")]
    )
    # a serializer outside a pass has no class to enumerate for: a loud
    # error, not a silent empty answer
    with pytest.raises(RuntimeError, match="not bound to a pass"):
        TOMLSettingsSerializer().get_dynamic_settings_names()


def test_section_enumeration_lists_the_bound_class_entries(configured_file):
    write_document(
        configured_file,
        deep_merge(
            dyn_document(DynSettings, {"checkbox": True, "window.x": 120}),
            dyn_document(OtherSettings, {"switch": False}),
            {SECTION: {"someone-elses-class": {"theirs": 1}}},
        ),
    )
    serializer = TOMLSettingsSerializer()
    serializer.set_serializer_params(DynSettings.__settings_context__)
    assert list(serializer.get_dynamic_settings_names()) == sorted(
        [dyn_full_name(DynSettings, "checkbox"), dyn_full_name(DynSettings, "window.x")]
    )
    # the other classes' entries are their own passes' business: their
    # serializers, bound to their classes, enumerate them the same way
    other = TOMLSettingsSerializer()
    other.set_serializer_params(OtherSettings.__settings_context__)
    assert list(other.get_dynamic_settings_names()) == [dyn_full_name(OtherSettings, "switch")]


def test_class_prefix_covers_namespace_and_class():
    prefix = get_dynamic_settings_class_prefix(DynSettings)
    assert dyn_full_name(DynSettings, "checkbox").startswith("D." + prefix)
    assert prefix == f"{DynSettings.__module__}.DynSettings."


def test_dynamic_setting_name_strips_the_class_part():
    # the context supplies its own settings class; the serializer argument
    # (optional) carries its delimiter wish
    context = DynSettings.get_plugin(TOMLDynamicSettingsPlugin).context
    full = dyn_full_name(DynSettings, "window.x")
    assert context.get_dynamic_setting_name(full) == "window.x"
    assert context.get_dynamic_setting_name(full, TOMLSettingsSerializer()) == "window.x"
    # another class's dynamic entry, a static name, foreign data: not ours
    other = context.get_dynamic_setting_name(dyn_full_name(OtherSettings, "window.x"))
    assert other is None
    static_name = static_full_name(DynSettings, "airplane_mode")
    assert context.get_dynamic_setting_name(static_name) is None
    assert context.get_dynamic_setting_name("someone-elses-key") is None


def test_dynamic_setting_full_name_builds_the_split_counterpart():
    # the context's build and split are inverses; the serializer argument
    # carries its delimiter wish, as in the split
    context = DynSettings.get_plugin(TOMLDynamicSettingsPlugin).context
    full = context.get_dynamic_setting_full_name("window.x")
    assert full == dyn_full_name(DynSettings, "window.x")
    assert context.get_dynamic_setting_full_name("window.x", TOMLSettingsSerializer()) == full
    assert context.get_dynamic_setting_name(full) == "window.x"


# -- name patterns ---------------------------------------------------------------------------


def test_pattern_without_field_name_slot_is_rejected(monkeypatch):
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}")
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="FieldName"):
        plugin.load_settings()


def test_custom_pattern_locates_dynamic_names(monkeypatch, configured_file):
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    write_document(configured_file, {"dynamic": {"DynSettings": {"checkbox": True}}})
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_pattern_without_class_part_rejects_the_section(monkeypatch, configured_file):
    # no class part in the pattern: the section layout cannot group (and
    # parse back) the entries, so it refuses to run — the flat layout can
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, NAME_PATTERN, "{FieldName}")
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    with pytest.raises(ValueError, match="no class part"):
        plugin.save_settings()

    plugin.dynamic_settings_section_name = None
    plugin.save_settings()
    assert read_document(configured_file) == {"D.checkbox": True}


def test_custom_pattern_round_trips_the_section_layout(monkeypatch, configured_file):
    # both visible names follow the parameter: the class object's key in the
    # section and the full names the collection enumerates, in a save and
    # the load that reads the file back
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("window.x", 120)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {
        SECTION: {"DynSettings": {"window.x": 120, "checkbox": True}}
    }
    plugin._DynamicSettingsBasePlugin__values.clear()
    plugin.load_settings()
    assert plugin.to_dict() == {"checkbox": True, "window.x": 120}


def test_custom_pattern_shapes_the_flat_layout(monkeypatch, configured_file):
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = None
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {"D.DynSettings.checkbox": True}
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_dynamic_parameter_leaves_static_keys_alone(monkeypatch, configured_file):
    # the parameter shapes the dynamic names alone: the static members keep the
    # full pattern (their own form is the static family options' business)
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    DynSettings.airplane_mode = True
    DynSettings.save_settings()
    plugin = DynSettings.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    module = DynSettings.__module__
    assert read_document(configured_file) == deep_merge(
        nested(f"{module}.DynSettings.airplane_mode", True),
        {SECTION: {"DynSettings": {"checkbox": True}}},
    )


# -- the pin's base fallback stays as the JSON side defines it ------------------------


def test_base_plugin_still_requires_the_binding():
    # the pin contract is the shared base plugin's: a binding-less dynamic
    # plugin class fails its own class statement (covered per-family once)
    with pytest.raises(TypeError, match="must declare 'binding'"):

        class NoPin(DynamicSettingsBasePlugin):
            @property
            def plugin_name(self) -> str:
                return "no-pin"


def test_module_is_self_sufficient(tmp_path):
    """The module carries the static side beside its own dynamic names."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import os

        import advexp.settings.plugins.toml_dynamic_settings as tds
        from advexp.settings import Settings

        os.chdir(r"{workdir}")


        class SelfSufficientSettings(
            Settings, options=tds.toml_source(file="self-sufficient.toml")
        ):
            # a static member of the file backend this module re-exports
            locale: str = tds.toml_setting(default="en-US")


        SelfSufficientSettings.load_settings()
        assert SelfSufficientSettings.locale == "en-US"

        plugin = SelfSufficientSettings.get_plugin(tds.TOMLDynamicSettingsPlugin)
        plugin.load_settings()
        assert plugin.get_setting("dark_mode", default=False) is False
        plugin.set_setting("dark_mode", True)
        plugin.save_settings()
        assert plugin.get_setting("dark_mode") is True
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
