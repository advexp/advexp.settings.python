"""YAML family naming options: the static document keys through the source binding."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path
from typing import Any, Iterator

import pytest
from ruamel.yaml import YAML

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.yaml_settings import (
    NAME_PATTERN,
    YAML_METADATA_OPTIONS,
    YAMLSetting,
    YAMLSettingsConfiguration,
    YAMLSettingsSerializer,
    yaml_setting,
    yaml_source,
)
from advexp.settings_base.sources import LINK_NAME_PATTERN_PARAM, YAML_SOURCE_METADATA
from advexp.settings_base.yaml_options import check_yaml_options


class ShortKeysSettings(
    Settings,
    options=yaml_source(name_pattern="{ClassName}.{FieldName}"),
):
    session_ttl: int = yaml_setting(default=30)  # ShortKeysSettings.session_ttl

    # an explicit name= is the full address, untouched by the pattern
    host: str = yaml_setting(name="host", default="localhost")

    # the pattern builds the key, path= locates it in the tree
    retries: int = yaml_setting(path="/net", default=2)  # net -> ShortKeysSettings.retries


class BaseKeysSettings(
    Settings,
    options=yaml_source(name_pattern="base.{FieldName}"),
):
    base_ttl: int = yaml_setting(default=1)  # base.base_ttl


class ChildKeysSettings(
    BaseKeysSettings,
    options=yaml_source(name_pattern="child.{FieldName}"),
):
    child_ttl: int = yaml_setting(default=2)  # child.child_ttl


class WishedSetting(YAMLSetting):
    """Attribute served by a serializer with naming wishes."""


class WishedSerializer(YAMLSettingsSerializer):
    """Naming wishes: the ``_`` delimiter and dash sanitization."""

    def delimiter(self) -> str:
        return "_"

    def remove_inappropriate_symbols(self, text: str) -> str:
        return text.replace("-", "_")


LibraryConfiguration.register_settings_attribute(WishedSetting, WishedSerializer)


def wished_setting(*, default: Any = NO_DEFAULT) -> Any:
    """Declare a setting that is served by the wished serializer. The factory
    spelling keeps the assignment type-checker-friendly, like ``yaml_setting``.
    """
    return WishedSetting(default=default)


class WishedKeysSettings(
    Settings, options=yaml_source(name_pattern="w{ClassName}{Delimiter}{FieldName}")
):
    window_scale: int = wished_setting(default=2)  # wWishedKeysSettings_window_scale


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.yaml"
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", path)
    yield path


def read_document(configured_file) -> Any:
    return YAML(typ="safe").load(configured_file.read_text(encoding="utf-8"))


def write_document(configured_file, document: Any) -> None:
    stream = StringIO()
    YAML(typ="rt").dump(document, stream)
    configured_file.write_text(stream.getvalue(), encoding="utf-8")


def reset_classes() -> None:
    for klass in (ShortKeysSettings, ChildKeysSettings, WishedKeysSettings):
        klass.reset_settings()


@pytest.fixture(autouse=True)
def clean_values():
    # settings classes keep values in class storage; start each test clean
    reset_classes()
    yield
    reset_classes()


def test_import_registers_the_family_validator():
    validator = LibraryConfiguration._get_class_metadata_validator(YAML_METADATA_OPTIONS)
    assert validator is check_yaml_options


def test_pattern_shapes_the_pattern_built_keys(configured_file):
    ShortKeysSettings.save_settings()
    assert read_document(configured_file) == {
        "ShortKeysSettings.session_ttl": 30,
        "host": "localhost",
        "net": {"ShortKeysSettings.retries": 2},
    }


def test_pattern_built_keys_load_back(configured_file):
    write_document(
        configured_file,
        {
            "ShortKeysSettings.session_ttl": 90,
            "host": "example.com",
            "net": {"ShortKeysSettings.retries": 5},
        },
    )
    ShortKeysSettings.load_settings()
    assert ShortKeysSettings.session_ttl == 90
    assert ShortKeysSettings.host == "example.com"
    assert ShortKeysSettings.retries == 5


def test_pattern_builds_contains_and_delete_keys(configured_file):
    ShortKeysSettings.save_settings()
    assert ShortKeysSettings.contains_setting("session_ttl")
    ShortKeysSettings.delete_setting(lambda s: s.session_ttl)
    assert read_document(configured_file) == {
        "host": "localhost",
        "net": {"ShortKeysSettings.retries": 2},
    }


def test_described_name_is_the_pattern_built_key(configured_file):
    # the load diagnostics quote the key the document actually carries, not
    # the pipeline's default spelling
    serializer = YAMLSettingsSerializer()
    serializer.set_serializer_params(ShortKeysSettings.__settings_context__)
    member = ShortKeysSettings.__settings_members__["session_ttl"]
    assert (
        serializer.describe_setting_name("ignored default name", member.attribute)
        == "key 'ShortKeysSettings.session_ttl'"
    )


def test_a_subclass_binding_replaces_the_pattern_for_it_and_below(configured_file):
    # the child's own binding replaces the base's for the child alone: the
    # inherited members read by the child's pattern, the base keeps its own
    ChildKeysSettings.save_settings()
    assert read_document(configured_file) == {
        "child.base_ttl": 1,
        "child.child_ttl": 2,
    }
    BaseKeysSettings.save_settings()
    assert read_document(configured_file) == {
        "child.base_ttl": 1,
        "child.child_ttl": 2,
        "base.base_ttl": 1,
    }


def test_runtime_change_of_options_changes_keys(configured_file):
    # a class on the module default retunes its keys through the family
    # entry's runtime channel — the seat the entry keeps without a binding
    class RuntimeKeysSettings(Settings):
        ttl: int = yaml_setting(default=30)

    RuntimeKeysSettings.set_class_metadata(YAML_METADATA_OPTIONS, {NAME_PATTERN: "rt.{FieldName}"})
    RuntimeKeysSettings.save_settings()
    assert read_document(configured_file) == {"rt.ttl": 30}


def test_runtime_invalid_options_rejected_before_storing():
    class GuardedSettings(Settings):
        mode: str = yaml_setting(default="x")

    with pytest.raises(
        TypeError,
        match=rf"GuardedSettings\.class_metadata\['{YAML_METADATA_OPTIONS}\.",
    ):
        GuardedSettings.set_class_metadata(YAML_METADATA_OPTIONS, {NAME_PATTERN: "{ClassName}"})
    # the previous state stands
    assert GuardedSettings.get_class_metadata(YAML_METADATA_OPTIONS) is None


@pytest.mark.parametrize(
    "options",
    [
        {NAME_PATTERN: "{ClassName}"},
        {NAME_PATTERN: ""},
        {NAME_PATTERN: 7},
        {NAME_PATTERN: "{FieldName}", "name_patrn": "typo"},
        "nope",
    ],
    ids=[
        "no-field-slot",
        "empty-pattern",
        "non-string-pattern",
        "unknown-option",
        "non-mapping",
    ],
)
def test_invalid_declaration_fails_the_class_statement(options):
    with pytest.raises(TypeError, match=rf"Broken\.class_metadata\['{YAML_METADATA_OPTIONS}\."):

        class Broken(Settings):
            class_metadata = {YAML_METADATA_OPTIONS: options}
            mode: str = yaml_setting(default="x")


def test_the_builder_carries_the_pattern_on_its_link():
    # the binding is the pattern's one seat: the builder lands it on the
    # link under the family's source key, not on the family entry
    entry = dict(yaml_source(name_pattern="{FieldName}"))
    assert set(entry) == {YAML_SOURCE_METADATA}
    link = entry[YAML_SOURCE_METADATA]
    assert link.param(LINK_NAME_PATTERN_PARAM) == "{FieldName}"
    assert dict(yaml_source())[YAML_SOURCE_METADATA].param(LINK_NAME_PATTERN_PARAM) is None


def test_the_builder_rejects_an_invalid_pattern():
    # a pattern without the field slot would collapse every member of the
    # class onto one key; the builder fails at the call, before the class
    with pytest.raises(TypeError, match="{FieldName}"):
        yaml_source(name_pattern="{ClassName}")
    with pytest.raises(TypeError, match="non-empty string"):
        yaml_source(name_pattern="")


def test_wishes_serve_the_pattern_built_keys(configured_file):
    # the keys build through the shared name builder, so the serializer's
    # wishes apply to a family pattern exactly as to the default one: the
    # {Delimiter} slot takes the delimiter wish, the fragments are sanitized
    WishedKeysSettings.save_settings()
    assert read_document(configured_file) == {"wWishedKeysSettings_window_scale": 2}


def test_default_pattern_without_a_binding(configured_file):
    # no declaration anywhere: the keys keep the default full pattern
    class PlainSettings(Settings):
        ttl: int = yaml_setting(default=1)

    module = PlainSettings.__module__
    PlainSettings.save_settings()
    assert read_document(configured_file) == {f"{module}.PlainSettings.ttl": 1}


def test_a_shared_key_names_the_overwrite_at_debug(configured_file, caplog):
    # the collision a short form invites: two classes sharing the file
    # build one key, and the later write wins. Not silently — the
    # channel's lowest-priority record names the overwritten key; a value
    # written over its own equal spelling stays quiet
    class FirstSettings(
        Settings,
        options=yaml_source(name_pattern="{FieldName}"),
    ):
        ttl: int = yaml_setting(default=30)

    class SecondSettings(
        Settings,
        options=yaml_source(name_pattern="{FieldName}"),
    ):
        ttl: int = yaml_setting(default=90)

    FirstSettings.save_settings()
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        SecondSettings.save_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "already stores a different value under the key 'ttl'" in message for message in messages
    )
    assert read_document(configured_file) == {"ttl": 90}

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        SecondSettings.save_settings()  # same value again: nothing to report
    assert not [
        record
        for record in caplog.records
        if "already stores a different value" in record.getMessage()
    ]
