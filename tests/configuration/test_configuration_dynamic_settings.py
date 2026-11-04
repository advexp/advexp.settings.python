"""Tests of the dynamic readers of the configuration package: the reading side
of a written group (JSON/TOML), the read-only contract, and the frozen
layouts.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator, Tuple

import pytest

import advexp.settings.plugins.json_dynamic_settings as writer_json
import advexp.settings.plugins.json_settings as writer_json_static
import advexp.settings.plugins.toml_dynamic_settings as writer_toml
import advexp.settings.plugins.toml_settings as writer_toml_static
import advexp.settings.plugins.yaml_dynamic_settings as writer_yaml
import advexp.settings.plugins.yaml_settings as writer_yaml_static
from advexp.configuration import Configuration, Sources, for_this_module
from advexp.configuration._internal.read_only_dynamic_settings_plugin import (
    ReadOnlyDocumentDynamicSettingsPlugin,
)
from advexp.configuration.plugins.json_dynamic_settings import (
    JSONDynamicSettingsConfiguration,
    JSONDynamicSettingsPlugin,
)
from advexp.configuration.plugins.json_settings import json_setting, json_source
from advexp.configuration.plugins.toml_dynamic_settings import (
    TOMLDynamicSettingsConfiguration,
    TOMLDynamicSettingsPlugin,
)
from advexp.configuration.plugins.toml_settings import toml_source
from advexp.configuration.plugins.yaml_dynamic_settings import (
    YAMLDynamicSettingsConfiguration,
    YAMLDynamicSettingsPlugin,
)
from advexp.configuration.plugins.yaml_settings import yaml_source
from advexp.settings import Settings
from advexp.settings_base.json_file import JSON_DYNAMIC_FILE_METADATA
from advexp.settings_base.sources import SOURCE_CHAIN_METADATA

# pytest imports test modules by their bare file name (prepend mode), so the
# module part of a writer class's group key is this file's stem — the literal
# the frozen-layout tests below spell consciously
WRITER_MODULE = "test_configuration_dynamic_settings"

JSON_GROUP = f"{WRITER_MODULE}.JsonWriter"
TOML_GROUP = f"{WRITER_MODULE}.TomlWriter"
YAML_GROUP = f"{WRITER_MODULE}.YamlWriter"

DECLARED_FILE = "app-settings.json"
"""The declared links' file: the fixture retargets it to its own tmp path."""


class JsonWriter(Settings):
    """The writing class whose group the JSON readers declare."""

    session_ttl: timedelta = writer_json_static.json_setting(default=timedelta(minutes=30))


class TomlWriter(Settings):
    """The writing class whose group the TOML readers declare."""


class YamlWriter(Settings):
    """The writing class whose group the YAML readers declare."""


class JsonReader(
    Configuration,
    options=json_source(file=DECLARED_FILE, dynamic_of=JSON_GROUP),
):
    """A mixed reading class: one declared member beside the dynamic group."""

    retries: int = json_setting(default=3)


class FlatJsonReader(
    Configuration,
    options=json_source(file=DECLARED_FILE, dynamic_of=JSON_GROUP),
):
    """A reader following a writer that disabled the section."""


class SeparateJsonReader(
    Configuration,
    options=json_source(file=DECLARED_FILE, dynamic_of=JSON_GROUP),
):
    """A reader that the test which uses it points at a dynamic file of its own."""


class UnboundReader(
    Configuration,
    options=json_source(file=DECLARED_FILE),
):
    """A reading class that declared no writer group."""


class TomlReader(
    Configuration,
    options=toml_source(file="app-settings.toml", dynamic_of=TOML_GROUP),
):
    """A reading class over the TOML writer's group."""


class YamlReader(
    Configuration,
    options=yaml_source(file="app-settings.yaml", dynamic_of=YAML_GROUP),
):
    """A reading class over the YAML writer's group."""


SECTION = "dynamic"


def _retarget(klass: Any, binding: Any) -> None:
    klass.__settings_context__.set_class_metadata(SOURCE_CHAIN_METADATA, Sources(binding))


def _clear_collection(plugin: Any) -> None:
    # noinspection PyProtectedMember
    plugin._DynamicSettingsBasePlugin__values.clear()
    # noinspection PyProtectedMember
    plugin._DynamicSettingsBasePlugin__metadata.clear()


def _reset_section_parameters(plugin: Any) -> None:
    from advexp.settings_base.document_dynamic_settings_plugin import _UNSET_SECTION

    # noinspection PyProtectedMember
    plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_name = _UNSET_SECTION
    # noinspection PyProtectedMember
    plugin._DocumentDynamicSettingsPlugin__dynamic_settings_section_path = _UNSET_SECTION


def _clear_module_declarations() -> None:
    from advexp.settings_base.module_default import _DECLARED_VALUES

    # noinspection PyProtectedMember
    for key in [key for key in _DECLARED_VALUES if key[2] == __name__]:
        # noinspection PyProtectedMember
        del _DECLARED_VALUES[key]


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch) -> Iterator[Tuple[Path, Path]]:
    """Reset the state, so that every test starts from the same shape:

    - both sides use one pair of temporary files;
    - there is no dynamic file of its own;
    - the sections have their default names;
    - no iteration order is declared;
    - the links of the readers point at the files of this run.
    """
    json_path = tmp_path / "app-settings.json"
    toml_path = tmp_path / "app-settings.toml"
    yaml_path = tmp_path / "app-settings.yaml"
    monkeypatch.setattr(writer_json_static.JSONSettingsConfiguration, "file_path", json_path)
    monkeypatch.setattr(writer_json.JSONDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(writer_toml_static.TOMLSettingsConfiguration, "file_path", toml_path)
    monkeypatch.setattr(writer_toml.TOMLDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(writer_yaml_static.YAMLSettingsConfiguration, "file_path", yaml_path)
    monkeypatch.setattr(writer_yaml.YAMLDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(YAMLDynamicSettingsConfiguration, "file_path", None)
    for klass in (JsonWriter, TomlWriter, YamlWriter):
        _clear_collection(klass.get_plugin(writer_json.JSONDynamicSettingsPlugin))
        _clear_collection(klass.get_plugin(writer_toml.TOMLDynamicSettingsPlugin))
        _clear_collection(klass.get_plugin(writer_yaml.YAMLDynamicSettingsPlugin))
        _reset_section_parameters(klass.get_plugin(writer_json.JSONDynamicSettingsPlugin))
        _reset_section_parameters(klass.get_plugin(writer_toml.TOMLDynamicSettingsPlugin))
        _reset_section_parameters(klass.get_plugin(writer_yaml.YAMLDynamicSettingsPlugin))
        klass.delete_class_metadata(writer_json.JSON_DYNAMIC_FILE_METADATA)
        klass.delete_class_metadata(writer_toml.TOML_DYNAMIC_FILE_METADATA)
        klass.delete_class_metadata(writer_yaml.YAML_DYNAMIC_FILE_METADATA)
    for reader in (
        JsonReader,
        FlatJsonReader,
        SeparateJsonReader,
        UnboundReader,
        TomlReader,
        YamlReader,
    ):
        _clear_collection(reader.get_plugin(JSONDynamicSettingsPlugin))
        _clear_collection(reader.get_plugin(TOMLDynamicSettingsPlugin))
        _clear_collection(reader.get_plugin(YAMLDynamicSettingsPlugin))
        _reset_section_parameters(reader.get_plugin(JSONDynamicSettingsPlugin))
        _reset_section_parameters(reader.get_plugin(TOMLDynamicSettingsPlugin))
        _reset_section_parameters(reader.get_plugin(YAMLDynamicSettingsPlugin))
        context = reader.__settings_context__
        context.delete_class_metadata(JSONDynamicSettingsPlugin.ITERATION_ORDER_METADATA)
        context.delete_class_metadata(TOMLDynamicSettingsPlugin.ITERATION_ORDER_METADATA)
        context.delete_class_metadata(YAMLDynamicSettingsPlugin.ITERATION_ORDER_METADATA)
    for reader, binding in (
        (JsonReader, json_source(file=json_path, dynamic_of=JSON_GROUP)),
        (FlatJsonReader, json_source(file=json_path, dynamic_of=JSON_GROUP)),
        (SeparateJsonReader, json_source(file=json_path, dynamic_of=JSON_GROUP)),
        (UnboundReader, json_source(file=json_path)),
        (TomlReader, toml_source(file=toml_path, dynamic_of=TOML_GROUP)),
        (YamlReader, yaml_source(file=yaml_path, dynamic_of=YAML_GROUP)),
    ):
        _retarget(reader, binding)
    _clear_module_declarations()
    yield json_path, toml_path
    _clear_module_declarations()


def _write_json_group(path: Path, entries: dict, group: str = JSON_GROUP) -> Path:
    document = {SECTION: {group: entries}}
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# -- the read-only contract ---------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda plugin: plugin.save_settings(),
            "the JSONDynamicSettings collection is read-only: it only loads entries and never "
            "writes to the storage. Writing is done by the dynamic plugin of the settings "
            "distribution",
        ),
        (
            lambda plugin: plugin.save_setting("dark_mode"),
            "the JSONDynamicSettings collection is read-only: it only loads entries and never "
            "writes to the storage. Writing is done by the dynamic plugin of the settings "
            "distribution",
        ),
        (
            lambda plugin: plugin.delete_settings(),
            "the JSONDynamicSettings collection is read-only: it only loads entries and never "
            "deletes anything from the storage. Writing is done by the dynamic plugin of the "
            "settings distribution",
        ),
        (
            lambda plugin: plugin.delete_setting("dark_mode"),
            "the JSONDynamicSettings collection is read-only: it only loads entries and never "
            "deletes anything from the storage. Writing is done by the dynamic plugin of the "
            "settings distribution",
        ),
        (
            lambda plugin: plugin.set_setting("dark_mode", True),
            "the JSONDynamicSettings collection is read-only: its values come only from the "
            "storage. Call load_configuration() to refresh them",
        ),
        (
            lambda plugin: plugin.update_from_dict({"dark_mode": True}),
            "the JSONDynamicSettings collection is read-only: its values come only from the "
            "storage. Call load_configuration() to refresh them",
        ),
        (
            lambda plugin: plugin.load_setting("dark_mode"),
            "the read-only collection does not support loading a single entry. Call "
            "load_configuration(), which refreshes every entry of the group",
        ),
        (
            lambda plugin: plugin.set_setting_metadata("dark_mode", "k", "v"),
            "the JSONDynamicSettings collection has no setting metadata: the storage holds none, "
            "and a reader never writes any",
        ),
        (
            lambda plugin: plugin.get_setting_metadata("dark_mode", "k"),
            "the JSONDynamicSettings collection has no setting metadata: the storage holds none, "
            "and a reader never writes any",
        ),
        (
            lambda plugin: plugin.get_setting_all_metadata("dark_mode"),
            "the JSONDynamicSettings collection has no setting metadata: the storage holds none, "
            "and a reader never writes any",
        ),
        (
            lambda plugin: plugin.contains_setting_metadata("dark_mode", "k"),
            "the JSONDynamicSettings collection has no setting metadata: the storage holds none, "
            "and a reader never writes any",
        ),
        (
            lambda plugin: plugin.delete_setting_metadata("dark_mode", "k"),
            "the JSONDynamicSettings collection has no setting metadata: the storage holds none, "
            "and a reader never writes any",
        ),
        (
            lambda plugin: plugin.delete_setting_all_metadata("dark_mode"),
            "the JSONDynamicSettings collection has no setting metadata: the storage holds none, "
            "and a reader never writes any",
        ),
    ],
)
def test_every_mutating_method_refuses_with_type_error(call, message, tmp_path, monkeypatch):
    _write_json_group(tmp_path / "app-settings.json", {"dark_mode": True})
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    with pytest.raises(TypeError, match=re.escape(message)):
        call(plugin)


def test_the_refusal_covers_every_method_the_facade_overrides():
    """The parametrized guard above names every method that refuses. A method that
    joins the read-only facade must join the guard, and a method that leaves the
    facade must leave the guard. The surface of the facade is also complete: it
    has the load spelling next to the refusing methods and the reading hooks.
    """
    overridden = {
        name
        for name, member in vars(ReadOnlyDocumentDynamicSettingsPlugin).items()
        if callable(member)
    }
    assert overridden == {
        "load_configuration",
        "save_settings",
        "save_setting",
        "delete_settings",
        "delete_setting",
        "set_setting",
        "update_from_dict",
        "load_setting",
        "set_setting_metadata",
        "get_setting_metadata",
        "get_setting_all_metadata",
        "contains_setting_metadata",
        "delete_setting_metadata",
        "delete_setting_all_metadata",
        # the reading hooks carrying the writer-group naming
        "_writer_group",
        "_ReadOnlyDocumentDynamicSettingsPlugin__require_writer_group",
        "_dynamic_full_name",
        "_dynamic_stored_names",
    }


# -- the round trip: the settings package writes, this package reads -----------------


def test_the_reader_loads_the_writers_group_from_the_shared_file(tmp_path):
    _write_json_group(tmp_path / "app-settings.json", {"dark_mode": True, "retries": 5})
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    assert sorted(plugin) == ["dark_mode", "retries"]
    assert plugin.get_setting("dark_mode", default=False) is True
    assert plugin.get_setting("retries", default=0) == 5
    assert len(plugin) == 2
    assert "dark_mode" in plugin
    assert plugin.to_dict() == {"dark_mode": True, "retries": 5}


def test_get_setting_converts_to_the_defaults_type_and_misses_fall_back(tmp_path):
    _write_json_group(tmp_path / "app-settings.json", {"ttl": "0:30:00", "broken": "not-a-number"})
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.get_setting("ttl", default=timedelta()) == timedelta(minutes=30)
    # a value that fails to convert falls back to the default, as on the
    # declared side
    assert plugin.get_setting("broken", default=7) == 7
    assert plugin.get_setting("absent", default="fallback") == "fallback"
    with pytest.raises(KeyError, match="no dynamic setting 'absent'"):
        plugin.get_setting("absent")


def test_the_reading_class_keeps_declared_members_beside_the_group(tmp_path):
    path = tmp_path / "app-settings.json"
    document = {
        f"{WRITER_MODULE}.JsonReader.retries": 9,
        SECTION: {JSON_GROUP: {"dark_mode": True}},
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    errors = JsonReader.load_configuration()
    assert errors == ()
    assert JsonReader.retries == 9
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.get_setting("dark_mode", default=False) is True


def test_load_configuration_rereads_the_group_on_every_call(tmp_path):
    path = _write_json_group(tmp_path / "app-settings.json", {"dark_mode": True})
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    _write_json_group(path, {"other": 1})
    plugin.load_configuration()
    assert sorted(plugin) == ["other"]


def test_the_iteration_order_follows_the_class_metadata(tmp_path):
    _write_json_group(tmp_path / "app-settings.json", {"b": 1, "a": 2, "c": 3})
    JsonReader.__settings_context__.set_class_metadata(
        JSONDynamicSettingsPlugin.ITERATION_ORDER_METADATA, ["c", "a"]
    )
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    assert list(plugin) == ["c", "a", "b"]
    assert list(plugin.to_dict()) == ["c", "a", "b"]


def test_only_the_declared_group_is_read_not_the_readers_own_names(tmp_path):
    """Entries that are keyed by the own class name of the reader, or by the group
    of another writer, are not read. Only the declared group key addresses the
    entries.
    """
    path = tmp_path / "app-settings.json"
    document = {
        SECTION: {
            f"{WRITER_MODULE}.JsonReader": {"imposter": 1},
            JSON_GROUP: {"real": 2},
            f"{WRITER_MODULE}.UnboundReader": {"bystander": 3},
        }
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"real": 2}


def test_a_class_without_a_group_reads_nothing_and_the_load_names_the_binding(tmp_path):
    _write_json_group(tmp_path / "app-settings.json", {"dark_mode": True})
    plugin = UnboundReader.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError) as report:
        plugin.load_configuration()
    assert "UnboundReader reads no dynamic group" in str(report.value)
    assert 'json_source(dynamic_of="app.LocalSettings")' in str(report.value)


# -- the frozen layouts: the public storage form --------------------------------------


def test_the_section_layout_is_the_frozen_public_form(tmp_path):
    """The stored document is a public contract between the distributions. This
    test writes its shape literally, and a change here is a migration of every
    stored file.
    """
    writer = JsonWriter.get_plugin(writer_json.JSONDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    document = json.loads((tmp_path / "app-settings.json").read_text(encoding="utf-8"))
    assert document == {"dynamic": {JSON_GROUP: {"dark_mode": True}}}


def test_the_flat_layout_is_the_frozen_public_form(tmp_path):
    writer = JsonWriter.get_plugin(writer_json.JSONDynamicSettingsPlugin)
    writer.dynamic_settings_section_name = None
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    document = json.loads((tmp_path / "app-settings.json").read_text(encoding="utf-8"))
    assert document == {f"D.{JSON_GROUP}.dark_mode": True}

    # the reader follows the writer's parameter and reads the flat keys
    reader = FlatJsonReader.get_plugin(JSONDynamicSettingsPlugin)
    reader.dynamic_settings_section_name = None
    reader.load_configuration()
    assert reader.to_dict() == {"dark_mode": True}


def test_the_moved_section_is_read_through_the_same_parameters(tmp_path):
    path = tmp_path / "app-settings.json"
    document = {"config": {"runtime": {JSON_GROUP: {"dark_mode": True}}}}
    path.write_text(json.dumps(document), encoding="utf-8")
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = "runtime"
    plugin.dynamic_settings_section_path = "/config"
    plugin.load_configuration()
    assert plugin.to_dict() == {"dark_mode": True}


# -- the file levels -------------------------------------------------------------------


def test_the_own_dynamic_file_of_the_reader_wins_over_the_shared_one(tmp_path):
    shared = _write_json_group(tmp_path / "app-settings.json", {"shared": 1})
    own = tmp_path / "reader-dynamic.json"
    own.write_text(json.dumps({SECTION: {JSON_GROUP: {"own": 2}}}), encoding="utf-8")
    _retarget(SeparateJsonReader, json_source(file=shared, dynamic_of=JSON_GROUP))
    SeparateJsonReader.__settings_context__.set_class_metadata(JSON_DYNAMIC_FILE_METADATA, own)
    plugin = SeparateJsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"own": 2}
    # the reader never writes: the shared file keeps what it held
    assert json.loads(shared.read_text(encoding="utf-8")) == {SECTION: {JSON_GROUP: {"shared": 1}}}


def test_the_module_declaration_of_the_own_dynamic_file(tmp_path, monkeypatch):
    _write_json_group(tmp_path / "app-settings.json", {"shared": 1})
    own = tmp_path / "declared-dynamic.json"
    own.write_text(json.dumps({SECTION: {JSON_GROUP: {"declared": 3}}}), encoding="utf-8")
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", for_this_module(own))
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"declared": 3}


def test_a_broken_dynamic_document_is_a_loud_error(tmp_path):
    path = tmp_path / "app-settings.json"
    path.write_text(json.dumps({SECTION: {JSON_GROUP: [1, 2]}}), encoding="utf-8")
    plugin = JsonReader.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError) as report:
        plugin.load_configuration()
    assert f"Dynamic settings of '{JSON_GROUP}'" in str(report.value)
    assert "must hold an object, got a list" in str(report.value)


# -- the TOML twin ------------------------------------------------------------------------


def _write_toml_group(path: Path, entries: dict) -> Path:
    lines = [f"[{SECTION}.{TOML_GROUP}]"]
    lines += [f"{name} = {json.dumps(value)}" for name, value in entries.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_toml_reader_loads_the_writers_group(tmp_path):
    _write_toml_group(tmp_path / "app-settings.toml", {"dark_mode": True, "retries": 5})
    plugin = TomlReader.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"dark_mode": True, "retries": 5}
    assert plugin.get_setting("retries", default=0) == 5


def test_the_toml_layout_is_written_by_the_settings_package_and_read_back(tmp_path):
    """The frozen TOML form: the section table, the class part nested by its dots,
    and the name of the entry as a plain literal key.
    """
    writer = TomlWriter.get_plugin(writer_toml.TOMLDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    text = (tmp_path / "app-settings.toml").read_text(encoding="utf-8")
    assert f"[{SECTION}.{TOML_GROUP}]" in text
    assert "dark_mode = true" in text

    plugin = TomlReader.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"dark_mode": True}


def test_the_toml_flat_layout_reads_back(tmp_path):
    path = tmp_path / "app-settings.toml"
    path.write_text(f'"D.{TOML_GROUP}.feature_x" = "on"\n', encoding="utf-8")
    plugin = TomlReader.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = None
    plugin.load_configuration()
    assert plugin.to_dict() == {"feature_x": "on"}


def test_the_toml_own_dynamic_file(tmp_path, monkeypatch):
    shared = tmp_path / "app-settings.toml"
    shared.write_text("[other]\nkey = 1\n", encoding="utf-8")
    own = tmp_path / "reader-dynamic.toml"
    own.write_text(f"[{SECTION}.{TOML_GROUP}]\nk = 42\n", encoding="utf-8")
    monkeypatch.setattr(TOMLDynamicSettingsConfiguration, "file_path", own)
    plugin = TomlReader.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"k": 42}


# -- the YAML twin ------------------------------------------------------------------------


def _write_yaml_group(path: Path, entries: dict) -> Path:
    lines = [f"{SECTION}:", f"  {YAML_GROUP}:"]
    lines += [f"    {name}: {json.dumps(value)}" for name, value in entries.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_yaml_reader_loads_the_writers_group(tmp_path):
    _write_yaml_group(tmp_path / "app-settings.yaml", {"dark_mode": True, "retries": 5})
    plugin = YamlReader.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"dark_mode": True, "retries": 5}
    assert plugin.get_setting("retries", default=0) == 5


def test_the_yaml_layout_is_written_by_the_settings_package_and_read_back(tmp_path):
    """The frozen YAML form: the section mapping, the class part as one flat key of
    its own, and the name of the entry as a plain key next to it.
    """
    writer = YamlWriter.get_plugin(writer_yaml.YAMLDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    text = (tmp_path / "app-settings.yaml").read_text(encoding="utf-8")
    assert f"{SECTION}:\n  {YAML_GROUP}:\n    dark_mode: true\n" in text

    plugin = YamlReader.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"dark_mode": True}


def test_the_yaml_flat_layout_reads_back(tmp_path):
    path = tmp_path / "app-settings.yaml"
    path.write_text(f'"D.{YAML_GROUP}.feature_x": "on"\n', encoding="utf-8")
    plugin = YamlReader.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.dynamic_settings_section_name = None
    plugin.load_configuration()
    assert plugin.to_dict() == {"feature_x": "on"}


def test_the_yaml_own_dynamic_file(tmp_path, monkeypatch):
    shared = tmp_path / "app-settings.yaml"
    shared.write_text("other:\n  key: 1\n", encoding="utf-8")
    own = tmp_path / "reader-dynamic.yaml"
    own.write_text(f"{SECTION}:\n  {YAML_GROUP}:\n    k: 42\n", encoding="utf-8")
    monkeypatch.setattr(YAMLDynamicSettingsConfiguration, "file_path", own)
    plugin = YamlReader.get_plugin(YAMLDynamicSettingsPlugin)
    plugin.load_configuration()
    assert plugin.to_dict() == {"k": 42}
