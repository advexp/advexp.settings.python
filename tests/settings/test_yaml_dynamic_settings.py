"""YAMLDynamicSettings plugin tests (file backend through tmp_path)."""

from __future__ import annotations

import enum
import re
from pathlib import Path
from typing import Any, Dict, Iterator, Type

import pytest
from ruamel.yaml import YAML

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import DynamicSettingAttribute
from advexp.settings.plugins.yaml_dynamic_settings import (
    YAMLDynamicSettingsConfiguration,
    YAMLDynamicSettingsPlugin,
)
from advexp.settings.plugins.yaml_settings import (
    NAME_PATTERN,
    YAMLSetting,
    YAMLSettingsConfiguration,
    YAMLSettingsSerializer,
    yaml_setting,
    yaml_source,
)
from advexp.settings_base.document_dynamic_settings_plugin import _UNSET_SECTION

# noinspection PyProtectedMember
from advexp.settings_base.names import (
    DEFAULT_SETTINGS_NAME_PATTERN,
    SettingNameMode,
    get_dynamic_settings_class_prefix,
    get_full_setting_name,
)
from advexp.settings_base.yaml_file import YAML_DYNAMIC_FILE_METADATA


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class DynSettings(Settings):
    """Mixed class: one declared member plus the dynamic collection."""

    airplane_mode: bool = yaml_setting(default=False)


class OtherSettings(Settings):
    """A second class sharing the file: dynamic entries are kept apart."""


SECTION = YAMLDynamicSettingsPlugin.DEFAULT_SECTION


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
    path = tmp_path / "settings.yaml"
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", path)
    # the dynamic side's own file and name pattern are off unless a test
    # opts in
    monkeypatch.setattr(YAMLDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(
        YAMLDynamicSettingsConfiguration, NAME_PATTERN, DEFAULT_SETTINGS_NAME_PATTERN
    )
    yield path


@pytest.fixture(autouse=True)
def clean_collections():
    # plugin instances and class metadata live as long as the settings class;
    # start each test with an empty dynamic collection, no declared order and
    # the default section binding
    for klass in (DynSettings, OtherSettings):
        plugin = klass.get_plugin(YAMLDynamicSettingsPlugin)
        # noinspection PyProtectedMember
        plugin._DynamicSettingsBasePlugin__values.clear()
        # noinspection PyProtectedMember
        plugin._DynamicSettingsBasePlugin__metadata.clear()
        # noinspection PyProtectedMember
        plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_name = _UNSET_SECTION
        # noinspection PyProtectedMember
        plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_path = _UNSET_SECTION
        # no own-file binding: the module default (or the static file) governs
        klass.delete_class_metadata(YAML_DYNAMIC_FILE_METADATA)
        klass.delete_class_metadata(YAMLDynamicSettingsPlugin.ITERATION_ORDER_METADATA)
    yield


def read_document(configured_file) -> Dict[str, Any]:
    document = YAML(typ="safe").load(configured_file.read_text(encoding="utf-8"))
    return document or {}


def write_document(configured_file, document: Dict[str, Any]) -> None:
    from io import StringIO

    stream = StringIO()
    YAML(typ="rt").dump(document, stream)
    configured_file.write_text(stream.getvalue(), encoding="utf-8")


# -- registration -----------------------------------------------------------------


def test_import_enables_plugin_and_registers_pin_pair():
    assert YAMLDynamicSettingsPlugin in LibraryConfiguration.registered_plugin_classes()
    # the pin's own slot, registered by the base setup from the declared
    # binding: the dynamic side lives apart from the static
    # plugin's YAMLSetting binding, so the two registrations cannot clash
    pin = YAMLDynamicSettingsPlugin.binding.attribute_class
    assert pin is DynamicSettingAttribute[YAMLSetting]
    assert LibraryConfiguration._get_serializer_factory(pin) is YAMLSettingsSerializer


# -- the document and its section ---------------------------------------------------


def test_save_writes_dynamic_section_beside_static(configured_file):
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
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
    # blank file is started over — in YAML it is valid and empty already
    configured_file.write_text("", encoding="utf-8")
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = read_document(configured_file)
    assert document == {
        SECTION: {
            dyn_class_key(DynSettings): {"checkbox": True},
        },
    }


def test_the_section_takes_the_libraries_layout_and_keeps_the_files_comments(
    configured_file,
):
    # the section the pass writes itself goes into the file with the
    # library's layout, and a comment the file already carries above its
    # own key survives the save
    configured_file.write_text(
        f"# prose of the file's own\n{static_full_name(DynSettings, 'airplane_mode')}: false\n",
        encoding="utf-8",
    )
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "# prose of the file's own" in text
    assert f"{SECTION}:\n  {dyn_class_key(DynSettings)}:\n    checkbox: true\n" in text


def test_load_rebuilds_collection_from_storage(configured_file):
    write_document(configured_file, dyn_document(DynSettings, {"checkbox": True, "login": "a"}))
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_settings()
    assert plugin.get_setting("checkbox", default=False) is True
    assert plugin.get_setting("login") == "a"


def test_load_picks_only_this_class_entries(configured_file):
    document = {
        SECTION: {
            dyn_class_key(DynSettings): {"checkbox": True},
            dyn_class_key(OtherSettings): {"foreign": True},
        }
    }
    write_document(configured_file, document)
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_settings()
    assert sorted(plugin) == ["checkbox"]


def test_values_round_trip_through_the_file(configured_file):
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.set_setting("login", "alice")
    plugin.set_setting("scale", 7)
    plugin.save_settings()

    plugin.load_settings()
    assert plugin.get_setting("checkbox", default=False) is True
    assert plugin.get_setting("login") == "alice"
    assert plugin.get_setting("scale") == 7


def test_yaml_native_values_round_trip_through_the_file(configured_file):
    # dates stay native in a YAML file, dynamic entries included
    import datetime

    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("launch_on", datetime.date(2026, 12, 1))
    plugin.save_settings()
    assert "launch_on: 2026-12-01\n" in configured_file.read_text(encoding="utf-8")

    plugin.load_settings()
    assert plugin.get_setting("launch_on") == datetime.date(2026, 12, 1)


def test_saving_none_stores_the_documents_null(configured_file):
    # None is a value like any other: it lands in the file as the null and
    # reads back, apart from a missing name
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("hint", None)
    plugin.save_settings()
    assert read_document(configured_file) == dyn_document(DynSettings, {"hint": None})

    plugin.load_settings()
    assert plugin.get_setting("hint") is None


def test_class_level_passes_do_not_touch_dynamic_collection(configured_file):
    DynSettings.reset_settings()  # an earlier test may have left a value on the class
    DynSettings.save_settings()
    assert read_document(configured_file) == {static_full_name(DynSettings, "airplane_mode"): False}


def test_save_settings_drops_orphaned_entries_of_this_class(configured_file):
    write_document(
        configured_file,
        {
            SECTION: {
                dyn_class_key(DynSettings): {"checkbox": True, "login": "a"},
                dyn_class_key(OtherSettings): {"foreign": 1},
            }
        },
    )
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_settings()
    plugin.save_settings()

    document = read_document(configured_file)
    assert document[SECTION][dyn_class_key(DynSettings)] == {"checkbox": True, "login": "a"}
    assert document[SECTION][dyn_class_key(OtherSettings)] == {"foreign": 1}


def test_deleting_the_last_entry_drops_class_object_and_section(configured_file):
    write_document(configured_file, dyn_document(DynSettings, {"checkbox": True}))
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_settings()
    plugin.delete_setting("checkbox")
    plugin.save_settings()
    assert read_document(configured_file) == {}


def test_delete_settings_clears_storage_and_collection(configured_file):
    write_document(
        configured_file,
        {SECTION: {dyn_class_key(DynSettings): {"a": 1}, dyn_class_key(OtherSettings): {"b": 2}}},
    )
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_settings()
    plugin.delete_settings()
    plugin.save_settings()
    assert read_document(configured_file) == {SECTION: {dyn_class_key(OtherSettings): {"b": 2}}}


# -- broken files -------------------------------------------------------------------


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("{not yaml", encoding="utf-8")
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    with pytest.raises(
        ValueError,
        match=re.escape(f"cannot parse the YAML settings file {configured_file}"),
    ):
        plugin.load_settings()


def test_unset_file_path_raises_to_caller(monkeypatch, tmp_path):
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(YAMLDynamicSettingsConfiguration, "file_path", None)
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="file_path"):
        plugin.set_setting("checkbox", True), plugin.save_settings()


def test_section_holding_a_scalar_raises_to_caller(configured_file):
    write_document(configured_file, {SECTION: 42})
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="must hold an object"):
        plugin.load_settings()


# -- the section parameters ---------------------------------------------------------


def test_section_can_be_renamed_and_disabled(configured_file):
    write_document(configured_file, {"runtime": {dyn_class_key(DynSettings): {"a": 1}}})
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    plugin.load_settings()
    assert plugin.get_setting("a") == 1
    plugin.save_settings()
    assert read_document(configured_file) == {"runtime": {dyn_class_key(DynSettings): {"a": 1}}}


def test_section_path_locates_the_section_in_the_tree(configured_file):
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    plugin.dynamic_settings_section_path = "/config/advexp"
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(configured_file) == {
        "config": {"advexp": {"runtime": {dyn_class_key(DynSettings): {"checkbox": True}}}}
    }

    # load follows the path back
    plugin._DynamicSettingsBasePlugin__values.clear()
    plugin.load_settings()
    assert plugin.get_setting("checkbox") is True


def test_static_key_of_the_section_name_is_rejected(configured_file):
    class GuardedSettings(Settings):
        plain: str = yaml_setting(name=SECTION, default="x")  # would shadow the section
        nested: str = yaml_setting(name="host", path=f"/{SECTION}", default="y")

    with pytest.raises(ValueError, match="reserved for the dynamic settings section"):
        GuardedSettings.save_settings()


# -- the own dynamic file -----------------------------------------------------------


def test_own_dynamic_file_separates_entries_from_static(tmp_path, configured_file, monkeypatch):
    own = tmp_path / "dynamic-settings.yaml"
    monkeypatch.setattr(YAMLDynamicSettingsConfiguration, "file_path", own)

    DynSettings.reset_settings()  # an earlier test may have left a value on the class
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    DynSettings.save_settings()

    assert read_document(own) == dyn_document(DynSettings, {"checkbox": True})
    # the static document holds no reservation once the entries moved out
    assert read_document(configured_file) == {static_full_name(DynSettings, "airplane_mode"): False}


def test_class_binding_through_the_source_builder_moves_the_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", None)
    own = tmp_path / "dynamic-settings.yaml"

    class BoundSettings(
        Settings,
        options=yaml_source(file=tmp_path / "static.yaml", dynamic_file=own),
    ):
        airplane_mode: bool = yaml_setting(default=False)

    plugin = BoundSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(own) == dyn_document(BoundSettings, {"checkbox": True})


def test_dynamic_passes_run_with_only_the_own_file_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(YAMLDynamicSettingsConfiguration, "file_path", None)

    class OwnFileSettings(Settings):
        airplane_mode: bool = yaml_setting(default=False)

    OwnFileSettings.set_class_metadata(YAML_DYNAMIC_FILE_METADATA, tmp_path / "dyn.yaml")
    plugin = OwnFileSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()
    assert read_document(tmp_path / "dyn.yaml") == dyn_document(OwnFileSettings, {"checkbox": True})


def test_static_keys_may_use_the_section_location_in_own_file_mode(
    tmp_path, configured_file, monkeypatch
):
    own = tmp_path / "dynamic-settings.yaml"
    monkeypatch.setattr(YAMLDynamicSettingsConfiguration, "file_path", own)

    # with the entries in a file of their own, the static document has no
    # section to collide with
    class PathedSettings(Settings):
        nested: str = yaml_setting(name="host", path=f"/{SECTION}", default="y")

    PathedSettings.save_settings()
    assert read_document(configured_file) == {SECTION: {"host": "y"}}


# -- the flat layout ------------------------------------------------------------------


def test_flat_enumeration_lists_the_bound_class_entries(configured_file):
    plugin = DynSettings.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = None
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    full = dyn_full_name(DynSettings, "checkbox")
    assert read_document(configured_file) == {full: True}
    plugin.load_settings()
    assert sorted(plugin) == ["checkbox"]
