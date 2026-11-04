"""The automated form of the manual usage matrix: a tour over the public API.

Every test mirrors one row of the manual testing checklist. The section
letters and the row numbers in the names of the tests match the checklist.
The walkthrough that was done by hand once covers:

- member states;
- declaration errors;
- loading through each backend;
- the two channels of load failures;
- conversion;
- constraints;
- saving;
- snapshots;
- inheritance;
- metadata;
- dynamic settings.

It is re-run by::

    pytest tests/settings/test_settings_usage_matrix.py
"""

from __future__ import annotations

import dataclasses
import enum
import json
import logging
import os
import stat
import types
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, List, Optional

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from advexp.settings import (
    REQUIRED,
    AggregateLoadError,
    ConstraintViolationError,
    ConversionError,
    LibraryConfiguration,
    MemberLoadError,
    MissingValueError,
    PluginNotEnabledError,
    SecretStr,
    Settings,
    SettingValidationError,
    SourceLoadError,
    declared_module_defaults,
    env_parameter,
    for_this_module,
    non_storage_setting,
    setting,
)
from advexp.settings.plugin_api import (
    NOT_FOUND,
    AttributeSerializerBinding,
    ISettingAttribute,
    SettingsAttribute,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings.plugins.environment import NameCase
from advexp.settings.plugins.environment.dotenv import (
    DotenvConfiguration,
    DotenvPlugin,
    dotenv_file,
    dotenv_setting,
    dotenv_source,
)
from advexp.settings.plugins.environment.variables import (
    env_source,
    environment_variable_setting,
)
from advexp.settings.plugins.json_dynamic_settings import (
    JSONDynamicSettingsConfiguration,
    JSONDynamicSettingsPlugin,
)
from advexp.settings.plugins.json_settings import (
    JSON_FILE_METADATA,
    JSONSettingsConfiguration,
    json_file,
    json_setting,
    json_source,
)
from advexp.settings.plugins.mapping_source import mapping_source, mapping_source_for
from advexp.settings.plugins.toml_dynamic_settings import (
    TOMLDynamicSettingsPlugin,
)
from advexp.settings.plugins.toml_settings import (
    TOMLSettingsConfiguration,
    toml_file,
    toml_setting,
    toml_source,
)
from advexp.settings.plugins.yaml_settings import (
    yaml_setting,
    yaml_source,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.module_default import _DECLARED_VALUES
from advexp.settings_base.sources import ENVIRONMENT_SOURCE_METADATA, JSON_SOURCE_METADATA


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


@dataclasses.dataclass
class DbConfig:
    host: str = "localhost"
    port: int = 5432


@dataclasses.dataclass
class Proxy:
    host: str
    port: int = 3128


class MatrixEndpoint:
    """A custom annotation outside the conversion contract."""


class ExplodingSetting(SettingsAttribute):
    """A test storage attribute whose loading always fails."""


class ExplodingSerializer(SettingsBaseSerializer):
    """A test storage serializer: load raises, the rest is inert."""

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        raise RuntimeError("storage exploded")

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """No-op: a test storage never writes."""

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: a test storage never deletes."""

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return False


class ExplodingPlugin(SettingsBasePlugin):
    """A test storage plugin binding the exploding pair."""

    binding = AttributeSerializerBinding(ExplodingSetting, ExplodingSerializer)

    @property
    def plugin_name(self) -> str:
        return "MatrixExploding"


LibraryConfiguration.register_settings_plugin(ExplodingPlugin)


def exploding_setting(**kwargs: Any) -> Any:
    return ExplodingSetting(**kwargs)


class WriteExplodingSetting(SettingsAttribute):
    """A test storage attribute: every write and probe operation fails."""


class WriteExplodingSerializer(SettingsBaseSerializer):
    """A test storage serializer: ``save`` and ``delete`` raise plain errors, and
    ``contains`` raises the user-facing error.
    """

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        raise RuntimeError("write exploded")

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        raise RuntimeError("delete exploded")

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        raise UserFacingError(ValueError("probe inner"))
        return False


class WriteExplodingPlugin(SettingsBasePlugin):
    """A test storage plugin binding the write-exploding pair."""

    binding = AttributeSerializerBinding(WriteExplodingSetting, WriteExplodingSerializer)

    @property
    def plugin_name(self) -> str:
        return "MatrixWriteExploding"


LibraryConfiguration.register_settings_plugin(WriteExplodingPlugin)


def write_exploding_setting(**kwargs: Any) -> Any:
    return WriteExplodingSetting(**kwargs)


def fallback_warning(caplog: pytest.LogCaptureFixture, member: str) -> bool:
    """Whether a captured record reports the member's fallback to its default."""
    return any(
        "using the default" in record.getMessage() and member in record.getMessage()
        for record in caplog.records
    )


def assert_diagnostic_context(text: str, *, member: str, owner: str, storage: str) -> None:
    """Check that every user-facing diagnostic names the member, its class, and its
    storage.

    ``storage`` is the full storage phrase that the message must carry: the kind
    of the storage together with the address, in the way that the environment
    family spells ``environment variable 'NAME'``.
    """
    assert member in text
    assert owner in text
    assert storage in text


class FailingSaveSetting(SettingsAttribute):
    """A test storage attribute whose saving always fails."""


class FailingSaveSerializer(SettingsBaseSerializer):
    """A test storage serializer: save raises a plain error."""

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        raise RuntimeError("save exploded")

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: a test storage never deletes."""

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return False


class FailingSavePlugin(SettingsBasePlugin):
    """A test storage plugin binding the failing-save pair."""

    binding = AttributeSerializerBinding(FailingSaveSetting, FailingSaveSerializer)

    @property
    def plugin_name(self) -> str:
        return "MatrixFailingSave"


LibraryConfiguration.register_settings_plugin(FailingSavePlugin)


def failing_save_setting(**kwargs: Any) -> Any:
    return FailingSaveSetting(**kwargs)


class BlockingSaveSetting(SettingsAttribute):
    """A test storage attribute whose saving blocks with a user-facing error."""


class BlockingSaveSerializer(SettingsBaseSerializer):
    """A test storage serializer: save raises a condition the user must see."""

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        raise UserFacingError(OSError("disk full"))

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: a test storage never deletes."""

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return False


class BlockingSavePlugin(SettingsBasePlugin):
    """A test storage plugin binding the blocking-save pair."""

    binding = AttributeSerializerBinding(BlockingSaveSetting, BlockingSaveSerializer)

    @property
    def plugin_name(self) -> str:
        return "MatrixBlockingSave"


LibraryConfiguration.register_settings_plugin(BlockingSavePlugin)


def blocking_save_setting(**kwargs: Any) -> Any:
    return BlockingSaveSetting(**kwargs)


# ---------------------------------------------------------------------------
# A. Member states: a default, no default, REQUIRED
# ---------------------------------------------------------------------------


def test_a1_default_is_converted_before_any_load():
    class S(Settings):
        retries: int = non_storage_setting(default="8080")

    assert S.retries == 8080
    assert isinstance(S.retries, int)


def test_a2_member_without_default_serves_none_and_never_aborts(monkeypatch):
    monkeypatch.delenv("MTX_A2_PLAIN", raising=False)

    class S(Settings):
        plain: str = environment_variable_setting(name="MTX_A2_PLAIN")

    report = S.load_settings()

    assert S.plain is None
    assert report == ()


def test_a3_required_missing_aborts_the_load(monkeypatch):
    monkeypatch.delenv("MTX_A3_TOKEN", raising=False)

    class S(Settings):
        token: str = environment_variable_setting(name="MTX_A3_TOKEN", default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, MissingValueError)
    text = str(error)
    assert "token" in text and "MTX_A3_TOKEN" in text and "S" in text


def test_a4_reading_a_never_loaded_required_member_raises():
    class S(Settings):
        token: str = environment_variable_setting(name="MTX_A4_TOKEN", default=REQUIRED)

    with pytest.raises(MemberLoadError, match="token.*is required"):
        _ = S.token


def test_a5_required_with_a_value_loads_cleanly(monkeypatch):
    monkeypatch.setenv("MTX_A5_TOKEN", "s3cret")

    class S(Settings):
        token: str = environment_variable_setting(name="MTX_A5_TOKEN", default=REQUIRED)

    report = S.load_settings()

    assert report == ()
    assert S.token == "s3cret"


def test_a6_mutable_default_is_never_shared():
    class S(Settings):
        items: List[int] = non_storage_setting(default=[])

    first = S.items
    first.append(1)
    second = S.items

    assert S.items == []
    assert first is not second


def test_a7_json_null_is_a_value_a_missing_key_is_not(tmp_path):
    path = tmp_path / "a7.json"
    path.write_text('{"present": null}', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        present: Optional[int] = json_setting(name="present", default=7)
        absent: int = json_setting(name="absent", default=8)

    S.load_settings()

    assert S.present is None
    assert S.absent == 8


def test_a8_constraint_rejecting_the_none_stand_in_fails_the_class():
    with pytest.raises(TypeError, match="member"):

        class S(Settings):
            member: int = environment_variable_setting(name="MTX_A8_MEMBER", eq=5)


# ---------------------------------------------------------------------------
# B. Declaration errors: the class statement itself
# ---------------------------------------------------------------------------


def test_b1_unconvertible_default_fails_the_class_statement():
    with pytest.raises(TypeError, match="born"):

        class S(Settings):
            born: date = non_storage_setting(default="not-a-date")


def test_b2_bool_default_on_an_int_member_fails():
    with pytest.raises(TypeError):

        class S(Settings):
            count: int = non_storage_setting(default=True)


def test_b3_custom_class_default_is_checked_with_isinstance():
    with pytest.raises(TypeError):

        class S(Settings):
            endpoint: MatrixEndpoint = non_storage_setting(default="https://x")


def test_b4_regex_that_does_not_compile_fails_the_declaration():
    with pytest.raises(ValueError):

        class S(Settings):
            code: str = non_storage_setting(default="code", regex="(")


def test_b5_bad_validator_and_mixed_constraint_kinds_fail():
    with pytest.raises(TypeError):

        class S1(Settings):
            count: int = non_storage_setting(default=1, validator=5)

    with pytest.raises(TypeError):

        class S2(Settings):
            count: int = non_storage_setting(default=5, gt=1, min_length=1)


def test_b6_option_key_declared_on_both_sides_fails_the_class_statement():
    with pytest.raises(TypeError):

        class S(
            Settings,
            options={"shared": 1},
        ):
            class_metadata = {"shared": 2}

            count: int = non_storage_setting(default=1)


def test_b7_attribute_without_a_registered_plugin_names_the_fix():
    class OrphanSetting(SettingsAttribute):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    def orphan_setting(**kwargs: Any) -> Any:
        return OrphanSetting(**kwargs)

    class S(Settings):
        count: int = orphan_setting(default=1)

    with pytest.raises(PluginNotEnabledError, match="serializer"):
        S.load_settings()


def test_b8_default_state_violating_a_cross_rule_fails_the_class():
    with pytest.raises(TypeError):

        class S(Settings):
            min_port: int = non_storage_setting(default=1024)
            max_port: int = non_storage_setting(default=80, ge=min_port)


def test_b9_a_plain_member_without_a_source_fails_the_class_statement():
    # a bare annotation is a member now, and a member needs a storage to
    # read: the class statement says so, naming the member
    with pytest.raises(
        TypeError,
        match="Orphan.token is a plain member, but the class declares no source",
    ):

        class Orphan(Settings):
            token: str


def test_b10_a_plain_member_between_two_sources_fails_the_class_statement():
    # two storages leave the member's storage a guess; the error names the
    # sources and the way out — a family factory picks the storage
    with pytest.raises(
        TypeError,
        match="TwoSources.token is a plain member, but the class declares 2 sources "
        "\\(JSONSetting, EnvironmentVariableSetting\\). To choose its storage, declare the "
        "member through a family factory",
    ):

        class TwoSources(
            Settings,
            options=(json_source(file="a.json"), env_source(name_prefix="A_")),
        ):
            token: str


def test_b11_two_builders_of_one_family_fail_the_class_statement():
    # the family's source seat is one: a second builder of the same family
    # is a metadata name declared twice, the existing rule's refusal
    with pytest.raises(TypeError, match="more than once in options="):

        class Dup(
            Settings,
            options=(json_source(file="a.json"), json_source(file="b.json")),
        ):
            token: str = json_setting(default="x")


# ---------------------------------------------------------------------------
# C. Loading: environment variables
# ---------------------------------------------------------------------------


def test_c1_c2_name_building_and_the_explicit_escape_hatch(monkeypatch):
    monkeypatch.setenv("legacy_flag", "on")
    monkeypatch.setenv("MTX_C1_MODE", "debug")

    class S(
        Settings,
        options=env_source(name_prefix="MTX_C1_", name_case=NameCase.UPPER),
    ):
        legacy: str = environment_variable_setting(name="legacy_flag", default="off")
        mode: str = environment_variable_setting(default="production")

    S.load_settings()

    assert S.legacy == "on"
    assert S.mode == "debug"


def test_c3_nested_delimiter_updates_the_dataclass_partially(monkeypatch):
    monkeypatch.setenv("MTX_DB__PORT", "6543")

    class S(
        Settings,
        options=env_source(name_prefix="MTX_", name_case=NameCase.UPPER, nested_delimiter="__"),
    ):
        db: DbConfig = environment_variable_setting(default=DbConfig(host="db.local"))

    S.load_settings()

    assert S.db == DbConfig(host="db.local", port=6543)


def test_c4_field_variable_wins_over_the_object_form(monkeypatch):
    monkeypatch.setenv("MTX_DB", '{"host": "h1", "port": 1}')
    monkeypatch.setenv("MTX_DB__PORT", "2")

    class S(
        Settings,
        options=env_source(name_prefix="MTX_", name_case=NameCase.UPPER, nested_delimiter="__"),
    ):
        db: DbConfig = environment_variable_setting(default=DbConfig())

    S.load_settings()

    assert S.db == DbConfig(host="h1", port=2)


def test_c5_saving_none_removes_the_variable(monkeypatch):
    monkeypatch.setenv("MTX_C5_HINT", "old")

    class S(Settings):
        hint: Optional[str] = environment_variable_setting(name="MTX_C5_HINT", default=None)

    S.load_settings()
    S.hint = None
    S.save_setting(lambda s: s.hint)

    assert "MTX_C5_HINT" not in os.environ


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("yes", True),
        ("on", True),
        ("1", True),
        ("TRUE", True),
        ("no", False),
        ("off", False),
        ("0", False),
        ("False", False),
    ],
)
def test_c6_bool_string_forms(raw: str, expected: bool, monkeypatch):
    monkeypatch.setenv("MTX_C6_FLAG", raw)

    class S(Settings):
        flag: bool = environment_variable_setting(name="MTX_C6_FLAG", default=not expected)

    S.load_settings()

    assert S.flag is expected


def test_c7_empty_string_is_a_value_for_str_but_not_for_int(monkeypatch, caplog):
    monkeypatch.setenv("MTX_C7_TEXT", "")
    monkeypatch.setenv("MTX_C7_COUNT", "")

    class S(Settings):
        text: str = environment_variable_setting(name="MTX_C7_TEXT", default="fallback")
        count: int = environment_variable_setting(name="MTX_C7_COUNT", default=5)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = S.load_settings()

    assert S.text == ""
    assert S.count == 5
    (entry,) = report
    assert isinstance(entry, ConversionError)
    assert fallback_warning(caplog, "count")


def test_c8_any_case_lookup_accepts_any_spelling(monkeypatch):
    monkeypatch.setenv("MTX_C8_MODE", "staging")
    monkeypatch.setenv("mtx_c8_legacy", "on")

    class S(
        Settings,
        options=env_source(name_prefix="MTX_C8_", name_case=NameCase.ANY),
    ):
        mode: str = environment_variable_setting(default="production")
        legacy: str = environment_variable_setting(name="MTX_C8_LEGACY", default="off")

    S.load_settings()

    # the built name and the explicit one alike resolve case-insensitively
    assert S.mode == "staging"
    assert S.legacy == "on"


def test_c9_any_case_two_folded_spellings_fail_the_load(monkeypatch):
    monkeypatch.setenv("MTX_C9_MODE", "one")
    monkeypatch.setenv("Mtx_C9_Mode", "two")

    class S(
        Settings,
        options=env_source(name_prefix="MTX_C9_", name_case=NameCase.ANY),
    ):
        mode: str = environment_variable_setting(default="production")

    with pytest.raises(ValueError, match="two differently-cased spellings"):
        S.load_settings()


# ---------------------------------------------------------------------------
# D. Loading: the JSON file backend
# ---------------------------------------------------------------------------


def test_d1_missing_file_serves_defaults(tmp_path):
    path = tmp_path / "absent.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="localhost")

    report = S.load_settings()

    assert report == ()
    assert S.host == "localhost"


def test_d2_corrupt_file_aborts_the_pass_and_keeps_values(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("{not json", encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        first: int = json_setting(name="first", default=1)
        second: int = json_setting(name="second", default=2)

    S.first = 99
    with pytest.raises(ValueError, match="cannot parse the JSON settings file"):
        S.load_settings()

    assert S.first == 99
    assert S.second == 2


def test_d3_unconfigured_file_path_names_the_parameters(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)

    class S(Settings):
        host: str = json_setting(default="localhost")

    with pytest.raises(ValueError, match="file_path"):
        S.load_settings()


def test_d4_array_path_pads_with_nulls(tmp_path):
    path = tmp_path / "a4.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        region: str = json_setting(name="region", path="/replicas/1", default="eu")

    S.save_settings()

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["replicas"] == [None, {"region": "eu"}]


def test_d5_unknown_keys_are_preserved(tmp_path):
    path = tmp_path / "a5.json"
    path.write_text('{"foreign": 1, "known": 5}', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        known: int = json_setting(name="known", default=0)

    S.load_settings()
    assert S.known == 5

    S.known = 6
    S.save_settings()

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {"foreign": 1, "known": 6}


def test_d6_save_settings_writes_every_member_into_one_document(tmp_path):
    path = tmp_path / "a6.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="localhost")
        port: int = json_setting(name="port", default=8080)

    S.save_settings()

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {"host": "localhost", "port": 8080}


def test_d7_path_segment_with_a_dot_names_an_object_key(tmp_path):
    path = tmp_path / "a7.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        api: str = json_setting(name="api", path="/endpoints/api.internal", default="")

    S.save_settings()

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {"endpoints": {"api.internal": {"api": ""}}}


def test_d8_save_keeps_the_files_key_order(tmp_path):
    path = tmp_path / "a8.json"
    path.write_text('{"zebra": 1, "known": 5}', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        known: int = json_setting(name="known", default=0)
        added: str = json_setting(name="added", default="x")

    S.load_settings()
    S.known = 6
    S.save_settings()

    assert list(json.loads(path.read_text(encoding="utf-8"))) == ["zebra", "known", "added"]


def test_d9_save_keeps_the_files_indent(tmp_path):
    path = tmp_path / "a9.json"
    path.write_text('{\n    "known": 5\n}\n', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        known: int = json_setting(name="known", default=0)
        added: str = json_setting(name="added", default="x")

    S.load_settings()
    S.known = 6
    S.save_settings()

    assert path.read_text(encoding="utf-8") == '{\n    "known": 6,\n    "added": "x"\n}\n'


def test_d10_save_keeps_the_files_raw_non_ascii(tmp_path):
    path = tmp_path / "a10.json"
    path.write_text('{\n  "host": "пример.local"\n}\n', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="")

    S.load_settings()
    S.host = "другой"
    S.save_settings()

    assert path.read_text(encoding="utf-8") == '{\n  "host": "другой"\n}\n'


def test_d11_save_keeps_the_files_bom(tmp_path):
    path = tmp_path / "a11.json"
    path.write_bytes(UTF8_BOM.encode("utf-8") + b'{\n  "host": "ok"\n}\n')

    class S(
        Settings,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="")

    S.load_settings()
    S.host = "new"
    S.save_settings()

    assert path.read_bytes() == UTF8_BOM.encode("utf-8") + b'{\n  "host": "new"\n}\n'


def test_d12_undecodable_file_names_itself(tmp_path):
    path = tmp_path / "a12.json"
    path.write_bytes('{\n  "host": "ok"\n}\n'.encode("utf-16"))

    class S(
        Settings,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="fallback")

    with pytest.raises(ValueError, match="cannot read the JSON settings file"):
        S.load_settings()


def test_d13_save_keeps_the_files_crlf(tmp_path):
    path = tmp_path / "a13.json"
    path.write_bytes(b'{\r\n  "known": 5\r\n}\r\n')

    class S(
        Settings,
        options=json_source(file=path),
    ):
        known: int = json_setting(name="known", default=0)
        added: str = json_setting(name="added", default="x")

    S.load_settings()
    S.known = 6
    S.save_settings()

    assert path.read_bytes() == b'{\r\n  "known": 6,\r\n  "added": "x"\r\n}\r\n'


def test_d14_save_keeps_the_files_permission_mode(tmp_path):
    path = tmp_path / "a14.json"
    path.write_text('{"known": 5}\n', encoding="utf-8")
    path.chmod(0o600)

    class S(
        Settings,
        options=json_source(file=path),
    ):
        known: int = json_setting(name="known", default=0)

    S.load_settings()
    S.known = 6
    S.save_settings()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


# ---------------------------------------------------------------------------
# E. Load failures: the abort channel and the report channel
# ---------------------------------------------------------------------------


def test_e1_optional_unconvertible_falls_back_with_a_report(monkeypatch, caplog):
    monkeypatch.setenv("MTX_E1_COUNT", "abc")

    class S(Settings):
        count: int = environment_variable_setting(name="MTX_E1_COUNT", default=5)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = S.load_settings()

    assert S.count == 5
    (entry,) = report
    assert isinstance(entry, ConversionError)
    assert "MTX_E1_COUNT" in str(entry)
    assert "cannot convert" in str(entry)
    assert fallback_warning(caplog, "count")


def test_e2_required_unconvertible_aborts(monkeypatch):
    monkeypatch.setenv("MTX_E2_COUNT", "abc")

    class S(Settings):
        count: int = environment_variable_setting(name="MTX_E2_COUNT", default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)


def test_e3_constraint_violation_splits_by_channel(monkeypatch, caplog):
    monkeypatch.setenv("MTX_E3_OPT", "0")
    monkeypatch.setenv("MTX_E3_REQ", "0")

    class S(Settings):
        opt: int = environment_variable_setting(name="MTX_E3_OPT", default=7, ge=1)
        req: int = environment_variable_setting(name="MTX_E3_REQ", default=REQUIRED, ge=1)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            S.load_settings()

    assert S.opt == 7
    (fallback,) = info.value.fallbacks
    assert isinstance(fallback, ConstraintViolationError)
    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert fallback_warning(caplog, "opt")


def test_e4_source_failure_for_a_required_member(monkeypatch):
    monkeypatch.delenv("MTX_E4", raising=False)

    class S(Settings):
        member: int = exploding_setting(default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, SourceLoadError)


def test_e5_one_run_reports_errors_and_fallbacks_apart(monkeypatch):
    monkeypatch.delenv("MTX_E5_REQ", raising=False)
    monkeypatch.setenv("MTX_E5_OPT", "abc")

    class S(Settings):
        req: int = environment_variable_setting(name="MTX_E5_REQ", default=REQUIRED)
        opt: int = environment_variable_setting(name="MTX_E5_OPT", default=3)

    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()

    (error,) = info.value.errors
    (fallback,) = info.value.fallbacks
    assert isinstance(error, MissingValueError)
    assert isinstance(fallback, ConversionError)


def test_e6_clean_load_returns_an_empty_report_and_stays_silent(caplog):
    class S(Settings):
        member: int = non_storage_setting(default=1)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = S.load_settings()

    assert report == ()
    assert not report
    # a clean load is nobody's news: no warning is issued
    assert not caplog.records


def test_e7_load_errors_share_the_valueerror_root():
    family = (
        MissingValueError,
        ConversionError,
        SourceLoadError,
        AggregateLoadError,
    )
    for error_type in family:
        assert issubclass(error_type, MemberLoadError)
    assert issubclass(MemberLoadError, ValueError)

    class S(Settings):
        member: int = exploding_setting(default=REQUIRED)

    # one except clause catches the whole family
    with pytest.raises(ValueError):
        S.load_settings()


def test_e8_single_setting_load_reports_nothing_when_nothing_fell_back(monkeypatch):
    monkeypatch.setenv("MTX_E8_MODE", "from-env")

    class S(Settings):
        mode: str = environment_variable_setting(name="MTX_E8_MODE", default="default-mode")

    # a loaded value is no news: None, like the empty report of a clean pass
    assert S.load_setting("mode") is None
    assert S.mode == "from-env"

    # a miss is the default's normal way of happening: None as well
    monkeypatch.delenv("MTX_E8_MODE", raising=False)
    assert S.load_setting("mode") is None
    assert S.mode == "default-mode"


def test_e9_single_setting_load_reports_the_fallback(monkeypatch, caplog):
    monkeypatch.setenv("MTX_E9_COUNT", "abc")
    monkeypatch.setenv("MTX_E9_RATE", "0")

    class S(Settings):
        count: int = environment_variable_setting(name="MTX_E9_COUNT", default=5)
        rate: int = environment_variable_setting(name="MTX_E9_RATE", default=9, ge=1)
        port: int = exploding_setting(default=8080)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        conversion = S.load_setting("count")
        violation = S.load_setting("rate")
        source = S.load_setting("port")

    assert S.count == 5
    assert S.rate == 9
    assert S.port == 8080
    # every fallback reason reports the same entry the class pass would
    assert isinstance(conversion, ConversionError)
    assert isinstance(violation, ConstraintViolationError)
    assert isinstance(source, SourceLoadError)
    for entry in (conversion, violation, source):
        assert "fell back to its default" in str(entry)


def test_e10_single_setting_load_of_a_required_member_raises(monkeypatch):
    monkeypatch.delenv("MTX_E10_TOKEN", raising=False)

    class S(Settings):
        token: str = environment_variable_setting(name="MTX_E10_TOKEN", default=REQUIRED)

    # no aggregate rides a single member: the member's own error surfaces
    with pytest.raises(MemberLoadError) as info:
        S.load_setting("token")

    assert info.value.member_name == "token"


# ---------------------------------------------------------------------------
# F. Conversion
# ---------------------------------------------------------------------------


def test_f1_value_types_survive_the_round_trip(tmp_path):
    path = tmp_path / "f1.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        ttl: timedelta = json_setting(default="0:30:00")
        amount: Decimal = json_setting(default="1.5")
        tag: uuid.UUID = json_setting(default="12345678-1234-5678-1234-567812345678")
        home: Path = json_setting(default="/tmp")
        shade: Color = json_setting(default=Color.RED)
        counts: List[int] = json_setting(default=[1, 2])

    S.ttl = timedelta(seconds=5400)
    S.amount = Decimal("2.5")
    S.tag = uuid.UUID("87654321-4321-8765-4321-210987654321")
    S.home = Path("/tmp/matrix")
    S.shade = Color.BLUE
    S.counts = [3, 4]

    S.save_settings()
    S.load_settings()

    assert S.ttl == timedelta(seconds=5400)
    assert isinstance(S.ttl, timedelta)
    assert S.amount == Decimal("2.5")
    assert isinstance(S.amount, Decimal)
    assert S.tag == uuid.UUID("87654321-4321-8765-4321-210987654321")
    assert S.home == Path("/tmp/matrix")
    assert S.shade is Color.BLUE
    assert S.counts == [3, 4]


def test_f2_update_from_dict_conversion_failure_applies_nothing():
    class S(Settings):
        count: int = non_storage_setting(default=5)
        text: str = non_storage_setting(default="keep")

    with pytest.raises(ValueError, match="abc"):
        S.update_from_dict({"count": "abc", "text": "new"})

    assert S.count == 5
    assert S.text == "keep"


def test_f3_constraint_reports_mask_the_secret(monkeypatch):
    monkeypatch.setenv("MTX_F3_TOKEN", "abcd")

    class S(Settings):
        token: SecretStr = environment_variable_setting(
            name="MTX_F3_TOKEN", default=REQUIRED, min_length=5
        )

    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    # the payload itself never appears; the message quotes the constraint,
    # not the value
    assert "abcd" not in str(error)


def test_f4_true_is_not_an_int():
    class S(Settings):
        count: int = non_storage_setting(default=5)

    with pytest.raises(ValueError):
        S.update_from_dict({"count": True})

    assert S.count == 5


def test_f5_dataclass_storage_tolerates_missing_and_extra_fields(tmp_path):
    path = tmp_path / "f5.json"
    path.write_text('{"proxy": {"host": "h", "unknown": 1}}', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        proxy: Proxy = json_setting(name="proxy", default=Proxy(host="seed"))

    S.load_settings()

    assert S.proxy == Proxy(host="h")


# ---------------------------------------------------------------------------
# G. Constraints and cross-member rules
# ---------------------------------------------------------------------------


def test_g1_invalid_assignment_never_reaches_the_storage():
    class S(Settings):
        port: int = non_storage_setting(default=80, le=65535)

    with pytest.raises(SettingValidationError):
        S.port = 70000

    assert S.port == 80


def test_g2_save_settings_checks_the_whole_class_first(tmp_path):
    path = tmp_path / "g2.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        min_port: int = json_setting(name="min_port", default=1024)
        max_port: int = json_setting(name="max_port", default=65535, ge=min_port)

    S.max_port = 80  # valid alone; the pair is inconsistent
    with pytest.raises(SettingValidationError):
        S.save_settings()

    assert not path.exists()


def test_g3_single_setting_save_runs_no_cross_checks(tmp_path):
    # the cross-member rules run at the whole-class checkpoints alone:
    # a single-setting save writes the member even when the pair it
    # belongs to is inconsistent — the next load settles it (see g5)
    path = tmp_path / "g3.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        min_port: int = json_setting(name="min_port", default=1024)
        max_port: int = json_setting(name="max_port", default=65535, ge=min_port)

    S.max_port = 80  # valid alone; the pair is inconsistent
    S.save_setting(lambda s: s.max_port)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {"max_port": 80}


def test_g4_validate_settings_collects_problems_and_changes_nothing():
    class S(Settings):
        min_port: int = non_storage_setting(default=1024)
        max_port: int = non_storage_setting(default=65535, ge=min_port)

    S.max_port = 80
    with pytest.raises(SettingValidationError) as info:
        S.validate_settings()

    assert info.value.problems
    assert S.max_port == 80


def test_g5_cross_rule_violation_on_load_resets_the_participants(tmp_path, caplog):
    path = tmp_path / "g5.json"
    path.write_text('{"min_port": 2000, "max_port": 1000}', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        min_port: int = json_setting(name="min_port", default=1024)
        max_port: int = json_setting(name="max_port", default=65535, ge=min_port)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = S.load_settings()

    assert S.min_port == 1024
    assert S.max_port == 65535
    assert report
    assert any(
        "resetting the members to their defaults" in record.getMessage()
        for record in caplog.records
    )


def test_g6_when_gates_the_constraints():
    class S(Settings):
        ssl: bool = non_storage_setting(default=False)
        port: int = non_storage_setting(default=80, eq=443, when=ssl)

    assert S.port == 80  # ssl is off: eq does not apply

    S.ssl = True
    with pytest.raises(SettingValidationError):
        S.validate_settings()

    S.port = 443
    S.validate_settings()  # the pair is consistent again


def test_g7_validate_hook_reports_and_must_return_a_dict():
    class S(Settings):
        mode: str = non_storage_setting(default="dev")
        ssl: Optional[str] = non_storage_setting(default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    S.mode = "prod"
    with pytest.raises(SettingValidationError) as info:
        S.validate_settings()

    assert "ssl" in info.value.problems

    class Broken(Settings):
        member: int = non_storage_setting(default=1)

        def __validate__(self) -> Any:
            return "not a dict"

    with pytest.raises(TypeError, match="must return a dict"):
        Broken.validate_settings()


def test_g8_validator_bugs_propagate_as_is(monkeypatch, caplog):
    def no_zero(value: int) -> bool:
        if value == 0:
            raise RuntimeError("validator bug")
        return value > 0

    class S(Settings):
        count: int = non_storage_setting(default=1, validator=no_zero)

    with pytest.raises(RuntimeError, match="validator bug"):
        S.count = 0

    assert S.count == 1

    # the load crash leaves an ERROR record before the exception flies:
    # the bug stays visible in the log even where the traceback is swallowed
    class Loaded(Settings):
        enabled: bool = environment_variable_setting(name="MTX_G8_ENABLED", default=False)
        count: int = environment_variable_setting(
            name="MTX_G8_COUNT", default=1, validator=no_zero, when=enabled
        )

    monkeypatch.setenv("MTX_G8_ENABLED", "1")
    monkeypatch.setenv("MTX_G8_COUNT", "0")
    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        with pytest.raises(RuntimeError, match="validator bug"):
            Loaded.load_settings()

    assert "validation exception for setting 'count': validator bug" in [
        record.getMessage() for record in caplog.records
    ]


def test_g9_hook_finding_no_reset_settles_aborts_the_load(monkeypatch, caplog):
    # the load channel: the finding names a member already at its
    # default, no reset can settle it, and the pass aborts — a completed
    # load is either consistent or did not complete
    monkeypatch.setenv("MTX_G9_MODE", "prod")

    class S(Settings):
        mode: str = environment_variable_setting(name="MTX_G9_MODE", default="dev")
        ssl: Optional[str] = environment_variable_setting(name="MTX_G9_SSL", default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            S.load_settings()

    (entry,) = info.value.errors
    assert isinstance(entry, ConstraintViolationError)
    assert "no reset to the declared defaults settles it" in str(entry)
    # the failed pass touched nothing: the class keeps the declared defaults
    assert S.mode == "dev"
    assert S.ssl is None
    assert any("the pass is aborted" in record.getMessage() for record in caplog.records)


def test_g10_hook_finding_resets_the_named_loaded_member(monkeypatch, caplog):
    # the member the hook names takes the reset when it holds a loaded
    # value; the members the hook merely read keep theirs
    monkeypatch.setenv("MTX_G10_SSL", "set")

    class S(Settings):
        mode: str = non_storage_setting(default="dev")
        ssl: Optional[str] = environment_variable_setting(name="MTX_G10_SSL", default=None)

        def __validate__(self) -> dict:
            if self.ssl is not None:
                return {"ssl": "ssl must stay empty"}
            return {}

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = S.load_settings()

    (entry,) = report
    assert isinstance(entry, ConstraintViolationError)
    assert S.ssl is None
    assert S.mode == "dev"
    assert any(
        "resetting the members to their defaults" in record.getMessage()
        for record in caplog.records
    )


def test_g11_hook_gates_bulk_updates():
    class S(Settings):
        mode: str = non_storage_setting(default="dev")
        ssl: Optional[str] = non_storage_setting(default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    with pytest.raises(SettingValidationError) as info:
        S.update_from_dict({"mode": "prod"})

    assert info.value.problems
    assert S.mode == "dev"  # rejected: nothing applied


def test_g12_hook_gates_the_whole_class_save(tmp_path):
    path = tmp_path / "g12.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        mode: str = json_setting(name="mode", default="dev")
        ssl: Optional[str] = json_setting(name="ssl", default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    S.mode = "prod"  # a single assignment runs no cross checks
    with pytest.raises(SettingValidationError):
        S.save_settings()

    assert not path.exists()


def test_g13_the_hook_does_not_run_at_class_creation():
    # the class statement checks the declared defaults against the
    # comparison rules alone; the README's five-point wording overstates
    # the hook's reach — it joins from the first load on (tour finding)
    class S(Settings):
        mode: str = non_storage_setting(default="prod")
        ssl: Optional[str] = non_storage_setting(default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    # created without an error, the all-default state violating the hook
    assert S.mode == "prod"
    assert S.ssl is None


def test_g14_hook_exceptions_propagate_as_is():
    # an exception the hook body raises is a bug in user code, not a
    # finding: every checkpoint lets it through unchanged, and the class
    # keeps the values it held
    class S(Settings):
        mode: str = non_storage_setting(default="dev")

        def __validate__(self) -> dict:
            raise ZeroDivisionError("hook bug")

    with pytest.raises(ZeroDivisionError, match="hook bug"):
        S.validate_settings()
    with pytest.raises(ZeroDivisionError, match="hook bug"):
        S.update_from_dict({"mode": "prod"})
    assert S.mode == "dev"


def test_g15_hook_reading_a_valueless_member_is_a_finding_everywhere(monkeypatch):
    monkeypatch.delenv("MTX_G15_TOKEN", raising=False)

    # reading a required member that holds no value is a property of the
    # values, not a bug in the hook: the reading is that member's finding
    # — a problem line of SettingValidationError at the strict
    # checkpoints, an entry of the load abort at load
    class S(Settings):
        mode: str = non_storage_setting(default="dev")
        token: str = environment_variable_setting(name="MTX_G15_TOKEN", default=REQUIRED)

        def __validate__(self) -> dict:
            _ = self.token
            return {}

    with pytest.raises(SettingValidationError) as info:
        S.validate_settings()

    assert info.value.problems == {
        "token": ["no loaded value to read; the __validate__ hook read the member"]
    }
    with pytest.raises(SettingValidationError, match="no loaded value to read"):
        S.update_from_dict({"mode": "prod"})
    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()

    # the abort carries the member's own miss and the hook's read beside
    # each other, and the failed pass leaves the class as it was
    miss, finding = info.value.errors
    assert isinstance(miss, MissingValueError)
    assert isinstance(finding, ConstraintViolationError)
    assert "no loaded value to read" in str(finding)
    assert S.mode == "dev"


def test_g16_a_hook_finding_that_survives_its_reset_aborts_the_load(monkeypatch, caplog):
    # the reset of the named member happens, the finding comes back —
    # the reset settled nothing, so the pass aborts and the class keeps
    # the state it had
    monkeypatch.setenv("MTX_G16_MODE", "prod")
    monkeypatch.setenv("MTX_G16_SSL", "maybe")

    class S(Settings):
        mode: str = environment_variable_setting(name="MTX_G16_MODE", default="dev")
        ssl: str = environment_variable_setting(name="MTX_G16_SSL", default="none")

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl != "on":
                return {"ssl": "ssl must be 'on' in production mode"}
            return {}

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            S.load_settings()

    (entry,) = info.value.errors
    assert isinstance(entry, ConstraintViolationError)
    assert "no reset to the declared defaults settles it" in str(entry)
    assert S.mode == "dev"
    assert S.ssl == "none"
    messages = [record.getMessage() for record in caplog.records]
    assert any("resetting the members to their defaults: ssl" in m for m in messages)
    assert any("the pass is aborted" in m for m in messages)


def test_g17_a_required_participant_no_reset_reaches_aborts_the_load(monkeypatch, caplog):
    # the declared rule binds ceil to the required floor; floor holds
    # its loaded value with no default to reset to, and ceil already
    # stands at its default — the pass cannot settle the rule and aborts
    monkeypatch.setenv("MTX_G17_FLOOR", "5000")
    monkeypatch.setenv("MTX_G17_CEIL", "100")

    class S(Settings):
        floor: int = environment_variable_setting(name="MTX_G17_FLOOR", default=REQUIRED)
        ceil: int = environment_variable_setting(name="MTX_G17_CEIL", default=100, ge=floor)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            S.load_settings()

    (entry,) = info.value.errors
    assert isinstance(entry, ConstraintViolationError)
    assert str(entry).startswith("setting 'ceil' of 'S' violates its constraints")
    assert "no reset to the declared defaults settles it" in str(entry)
    assert any("has no default to reset to" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# H. Saving and deleting
# ---------------------------------------------------------------------------


def test_h1_save_settings_writes_all_save_setting_writes_one(tmp_path):
    path = tmp_path / "h1.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        first: int = json_setting(name="first", default=1)
        second: int = json_setting(name="second", default=2)

    S.save_setting(lambda s: s.first)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {"first": 1}

    S.save_settings()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {"first": 1, "second": 2}


def test_h2_delete_restores_the_default_and_clears_the_storage(tmp_path):
    path = tmp_path / "h2.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        member: int = json_setting(name="member", default=7)

    S.member = 9
    S.save_settings()
    assert S.contains_setting("member")

    S.delete_setting(lambda s: s.member)

    assert not S.contains_setting("member")
    assert S.member == 7


def test_h3_reset_settings_resets_every_member():
    class S(Settings):
        first: int = non_storage_setting(default=1)
        second: str = non_storage_setting(default="x")

    S.first = 5
    S.second = "y"
    S.reset_settings()

    assert S.first == 1
    assert S.second == "x"


def test_h4_dotenv_preserves_comments_and_foreign_variables(tmp_path):
    env_path = tmp_path / "team.env"
    env_path.write_text("# team comment\nexport FOREIGN=keep\nMTX_H4_MODE=old\n", encoding="utf-8")

    class S(
        Settings,
        options=dotenv_source(file=env_path),
    ):
        mode: str = dotenv_setting(name="MTX_H4_MODE", default="production")

    S.load_settings()
    assert S.mode == "old"

    S.mode = "new"
    S.save_settings()

    text = env_path.read_text(encoding="utf-8")
    assert "# team comment" in text
    assert "FOREIGN=keep" in text
    # python-dotenv rewrites the member's line and quotes the value
    assert "MTX_H4_MODE='new'" in text


def test_h5_single_setting_write_failures_follow_the_class_policy(caplog):
    # the narrow write paths follow the write directions' policy: a
    # plain storage error is an ERROR record and a skipped operation, a
    # user-facing one arrives unwrapped into the inner exception, and
    # the probe has no soft answer at all
    class S(Settings):
        member: str = write_exploding_setting(default="v")

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        S.save_setting("member")
        S.delete_setting("member")

    assert [record.getMessage() for record in caplog.records] == [
        "save exception for setting 'member': write exploded",
        "delete exception for setting 'member': delete exploded",
    ]
    with pytest.raises(ValueError, match="probe inner") as info:
        S.contains_setting("member")
    assert isinstance(info.value.__cause__, UserFacingError)


def test_h6_default_reset_clears_a_required_member(monkeypatch):
    monkeypatch.setenv("MTX_H6_TOKEN", "s3cret")

    class S(Settings):
        first: int = non_storage_setting(default=1)
        token: str = environment_variable_setting(name="MTX_H6_TOKEN", default=REQUIRED)
        last: int = non_storage_setting(default=3)

    S.load_settings()
    S.first = 5
    S.last = 9
    S.reset_settings()

    # the members around the required one reset too, whatever the order
    assert S.first == 1
    assert S.last == 3
    with pytest.raises(MemberLoadError, match="token.*is required"):
        _ = S.token

    # the single form clears the one member the same way, and a reload
    # brings the required value back — the class stays usable
    S.load_settings()
    S.reset_setting(lambda s: s.token)
    with pytest.raises(MemberLoadError, match="token.*is required"):
        _ = S.token


def test_h7_delete_leaves_a_required_member_unset(monkeypatch, caplog):
    monkeypatch.setenv("MTX_H7_TOKEN", "s3cret")

    class S(Settings):
        token: str = environment_variable_setting(name="MTX_H7_TOKEN", default=REQUIRED)
        mode: str = non_storage_setting(default="on")

    S.load_settings()
    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        S.delete_settings()
        S.delete_setting(lambda s: s.token)

    assert "MTX_H7_TOKEN" not in os.environ
    # no error record: a required member has no default to serve, so the
    # reset taking it to the never-loaded state is the pass's design
    assert caplog.records == []
    with pytest.raises(MemberLoadError, match="token.*is required"):
        _ = S.token
    assert S.mode == "on"


# ---------------------------------------------------------------------------
# I. Snapshots and bulk updates
# ---------------------------------------------------------------------------


def test_i1_to_dict_hands_out_deep_copies():
    class S(Settings):
        items: List[int] = non_storage_setting(default=[1])

    snapshot = S.to_dict()
    snapshot["items"].append(99)

    assert S.items == [1]


def test_i2_update_from_dict_unknown_key_names_the_settings():
    class S(Settings):
        member: int = non_storage_setting(default=1)

    with pytest.raises(KeyError) as info:
        S.update_from_dict({"typo": 2})

    assert "member" in str(info.value)


def test_i3_updates_are_all_or_nothing():
    class S(Settings):
        first: int = non_storage_setting(default=1)
        second: int = non_storage_setting(default=2, le=10)

    with pytest.raises(SettingValidationError):
        S.update_from_dict({"first": 5, "second": 99})

    assert S.first == 1
    assert S.second == 2


def test_i4_object_snapshots_are_detached_and_validated():
    class S(Settings):
        port: int = non_storage_setting(default=80, le=65535)

    state = S.to_object()
    state.port = 8080
    assert S.port == 80

    with pytest.raises(SettingValidationError):
        state.port = 70000

    S.update_from_object(state)
    assert S.port == 8080


def test_i5_ignore_unknown_skips_foreign_keys_with_a_debug_record(caplog):
    # the update is a mutator, so a key naming no setting fails it loudly
    # by default; a dictionary from elsewhere — the model_dump() of
    # another model — passes ignore_unknown=True and the foreign keys
    # drop out with a debug record, the way the load overrides drop them
    class S(Settings):
        port: int = non_storage_setting(default=80)
        token: str = non_storage_setting(default="t")

    dump = {"port": 8080, "computed": 42}

    with pytest.raises(KeyError, match="'computed' not a setting of S"):
        S.update_from_dict(dump)

    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        S.update_from_dict(dump, ignore_unknown=True)
    assert S.port == 8080
    assert any("does not match any setting" in record.getMessage() for record in caplog.records)

    class Foreign:
        def __init__(self) -> None:
            self.token = "obj"
            self.computed = 42

    S.update_from_object(Foreign(), ignore_unknown=True)
    assert S.token == "obj"


# ---------------------------------------------------------------------------
# J. Inheritance and instances
# ---------------------------------------------------------------------------


def test_j1_subclass_loads_base_members_into_its_own_storage(monkeypatch):
    monkeypatch.setenv("MTX_J1_MODE", "env-value")

    class Base(Settings):
        mode: str = environment_variable_setting(name="MTX_J1_MODE", default="base-default")

    class Child(Base):
        extra: int = non_storage_setting(default=1)

    Child.load_settings()

    assert Child.mode == "env-value"
    assert Base.mode == "base-default"


def test_j2_subclass_options_do_not_move_inherited_names(monkeypatch):
    monkeypatch.setenv("MTX_BASE_MODE", "from-base")
    monkeypatch.setenv("MTX_CHILD_OWN", "from-child")

    class Base(
        Settings,
        options=env_source(name_prefix="MTX_BASE_", name_case=NameCase.UPPER),
    ):
        mode: str = environment_variable_setting(default="production")

    class Child(
        Base,
        options=env_source(name_prefix="MTX_CHILD_", name_case=NameCase.UPPER),
    ):
        own: str = environment_variable_setting(default="x")

    Child.load_settings()

    assert Child.mode == "from-base"
    assert Child.own == "from-child"


def test_j3_a_branch_redeclares_the_member_under_its_own_naming(monkeypatch):
    # the class options that retuned an ancestor's members are gone with
    # their helpers; a branch retunes its names by redeclaring the member
    # under its own source binding
    monkeypatch.setenv("MTX_SAFE_MODE", "safe-value")
    monkeypatch.setenv("MTX_BASE_MODE", "base-value")

    class Base(
        Settings,
        options=env_source(name_prefix="MTX_BASE_", name_case=NameCase.UPPER),
    ):
        mode: str = environment_variable_setting(default="production")

    class Branch(
        Base,
        options=env_source(name_prefix="MTX_SAFE_", name_case=NameCase.UPPER),
    ):
        mode: str = environment_variable_setting(default="production")

    Branch.load_settings()
    assert Branch.mode == "safe-value"

    Base.load_settings()
    assert Base.mode == "base-value"


def test_j4_instances_share_the_class_storage():
    class S(Settings):
        count: int = non_storage_setting(default=1)

    instance = S()
    instance.count = 7

    assert S.count == 7


# ---------------------------------------------------------------------------
# K. Metadata
# ---------------------------------------------------------------------------


def test_k1_declared_metadata_is_readable_without_runtime_calls():
    class S(Settings):
        class_metadata = {"config-version": 2}

        mode: str = non_storage_setting(default="production", metadata={"ui-label": "Mode"})

    assert S.get_setting_metadata("mode", "ui-label") == "Mode"
    assert S.get_class_all_metadata() == {"config-version": 2}


def test_k2_runtime_deleted_declared_entry_does_not_reappear():
    class S(Settings):
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode"})

    assert S.delete_setting_metadata("mode", "ui-label") is True
    assert S.get_setting_metadata("mode", "ui-label") is None


def test_k3_metadata_resolves_along_the_inheritance_chain():
    class Base(Settings):
        class_metadata = {"shared": "base"}

    class Child(Base):
        class_metadata = {"own": "child"}

    assert Child.get_class_all_metadata() == {"shared": "base", "own": "child"}
    assert Base.get_class_all_metadata() == {"shared": "base"}

    Base.set_class_metadata("runtime", 1)
    assert Child.get_class_metadata("runtime") == 1
    assert Base.get_class_metadata("runtime") == 1


# ---------------------------------------------------------------------------
# L. Dynamic settings
# ---------------------------------------------------------------------------


def test_l1_dynamic_get_setting_converts_by_the_default(tmp_path):
    path = tmp_path / "l1.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        member: int = json_setting(name="member", default=1)

    plugin = S.get_plugin(JSONDynamicSettingsPlugin)

    with pytest.raises(KeyError):
        plugin.get_setting("missing")

    plugin.set_setting("flag", True)
    assert plugin.get_setting("flag", default=False) is True

    plugin.save_settings()
    plugin.load_settings()
    assert plugin.get_setting("flag", default=False) is True


def test_l2_the_dynamic_collection_is_dict_like(tmp_path):
    path = tmp_path / "l2.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        member: int = json_setting(name="member", default=1)

    plugin = S.get_plugin(JSONDynamicSettingsPlugin)

    plugin.set_setting("first", 1)
    plugin.set_setting("second", 2)

    assert len(plugin) == 2
    assert "first" in plugin
    assert "third" not in plugin
    assert plugin.to_dict() == {"first": 1, "second": 2}


def test_l3_static_key_cannot_take_the_dynamic_section(tmp_path):
    path = tmp_path / "l3.json"

    class S(
        Settings,
        options=(json_source(file=path, dynamic_file=path)),
    ):
        member: str = json_setting(name="dynamic", default="v")

    # the reservation is enforced at the storage operation, not at the
    # class statement
    with pytest.raises(ValueError, match="reserved"):
        S.save_settings()


def test_l4_toml_dynamic_entries_live_beside_the_static_and_none_drops(tmp_path):
    path = tmp_path / "l4.toml"

    class S(
        Settings,
        options=(toml_source(file=path, dynamic_file=path)),
    ):
        member: int = toml_setting(name="member", default=1)

    plugin = S.get_plugin(TOMLDynamicSettingsPlugin)
    plugin.set_setting("flag", True)
    S.save_settings()
    plugin.save_settings()

    document = tomllib.loads(path.read_text(encoding="utf-8"))
    assert document["member"] == 1
    # the class part of the section nests by its dots: the entries sit at
    # [dynamic.<module>.<class>]
    entries = document["dynamic"]
    for level in S.__module__.split(".") + [S.__name__]:
        entries = entries[level]
    assert entries == {"flag": True}

    # TOML has no null: saving None removes the entry, and the emptied
    # section goes with it
    plugin.set_setting("flag", None)
    plugin.save_settings()
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"member": 1}


# ---------------------------------------------------------------------------
# M. Message completeness: the context every diagnostic carries
# ---------------------------------------------------------------------------


def test_m1_env_conversion_entry_and_log_name_everything(monkeypatch, caplog):
    monkeypatch.setenv("MTX_M1_RETRY_COUNT", "abc")

    class MatrixMsgSettings(Settings):
        retry_count: int = environment_variable_setting(name="MTX_M1_RETRY_COUNT", default=5)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        (entry,) = MatrixMsgSettings.load_settings()

    storage = "environment variable 'MTX_M1_RETRY_COUNT'"
    assert_diagnostic_context(
        str(entry), member="retry_count", owner="MatrixMsgSettings", storage=storage
    )
    warning = caplog.records[0].getMessage()
    assert_diagnostic_context(
        warning, member="retry_count", owner="MatrixMsgSettings", storage=storage
    )


def test_m2_env_missing_required_names_everything(monkeypatch):
    monkeypatch.delenv("MTX_M2_API_TOKEN", raising=False)

    class MatrixMsgSettings(Settings):
        api_token: str = environment_variable_setting(name="MTX_M2_API_TOKEN", default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        MatrixMsgSettings.load_settings()

    entry_text = str(info.value.errors[0])
    assert_diagnostic_context(
        entry_text,
        member="api_token",
        owner="MatrixMsgSettings",
        storage="environment variable 'MTX_M2_API_TOKEN'",
    )
    # the aggregate's own message repeats each entry verbatim
    assert entry_text in str(info.value)


def test_m3_constraint_entry_names_everything(monkeypatch):
    monkeypatch.setenv("MTX_M3_RETRY_COUNT", "0")

    class MatrixMsgSettings(Settings):
        retry_count: int = environment_variable_setting(name="MTX_M3_RETRY_COUNT", default=5, ge=1)

    (entry,) = MatrixMsgSettings.load_settings()

    assert_diagnostic_context(
        str(entry),
        member="retry_count",
        owner="MatrixMsgSettings",
        storage="environment variable 'MTX_M3_RETRY_COUNT'",
    )


def test_m4_dotenv_entry_names_the_file_too(tmp_path):
    env_path = tmp_path / "m4.env"
    env_path.write_text("MTX_M4_RETRY_COUNT=abc\n", encoding="utf-8")

    class MatrixMsgSettings(
        Settings,
        options=dotenv_source(file=env_path),
    ):
        retry_count: int = dotenv_setting(name="MTX_M4_RETRY_COUNT", default=5)

    (entry,) = MatrixMsgSettings.load_settings()

    assert_diagnostic_context(
        str(entry),
        member="retry_count",
        owner="MatrixMsgSettings",
        storage=(f"environment variable 'MTX_M4_RETRY_COUNT' in the dotenv file {env_path}"),
    )


def test_m5_json_entry_names_the_file_too(tmp_path):
    path = tmp_path / "m5.json"
    path.write_text('{"retry_count": "abc"}', encoding="utf-8")

    class MatrixMsgSettings(
        Settings,
        options=json_source(file=path),
    ):
        retry_count: int = json_setting(name="retry_count", default=5)

    (entry,) = MatrixMsgSettings.load_settings()

    assert_diagnostic_context(
        str(entry),
        member="retry_count",
        owner="MatrixMsgSettings",
        storage=f"key 'retry_count' in the JSON file {path}",
    )


def test_m6_source_failure_entry_names_member_and_class_but_not_the_storage(caplog):
    # the exception entry names the member and its class but not the
    # storage the member lives in; the ERROR log record carries the full
    # fallback shape — the member's place and the source that raised —
    # with no tail, for the required member holds no default to fall
    # back to (the abort carries its channel words)
    class MatrixMsgSettings(Settings):
        api_token: str = exploding_setting(default=REQUIRED)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            MatrixMsgSettings.load_settings()

    text = str(info.value.errors[0])
    assert "api_token" in text
    assert "MatrixMsgSettings" in text
    record = caplog.records[0].getMessage()
    assert record == (
        "setting 'api_token' (test_settings_usage_matrix.MatrixMsgSettings.api_token) "
        "of 'MatrixMsgSettings': its source raised RuntimeError (storage exploded)"
    )


def test_m7_toml_entry_names_the_file_too(tmp_path):
    path = tmp_path / "m7.toml"
    path.write_text('retry_count = "abc"\n', encoding="utf-8")

    class MatrixMsgSettings(
        Settings,
        options=toml_source(file=path),
    ):
        retry_count: int = toml_setting(name="retry_count", default=5)

    (entry,) = MatrixMsgSettings.load_settings()

    assert_diagnostic_context(
        str(entry),
        member="retry_count",
        owner="MatrixMsgSettings",
        storage=f"key 'retry_count' in the TOML file {path}",
    )


# ---------------------------------------------------------------------------
# R. The repeated pass: a completed load rebuilds the state from a clean
#    slate, a failed one leaves the class as the call found it
# ---------------------------------------------------------------------------


def test_r1_a_completed_pass_leaves_no_value_of_an_earlier_one(monkeypatch):
    class S(Settings):
        mode: str = environment_variable_setting(name="MTX_R1_MODE", default="default-mode")

    monkeypatch.setenv("MTX_R1_MODE", "from-env")
    S.load_settings()
    assert S.mode == "from-env"

    monkeypatch.delenv("MTX_R1_MODE", raising=False)
    assert S.load_settings() == ()
    # the member's source came up empty: the earlier pass's value does not
    # survive, the declared default is what stands
    assert S.mode == "default-mode"


def test_r2_an_aborting_pass_leaves_the_class_as_it_found_it(monkeypatch):
    class S(Settings):
        token: str = environment_variable_setting(name="MTX_R2_TOKEN", default=REQUIRED)
        mode: str = environment_variable_setting(name="MTX_R2_MODE", default="default-mode")

    monkeypatch.setenv("MTX_R2_TOKEN", "token-value")
    monkeypatch.setenv("MTX_R2_MODE", "from-env")
    S.load_settings()
    S.mode = "manual"

    monkeypatch.delenv("MTX_R2_TOKEN", raising=False)
    with pytest.raises(AggregateLoadError):
        S.load_settings()

    # nothing the failed pass produced is applied: not the fresh 'from-env',
    # not a served default — the class keeps the state it had
    assert S.mode == "manual"
    assert S.token == "token-value"


def test_r3_a_user_facing_source_error_leaves_the_class_as_it_found_it(monkeypatch, tmp_path):
    path = tmp_path / "r3.toml"
    path.write_text("[not toml", encoding="utf-8")

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        mode: str = environment_variable_setting(name="MTX_R3_MODE", default="default-mode")
        port: int = toml_setting(name="port", default=8080)

    monkeypatch.setenv("MTX_R3_MODE", "from-env")
    with pytest.raises(ValueError, match="cannot parse the TOML settings file"):
        S.load_settings()

    # mode loaded before the source broke; the abort applies nothing
    assert S.mode == "default-mode"
    assert S.port == 8080


def test_r4_a_failing_optional_member_gets_its_default_not_the_old_value(monkeypatch):
    class S(Settings):
        count: int = environment_variable_setting(name="MTX_R4_COUNT", default=5)

    monkeypatch.setenv("MTX_R4_COUNT", "42")
    S.load_settings()
    assert S.count == 42

    monkeypatch.setenv("MTX_R4_COUNT", "abc")
    S.load_settings()

    # even a formally successful pass depends only on the declared defaults
    # and the current sources: the old value does not stand in
    assert S.count == 5


# ---------------------------------------------------------------------------
# T. The TOML file backend
# ---------------------------------------------------------------------------


def test_t1_missing_file_serves_defaults(tmp_path):
    path = tmp_path / "absent.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="localhost")

    report = S.load_settings()

    assert report == ()
    assert S.host == "localhost"


def test_t2_corrupt_file_aborts_the_pass_and_keeps_values(tmp_path):
    path = tmp_path / "corrupt.toml"
    path.write_text("[not toml", encoding="utf-8")

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        first: int = toml_setting(name="first", default=1)
        second: int = toml_setting(name="second", default=2)

    S.first = 99
    with pytest.raises(ValueError, match="cannot parse the TOML settings file"):
        S.load_settings()

    assert S.first == 99
    assert S.second == 2


def test_t3_path_walks_tables_and_a_dotted_segment_names_a_key(tmp_path):
    path = tmp_path / "t3.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        api: str = toml_setting(name="api", path="/endpoints/api.internal", default="")
        region: str = toml_setting(name="region", path="/replicas/0", default="eu")

    S.save_settings()

    document = tomllib.loads(path.read_text(encoding="utf-8"))
    assert document["endpoints"] == {"api.internal": {"api": ""}}
    assert document["replicas"] == [{"region": "eu"}]


def test_t4_datetimes_stay_native_no_iso_strings(tmp_path):
    path = tmp_path / "t4.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        stamp: datetime = toml_setting(name="stamp", default=datetime(2026, 1, 1))

    S.stamp = datetime(2026, 10, 19, 12, 30, 0)
    S.save_settings()

    assert tomllib.loads(path.read_text(encoding="utf-8"))["stamp"] == datetime(
        2026, 10, 19, 12, 30, 0
    )
    assert 'stamp = "' not in path.read_text(encoding="utf-8")

    S.reset_settings()
    S.load_settings()
    assert S.stamp == datetime(2026, 10, 19, 12, 30, 0)


def test_t5_an_array_grows_at_its_tail_a_far_position_is_refused(tmp_path):
    path = tmp_path / "t5.toml"
    path.write_text("replicas = [{}, {}]\n", encoding="utf-8")

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        region: str = toml_setting(name="region", path="/replicas/2", default="eu")
        late: str = toml_setting(name="late", path="/replicas/5", default="us")

    S.region = "eu-west"
    S.late = "us-west"
    with pytest.raises(ValueError, match="cannot grow to position 5"):
        S.save_settings()

    # the pass aborted before its single write: the file keeps its document
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"replicas": [{}, {}]}


def test_t6_none_inside_a_container_is_skipped_and_logged(tmp_path, caplog):
    path = tmp_path / "t6.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        chain: List[Optional[Color]] = toml_setting(name="chain", default=[])
        host: str = toml_setting(name="host", default="localhost")

    S.chain = [Color.RED, None]
    S.host = "example.com"
    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        S.save_settings()

    # the refusing member never reached the file; the rest of the pass did
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"host": "example.com"}
    assert any(
        "setting 'chain'" in record.message and "TOML has no null" in record.message
        for record in caplog.records
    )


def test_t7_rewrites_preserve_the_file_and_foreign_keys_survive(tmp_path):
    path = tmp_path / "t7.toml"
    path.write_text(
        "# the author's own comments and order\nzebra = 1\nalpha = 2\n",
        encoding="utf-8",
    )

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        known: int = toml_setting(name="known", default=0)

    S.load_settings()
    S.known = 6
    S.save_settings()

    document = tomllib.loads(path.read_text(encoding="utf-8"))
    assert document == {"zebra": 1, "alpha": 2, "known": 6}
    # the editor is format-preserving: the comment stays and the file's
    # key order survives — a new key joins the end of the root keys
    assert list(document) == ["zebra", "alpha", "known"]
    assert "# the author's own comments and order" in path.read_text(encoding="utf-8")


def test_t8_a_key_is_stored_at_the_address_it_names(tmp_path):
    path = tmp_path / "t8.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        port: int = toml_setting(default=8080)  # the full pattern name
        host: str = toml_setting(name="host", default="localhost")
        net_host: str = toml_setting(name="net.host", default="proxy.example")

    S.save_settings()

    # the dot is TOML's table separator: every key sits at the address it
    # names — [module.Class] port, a plain root key, [net] host — and the
    # file carries no quoted dotted keys
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    assert document["host"] == "localhost"
    assert document["net"] == {"host": "proxy.example"}
    pattern = document
    for level in S.__module__.split(".") + [S.__name__]:
        pattern = pattern[level]
    assert pattern == {"port": 8080}

    S.reset_settings()
    S.load_settings()
    assert S.port == 8080
    assert S.net_host == "proxy.example"


def test_t9_colliding_addresses_are_refused_both_ways(tmp_path):
    path = tmp_path / "t9.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        deep: str = toml_setting(name="net.proxy.host", default="x")
        plain: str = toml_setting(name="net.proxy", default="y")

    # one member's name is a level of the other's: the scalar write over
    # the table refuses (a scalar on a path already does), and the table
    # write through the scalar hits the path guard; the single-setting
    # pass unwraps the user-facing refusal into the inner ValueError,
    # the way every pass of the family does
    S.deep = "set"
    S.save_setting(lambda s: s.deep)
    with pytest.raises(ValueError, match="holds a table or an array"):
        S.save_setting(lambda s: s.plain)

    path.unlink()
    S.save_setting(lambda s: s.plain)
    with pytest.raises(ValueError, match="not an object"):
        S.save_setting(lambda s: s.deep)
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"net": {"proxy": "y"}}


def test_t10_undecodable_file_names_itself(tmp_path):
    path = tmp_path / "t10.toml"
    path.write_bytes('host = "ok"\n'.encode("utf-16"))

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="fallback")

    with pytest.raises(ValueError, match="cannot read the TOML settings file"):
        S.load_settings()


def test_t11_bom_file_names_the_cause(tmp_path):
    path = tmp_path / "t11.toml"
    path.write_bytes(UTF8_BOM.encode("utf-8") + b'host = "ok"\n')

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="fallback")

    with pytest.raises(ValueError, match="it starts with a UTF-8 BOM"):
        S.load_settings()


def test_t12_save_keeps_the_files_crlf(tmp_path):
    path = tmp_path / "t12.toml"
    path.write_bytes(b'# comment\r\nhost = "ok"\r\nport = 1\r\n')

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="")
        port: int = toml_setting(name="port", default=0)

    S.load_settings()
    S.port = 2
    S.save_settings()

    assert path.read_bytes() == b'# comment\r\nhost = "ok"\r\nport = 2\r\n'


def test_t13_save_keeps_the_files_permission_mode(tmp_path):
    path = tmp_path / "t13.toml"
    path.write_text('host = "ok"\n', encoding="utf-8")
    path.chmod(0o600)

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="")

    S.load_settings()
    S.host = "new"
    S.save_settings()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


# ---------------------------------------------------------------------------
# V. Validation: every parameter, every checkpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "parameter,bound,bad,good",
    [
        ("gt", 10, 10, 11),
        ("ge", 10, 9, 10),
        ("lt", 10, 10, 9),
        ("le", 10, 11, 10),
    ],
)
def test_v1_ordering_bounds(parameter: str, bound: int, bad: int, good: int):
    constraints: dict[str, Any] = {parameter: bound}

    class S(Settings):
        member: int = non_storage_setting(default=good, **constraints)

    with pytest.raises(SettingValidationError):
        S.member = bad

    S.member = good
    assert S.member == good


def test_v2_eq_and_ne():
    class S(Settings):
        pinned: int = non_storage_setting(default=5, eq=5)
        banned: int = non_storage_setting(default=6, ne=5)

    with pytest.raises(SettingValidationError):
        S.pinned = 6
    with pytest.raises(SettingValidationError):
        S.banned = 5

    S.pinned = 5
    S.banned = 6
    assert (S.pinned, S.banned) == (5, 6)


def test_v3_length_bounds():
    class S(Settings):
        name: str = non_storage_setting(default="ab", min_length=2, max_length=4)
        tags: List[str] = non_storage_setting(default=["seed"], min_length=1)

    with pytest.raises(SettingValidationError):
        S.name = "a"
    with pytest.raises(SettingValidationError):
        S.name = "abcde"
    with pytest.raises(SettingValidationError):
        S.tags = []

    S.name = "abc"
    S.tags = ["x", "y"]
    assert S.name == "abc"
    assert S.tags == ["x", "y"]


def test_v4_regex_is_unanchored():
    # the anchors are the declarer's: a bare pattern matches anywhere
    class S(Settings):
        anywhere: str = non_storage_setting(default="hello", regex="ell")
        exact: str = non_storage_setting(default="ell", regex=r"^ell$")

    S.anywhere = "shell"
    with pytest.raises(SettingValidationError):
        S.anywhere = "abc"
    with pytest.raises(SettingValidationError):
        S.exact = "hello"


def test_v5_validator_callable():
    def even(value: int) -> bool:
        return value % 2 == 0

    class S(Settings):
        count: int = non_storage_setting(default=2, validator=even)

    with pytest.raises(SettingValidationError):
        S.count = 3

    S.count = 4
    assert S.count == 4


def test_v6_none_passes_ordering_length_regex_and_ne_but_not_eq():
    class S(Settings):
        bounded: Optional[int] = non_storage_setting(default=None, gt=0)
        texty: Optional[str] = non_storage_setting(default=None, regex="ell", min_length=1)
        banned: Optional[int] = non_storage_setting(default=None, ne=5)
        pinned: int = non_storage_setting(default=5, eq=5)

    S.bounded = None
    S.texty = None
    S.banned = None
    with pytest.raises(SettingValidationError):
        S.pinned = None


def test_v7_constraints_a_value_cannot_apply_to_are_violations():
    # reported as violations with their own messages, never as crashes
    with pytest.raises(TypeError, match="not comparable"):

        class BadOrdering(Settings):
            member: object = non_storage_setting(default="text", gt=0)

    with pytest.raises(TypeError, match="no length"):

        class BadLength(Settings):
            member: int = non_storage_setting(default=5, min_length=2)

    with pytest.raises(TypeError, match="not a string"):

        class BadRegex(Settings):
            member: object = non_storage_setting(default=5, regex=r"\d+")

    class S(Settings):
        member: object = non_storage_setting(default=3, gt=0)

    with pytest.raises(SettingValidationError, match="not comparable"):
        S.member = "text"


def test_v8_instance_assignments_validate_too():
    class S(Settings):
        port: int = non_storage_setting(default=80, le=65535)

    instance = S()
    with pytest.raises(SettingValidationError):
        instance.port = 70000


def test_v9_every_checkpoint_a_violation_meets(monkeypatch):
    # one violated bound walks every validation point the package has
    with pytest.raises(TypeError, match="invalid defaults"):

        class AtClassCreation(Settings):
            member: int = non_storage_setting(default=0, ge=1)

    class S(Settings):
        member: int = non_storage_setting(default=5, ge=1)

    with pytest.raises(SettingValidationError):
        S.member = 0  # a plain assignment
    with pytest.raises(SettingValidationError):
        S.update_from_dict({"member": 0})  # a bulk update

    class Loaded(Settings):
        member: int = environment_variable_setting(name="MTX_V9_MEMBER", default=5, ge=1)

    monkeypatch.setenv("MTX_V9_MEMBER", "0")
    (entry,) = Loaded.load_settings()  # a load: the soft channel
    assert isinstance(entry, ConstraintViolationError)
    assert Loaded.member == 5

    # the whole-class checkpoints need a pair: a single assignment runs no
    # cross checks, so the inconsistent state is reachable
    class Pair(Settings):
        min_port: int = non_storage_setting(default=1024)
        max_port: int = non_storage_setting(default=65535, ge=min_port)

    Pair.max_port = 80
    with pytest.raises(SettingValidationError):
        Pair.validate_settings()  # the manual check
    with pytest.raises(SettingValidationError):
        Pair.save_settings()  # the whole-class save pre-check
    with pytest.raises(SettingValidationError):
        Pair.update_from_dict({"max_port": 80})
    Pair.save_setting(lambda s: s.max_port)  # single-setting save: no cross checks


# ---------------------------------------------------------------------------
# W. Writing in all its variants: assignment, save, delete, updates
# ---------------------------------------------------------------------------


def test_w1_assignment_stores_the_value_exactly_as_given():
    # conversion is the load-and-update path: a plain assignment keeps
    # whatever it receives, the annotation included
    class S(Settings):
        count: int = non_storage_setting(default=5)

    S.count = "9"  # type: ignore[assignment]  # the behavior under test

    assert S.count == "9"


def test_w2_assignment_touches_the_class_storage_only(tmp_path):
    path = tmp_path / "w2.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        member: int = json_setting(name="member", default=1)

    S.member = 2

    assert not path.exists()
    assert not S.contains_setting("member")

    S.save_settings()

    assert S.contains_setting("member")
    assert json.loads(path.read_text(encoding="utf-8")) == {"member": 2}


def test_w3_save_settings_writes_the_environment_variables(monkeypatch):
    # the seed guarantees the teardown removes the variable the library
    # writes into the process environment
    monkeypatch.setenv("MTX_W3_MODE", "seed")

    class S(Settings):
        mode: str = environment_variable_setting(name="MTX_W3_MODE", default="d")

    S.mode = "written"
    S.save_settings()

    assert os.environ["MTX_W3_MODE"] == "written"


def test_w4_saving_none_to_dotenv_removes_the_line(tmp_path):
    env_path = tmp_path / "w4.env"
    env_path.write_text("MTX_W4_HINT=old\nOTHER=1\n", encoding="utf-8")

    class S(
        Settings,
        options=dotenv_source(file=env_path),
    ):
        hint: Optional[str] = dotenv_setting(name="MTX_W4_HINT", default="fallback")

    S.load_settings()
    S.hint = None
    S.save_settings()

    text = env_path.read_text(encoding="utf-8")
    assert "MTX_W4_HINT" not in text
    assert "OTHER=1" in text


def test_w5_saving_none_to_json_stores_null_delete_drops_the_key(tmp_path):
    path = tmp_path / "w5.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        hint: Optional[str] = json_setting(name="hint", default="fallback")

    S.hint = None
    S.save_settings()
    assert json.loads(path.read_text(encoding="utf-8")) == {"hint": None}

    S.delete_setting(lambda s: s.hint)
    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_w6_secrets_are_saved_unwrapped(tmp_path):
    path = tmp_path / "w6.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        token: SecretStr = json_setting(name="token", default="seed")

    S.token = SecretStr("s3cr3t")
    S.save_settings()

    # the storage form is the plain payload: saving unwraps before the
    # serializer sees the value
    assert json.loads(path.read_text(encoding="utf-8")) == {"token": "s3cr3t"}


def test_w7_delete_settings_prunes_the_emptied_containers(tmp_path):
    path = tmp_path / "w7.json"
    path.write_text('{"arr": [null, {"tag": "x"}], "keep": 1}', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        tag: str = json_setting(name="tag", path="/arr/1", default="x")
        keep: int = json_setting(name="keep", default=0)

    S.delete_settings()

    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_w8_updates_apply_to_the_class_but_never_write_storage(tmp_path):
    path = tmp_path / "w8.json"
    path.write_text('{"count": 1}', encoding="utf-8")

    class S(
        Settings,
        options=json_source(file=path),
    ):
        count: int = json_setting(name="count", default=0)

    S.update_from_dict({"count": 99})

    assert S.count == 99
    assert json.loads(path.read_text(encoding="utf-8")) == {"count": 1}


def test_w9_a_failing_save_is_skipped_and_logged_the_rest_written(tmp_path, caplog):
    path = tmp_path / "w9.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        member: int = json_setting(name="member", default=1)
        broken: int = failing_save_setting(default=2)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        S.save_settings()

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {"member": 1}
    assert any("broken" in record.getMessage() for record in caplog.records)


def test_w10_a_user_facing_save_error_aborts_the_pass(tmp_path):
    path = tmp_path / "w10.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        member: int = json_setting(name="member", default=1)
        blocked: int = blocking_save_setting(default=2)

    with pytest.raises(OSError, match="disk full"):
        S.save_settings()

    # the abort happens before the flush: nothing reached the file
    assert not path.exists()


def test_w11_save_setting_accepts_the_member_name_string(tmp_path):
    path = tmp_path / "w11.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        member: int = json_setting(name="member", default=1)

    S.member = 2
    S.save_setting("member")

    assert json.loads(path.read_text(encoding="utf-8")) == {"member": 2}


def test_w12_saving_none_to_toml_removes_the_entry(tmp_path):
    path = tmp_path / "w12.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        hint: Optional[str] = toml_setting(name="hint", default="fallback")

    S.hint = "kept"
    S.save_settings()
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"hint": "kept"}

    # TOML has no null: the entry is gone, and the next load serves the
    # default — the JSON null of W5 has no TOML counterpart
    S.hint = None
    S.save_settings()
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {}
    S.load_settings()
    assert S.hint == "fallback"
    assert S.contains_setting("hint") is False


def test_w13_save_keeps_the_dotenv_files_crlf(tmp_path):
    path = tmp_path / "w13.env"
    path.write_bytes(b"# comment\r\nHOST=old\r\nOTHER=keep\r\n")

    class S(
        Settings,
        options=dotenv_source(file=path),
    ):
        host: str = dotenv_setting(name="HOST", default="")

    S.load_settings()
    S.host = "new"
    S.save_settings()

    assert path.read_bytes() == b"# comment\r\nHOST='new'\r\nOTHER=keep\r\n"


def test_w14_save_keeps_the_dotenv_files_permission_mode(tmp_path):
    path = tmp_path / "w14.env"
    path.write_text("HOST=old\n", encoding="utf-8")
    path.chmod(0o600)

    class S(
        Settings,
        options=dotenv_source(file=path),
    ):
        host: str = dotenv_setting(name="HOST", default="")

    S.load_settings()
    S.host = "new"
    S.save_settings()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


# ---------------------------------------------------------------------------
# N: aliases — several addresses of one member, first found wins
# ---------------------------------------------------------------------------


def test_n1_alias_order_primary_then_declaration_order(monkeypatch):
    for name in ("MTX_N1_PRIMARY", "MTX_N1_FIRST", "MTX_N1_SECOND"):
        monkeypatch.delenv(name, raising=False)

    class S(Settings):
        ttl: str = environment_variable_setting(
            name="MTX_N1_PRIMARY",
            aliases=["MTX_N1_FIRST", "MTX_N1_SECOND"],
            default="default",
        )

    monkeypatch.setenv("MTX_N1_SECOND", "second")
    S.load_settings()
    assert S.ttl == "second"  # the last alias serves alone

    monkeypatch.setenv("MTX_N1_FIRST", "first")
    S.load_settings()
    assert S.ttl == "first"  # the first declared alias wins

    monkeypatch.setenv("MTX_N1_PRIMARY", "primary")
    S.load_settings()
    assert S.ttl == "primary"  # the primary address outranks every alias


def test_n2_json_alias_keys_land_under_the_same_path(tmp_path):
    path = tmp_path / "n2.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        host: str = json_setting(
            name="host", path="/net/proxy", aliases=["host_main"], default="localhost"
        )

    path.write_text('{"net": {"proxy": {"host_main": "alias.example"}}}', encoding="utf-8")
    S.load_settings()
    assert S.host == "alias.example"

    # the write direction serves the primary key alone
    S.host = "saved"
    S.save_setting("host")
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "net": {"proxy": {"host": "saved", "host_main": "alias.example"}}
    }


def test_n3_toml_alias_address_nests_by_its_own_dots(tmp_path):
    path = tmp_path / "n3.toml"

    class S(
        Settings,
        options=toml_source(file=path),
    ):
        port: int = toml_setting(name="net.port", aliases=["port_main"], default=80)

    path.write_text("port_main = 9000\n", encoding="utf-8")
    S.load_settings()
    assert S.port == 9000


def test_n4_delete_clears_the_alias_addresses_too(monkeypatch):
    for name in ("MTX_N4_PRIMARY", "MTX_N4_FIRST"):
        monkeypatch.delenv(name, raising=False)

    class S(Settings):
        ttl: str = environment_variable_setting(
            name="MTX_N4_PRIMARY", aliases=["MTX_N4_FIRST"], default="default"
        )

    monkeypatch.setenv("MTX_N4_FIRST", "old-value")
    S.load_settings()
    assert S.ttl == "old-value"

    # an alias left behind would resurrect the value at the next load
    S.delete_setting("ttl")
    assert "MTX_N4_PRIMARY" not in os.environ
    assert "MTX_N4_FIRST" not in os.environ
    S.load_settings()
    assert S.ttl == "default"


def test_n5_miss_diagnostics_list_every_address(monkeypatch):
    for name in ("MTX_N5_TOKEN", "MTX_N5_TOKEN_OLD"):
        monkeypatch.delenv(name, raising=False)

    class S(Settings):
        token: str = environment_variable_setting(
            name="MTX_N5_TOKEN", aliases=["MTX_N5_TOKEN_OLD"], default=REQUIRED
        )

    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()

    assert "(environment variable 'MTX_N5_TOKEN' (aliases: 'MTX_N5_TOKEN_OLD'))" in str(
        info.value.errors[0]
    )


# ---------------------------------------------------------------------------
# P. Plain declarations and the source bindings (#91)
# ---------------------------------------------------------------------------


def test_p1_a_bare_annotation_is_required_an_assignment_a_default(tmp_path):
    # the plain spellings of a member: a bare annotation has no default —
    # the storage must provide the value or the load aborts — and an
    # annotated assignment carries that value as its default, converted
    # to the annotated type
    path = tmp_path / "p1.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        token: str
        ttl: timedelta = timedelta(minutes=30)
        count: int = "42"

    path.write_text(json.dumps({f"{S.__module__}.S.token": "abc"}), encoding="utf-8")
    assert S.load_settings() == ()
    assert S.token == "abc"
    assert S.ttl == timedelta(minutes=30)
    assert S.count == 42

    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AggregateLoadError) as info:
        S.load_settings()
    assert isinstance(info.value.errors[0], MissingValueError)
    assert "S.token" in str(info.value.errors[0])


def test_p2_the_rich_setting_spelling_binds_constraints_and_the_full_name(tmp_path):
    path = tmp_path / "p2.json"

    class S(
        Settings,
        options=json_source(file=path),
    ):
        port: int = setting(name="port", ge=1, le=65535, default=8080)

    S.save_settings()
    assert json.loads(path.read_text(encoding="utf-8")) == {"port": 8080}
    S.load_settings()
    assert S.port == 8080
    S.port = 80  # the declared constraints hold on assignment too
    with pytest.raises(SettingValidationError):
        S.port = 70000


def test_p3_a_classvar_annotation_is_not_a_member(monkeypatch):
    monkeypatch.setenv("MTX_P3_MODE", "plain")

    class S(
        Settings,
        options=env_source(name_prefix="MTX_P3_", name_case=NameCase.UPPER),
    ):
        flag: ClassVar[bool] = True
        mode: str = "default"

    assert set(S.__settings_members__) == {"mode"}
    assert S.flag is True  # the plain class attribute it always was
    S.load_settings()
    assert S.mode == "plain"


def test_p4_family_factories_pick_storages_in_a_multi_source_class(tmp_path, monkeypatch):
    # a class may hold several sources, one builder per family: the
    # members declared through factories read their own family's builder,
    # so several storages are fine the moment no member is plain
    path = tmp_path / "p4.json"
    monkeypatch.setenv("MTX_P4_TOKEN", "env-token")

    class S(
        Settings,
        options=(
            env_source(name_prefix="MTX_P4_", name_case=NameCase.UPPER),
            json_source(file=path),
        ),
    ):
        url: str = json_setting(default="https://example.com")
        token: str = environment_variable_setting(default="fallback")

    S.load_settings()
    assert S.token == "env-token"
    assert S.url == "https://example.com"
    S.url = "https://edited.example.com"
    S.save_settings()
    assert (
        json.loads(path.read_text(encoding="utf-8"))[f"{S.__module__}.S.url"]
        == "https://edited.example.com"
    )


def test_p5_the_source_binding_is_inherited_and_replaced_per_family(tmp_path):
    base_file = tmp_path / "base.json"
    child_file = tmp_path / "child.json"

    class Base(
        Settings,
        options=json_source(file=base_file),
    ):
        token: str = "base-default"

    class Child(Base):
        pass  # no binding of its own: the nearest one above governs

    class Rebound(
        Base,
        options=json_source(file=child_file),
    ):
        pass  # the family's own binding replaces the base's for it and below

    # the pattern's class part is the reading class's name, the family's
    # own namespacing
    base_file.write_text(
        json.dumps(
            {
                f"{Base.__module__}.Base.token": "from-base",
                f"{Child.__module__}.Child.token": "from-base",
            }
        )
    )
    child_file.write_text(json.dumps({f"{Rebound.__module__}.Rebound.token": "from-child"}))
    Child.load_settings()
    assert Child.token == "from-base"
    Rebound.load_settings()
    assert Rebound.token == "from-child"
    Base.load_settings()
    assert Base.token == "from-base"


def test_p6_the_naming_dictionary_has_one_seat_serving_both_storages(tmp_path):
    env_path = tmp_path / "p6.env"

    class BothStorages(
        Settings,
        options=(
            env_source(name_prefix="MTX_P6_", name_case=NameCase.UPPER),
            dotenv_source(file=env_path),
        ),
    ):
        token: str = dotenv_setting(default="none")

    # the dictionary declared on env_source serves the dotenv sibling too:
    # the two are one variable namespace
    BothStorages.token = "written"
    BothStorages.save_settings()
    assert "MTX_P6_TOKEN" in env_path.read_text(encoding="utf-8")

    with pytest.raises(TypeError, match="more than once in options="):

        class TwiceNamed(
            Settings,
            options=(
                env_source(name_prefix="A_"),
                dotenv_source(file=env_path, name_prefix="B_"),
            ),
        ):
            mode: str = "x"


def test_p7_a_templated_file_reads_one_file_per_environment(tmp_path, monkeypatch):
    app_env = env_parameter("MTX_P7_ENV", choices=("dev", "test", "prod"), default="dev")

    class S(
        Settings,
        options=json_source(file=tmp_path / "s-{MTX_P7_ENV}.json", parameters=app_env),
    ):
        token: str = "none"

    monkeypatch.setenv("MTX_P7_ENV", "dev")
    S.token = "dev-value"
    S.save_settings()
    assert (tmp_path / "s-dev.json").exists()

    monkeypatch.setenv("MTX_P7_ENV", "test")
    S.load_settings()  # the test file holds nothing: the default stands
    assert S.token == "none"

    monkeypatch.setenv("MTX_P7_ENV", "prodd")  # a typo outside the whitelist
    with pytest.raises(ValueError, match="do not allow"):
        S.load_settings()

    # an unset variable resolves through the declared default; without one
    # it is a broken link the load names with the variable
    monkeypatch.delenv("MTX_P7_ENV")
    S.load_settings()
    assert S.token == "dev-value"  # the dev file the default pointed to

    strict_env = env_parameter("MTX_P7_STRICT", choices=("a", "b"))

    class Strict(
        Settings,
        options=json_source(file=tmp_path / "strict-{MTX_P7_STRICT}.json", parameters=strict_env),
    ):
        token: str = "none"

    with pytest.raises(ValueError, match="MTX_P7_STRICT.*declares no default"):
        Strict.load_settings()


def test_p8_writes_land_in_the_environment_they_were_loaded_from(tmp_path, monkeypatch):
    app_env = env_parameter("MTX_P8_ENV", choices=("dev", "test"))

    class S(
        Settings,
        options=json_source(file=tmp_path / "p8-{MTX_P8_ENV}.json", parameters=app_env),
    ):
        token: str = "none"

    monkeypatch.setenv("MTX_P8_ENV", "dev")
    S.load_settings()
    S.token = "dev-value"

    monkeypatch.setenv("MTX_P8_ENV", "test")  # the variable moved on
    S.save_settings()  # the write still lands in the dev file it loaded
    assert (
        json.loads((tmp_path / "p8-dev.json").read_text(encoding="utf-8"))[
            f"{S.__module__}.S.token"
        ]
        == "dev-value"
    )
    assert not (tmp_path / "p8-test.json").exists()

    S.load_settings()  # a load rereads the variable: test answers now
    assert S.token == "none"


def test_p9_a_source_chain_is_the_other_packages_declaration():
    from advexp.configuration.plugins.environment.variables import (
        env_source as configuration_env_source,
    )
    from advexp.settings_base.sources import Sources

    with pytest.raises(TypeError, match="source chains are provided by advexp.configuration"):

        class Chained(
            Settings,
            options=Sources(configuration_env_source()),
        ):
            pass


def test_p10_file_seats_name_the_classs_file_beside_the_source(tmp_path):
    # json_file/toml_file name the file of the class's family members
    # without binding the class to that storage: the plain members keep
    # the class's single source, and the members declared through the
    # family factories read the seated file
    json_path = tmp_path / "p10.json"
    toml_path = tmp_path / "p10.toml"
    json_path.write_text(json.dumps({"retries": 7}), encoding="utf-8")
    toml_path.write_text("retries = 9\n", encoding="utf-8")

    class J(
        Settings,
        options=(
            env_source(name_prefix="MTX_P10_", name_case=NameCase.UPPER),
            json_file(json_path),
        ),
    ):
        mode: str = "production"  # plain: the class's one source is env

        retries: int = json_setting(name="retries", default=3)

    class T(
        Settings,
        options=(
            env_source(name_prefix="MTX_P10_", name_case=NameCase.UPPER),
            toml_file(toml_path),
        ),
    ):
        mode: str = "production"

        retries: int = toml_setting(name="retries", default=3)

    J.load_settings()
    T.load_settings()
    assert (J.mode, J.retries) == ("production", 7)
    assert (T.mode, T.retries) == ("production", 9)


def test_p11_a_file_seat_refuses_an_invalid_path_at_the_call():
    # the seat's path is checked at the builder call, so a bad value
    # fails before the class statement ever runs
    with pytest.raises(TypeError, match="invalid JSON file binding"):
        json_file(42)
    with pytest.raises(TypeError, match="invalid JSON file binding"):
        json_file("")
    with pytest.raises(TypeError, match="invalid TOML file binding"):
        toml_file(None)


def test_p12_a_file_seat_is_inherited_and_replaced_per_class(tmp_path):
    # the seat is the class's own metadata entry: a subclass without its
    # own reads the nearest one above, a subclass with one switches to it
    # for itself and below, and the base class keeps its own file
    from advexp.settings.plugins.json_settings import JSON_FILE_METADATA

    base_file = tmp_path / "p12-base.json"
    own_file = tmp_path / "p12-own.json"
    base_file.write_text(json.dumps({"retries": 7}), encoding="utf-8")
    own_file.write_text(json.dumps({"retries": 11}), encoding="utf-8")

    class Base(
        Settings,
        options=(
            env_source(name_prefix="MTX_P12_", name_case=NameCase.UPPER),
            json_file(base_file),
        ),
    ):
        mode: str = "production"

        retries: int = json_setting(name="retries", default=3)

    class Child(Base):
        pass  # no seat of its own: the base's file governs

    class OwnSeat(Base):
        # the body spelling of the same entry
        class_metadata = {JSON_FILE_METADATA: str(own_file)}

    Base.load_settings()
    Child.load_settings()
    OwnSeat.load_settings()
    assert Base.retries == 7
    assert Child.retries == 7
    assert OwnSeat.retries == 11
    Base.load_settings()
    assert Base.retries == 7  # the base kept its own file


def test_p13_the_dotenv_file_seat_rides_the_env_naming(tmp_path):
    # dotenv_file seats the class's .env file while the env binding
    # stays the class's single source: the plain members live, the
    # dotenv factory member reads the seated file, and its variable
    # name builds by the environment family's shared dictionary
    env_path = tmp_path / "p13.env"
    env_path.write_text("MTX_P13_FLAG=true\n", encoding="utf-8")

    class D(
        Settings,
        options=(
            env_source(name_prefix="MTX_P13_", name_case=NameCase.UPPER),
            dotenv_file(env_path),
        ),
    ):
        mode: str = "production"  # plain: the class's one source is env

        flag: bool = dotenv_setting(default=False)  # MTX_P13_FLAG

    D.load_settings()
    assert (D.mode, D.flag) == ("production", True)

    # the plugin handle reads the same seat at runtime
    assert D.get_plugin(DotenvPlugin).file_path == env_path


def test_p14_a_file_seat_beside_its_own_source_binding_fails(tmp_path):
    # one storage named twice: the pair is refused whatever side of the
    # declaration spelled it — a bound family's file belongs on its
    # source builder, file or no file on it
    refusal = "For a bound family, the file"

    with pytest.raises(TypeError, match=refusal):

        class WithFile(
            Settings,
            options=(
                json_source(file=tmp_path / "p14.json"),
                json_file(tmp_path / "p14-seat.json"),
            ),
        ):
            pass

    with pytest.raises(TypeError, match=refusal):
        # a file-less source builder leaves the file to the module
        # default — the seat is still the second spelling of it

        class FileLess(
            Settings,
            options=(
                json_source(name_pattern="{FieldName}"),
                json_file(tmp_path / "p14-seat.json"),
            ),
        ):
            pass

    with pytest.raises(TypeError, match=refusal):

        class TomlPair(
            Settings,
            options=(
                toml_source(file=tmp_path / "p14.toml"),
                toml_file(tmp_path / "p14-seat.toml"),
            ),
        ):
            pass

    with pytest.raises(TypeError, match=refusal):

        class DotenvPair(
            Settings,
            options=(
                dotenv_source(file=tmp_path / "p14.env"),
                dotenv_file(tmp_path / "p14-seat.env"),
            ),
        ):
            pass

    with pytest.raises(TypeError, match=refusal):
        # the body spelling meets the same refusal

        class BodySeat(
            Settings,
            options=json_source(file=tmp_path / "p14.json"),
        ):
            class_metadata = {JSON_FILE_METADATA: str(tmp_path / "p14-seat.json")}


# -- module file declarations (matrix Q) ------------------------------------------------


@pytest.fixture(autouse=True)
def clean_module_declarations():
    # for_this_module declarations live in a process-wide registry; one
    # test's declarations never reach the next
    yield
    _DECLARED_VALUES.clear()


_FOREIGN_SOURCE = """
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class ForeignSettings(adv_settings.Settings):
    retries: int = js.json_setting(name="retries", default=3)
"""


def _foreign_settings_class() -> type:
    """A settings class of another module: no declaration of ours reaches it."""
    module = types.ModuleType("foreign_matrix_module")
    exec(_FOREIGN_SOURCE, module.__dict__)
    return module.ForeignSettings


def test_q1_the_module_declaration_gives_the_module_its_file(tmp_path, monkeypatch):
    process_file = tmp_path / "q1-process.json"
    module_file = tmp_path / "q1-module.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", process_file)

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    class Q1Settings(Settings):
        retries: int = json_setting(name="retries", default=3)

    Q1Settings.retries = 7
    Q1Settings.save_settings()

    assert json.loads(module_file.read_text(encoding="utf-8")) == {"retries": 7}
    assert JSONSettingsConfiguration.file_path == process_file
    assert not process_file.exists()


def test_q2_a_class_of_another_module_keeps_the_process_default(tmp_path, monkeypatch):
    process_file = tmp_path / "q2-process.json"
    module_file = tmp_path / "q2-module.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", process_file)

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    foreign = _foreign_settings_class()
    foreign.retries = 9
    foreign.save_settings()

    assert json.loads(process_file.read_text(encoding="utf-8")) == {"retries": 9}
    assert not module_file.exists()


def test_q3_a_class_binding_wins_over_the_module_declaration(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    module_file = tmp_path / "q3-module.json"

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    class Q3Settings(
        Settings,
        options=json_source(file=tmp_path / "q3-class.json"),
    ):
        retries: int = json_setting(name="retries", default=3)

    Q3Settings.retries = 7
    Q3Settings.save_settings()

    assert json.loads((tmp_path / "q3-class.json").read_text(encoding="utf-8")) == {"retries": 7}
    assert not module_file.exists()


def test_q4_the_file_families_take_the_declaration_each(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(DotenvConfiguration, "file_path", ".env")
    declared_toml = tmp_path / "q4-module.toml"
    declared_dotenv = tmp_path / "q4-module.env"

    TOMLSettingsConfiguration.file_path = for_this_module(declared_toml)
    DotenvConfiguration.file_path = for_this_module(declared_dotenv)

    class Q4Toml(Settings):
        retries: int = toml_setting(name="retries", default=3)

    class Q4Dotenv(Settings):
        host: str = dotenv_setting(name="HOST", default="localhost")

    Q4Toml.retries = 7
    Q4Toml.save_settings()
    Q4Dotenv.host = "db.example.com"
    Q4Dotenv.save_settings()

    assert tomllib.loads(declared_toml.read_text(encoding="utf-8")) == {"retries": 7}
    assert declared_dotenv.exists()
    assert not (tmp_path / ".env").exists()


def test_q5_the_dynamic_own_file_is_declared_for_the_module(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", None)
    dynamic_file = tmp_path / "q5-dynamic.json"

    JSONDynamicSettingsConfiguration.file_path = for_this_module(dynamic_file)

    class Q5Settings(Settings):
        airplane_mode: bool = json_setting(default=False)

    plugin = Q5Settings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = json.loads(dynamic_file.read_text(encoding="utf-8"))
    assert document[JSONDynamicSettingsPlugin.DEFAULT_SECTION]


def test_q6_dynamic_entries_share_the_module_declared_static_file(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", None)
    static_file = tmp_path / "q6-static.json"

    JSONSettingsConfiguration.file_path = for_this_module(static_file)

    class Q6Settings(Settings):
        airplane_mode: bool = json_setting(default=False)

    plugin = Q6Settings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = json.loads(static_file.read_text(encoding="utf-8"))
    assert JSONDynamicSettingsPlugin.DEFAULT_SECTION in document


def test_q7_bad_declarations_fail_the_assignment_line():
    with pytest.raises(TypeError, match="invalid module declaration"):
        JSONSettingsConfiguration.file_path = for_this_module(123)

    with pytest.raises(TypeError, match="does not accept a module declaration"):
        JSONSettingsConfiguration.file_patth = for_this_module("q7.json")


def test_q8_the_snapshot_hands_over_every_declaration(tmp_path, monkeypatch):
    module_file = tmp_path / "q8-module.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    snapshot = declared_module_defaults()
    assert snapshot == {(JSONSettingsConfiguration, "file_path", __name__): module_file}

    snapshot.clear()
    assert declared_module_defaults() == {
        (JSONSettingsConfiguration, "file_path", __name__): module_file
    }


# ---------------------------------------------------------------------------
# S. The mapping storage: the class's dictionary (#89)
# ---------------------------------------------------------------------------


def test_s1_the_seeded_dictionary_serves_the_load():
    # the builder's dictionary seeds the storage: copied at the call,
    # served as fresh copies, never written back by the caller's object
    class S(
        Settings,
        options=mapping_source({"token": "seed-token", "port": 8080}),
    ):
        token: str = "fallback"
        port: int = 0

    S.load_settings()
    assert S.token == "seed-token"
    assert S.port == 8080


def test_s2_an_empty_storage_misses_silently_until_set_fills_it():
    # a storage nothing seeded and nothing filled is a plain miss — the
    # declared defaults stand — and set() through the resolver is what
    # the next load reads
    class S(
        Settings,
        options=mapping_source(),
    ):
        token: str = "fallback"

    S.load_settings()
    assert S.token == "fallback"  # the empty storage let the load pass

    mapping_source_for(S).set({"token": "runtime-token"})
    S.load_settings()
    assert S.token == "runtime-token"


def test_s3_get_hands_the_current_dictionary_as_a_copy():
    # get() returns what stands now — the last set and the saves alike —
    # as a deep copy: the caller's mutations never reach the storage
    class S(
        Settings,
        options=mapping_source({"token": "seed-token"}),
    ):
        token: str = "fallback"

    handle = mapping_source_for(S)
    assert mapping_source_for(S) is handle  # one handle, every call

    S.token = "assigned"
    S.save_settings()
    snapshot = handle.get()
    assert snapshot == {"token": "assigned"}
    snapshot["token"] = "mutated-after-the-call"
    assert handle.get() == {"token": "assigned"}


def test_s4_save_and_delete_touch_the_member_keys_alone():
    # the dictionary is a shared document: a save writes the class's
    # member keys and leaves the rest as it stands, a delete removes its
    # member's key the same way
    class S(
        Settings,
        options=mapping_source({}),
    ):
        token: str = "fallback"
        port: int = 0

    mapping_source_for(S).set({"token": "seed", "port": 1, "foreign": 42, "another": "kept"})
    S.load_settings()

    S.token = "saved"
    S.save_settings()
    dictionary = mapping_source_for(S).get()
    assert dictionary == {"token": "saved", "port": 1, "foreign": 42, "another": "kept"}

    S.delete_setting("port")
    assert mapping_source_for(S).get() == {
        "token": "saved",
        "foreign": 42,
        "another": "kept",
    }


def test_s5_the_storage_dictionary_speaks_member_names_alone(caplog):
    # the dictionary's keys are member names: a name= and declared
    # aliases change nothing for it, and a key naming no member drops
    # out with a debug record — the one lexicon of the family's
    # dictionary handles
    class S(
        Settings,
        options=mapping_source({}),
    ):
        host: str = setting(name="HOST", aliases=["OLD_HOST"], default="fallback")

    mapping_source_for(S).set({"host": "map-host", "foreign": 42})
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        S.load_settings()
    assert S.host == "map-host"
    assert any("does not match any member" in record.getMessage() for record in caplog.records)


def test_s6_a_subclass_without_its_own_binding_shares_the_storage():
    # the seat is the class's own declaration: a subclass without one
    # inherits the nearest above it — the same link, one dictionary,
    # one set and one get for both classes
    class Base(
        Settings,
        options=mapping_source(),
    ):
        token: str = "fallback"

    class Child(Base):
        pass

    assert mapping_source_for(Child) is mapping_source_for(Base)

    mapping_source_for(Child).set({"token": "child-token"})
    Base.load_settings()
    assert Base.token == "child-token"  # one dictionary behind both


def test_s7_the_storage_is_the_classs_one_source_binding():
    # a storage the plain members read cannot share the class with
    # another source binding: there is no order between the bindings
    # for a plain member to follow, and the class statement refuses the
    # mix — the subclass declaring the second seat over an inherited
    # storage included
    with pytest.raises(TypeError, match=f"alongside the source seat {JSON_SOURCE_METADATA!r}"):

        class Same(
            Settings,
            options=[mapping_source(), json_source(file="s7.json")],
        ):
            token: str = "t"

    class Inherited(
        Settings,
        options=mapping_source(),
    ):
        token: str = "t"

    with pytest.raises(
        TypeError, match=f"alongside the source seat {ENVIRONMENT_SOURCE_METADATA!r}"
    ):

        class Sub(
            Inherited,
            options=env_source(name_prefix="S7_"),
        ):
            pass


def test_s8_family_seats_sit_beside_the_storage():
    # the exclusivity is about the plain members' storages alone: a
    # family's file seat names the file of its factory members beside
    # the dictionary, and those members read their file, the plain ones
    # the dictionary
    class S(
        Settings,
        options=[mapping_source(), json_file("s8.json")],
    ):
        token: str = "fallback"
        note: str = json_setting(name="note", default="file-note")

    mapping_source_for(S).set({"token": "map-token"})
    S.load_settings()
    assert S.token == "map-token"
    assert S.note == "file-note"  # the family seat served its member


# ---------------------------------------------------------------------------
# Y. YAML-бэкенд
# ---------------------------------------------------------------------------


def test_y1_missing_file_serves_defaults(tmp_path):
    path = tmp_path / "absent.yaml"

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    report = S.load_settings()

    assert report == ()
    assert S.host == "localhost"


def test_y2_corrupt_file_aborts_the_pass_and_keeps_values(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("{not yaml", encoding="utf-8")

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match=f"cannot parse the YAML settings file {path}"):
        S.load_settings()
    assert S.host == "localhost"  # the abort left the class as the call found it


def test_y3_a_blank_file_is_an_empty_document_both_ways(tmp_path):
    # a blank YAML file is valid YAML: a load reads no keys from it and a
    # save starts it over — the parse error richer formats make of an
    # empty file has no counterpart here
    path = tmp_path / "blank.yaml"
    path.write_text("   \n", encoding="utf-8")

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    report = S.load_settings()
    assert report == ()
    assert S.host == "localhost"

    S.host = "changed"
    S.save_settings()
    from ruamel.yaml import YAML

    assert YAML(typ="safe").load(path.read_text(encoding="utf-8")) == {"host": "changed"}


def test_y4_a_second_document_in_the_stream_is_refused(tmp_path):
    # a save must not drop what sits beyond the separator: two documents
    # in one file fail the parse
    path = tmp_path / "two-docs.yaml"
    path.write_text("host: a\n---\nhost: b\n", encoding="utf-8")

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match="expected a single document"):
        S.load_settings()


def test_y5_an_unknown_tag_is_refused(tmp_path):
    # the settings file is data, not code: a tag the YAML core schema does
    # not know fails the parse, and nothing gets constructed
    path = tmp_path / "tagged.yaml"
    path.write_text("host: !!python/object/apply:os.system ['no']\n", encoding="utf-8")

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match="could not determine a constructor"):
        S.load_settings()


def test_y6_yaml_native_values_round_trip(tmp_path):
    # dates and timestamps native (no ISO strings), integers may carry
    # underscores, true/false are booleans and yes/no stay strings
    path = tmp_path / "native.yaml"
    path.write_text(
        "launch_on: 2026-12-01\nseen: true\namount: 1_000\nword: yes\n",
        encoding="utf-8",
    )

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        launch_on: date = yaml_setting(name="launch_on", default=date(2026, 1, 1))
        seen: bool = yaml_setting(name="seen", default=False)
        amount: int = yaml_setting(name="amount", default=1)
        word: str = yaml_setting(name="word", default="no")

    S.load_settings()
    assert S.launch_on == date(2026, 12, 1)
    assert S.seen is True
    assert S.amount == 1000
    assert S.word == "yes"

    S.launch_on = date(2027, 1, 2)
    S.save_settings()
    assert "launch_on: 2027-01-02\n" in path.read_text(encoding="utf-8")


def test_y7_path_walks_mappings_and_sequence_positions(tmp_path):
    path = tmp_path / "paths.yaml"

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="x", path="/net/proxy")
        second: str = yaml_setting(name="second", default="y", path="/mirrors/1")

    S.host = "example.com"
    S.second = "two"
    S.save_settings()
    from ruamel.yaml import YAML

    document = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    # the missing sequence grows with nulls up to the indexed position
    assert document == {
        "net": {"proxy": {"host": "example.com"}},
        "mirrors": [None, {"second": "two"}],
    }

    S.reset_settings()
    S.load_settings()
    assert S.host == "example.com"
    assert S.second == "two"


def test_y8_a_dotted_name_is_one_flat_key(tmp_path):
    path = tmp_path / "dotted.yaml"

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        first: str = yaml_setting(name="a.b.c", default="v")

    S.save_settings()
    from ruamel.yaml import YAML

    assert YAML(typ="safe").load(path.read_text(encoding="utf-8")) == {"a.b.c": "v"}


def test_y9_rewrites_preserve_the_file_and_foreign_keys_survive(tmp_path):
    path = tmp_path / "layout.yaml"
    path.write_text(
        "# the file's own header\n"
        "'quoted': kept  # inline prose\n"
        "anchored: &a mirror.example.com\n"
        "alias: *a\n"
        "flow: {a: 1}\n"
        "foreign:\n"
        "  nested: keep\n",
        encoding="utf-8",
    )

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    S.load_settings()
    S.host = "changed"
    S.save_settings()
    text = path.read_text(encoding="utf-8")
    assert "# the file's own header" in text
    assert "'quoted': kept  # inline prose" in text
    assert "anchored: &a mirror.example.com" in text
    assert "alias: *a" in text
    assert "flow: {a: 1}" in text
    assert text.index("host: changed") > text.index("foreign:")  # new keys append


def test_y10_a_fresh_file_takes_the_libraries_layout(tmp_path):
    # two spaces per mapping level, a sequence's dashes two spaces into
    # it, and a string key that looks like a number keeps its quotes —
    # the form that reads back a string again
    path = tmp_path / "fresh.yaml"

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        tags: List[str] = yaml_setting(name="tags", default=[])
        port: str = yaml_setting(name="80", default="eighty")

    S.tags = ["one", "two"]
    S.save_settings()
    assert path.read_text(encoding="utf-8") == ("tags:\n  - one\n  - two\n'80': eighty\n")


def test_y11_none_is_stored_as_the_documents_null(tmp_path):
    path = tmp_path / "nulls.yaml"

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        hint: Optional[str] = yaml_setting(name="hint", default=None)

    S.hint = None
    S.save_settings()
    from ruamel.yaml import YAML

    assert YAML(typ="safe").load(path.read_text(encoding="utf-8")) == {"hint": None}

    S.reset_settings()
    S.load_settings()
    assert S.hint is None  # the stored null, not the default happening to match


def test_y12_the_files_bom_and_line_endings_survive_the_save(tmp_path):
    path = tmp_path / "layout-kept.yaml"
    path.write_bytes(UTF8_BOM.encode("utf-8") + b"host: elsewhere\r\n")

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")
        port: int = yaml_setting(name="port", default=1)

    S.load_settings()
    S.port = 7
    S.save_settings()
    data = path.read_bytes()
    assert data.startswith(UTF8_BOM.encode("utf-8"))
    assert b"\r\n" in data


def test_y13_a_non_mapping_root_is_named(tmp_path):
    path = tmp_path / "sequence.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match="mapping at the top level, got a sequence"):
        S.load_settings()


def test_y14_the_files_permission_mode_survives_the_save(tmp_path):
    import stat

    path = tmp_path / "rights.yaml"
    path.write_text("host: elsewhere\n", encoding="utf-8")
    path.chmod(0o600)

    class S(
        Settings,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")
        port: int = yaml_setting(name="port", default=1)

    S.load_settings()
    S.port = 7
    S.save_settings()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
