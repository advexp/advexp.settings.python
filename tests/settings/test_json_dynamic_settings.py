"""JSONDynamicSettings plugin tests (runtime-named settings in the JSON file)."""

from __future__ import annotations

import dataclasses
import enum
import json
import logging
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Type

import pytest

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import (
    NO_DEFAULT,
    NOT_FOUND,
    AttributeSerializerBinding,
    DynamicSettingAttribute,
    DynamicSettingsBasePlugin,
    SettingsAttribute,
    SettingsBaseSerializer,
)
from advexp.settings.plugins.json_dynamic_settings import (
    JSON_DYNAMIC_FILE_METADATA,
    JSONDynamicSettingsConfiguration,
    JSONDynamicSettingsPlugin,
)
from advexp.settings.plugins.json_settings import (
    NAME_PATTERN,
    JSONSetting,
    JSONSettingsConfiguration,
    JSONSettingsSerializer,
    json_setting,
    json_source,
)
from advexp.settings_base.document_dynamic_settings_plugin import _UNSET_SECTION

# noinspection PyProtectedMember
from advexp.settings_base.names import (
    DEFAULT_SETTINGS_NAME_PATTERN,
    SettingNameMode,
    get_dynamic_settings_class_prefix,
    get_full_setting_name,
)


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


@dataclasses.dataclass
class Point:
    x: int
    y: int = 0


class DynSettings(Settings):
    """Mixed class: one declared member plus the dynamic collection."""

    airplane_mode: bool = json_setting(default=False)


class OtherSettings(Settings):
    """A second class sharing the file: dynamic entries are kept apart."""


SECTION = JSONDynamicSettingsPlugin.DEFAULT_SECTION


def dyn_full_name(settings_class: type, name: str) -> str:
    return get_full_setting_name(name, None, settings_class, mode=SettingNameMode.DYNAMIC)


def dyn_class_key(settings_class: type) -> str:
    prefix = get_dynamic_settings_class_prefix(settings_class)
    return prefix[:-1] if prefix else ""


def dyn_document(settings_class: type, entries: Dict[str, Any]) -> Dict[str, Any]:
    """The document part holding one class's dynamic entries."""
    class_key = dyn_class_key(settings_class)
    section = {class_key: entries} if class_key else entries
    return {SECTION: section}


def static_full_name(settings_class: Type[Settings], member: str) -> str:
    attr = settings_class.__settings_members__[member].attribute
    return get_full_setting_name(member, attr, settings_class)


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", path)
    # the dynamic side's own file and name pattern are off unless a test
    # opts in
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(
        JSONDynamicSettingsConfiguration, NAME_PATTERN, DEFAULT_SETTINGS_NAME_PATTERN
    )
    yield path


@pytest.fixture(autouse=True)
def clean_collections():
    # plugin instances and class metadata live as long as the settings class;
    # start each test with an empty dynamic collection, no declared order and
    # the default section binding
    for klass in (DynSettings, OtherSettings):
        plugin = klass.get_plugin(JSONDynamicSettingsPlugin)
        # noinspection PyProtectedMember
        plugin._DynamicSettingsBasePlugin__values.clear()
        # noinspection PyProtectedMember
        plugin._DynamicSettingsBasePlugin__metadata.clear()
        # noinspection PyProtectedMember
        plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_name = _UNSET_SECTION
        # noinspection PyProtectedMember
        plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_path = _UNSET_SECTION
        # no own-file binding: the module default (or the static file) governs
        klass.delete_class_metadata(JSON_DYNAMIC_FILE_METADATA)
        klass.delete_class_metadata(JSONDynamicSettingsPlugin.ITERATION_ORDER_METADATA)
    yield


def read_document(configured_file) -> Dict[str, Any]:
    return json.loads(configured_file.read_text(encoding="utf-8"))


def write_document(configured_file, document: Dict[str, Any]) -> None:
    configured_file.write_text(json.dumps(document), encoding="utf-8")


# -- registration -----------------------------------------------------------------


def test_import_enables_plugin_and_registers_pin_pair():
    assert JSONDynamicSettingsPlugin in LibraryConfiguration.registered_plugin_classes()
    # the pin's own slot, registered by the base setup from the declared
    # binding: the dynamic side lives apart from the static
    # plugin's JSONSetting binding, so the two registrations cannot clash
    pin = JSONDynamicSettingsPlugin.binding.attribute_class
    assert pin is DynamicSettingAttribute[JSONSetting]
    assert LibraryConfiguration._get_serializer_factory(pin) is JSONSettingsSerializer


def test_plugin_instance_is_cached_per_class():
    assert DynSettings.get_plugin(JSONDynamicSettingsPlugin) is DynSettings.get_plugin(
        JSONDynamicSettingsPlugin
    )
    assert DynSettings.get_plugin(JSONDynamicSettingsPlugin) is not OtherSettings.get_plugin(
        JSONDynamicSettingsPlugin
    )


def test_base_plugin_requires_the_binding():
    with pytest.raises(TypeError, match="must declare 'binding'"):
        # (the class statement itself is the failing act: defining it raises)
        # noinspection PyUnusedLocal
        class NoPin(DynamicSettingsBasePlugin):
            @property
            def plugin_name(self) -> str:
                return "no-pin"

    with pytest.raises(TypeError, match="ISettingAttribute implementation"):
        # (same here: the definition fails the binding validation)
        # noinspection PyUnusedLocal
        class WrongPin(DynamicSettingsBasePlugin):
            # (int is not a setting attribute class: that is the case tested)
            # noinspection PyTypeChecker
            binding = AttributeSerializerBinding(int, JSONSettingsSerializer)

            @property
            def plugin_name(self) -> str:
                return "wrong-pin"


def test_base_plugin_subclass_inherits_the_binding():
    class Child(JSONDynamicSettingsPlugin):
        pass

    assert Child.binding.attribute_class is DynamicSettingAttribute[JSONSetting]


# -- save / load round trip ----------------------------------------------------------


def test_save_writes_dynamic_section_beside_static(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.set_setting("login", "alice")
    plugin.save_settings()

    # the same name as a declared member: static and dynamic entries coexist
    DynSettings.airplane_mode = True
    DynSettings.save_settings()

    document = read_document(configured_file)
    assert document == {
        SECTION: {
            dyn_class_key(DynSettings): {"checkbox": True, "login": "alice"},
        },
        static_full_name(DynSettings, "airplane_mode"): True,
    }
    assert not [key for key in document if key.startswith("D.")]


def test_save_pass_starts_a_blank_file_as_an_empty_document(configured_file):
    # the dynamic side's save enumerates the section before writing: a
    # blank file is started over, not treated as a parse error
    configured_file.write_text("", encoding="utf-8")
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = read_document(configured_file)
    assert document == {
        SECTION: {
            dyn_class_key(DynSettings): {"checkbox": True},
        },
    }


def test_load_rebuilds_collection_from_storage(configured_file):
    write_document(
        configured_file,
        {
            **dyn_document(DynSettings, {"checkbox": True, "login": "alice", "edittext": 42}),
            "someone-elses-key": "kept",
        },
    )
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
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
        {
            SECTION: {
                dyn_class_key(DynSettings): {"checkbox": True},
                dyn_class_key(OtherSettings): {"checkbox": False, "switch": False},
            }
        },
    )
    mine = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    mine.load_settings()
    assert list(mine) == ["checkbox"]
    assert mine.get_setting("checkbox") is True

    other = OtherSettings.get_plugin(JSONDynamicSettingsPlugin)
    other.load_settings()
    assert list(other) == ["checkbox", "switch"]
    assert other.get_setting("checkbox") is False


def test_values_round_trip_through_the_file(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
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

    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    assert len(plugin) == 0


# -- get_setting / set_setting -------------------------------------------------------


def test_get_setting_without_default_returns_storage_form():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("raw", "2026-09-13T10:00:00")
    # no target type: the value comes back as stored, unconverted
    value = plugin.get_setting("raw")
    assert value == "2026-09-13T10:00:00"
    assert isinstance(value, str)


def test_get_setting_converts_string_forms_like_load(configured_file):
    write_document(
        configured_file,
        dyn_document(
            DynSettings,
            {
                "airplane": "yes",
                "stamp": "2026-09-13T10:00:00",
                "color": "BLUE",
                "point": {"x": 3, "y": 4},
            },
        ),
    )
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_settings()
    assert plugin.get_setting("airplane", default=False) is True
    assert plugin.get_setting("stamp", default=datetime(2026, 1, 1)) == datetime(
        2026, 9, 13, 10, 0, 0
    )
    assert plugin.get_setting("color", default=Color.RED) is Color.BLUE
    assert plugin.get_setting("point", default=Point(0, 0)) == Point(3, 4)


def test_get_setting_missing_name_raises_without_default():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(KeyError, match="no-such"):
        plugin.get_setting("no-such")


def test_get_setting_default_is_isolated_per_call():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    returned = plugin.get_setting("missing", default=[1, 2])
    returned.append(3)
    assert plugin.get_setting("missing", default=[1, 2]) == [1, 2]


def test_set_and_get_keep_assignment_reference_semantics():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    tags = ["a"]
    plugin.set_setting("tags", tags)
    assert plugin.get_setting("tags") is tags  # plain assignment, no copies


def test_unconvertible_value_falls_back_to_default_with_warning(configured_file, caplog):
    write_document(configured_file, dyn_document(DynSettings, {"stamp": "not-a-timestamp"}))
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_settings()
    fallback = datetime(2020, 1, 1)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        assert plugin.get_setting("stamp", default=fallback) == fallback
    assert any("dynamic setting 'stamp'" in record.message for record in caplog.records)


# -- single-setting operations ---------------------------------------------------------


def test_save_setting_writes_and_flushes_one_value(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_setting("checkbox")
    assert read_document(configured_file) == dyn_document(DynSettings, {"checkbox": True})


def test_save_setting_unknown_name_raises():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(KeyError, match="no value to save"):
        plugin.save_setting("never-set")


def test_load_setting_refreshes_one_value(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")
    write_document(configured_file, dyn_document(DynSettings, {"login": "bob"}))
    plugin.load_setting("login")
    assert plugin.get_setting("login") == "bob"


def test_load_setting_drops_name_missing_from_storage(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")
    plugin.load_setting("login")  # the (fresh) file holds no such entry
    assert "login" not in plugin
    plugin.load_setting("never-known")  # a no-op, not an error


def test_delete_setting_removes_from_storage_and_collection(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.delete_setting("checkbox")

    assert "checkbox" not in plugin
    assert read_document(configured_file) == {}  # the emptied section is dropped too
    plugin.delete_setting("checkbox")  # deleting again is not an error


def test_saving_none_stores_json_null(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.set_setting("checkbox", None)
    plugin.save_settings()

    document = read_document(configured_file)
    assert document[SECTION][dyn_class_key(DynSettings)]["checkbox"] is None
    plugin.load_settings()
    assert "checkbox" in plugin  # null, not missing
    assert plugin.get_setting("checkbox") is None

    # removal is the job of delete; the emptied section goes with it
    plugin.delete_setting("checkbox")
    assert read_document(configured_file) == {}


# -- save_settings cleanup ----------------------------------------------------------


def test_save_settings_drops_orphaned_entries_of_this_class(configured_file):
    write_document(
        configured_file,
        {
            SECTION: {
                dyn_class_key(DynSettings): {"orphan": "gone"},
                dyn_class_key(OtherSettings): {"kept": "theirs"},
            },
            "someone-elses-key": 42,
        },
    )
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = read_document(configured_file)
    assert document == {
        SECTION: {
            dyn_class_key(DynSettings): {"checkbox": True},
            dyn_class_key(OtherSettings): {"kept": "theirs"},
        },
        "someone-elses-key": 42,
    }


def test_delete_settings_clears_storage_and_collection(configured_file):
    write_document(
        configured_file,
        {
            SECTION: {
                dyn_class_key(DynSettings): {"checkbox": True},
                dyn_class_key(OtherSettings): {"kept": "theirs"},
            }
        },
    )
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")  # never saved: deleted from storage anyway
    plugin.delete_settings()

    assert len(plugin) == 0
    assert read_document(configured_file) == dyn_document(OtherSettings, {"kept": "theirs"})


def test_bulk_save_logs_and_skips_unconvertible_values(configured_file, caplog):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("good", 1)
    plugin.set_setting("bad", object())  # no JSON form

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        plugin.save_settings()

    assert read_document(configured_file) == dyn_document(DynSettings, {"good": 1})
    assert any("dynamic setting 'bad'" in record.message for record in caplog.records)


def test_single_save_propagates_unconvertible_value():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("bad", object())
    with pytest.raises(TypeError):
        plugin.save_setting("bad")


# -- user-facing storage errors --------------------------------------------------------


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("{not json", encoding="utf-8")
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="cannot parse the JSON settings file"):
        plugin.load_settings()


def test_unset_file_path_raises_to_caller(monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="file_path"):
        plugin.save_settings()


def test_section_holding_a_scalar_raises_to_caller(configured_file):
    write_document(configured_file, {SECTION: 42})
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="must hold an object"):
        plugin.load_settings()


# -- the document section ----------------------------------------------------------------


def test_section_can_be_renamed_and_disabled(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    assert plugin.dynamic_settings_section_name == "runtime"
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {
        "runtime": {dyn_class_key(DynSettings): {"checkbox": True}}
    }

    # None switches to the flat layout: D-prefixed full-name keys at the root
    plugin.dynamic_settings_section_name = None
    plugin.save_settings()
    assert read_document(configured_file)[dyn_full_name(DynSettings, "checkbox")] is True


def test_section_rejects_empty_and_non_string_names():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="non-empty string"):
        plugin.dynamic_settings_section_name = ""
    with pytest.raises(ValueError, match="non-empty string"):
        plugin.dynamic_settings_section_name = 42
    # the path follows the path= rules of JSONSetting: a JSON Pointer
    with pytest.raises(ValueError, match="must start with '/'"):
        plugin.dynamic_settings_section_path = "config/runtime"
    plugin.dynamic_settings_section_path = None  # back to the document root


def test_section_path_locates_the_section_in_the_tree(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    plugin.dynamic_settings_section_path = "/config/advexp"
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {
        "config": {"advexp": {"runtime": {dyn_class_key(DynSettings): {"checkbox": True}}}}
    }

    # load, single ops and cleanup all follow the path
    plugin._DynamicSettingsBasePlugin__values.clear()
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True
    plugin.set_setting("login", "alice")
    plugin.save_setting("login")
    assert read_document(configured_file)["config"]["advexp"]["runtime"][
        dyn_class_key(DynSettings)
    ] == {
        "checkbox": True,
        "login": "alice",
    }

    # deleting the last entry drops the emptied objects along the whole path
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
    Base.get_plugin(JSONDynamicSettingsPlugin).dynamic_settings_section_path = "/config"
    derived = Derived.get_plugin(JSONDynamicSettingsPlugin)
    derived.dynamic_settings_section_name = "runtime"
    derived.set_setting("checkbox", True)
    derived.save_settings()
    assert read_document(configured_file) == {
        "config": {"runtime": {dyn_class_key(Derived): {"checkbox": True}}}
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

    Base.get_plugin(JSONDynamicSettingsPlugin).dynamic_settings_section_name = "runtime"
    derived = Derived.get_plugin(JSONDynamicSettingsPlugin)
    # like file_path, the property shows the class's own binding: the base's
    # binding applies at storage time, through the MRO walk
    assert derived.dynamic_settings_section_name == JSONDynamicSettingsPlugin.DEFAULT_SECTION
    derived.set_setting("checkbox", True)
    derived.save_settings()
    assert read_document(configured_file) == {
        "runtime": {dyn_class_key(Derived): {"checkbox": True}}
    }

    # the most derived explicit binding wins over the inherited one
    derived.dynamic_settings_section_name = None
    derived.save_settings()
    assert read_document(configured_file)[dyn_full_name(Derived, "checkbox")] is True


def test_static_key_of_the_section_name_is_rejected(configured_file):
    class GuardedSettings(Settings):
        plain: str = json_setting(name=SECTION, default="x")  # would shadow the section
        nested: str = json_setting(name="host", path=f"/{SECTION}", default="y")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_static_index_path_under_the_section_key_is_rejected(configured_file):
    class GuardedSettings(Settings):
        # would replace the section object with an array
        element: str = json_setting(name="x", path=f"/{SECTION}/0", default="!")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_static_location_overlapping_a_pathed_section_is_rejected(configured_file):
    class GuardedSettings(Settings):
        inside: str = json_setting(name="x", path="/config/advexp/runtime", default="!")
        at_node: str = json_setting(name="advexp", path="/config", default="~")
        at_leaf: str = json_setting(name="runtime", path="/config/advexp", default="=")
        root: str = json_setting(name="config", default="*")
        sibling: str = json_setting(name="y", path="/config/logs", default="ok")  # legal

    plugin = GuardedSettings.get_plugin(JSONDynamicSettingsPlugin)
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
        {
            **dyn_document(DynSettings, {"checkbox": True}),
            **dyn_document(OtherSettings, {"switch": False}),
        },
    )
    DynSettings.get_plugin(JSONDynamicSettingsPlugin).delete_setting("checkbox")
    # this class's object left the section; the other class's entries stay
    assert read_document(configured_file) == dyn_document(OtherSettings, {"switch": False})

    OtherSettings.get_plugin(JSONDynamicSettingsPlugin).delete_setting("switch")
    assert read_document(configured_file) == {}  # the emptied section is gone


# -- an own file for the dynamic entries ---------------------------------------------


def test_own_dynamic_file_separates_entries_from_static(tmp_path, configured_file, monkeypatch):
    runtime_file = tmp_path / "runtime.json"
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", runtime_file)

    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    DynSettings.airplane_mode = True
    DynSettings.save_settings()

    assert read_document(runtime_file) == dyn_document(DynSettings, {"checkbox": True})
    assert read_document(configured_file) == {static_full_name(DynSettings, "airplane_mode"): True}


def test_load_reads_the_own_file_not_the_static_one(tmp_path, configured_file, monkeypatch):
    runtime_file = tmp_path / "runtime.json"
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", runtime_file)
    write_document(runtime_file, dyn_document(DynSettings, {"checkbox": True}))
    # a section left in the static file (written before the own file was set)
    # is not this collection's storage anymore
    write_document(configured_file, dyn_document(DynSettings, {"checkbox": False}))

    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_settings()
    assert list(plugin) == ["checkbox"]
    assert plugin.get_setting("checkbox") is True


def test_per_class_static_binding_does_not_catch_the_dynamic_side(tmp_path, monkeypatch):
    runtime_file = tmp_path / "runtime.json"
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", runtime_file)

    class WindowSettings(
        Settings,
        options=json_source(file=tmp_path / "window.json"),
    ):
        pass

    plugin = WindowSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(runtime_file) == dyn_document(WindowSettings, {"checkbox": True})
    # the dynamic pass never pulled the class's static file into existence
    assert not (tmp_path / "window.json").exists()


def test_switching_to_the_own_file_keeps_old_entries_where_they_were(
    tmp_path, configured_file, monkeypatch
):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    runtime_file = tmp_path / "runtime.json"
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", runtime_file)
    plugin.save_settings()  # no migration: the entries were written where they live

    assert read_document(configured_file) == dyn_document(DynSettings, {"checkbox": True})
    assert read_document(runtime_file) == dyn_document(DynSettings, {"checkbox": True})


def test_static_keys_may_use_the_section_location_in_own_file_mode(
    tmp_path, configured_file, monkeypatch
):
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", tmp_path / "runtime.json")

    class GuardedSettings(Settings):
        plain: str = json_setting(name=SECTION, default="x")  # the section key, now free

    GuardedSettings.save_settings()
    assert read_document(configured_file)[SECTION] == "x"


def test_section_reservation_kept_when_the_own_file_names_the_static_file(
    configured_file, monkeypatch
):
    # one file named by both sides: one document, the section stays reserved
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", configured_file)

    class GuardedSettings(Settings):
        plain: str = json_setting(name=SECTION, default="x")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_dynamic_passes_run_with_only_the_own_file_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    runtime_file = tmp_path / "runtime.json"
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", runtime_file)

    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_no_file_configured_names_both_configurations(monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="JSONDynamicSettingsConfiguration.file_path"):
        plugin.save_settings()


# -- the per-class own-file binding ----------------------------------------------------


def test_per_class_binding_wins_over_the_module_default(tmp_path, monkeypatch):
    module_file = tmp_path / "module-dynamic.json"
    class_file = tmp_path / "class-dynamic.json"
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", module_file)

    class BoundSettings(
        Settings,
        options=json_source(dynamic_file=class_file),
    ):
        pass

    bound = BoundSettings.get_plugin(JSONDynamicSettingsPlugin)
    bound.set_setting("checkbox", True)
    bound.save_settings()

    # a class without the binding keeps the module default
    other = OtherSettings.get_plugin(JSONDynamicSettingsPlugin)
    other.set_setting("switch", False)
    other.save_settings()

    assert read_document(class_file) == dyn_document(BoundSettings, {"checkbox": True})
    assert read_document(module_file) == dyn_document(OtherSettings, {"switch": False})


def test_file_path_binding_follows_the_class_mro(tmp_path, configured_file):
    own_file = tmp_path / "own-dynamic.json"

    class BaseSettings(
        Settings,
        options=json_source(dynamic_file=own_file),
    ):
        pass

    class DerivedSettings(BaseSettings):
        pass

    derived = DerivedSettings.get_plugin(JSONDynamicSettingsPlugin)
    # like the static file_path, the property reads the chain: the base's
    # binding governs the derived class
    assert derived.file_path == own_file
    derived.set_setting("checkbox", True)
    derived.save_settings()
    assert read_document(own_file) == dyn_document(DerivedSettings, {"checkbox": True})

    # the most derived explicit binding wins over the inherited one; the
    # property setter re-binds the class itself
    nearer_file = tmp_path / "nearer-dynamic.json"
    derived.file_path = nearer_file
    derived.save_settings()
    assert read_document(nearer_file) == dyn_document(DerivedSettings, {"checkbox": True})
    # no migration: the inherited file keeps what it already holds
    assert read_document(own_file) == dyn_document(DerivedSettings, {"checkbox": True})
    # and the base class keeps its own binding
    assert BaseSettings.get_plugin(JSONDynamicSettingsPlugin).file_path == own_file


def test_per_class_binding_lifts_the_section_reservation(tmp_path, configured_file):
    class GuardedSettings(
        Settings,
        options=json_source(dynamic_file=tmp_path / "own-dynamic.json"),
    ):
        plain: str = json_setting(name=SECTION, default="x")  # the section key, now free

    GuardedSettings.save_settings()
    assert read_document(configured_file)[SECTION] == "x"


def test_per_class_binding_naming_the_static_file_keeps_the_reservation(configured_file):
    # one file named by both sides: one document, the section stays reserved
    class GuardedSettings(
        Settings,
        options=json_source(dynamic_file=configured_file),
    ):
        plain: str = json_setting(name=SECTION, default="x")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


def test_dynamic_passes_run_on_the_per_class_binding_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    own_file = tmp_path / "own-dynamic.json"

    class OwnFileSettings(
        Settings,
        options=json_source(dynamic_file=own_file),
    ):
        airplane_mode: bool = json_setting(default=False)

    plugin = OwnFileSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_invalid_dynamic_binding_fails_class_statement():
    with pytest.raises(TypeError, match=f"{JSON_DYNAMIC_FILE_METADATA}.*must be a file path"):

        class BrokenSettings(
            Settings,
            options={JSON_DYNAMIC_FILE_METADATA: None},
        ):
            airplane_mode: bool = json_setting(default=False)


def test_invalid_dynamic_path_fails_at_helper_call():
    with pytest.raises(TypeError, match="invalid JSON dynamic file"):
        json_source(dynamic_file="")


# -- iteration order ----------------------------------------------------------------------


def test_iteration_follows_declared_order_then_insertion():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.set_setting("switch", False)
    plugin.set_setting("edittext", "hi")

    DynSettings.set_class_metadata(
        JSONDynamicSettingsPlugin.ITERATION_ORDER_METADATA,
        ["edittext", "switch", "unknown-name", "checkbox"],
    )
    assert list(plugin) == ["edittext", "switch", "checkbox"]

    # without metadata: the order the names were added
    DynSettings.delete_class_metadata(JSONDynamicSettingsPlugin.ITERATION_ORDER_METADATA)
    assert list(plugin) == ["checkbox", "switch", "edittext"]


def test_duplicated_order_entries_are_listed_once():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("a", 1)
    plugin.set_setting("b", 2)
    DynSettings.set_class_metadata(
        JSONDynamicSettingsPlugin.ITERATION_ORDER_METADATA, ["b", "b", "a"]
    )
    assert list(plugin) == ["b", "a"]


# -- snapshots ------------------------------------------------------------------------------


def test_to_dict_snapshots_in_iteration_order_isolated():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.set_setting("tags", ["a"])

    snapshot = plugin.to_dict()
    assert list(snapshot) == ["checkbox", "tags"]
    snapshot["tags"].append("mutated")
    assert plugin.get_setting("tags") == ["a"]  # the class keeps its own copy


def test_update_from_dict_sets_values_and_adds_names():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)

    data = {"checkbox": False, "login": "alice"}  # 'login' is new, not rejected
    tags = ["shared"]
    plugin.update_from_dict({"tags": tags})
    tags.append("mutated")
    assert plugin.get_setting("tags") == ["shared"]  # the update deep-copied

    plugin.update_from_dict(data)
    assert plugin.get_setting("checkbox") is False
    assert plugin.get_setting("login") == "alice"


# -- setting metadata -----------------------------------------------------------------------


def test_setting_metadata_round_trip_and_default():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("window.x", 120)
    plugin.set_setting_metadata("window.x", "ui-label", "Horizontal position")
    assert plugin.get_setting_metadata("window.x", "ui-label") == "Horizontal position"
    assert plugin.get_setting_metadata("window.x", "missing", "fallback") == "fallback"


def test_get_setting_all_metadata_snapshots_the_bucket():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("dark_mode", True)
    plugin.set_setting_metadata("dark_mode", "ui", {"text": "Dark mode"})
    plugin.set_setting_metadata("dark_mode", "hint", 2)

    snapshot = plugin.get_setting_all_metadata("dark_mode")
    assert snapshot == {"ui": {"text": "Dark mode"}, "hint": 2}
    snapshot["ui"]["text"] = "mutated"  # the snapshot is a copy
    snapshot["extra"] = 3
    assert plugin.get_setting_all_metadata("dark_mode") == {
        "ui": {"text": "Dark mode"},
        "hint": 2,
    }

    plugin.delete_setting_all_metadata("dark_mode")
    assert plugin.get_setting_all_metadata("dark_mode") == {}  # nothing stored left
    with pytest.raises(KeyError):  # the collection-member check applies here too
        plugin.get_setting_all_metadata("nope")


def test_setting_metadata_rejects_name_the_collection_does_not_hold():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    # a name the collection does not hold could never be read back — it is
    # a typo, and every metadata operation says so instead of playing along
    with pytest.raises(KeyError, match="'nope' is not a dynamic setting of DynSettings"):
        plugin.set_setting_metadata("nope", "k", "v")
    with pytest.raises(KeyError):
        plugin.get_setting_metadata("nope", "k")
    with pytest.raises(KeyError):
        plugin.contains_setting_metadata("nope", "k")
    with pytest.raises(KeyError):
        plugin.delete_setting_metadata("nope", "k")
    with pytest.raises(KeyError):
        plugin.delete_setting_all_metadata("nope")
    # a name that once held a value but left the collection is the same miss
    plugin.delete_setting("checkbox")
    with pytest.raises(KeyError):
        plugin.set_setting_metadata("checkbox", "k", "v")


def test_setting_metadata_contains_tells_stored_none_from_missing():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("window.x", 120)
    assert not plugin.contains_setting_metadata("window.x", "ui-label")
    plugin.set_setting_metadata("window.x", "ui-label", None)  # None is a stored value
    assert plugin.get_setting_metadata("window.x", "ui-label", "gone") is None
    assert plugin.contains_setting_metadata("window.x", "ui-label")


def test_setting_metadata_is_deep_copied_both_ways():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("dark_mode", True)
    label = {"text": "Dark mode"}
    plugin.set_setting_metadata("dark_mode", "ui", label)
    label["text"] = "mutated"
    assert plugin.get_setting_metadata("dark_mode", "ui") == {"text": "Dark mode"}

    got = plugin.get_setting_metadata("dark_mode", "ui")
    got["text"] = "mutated"
    assert plugin.get_setting_metadata("dark_mode", "ui") == {"text": "Dark mode"}


def test_setting_metadata_delete_drops_last_entry_of_a_name():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("dark_mode", True)
    plugin.set_setting_metadata("dark_mode", "ui", 1)
    plugin.set_setting_metadata("dark_mode", "hint", 2)
    plugin.delete_setting_metadata("dark_mode", "ui")
    assert not plugin.contains_setting_metadata("dark_mode", "ui")
    assert plugin.contains_setting_metadata("dark_mode", "hint")
    plugin.delete_setting_metadata("dark_mode", "hint")  # the bucket went with it
    plugin.delete_setting_metadata("dark_mode", "hint")  # a missing entry is not an error
    assert not plugin.contains_setting_metadata("dark_mode", "hint")


def test_delete_setting_all_metadata_drops_the_whole_bucket():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("dark_mode", True)
    plugin.set_setting_metadata("dark_mode", "ui", 1)
    plugin.set_setting_metadata("dark_mode", "hint", 2)

    plugin.delete_setting_all_metadata("dark_mode")  # every entry of the name
    assert not plugin.contains_setting_metadata("dark_mode", "ui")
    assert not plugin.contains_setting_metadata("dark_mode", "hint")
    plugin.delete_setting_all_metadata("dark_mode")  # no metadata stored: not an error
    assert not plugin.contains_setting_metadata("dark_mode", "ui")

    # the setting itself stays: only the metadata went
    assert "dark_mode" in plugin


def test_delete_setting_takes_the_names_metadata_along(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")
    plugin.set_setting_metadata("login", "obfuscate", True)
    plugin.set_setting_metadata("login", "hint", "two entries go together")

    plugin.delete_setting("login")  # the setting went, its metadata with it
    assert "login" not in plugin
    # the name left the collection: no metadata operation reaches it anymore
    with pytest.raises(KeyError):
        plugin.set_setting_metadata("login", "obfuscate", True)
    plugin.set_setting("login", "bob")  # the name returns with a clean slate
    assert not plugin.contains_setting_metadata("login", "obfuscate")
    assert not plugin.contains_setting_metadata("login", "hint")


def test_delete_settings_clears_the_metadata_with_the_collection(configured_file):
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")
    plugin.set_setting("switch", False)
    plugin.set_setting_metadata("login", "ui-label", "Login")
    plugin.set_setting_metadata("switch", "ui-label", "Switch")

    plugin.delete_settings()
    assert len(plugin) == 0
    with pytest.raises(KeyError):
        plugin.get_setting_metadata("login", "ui-label")
    plugin.set_setting("login", "alice")  # the collection restarts with a clean slate
    plugin.set_setting("switch", False)
    assert not plugin.contains_setting_metadata("login", "ui-label")
    assert not plugin.contains_setting_metadata("switch", "ui-label")


def test_load_clears_the_whole_metadata_with_the_collection(configured_file):
    write_document(configured_file, dyn_document(DynSettings, {"login": "alice"}))
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("stale", 1)
    plugin.set_setting_metadata("stale", "ui-label", "Stale")

    plugin.load_settings()  # values arrive from the storage; it holds no metadata
    assert plugin.get_setting("login") == "alice"
    assert "stale" not in plugin
    with pytest.raises(KeyError):  # 'stale' left with the rebuild
        plugin.get_setting_metadata("stale", "ui-label")
    # 'login' arrived — into a metadata storage wiped clean by the load
    assert not plugin.contains_setting_metadata("login", "ui-label")


def test_load_setting_drops_the_names_metadata(configured_file):
    write_document(configured_file, dyn_document(DynSettings, {"login": "bob"}))
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("login", "alice")
    plugin.set_setting("offline", True)  # this one the storage does not hold
    plugin.set_setting_metadata("login", "ui-label", "Login")
    plugin.set_setting_metadata("offline", "ui-label", "Offline")

    plugin.load_setting("login")  # the value arrived; its metadata reset with the load
    assert plugin.get_setting("login") == "bob"
    assert not plugin.contains_setting_metadata("login", "ui-label")

    plugin.load_setting("offline")  # the storage holds no entry: the name left entirely
    assert "offline" not in plugin
    with pytest.raises(KeyError):
        plugin.set_setting_metadata("offline", "ui-label", "again")


def test_setting_metadata_lives_per_class():
    mine = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    other = OtherSettings.get_plugin(JSONDynamicSettingsPlugin)
    mine.set_setting("checkbox", True)
    other.set_setting("checkbox", False)
    mine.set_setting_metadata("checkbox", "ui-label", "Mine")
    # the same name in the other class's collection: its own storage
    assert other.get_setting_metadata("checkbox", "ui-label") is None


def test_dynamic_and_member_metadata_are_apart_even_on_one_name():
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    # 'airplane_mode' is a declared member; the dynamic name space is its own
    plugin.set_setting("airplane_mode", True)
    plugin.set_setting_metadata("airplane_mode", "owner", "dynamic")
    DynSettings.set_setting_metadata("airplane_mode", "owner", "static")

    assert plugin.get_setting_metadata("airplane_mode", "owner") == "dynamic"
    assert DynSettings.get_setting_metadata("airplane_mode", "owner") == "static"

    plugin.delete_setting_metadata("airplane_mode", "owner")
    assert DynSettings.get_setting_metadata("airplane_mode", "owner") == "static"


# -- serializer enumeration -------------------------------------------------------------------


def test_flat_enumeration_lists_the_bound_class_entries(configured_file):
    # the flat layout keeps full names as the top-level keys; the
    # enumeration picks the bound class's names out of the document
    DynSettings.get_plugin(JSONDynamicSettingsPlugin).dynamic_settings_section_name = None
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
    serializer = JSONSettingsSerializer()
    serializer.set_serializer_params(DynSettings.__settings_context__)
    assert list(serializer.get_dynamic_settings_names()) == sorted(
        [dyn_full_name(DynSettings, "aaa"), dyn_full_name(DynSettings, "zzz")]
    )
    # a serializer outside a pass has no class to enumerate for: a loud
    # error, not a silent empty answer
    with pytest.raises(RuntimeError, match="not bound to a pass"):
        JSONSettingsSerializer().get_dynamic_settings_names()


def test_section_enumeration_lists_the_bound_class_entries(configured_file):
    write_document(
        configured_file,
        {
            SECTION: {
                dyn_class_key(DynSettings): {"checkbox": True, "window.x": 120},
                dyn_class_key(OtherSettings): {"switch": False},
                "someone-elses-class": {"theirs": 1},
            }
        },
    )
    serializer = JSONSettingsSerializer()
    serializer.set_serializer_params(DynSettings.__settings_context__)
    assert list(serializer.get_dynamic_settings_names()) == sorted(
        [dyn_full_name(DynSettings, "checkbox"), dyn_full_name(DynSettings, "window.x")]
    )
    # the other classes' entries are their own passes' business: their
    # serializers, bound to their classes, enumerate them the same way
    other = JSONSettingsSerializer()
    other.set_serializer_params(OtherSettings.__settings_context__)
    assert list(other.get_dynamic_settings_names()) == [dyn_full_name(OtherSettings, "switch")]


def test_class_prefix_covers_namespace_and_class():
    prefix = get_dynamic_settings_class_prefix(DynSettings)
    assert dyn_full_name(DynSettings, "checkbox").startswith("D." + prefix)
    assert prefix == f"{DynSettings.__module__}.DynSettings."


def test_dynamic_setting_name_strips_the_class_part():
    # the context supplies its own settings class; the serializer argument
    # (optional) carries its delimiter wish
    context = DynSettings.get_plugin(JSONDynamicSettingsPlugin).context
    full = dyn_full_name(DynSettings, "window.x")
    assert context.get_dynamic_setting_name(full) == "window.x"
    assert context.get_dynamic_setting_name(full, JSONSettingsSerializer()) == "window.x"
    # another class's dynamic entry, a static name, foreign data: not ours
    other = context.get_dynamic_setting_name(dyn_full_name(OtherSettings, "window.x"))
    assert other is None
    static_name = static_full_name(DynSettings, "airplane_mode")
    assert context.get_dynamic_setting_name(static_name) is None
    assert context.get_dynamic_setting_name("someone-elses-key") is None


def test_dynamic_setting_full_name_builds_the_split_counterpart():
    # the context's build and split are inverses; the serializer argument
    # carries its delimiter wish, as in the split
    context = DynSettings.get_plugin(JSONDynamicSettingsPlugin).context
    full = context.get_dynamic_setting_full_name("window.x")
    assert full == dyn_full_name(DynSettings, "window.x")
    assert context.get_dynamic_setting_full_name("window.x", JSONSettingsSerializer()) == full
    assert context.get_dynamic_setting_name(full) == "window.x"


def test_pattern_without_field_name_slot_is_rejected(monkeypatch):
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}")
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="FieldName"):
        plugin.load_settings()


def test_custom_pattern_locates_dynamic_names(monkeypatch, configured_file):
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    write_document(configured_file, {"dynamic": {"DynSettings": {"checkbox": True}}})
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_pattern_without_class_part_rejects_the_section(monkeypatch, configured_file):
    # no class part in the pattern: the section layout cannot group (and
    # parse back) the entries, so it refuses to run — the flat layout can
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, NAME_PATTERN, "{FieldName}")
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
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
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
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
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = None
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {"D.DynSettings.checkbox": True}
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_dynamic_parameter_leaves_static_keys_alone(monkeypatch, configured_file):
    # the parameter shapes the dynamic names alone: the static members keep the
    # full pattern (their own form is the static family options' business)
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, NAME_PATTERN, "{ClassName}.{FieldName}")
    DynSettings.airplane_mode = True
    DynSettings.save_settings()
    plugin = DynSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    module = DynSettings.__module__
    assert read_document(configured_file) == {
        f"{module}.DynSettings.airplane_mode": True,
        SECTION: {"DynSettings": {"checkbox": True}},
    }


# -- a backend that cannot enumerate -------------------------------------------------------------


class BlindSetting(SettingsAttribute):
    """Attribute served by a storage that cannot enumerate its entries."""


def blind_setting(*, name: Optional[str] = None, default: Any = NO_DEFAULT) -> Any:
    return BlindSetting(name=name, default=default)


class BlindStorage:
    data: Dict[str, Any] = {}


class BlindSerializer(SettingsBaseSerializer):
    def load(self, setting_name: str, attr: Any) -> Any:
        return BlindStorage.data.get(setting_name, NOT_FOUND)

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        BlindStorage.data[setting_name] = value

    def delete(self, setting_name: str, attr: Any) -> None:
        BlindStorage.data.pop(setting_name, None)

    def contains(self, setting_name: str, attr: Any) -> bool:
        return setting_name in BlindStorage.data


class BlindDynamicPlugin(DynamicSettingsBasePlugin):
    binding = AttributeSerializerBinding(BlindSetting, BlindSerializer)

    @property
    def plugin_name(self) -> str:
        return "Blind"


LibraryConfiguration.register_settings_plugin(BlindDynamicPlugin)


class BlindSettings(Settings):
    flag: bool = blind_setting(default=False)


@pytest.fixture()
def blind_plugin():
    plugin = BlindSettings.get_plugin(BlindDynamicPlugin)
    # noinspection PyProtectedMember
    plugin._DynamicSettingsBasePlugin__values.clear()
    BlindStorage.data.clear()
    yield plugin
    BlindStorage.data.clear()


def test_blind_backend_rejects_enumerating_load(blind_plugin):
    with pytest.raises(TypeError, match="IDynamicSettingsInfo"):
        blind_plugin.load_settings()


def test_blind_backend_works_by_explicit_name(blind_plugin):
    blind_plugin.set_setting("checkbox", True)
    blind_plugin.save_setting("checkbox")
    blind_plugin.load_setting("checkbox")
    assert blind_plugin.get_setting("checkbox") is True

    blind_plugin.delete_setting("checkbox")
    assert "checkbox" not in BlindStorage.data


# -- a subclass may coin the machinery's plain names for its own use ---------------


class ShadowStorage:
    data: Dict[str, Any] = {}


class ShadowSerializer(SettingsBaseSerializer):
    def load(self, setting_name: str, attr: Any) -> Any:
        return ShadowStorage.data.get(setting_name, NOT_FOUND)

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        ShadowStorage.data[setting_name] = value

    def delete(self, setting_name: str, attr: Any) -> None:
        ShadowStorage.data.pop(setting_name, None)

    def contains(self, setting_name: str, attr: Any) -> bool:
        return setting_name in ShadowStorage.data


class ShadowSetting(SettingsAttribute):
    pass


class ShadowNamesPlugin(DynamicSettingsBasePlugin):
    """A plugin that uses plain names for its own bookkeeping.

    The base machinery spells its internals with name mangling (``__values``,
    ``__serializer``, and the inherited ``__context``). Members of the same
    name here therefore belong to this class alone and shadow nothing.
    """

    binding = AttributeSerializerBinding(ShadowSetting, ShadowSerializer)

    def __init__(self) -> None:
        super().__init__()
        self._values: List[Any] = []  # own notes, not the dynamic collection
        self._serializer = "own bookkeeping note"
        self._context = "own context note"

    @property
    def plugin_name(self) -> str:
        return "Shadow"


LibraryConfiguration.register_settings_plugin(ShadowNamesPlugin)


class ShadowSettings(Settings):
    pass


@pytest.fixture()
def shadow_plugin():
    plugin = ShadowSettings.get_plugin(ShadowNamesPlugin)
    ShadowStorage.data.clear()
    yield plugin
    ShadowStorage.data.clear()


def test_dynamic_plugin_subclass_may_use_the_machinerys_plain_names(shadow_plugin):
    shadow_plugin.set_setting("counter", 5)
    shadow_plugin.save_setting("counter")
    assert ShadowStorage.data != {}

    shadow_plugin.load_setting("counter")
    assert shadow_plugin.get_setting("counter") == 5

    # the same-named own members kept their values; the binding held
    assert shadow_plugin._values == []
    assert shadow_plugin._serializer == "own bookkeeping note"
    assert shadow_plugin.context.settings_class is ShadowSettings


# -- the namespaced pin: own registry slot, base fallback --------------------------


class RideSetting(SettingsAttribute):
    """Attribute whose registered serializer also serves a pin-less plugin."""


class RideStorage:
    data: Dict[str, Any] = {}


class DetourStorage:
    data: Dict[str, Any] = {}


class RideSerializer(SettingsBaseSerializer):
    def load(self, setting_name: str, attr: Any) -> Any:
        return RideStorage.data.get(setting_name, NOT_FOUND)

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        RideStorage.data[setting_name] = value

    def delete(self, setting_name: str, attr: Any) -> None:
        RideStorage.data.pop(setting_name, None)

    def contains(self, setting_name: str, attr: Any) -> bool:
        return setting_name in RideStorage.data


class DetourSerializer(SettingsBaseSerializer):
    def load(self, setting_name: str, attr: Any) -> Any:
        return DetourStorage.data.get(setting_name, NOT_FOUND)

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        DetourStorage.data[setting_name] = value

    def delete(self, setting_name: str, attr: Any) -> None:
        DetourStorage.data.pop(setting_name, None)

    def contains(self, setting_name: str, attr: Any) -> bool:
        return setting_name in DetourStorage.data


class RideDynamicPlugin(DynamicSettingsBasePlugin):
    # the binding fills the pin's own slot at import; the ride_plugin fixture
    # pops it again so each test controls the slot exactly
    # (the pin subclass is built at runtime; statically the generic class
    # reads as abstract — same ignore as the pin binding in the sample)
    binding = AttributeSerializerBinding(
        DynamicSettingAttribute[RideSetting],  # type: ignore[type-abstract]
        RideSerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "Ride"


LibraryConfiguration.register_settings_plugin(RideDynamicPlugin)


class RideSettings(Settings):
    pass


@pytest.fixture()
def ride_plugin():
    # the plugin's registration filled the pin slot at import; pop it so
    # each test decides what the slot holds
    # noinspection PyProtectedMember
    LibraryConfiguration._attribute_serializers.pop(DynamicSettingAttribute[RideSetting], None)
    plugin = RideSettings.get_plugin(RideDynamicPlugin)
    # noinspection PyProtectedMember
    plugin._DynamicSettingsBasePlugin__values.clear()
    yield plugin
    # noinspection PyProtectedMember
    plugin._DynamicSettingsBasePlugin__values.clear()
    # noinspection PyProtectedMember
    LibraryConfiguration._attribute_serializers.pop(RideSetting, None)
    # noinspection PyProtectedMember
    LibraryConfiguration._attribute_serializers.pop(DynamicSettingAttribute[RideSetting], None)
    RideStorage.data.clear()
    DetourStorage.data.clear()


def test_pin_own_slot_serves_dynamic_side_without_touching_base(ride_plugin):
    # different factories under the pin and under the base attribute are not
    # a conflict: the slots are independent
    LibraryConfiguration.register_settings_attribute(RideSetting, RideSerializer)
    LibraryConfiguration.register_settings_attribute(
        DynamicSettingAttribute[RideSetting], DetourSerializer
    )

    ride_plugin.set_setting("counter", 5)
    ride_plugin.save_settings()
    assert list(DetourStorage.data.values()) == [5]  # the pin's own serializer
    assert RideStorage.data == {}  # the base attribute's slot untouched

    ride_plugin.load_setting("counter")
    assert ride_plugin.get_setting("counter") == 5


def test_module_is_self_sufficient(tmp_path):
    """The module carries the static side beside its own dynamic names."""
    script = textwrap.dedent(
        """
        import os

        import advexp.settings.plugins.json_dynamic_settings as jds
        from advexp.settings import Settings

        os.chdir(r"{workdir}")


        class SelfSufficientSettings(
            Settings, options=jds.json_source(file="self-sufficient.json")
        ):
            # a static member of the file backend this module re-exports
            locale: str = jds.json_setting(default="en-US")


        SelfSufficientSettings.load_settings()
        assert SelfSufficientSettings.locale == "en-US"

        plugin = SelfSufficientSettings.get_plugin(jds.JSONDynamicSettingsPlugin)
        plugin.load_settings()
        assert plugin.get_setting("dark_mode", default=False) is False
        plugin.set_setting("dark_mode", True)
        plugin.save_settings()
        assert plugin.get_setting("dark_mode") is True
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
