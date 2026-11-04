"""The automated form of the manual usage matrix: a tour over the public API.

This is the place of the configuration package for the walkthrough that the
settings matrix runs. It covers:

- member states (the own rule of this package: omitting ``default=`` means
  ``REQUIRED``);
- declaration errors;
- each read-only source;
- the two channels of load failures;
- conversion;
- constraints;
- the read-only contract, which closes every write path;
- snapshots;
- inheritance.

The ids of the rows in the names of the tests match the manual checklist, so
the tour is re-run by::

    pytest tests/configuration/test_configuration_usage_matrix.py
"""

from __future__ import annotations

import dataclasses
import enum
import json
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, List, Optional

import pytest

from advexp.configuration import (
    REQUIRED,
    AggregateLoadError,
    Configuration,
    ConstraintViolationError,
    ConversionError,
    MemberLoadError,
    MissingValueError,
    SecretStr,
    SourceLoadError,
    Sources,
    chain_setting,
    constant_setting,
    env_parameter,
)
from advexp.configuration.plugin_api import (
    AttributeSerializerBinding,
    ConfigurationAttribute,
    ISettingAttribute,
    LibraryConfiguration,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    SourceBinding,
    SourceLink,
    UserFacingError,
)
from advexp.configuration.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.configuration.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.configuration.plugins.environment.variables import (
    NameCase,
    env_source,
    environment_variable_setting,
)
from advexp.configuration.plugins.environment.variables.serializer import (
    EnvironmentVariablesSerializer,
)
from advexp.configuration.plugins.json_settings import (
    JSONSetting,
    JSONSettingsSerializer,
    json_setting,
    json_source,
)
from advexp.configuration.plugins.mapping_source import mapping_source, mapping_source_for
from advexp.configuration.plugins.toml_settings import (
    TOMLSettingsSerializer,
    toml_setting,
    toml_source,
)
from advexp.configuration.plugins.yaml_settings import (
    yaml_setting,
    yaml_source,
)
from advexp.settings_base.file_bom import UTF8_BOM


class Shade(enum.Enum):
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


class ExplodingAttribute(ConfigurationAttribute):
    """A test source attribute whose loading always fails."""


class ExplodingSerializer(SettingsBaseSerializer):
    """A test source serializer: load raises, the rest is inert."""

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        raise RuntimeError("source exploded")

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """No-op: a test source never writes."""

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: a test source never deletes."""

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return False


class ExplodingPlugin(SettingsBasePlugin):
    """A test source plugin that binds the exploding pair."""

    binding = AttributeSerializerBinding(ExplodingAttribute, ExplodingSerializer)

    @property
    def plugin_name(self) -> str:
        return "MatrixExplodingSource"


LibraryConfiguration.register_settings_plugin(ExplodingPlugin)


def exploding_setting(**kwargs: Any) -> Any:
    return ExplodingAttribute(**kwargs)


def exploding_link() -> Any:
    # the third-party source's chain spelling: a link of its family
    return SourceBinding(SourceLink(attribute_class=ExplodingAttribute))


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


# ---------------------------------------------------------------------------
# A. Member states: this package's own rule — no default means REQUIRED
# ---------------------------------------------------------------------------


def test_a1_a_member_without_default_is_required(monkeypatch):
    monkeypatch.delenv("CMX_A1_TOKEN", raising=False)

    class C(
        Configuration,
        options=env_source(),
    ):
        token: str = environment_variable_setting(name="CMX_A1_TOKEN")

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, MissingValueError)


def test_a2_an_explicit_default_is_optional():
    class C(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="CMX_A2_MODE", default="fallback")

    report = C.load_configuration()

    assert C.mode == "fallback"
    assert report == ()


def test_a3_default_none_is_optional_the_family_way():
    class C(
        Configuration,
        options=env_source(),
    ):
        hint: Optional[str] = environment_variable_setting(name="CMX_A3_HINT", default=None)

    C.load_configuration()

    assert C.hint is None


def test_a4_reading_a_required_member_before_load_raises():
    class C(
        Configuration,
        options=env_source(),
    ):
        token: str = environment_variable_setting(name="CMX_A4_TOKEN")

    with pytest.raises(MemberLoadError, match="token"):
        _ = C.token


def test_a5_reading_an_optional_member_before_load_serves_the_default():
    class C(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="CMX_A5_MODE", default="fallback")

    assert C.mode == "fallback"


def test_a6_constant_setting_is_a_typed_constant():
    class C(Configuration):
        url: str = constant_setting(default="https://api.example")

    report = C.load_configuration()

    assert report == ()
    assert C.url == "https://api.example"


def test_a7_required_member_with_a_value_loads(monkeypatch):
    monkeypatch.setenv("CMX_A7_TOKEN", "s3cret")

    class C(
        Configuration,
        options=env_source(),
    ):
        token: str = environment_variable_setting(name="CMX_A7_TOKEN", default=REQUIRED)

    report = C.load_configuration()

    assert report == ()
    assert C.token == "s3cret"


# ---------------------------------------------------------------------------
# B. Declaration errors: the class statement itself
# ---------------------------------------------------------------------------


def test_b1_unconvertible_default_fails_the_class_statement():
    with pytest.raises(TypeError, match="born"):

        class C(Configuration):
            born: date = constant_setting(default="not-a-date")


def test_b2_default_none_rejected_by_constraints_fails_the_class():
    # a member like this is required in disguise: without a source value it
    # could never be valid
    with pytest.raises(TypeError):

        class C(Configuration):
            member: int = constant_setting(default=None, eq=5)


def test_b3_regex_that_does_not_compile_fails_the_declaration():
    with pytest.raises(ValueError):

        class C(Configuration):
            code: str = constant_setting(default="code", regex="(")


def test_b4_option_key_declared_on_both_sides_fails_the_class_statement():
    with pytest.raises(TypeError):

        class C(
            Configuration,
            options={"shared": 1},
        ):
            class_metadata = {"shared": 2}

            count: int = constant_setting(default=1)


def test_b5_an_attribute_without_a_link_names_the_fix():
    # a source family's member needs its family's link in the chain: the
    # class statement names the member, the family and the fix — before
    # any pass runs
    class OrphanAttribute(ConfigurationAttribute):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    def orphan_setting(**kwargs: Any) -> Any:
        return OrphanAttribute(**kwargs)

    with pytest.raises(
        TypeError,
        match="C.count is declared with OrphanAttribute, but the class's "
        "source chain has no link of that family. Add one to options=",
    ):

        class C(
            Configuration,
            options=env_source(),
        ):
            count: int = orphan_setting(default=1)


# ---------------------------------------------------------------------------
# C. The environment variables source
# ---------------------------------------------------------------------------


def test_c1_name_building_and_the_explicit_escape_hatch(monkeypatch):
    monkeypatch.setenv("legacy_flag", "on")
    monkeypatch.setenv("CMX_C1_MODE", "debug")

    class C(
        Configuration,
        options=env_source(name_prefix="CMX_C1_", name_case=NameCase.UPPER),
    ):
        legacy: str = environment_variable_setting(name="legacy_flag", default="off")
        mode: str = environment_variable_setting()

    C.load_configuration()

    assert C.legacy == "on"
    assert C.mode == "debug"


def test_c2_nested_delimiter_updates_the_dataclass_partially(monkeypatch):
    monkeypatch.setenv("CMX_DB__PORT", "6543")

    class C(
        Configuration,
        options=env_source(name_prefix="CMX_", name_case=NameCase.UPPER, nested_delimiter="__"),
    ):
        db: DbConfig = environment_variable_setting(default=DbConfig(host="db.local"))

    C.load_configuration()

    assert C.db == DbConfig(host="db.local", port=6543)


def test_c3_field_variable_wins_over_the_object_form(monkeypatch):
    monkeypatch.setenv("CMX_DB", '{"host": "h1", "port": 1}')
    monkeypatch.setenv("CMX_DB__PORT", "2")

    class C(
        Configuration,
        options=env_source(name_prefix="CMX_", name_case=NameCase.UPPER, nested_delimiter="__"),
    ):
        db: DbConfig = environment_variable_setting(default=DbConfig())

    C.load_configuration()

    assert C.db == DbConfig(host="h1", port=2)


def test_c4_empty_string_is_a_value_for_str_but_not_for_int(monkeypatch, caplog):
    monkeypatch.setenv("CMX_C4_TEXT", "")
    monkeypatch.setenv("CMX_C4_COUNT", "")

    class C(
        Configuration,
        options=env_source(),
    ):
        text: str = environment_variable_setting(name="CMX_C4_TEXT", default="fallback")
        count: int = environment_variable_setting(name="CMX_C4_COUNT", default=5)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = C.load_configuration()

    assert C.text == ""
    assert C.count == 5
    (entry,) = report
    assert isinstance(entry, ConversionError)
    assert fallback_warning(caplog, "count")


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
def test_c5_bool_string_forms(raw: str, expected: bool, monkeypatch):
    monkeypatch.setenv("CMX_C5_FLAG", raw)

    class C(
        Configuration,
        options=env_source(),
    ):
        flag: bool = environment_variable_setting(name="CMX_C5_FLAG", default=not expected)

    C.load_configuration()

    assert C.flag is expected


def test_c6_any_case_lookup_accepts_any_spelling(monkeypatch):
    monkeypatch.setenv("CMX_C6_HOST", "any.example.com")
    monkeypatch.setenv("cmx_c6_legacy", "on")

    class C(
        Configuration,
        options=env_source(name_prefix="CMX_C6_", name_case=NameCase.ANY),
    ):
        host: str = environment_variable_setting()
        legacy: str = environment_variable_setting(name="CMX_C6_LEGACY", default="off")

    C.load_configuration()

    # the built name and the explicit one alike resolve case-insensitively
    assert C.host == "any.example.com"
    assert C.legacy == "on"


def test_c7_any_case_two_folded_spellings_fail_the_load(monkeypatch):
    monkeypatch.setenv("CMX_C7_HOST", "one")
    monkeypatch.setenv("Cmx_C7_Host", "two")

    class C(
        Configuration,
        options=env_source(name_prefix="CMX_C7_", name_case=NameCase.ANY),
    ):
        host: str = environment_variable_setting()

    with pytest.raises(AggregateLoadError, match="two differently-cased spellings"):
        C.load_configuration()


# ---------------------------------------------------------------------------
# D. The JSON file source
# ---------------------------------------------------------------------------


def test_d1_missing_file_serves_defaults(tmp_path):
    path = tmp_path / "absent.json"

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="localhost")

    report = C.load_configuration()

    assert report == ()
    assert C.host == "localhost"


def test_d2_corrupt_file_aborts_even_for_an_optional_member(tmp_path):
    # a default must not mask the condition
    path = tmp_path / "corrupt.json"
    path.write_text("{oops", encoding="utf-8")

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        opt: int = json_setting(name="opt", default=1)

    with pytest.raises(ValueError, match="cannot parse the JSON configuration file"):
        C.load_configuration()


def test_d3_a_link_without_its_file_names_the_parameter(tmp_path):
    # a hand-built link that never spelled its file is the load's own
    # finding: the error names the builder parameter that fills it
    class C(
        Configuration,
        options=SourceBinding(SourceLink(attribute_class=JSONSetting)),
    ):
        host: str = json_setting(default="localhost")

    with pytest.raises(ValueError, match="json_source"):
        C.load_configuration()


def test_d4_dataclass_member_loads_from_the_json_object(tmp_path):
    path = tmp_path / "d4.json"
    path.write_text('{"proxy": {"host": "h", "unknown": 1}}', encoding="utf-8")

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        proxy: Proxy = json_setting(name="proxy", default=Proxy(host="seed"))

    C.load_configuration()

    assert C.proxy == Proxy(host="h")


def test_d5_load_tolerates_a_bom(tmp_path):
    path = tmp_path / "d5.json"
    path.write_bytes(UTF8_BOM.encode("utf-8") + b'{\n  "host": "remote"\n}\n')

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="localhost")

    C.load_configuration()

    assert C.host == "remote"


def test_d6_undecodable_file_names_itself(tmp_path):
    path = tmp_path / "d6.json"
    path.write_bytes('{\n  "host": "ok"\n}\n'.encode("utf-16"))

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        host: str = json_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match="cannot read the JSON configuration file"):
        C.load_configuration()


# ---------------------------------------------------------------------------
# E. Load failures: the abort channel and the report channel
# ---------------------------------------------------------------------------


def test_e1_required_unconvertible_aborts(monkeypatch):
    monkeypatch.setenv("CMX_E1_COUNT", "abc")

    class C(
        Configuration,
        options=env_source(),
    ):
        count: int = environment_variable_setting(name="CMX_E1_COUNT")

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)


def test_e2_optional_unconvertible_lands_in_the_returned_report(monkeypatch, caplog):
    monkeypatch.setenv("CMX_E2_COUNT", "abc")

    class C(
        Configuration,
        options=env_source(),
    ):
        count: int = environment_variable_setting(name="CMX_E2_COUNT", default=5)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = C.load_configuration()

    assert C.count == 5
    (entry,) = report
    assert isinstance(entry, ConversionError)
    assert fallback_warning(caplog, "count")


def test_e3_mixed_run_reports_errors_and_fallbacks_apart(monkeypatch):
    monkeypatch.delenv("CMX_E3_REQ", raising=False)
    monkeypatch.setenv("CMX_E3_OPT", "abc")

    class C(
        Configuration,
        options=env_source(),
    ):
        req: int = environment_variable_setting(name="CMX_E3_REQ")
        opt: int = environment_variable_setting(name="CMX_E3_OPT", default=3)

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()

    (error,) = info.value.errors
    (fallback,) = info.value.fallbacks
    assert isinstance(error, MissingValueError)
    assert isinstance(fallback, ConversionError)


def test_e4_clean_load_returns_an_empty_report_and_stays_silent(caplog):
    class C(Configuration):
        member: int = constant_setting(default=1)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = C.load_configuration()

    assert report == ()
    assert not report
    # a clean load is nobody's news: no warning is issued
    assert not caplog.records


def test_e5_the_taxonomy_shares_the_valueerror_root(monkeypatch):
    monkeypatch.delenv("CMX_E5", raising=False)

    family = (
        MissingValueError,
        ConversionError,
        SourceLoadError,
        AggregateLoadError,
    )
    for error_type in family:
        assert issubclass(error_type, MemberLoadError)
    assert issubclass(MemberLoadError, ValueError)

    class C(
        Configuration,
        options=exploding_link(),
    ):
        member: int = exploding_setting()

    with pytest.raises(ValueError):
        C.load_configuration()


def test_e6_the_load_is_retryable_after_an_abort(monkeypatch):
    monkeypatch.delenv("CMX_E6_TOKEN", raising=False)

    class C(
        Configuration,
        options=env_source(),
    ):
        token: str = environment_variable_setting(name="CMX_E6_TOKEN")

    with pytest.raises(AggregateLoadError):
        C.load_configuration()

    monkeypatch.setenv("CMX_E6_TOKEN", "fixed")
    report = C.load_configuration()

    assert report == ()
    assert C.token == "fixed"


def test_e7_source_failure_for_a_required_member():
    class C(
        Configuration,
        options=exploding_link(),
    ):
        member: int = exploding_setting()

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, SourceLoadError)


def test_e8_optional_member_source_failure_falls_back(caplog):
    class C(
        Configuration,
        options=exploding_link(),
    ):
        member: int = exploding_setting(default=7)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = C.load_configuration()

    assert C.member == 7
    (entry,) = report
    assert isinstance(entry, SourceLoadError)
    # a source exception is logged at ERROR in the full fallback shape —
    # the member's place, the source that raised, the fallback tail — so
    # the log alone tells the member stood at its default; the report
    # entry carries the same finding for the caller
    assert [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ] == [
        "member 'member' (test_configuration_usage_matrix.C.member) of 'C': "
        "its source raised RuntimeError (source exploded); using the default value"
    ]


# ---------------------------------------------------------------------------
# F. Conversion
# ---------------------------------------------------------------------------


def test_f1_value_types_load_converted(tmp_path):
    path = tmp_path / "f1.json"
    path.write_text(
        json.dumps(
            {
                "ttl": "1:30:00",
                "amount": "2.5",
                "tag": "12345678-1234-5678-1234-567812345678",
                "shade": "BLUE",
                "counts": [3, 4],
            }
        ),
        encoding="utf-8",
    )

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        ttl: timedelta = json_setting(name="ttl", default="0:30:00")
        amount: Decimal = json_setting(name="amount", default="1.5")
        tag: uuid.UUID = json_setting(name="tag", default="00000000-0000-0000-0000-000000000000")
        shade: Shade = json_setting(name="shade", default=Shade.RED)
        counts: List[int] = json_setting(name="counts", default=[1, 2])

    C.load_configuration()

    assert C.ttl == timedelta(seconds=5400)
    assert isinstance(C.ttl, timedelta)
    assert C.amount == Decimal("2.5")
    assert isinstance(C.amount, Decimal)
    assert C.tag == uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert C.shade is Shade.BLUE
    assert C.counts == [3, 4]


def test_f2_secret_members_mask_their_payload(monkeypatch):
    monkeypatch.setenv("CMX_F2_TOKEN", "s3cr3t")

    class C(
        Configuration,
        options=env_source(),
    ):
        token: SecretStr = environment_variable_setting(name="CMX_F2_TOKEN")

    C.load_configuration()

    assert str(C.token) == "**********"
    assert C.token.get_secret_value() == "s3cr3t"


def test_f3_true_is_not_an_int(tmp_path):
    path = tmp_path / "f3.json"
    path.write_text('{"count": true}', encoding="utf-8")

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        count: int = json_setting(name="count", default=5)

    report = C.load_configuration()

    assert C.count == 5
    (entry,) = report
    assert isinstance(entry, ConversionError)


# ---------------------------------------------------------------------------
# G. Constraints and cross-member rules
# ---------------------------------------------------------------------------


def test_g1_load_time_violation_splits_by_channel(monkeypatch, caplog):
    monkeypatch.setenv("CMX_G1_OPT", "0")
    monkeypatch.setenv("CMX_G1_REQ", "0")

    class C(
        Configuration,
        options=env_source(),
    ):
        opt: int = environment_variable_setting(name="CMX_G1_OPT", default=7, ge=1)
        req: int = environment_variable_setting(name="CMX_G1_REQ", ge=1)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            C.load_configuration()

    assert C.opt == 7
    (fallback,) = info.value.fallbacks
    assert isinstance(fallback, ConstraintViolationError)
    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert fallback_warning(caplog, "opt")


def test_g2_cross_rule_violation_on_load_resets_the_participants(tmp_path, caplog):
    path = tmp_path / "g2.json"
    path.write_text('{"min_port": 2000, "max_port": 1000}', encoding="utf-8")

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        min_port: int = json_setting(name="min_port", default=1024)
        max_port: int = json_setting(name="max_port", default=65535, ge=min_port)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = C.load_configuration()

    assert C.min_port == 1024
    assert C.max_port == 65535
    assert report
    assert any(
        "resetting the members to their defaults" in record.getMessage()
        for record in caplog.records
    )


def test_g3_when_gates_the_constraints():
    class C(Configuration):
        ssl: bool = constant_setting(default=False)
        port: int = constant_setting(default=80, eq=443, when=ssl)

    report = C.load_configuration()

    assert report == ()
    assert C.port == 80


def test_g4_hook_findings_no_reset_settles_abort_the_load(monkeypatch, caplog):
    # the finding names a member already at its default: no reset can
    # settle it, the pass aborts, and the class keeps the state it had
    # — a completed load is either consistent or did not complete
    monkeypatch.setenv("CMX_G4_MODE", "prod")

    class C(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="CMX_G4_MODE", default="dev")
        ssl: Optional[str] = environment_variable_setting(name="CMX_G4_SSL", default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            C.load_configuration()

    (entry,) = info.value.errors
    assert isinstance(entry, ConstraintViolationError)
    assert "no reset to the declared defaults settles it" in str(entry)
    assert C.mode == "dev"
    assert C.ssl is None
    assert any("the pass is aborted" in record.getMessage() for record in caplog.records)


def test_g5_the_hook_does_not_run_at_class_creation():
    # the class statement checks the declared defaults against the
    # comparison rules alone; the README's checkpoint wording overstates
    # the hook's reach — it joins from the first load on (tour finding)
    class C(Configuration):
        mode: str = constant_setting(default="prod")
        ssl: Optional[str] = constant_setting(default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    # created without an error, the all-default state violating the hook
    assert C.mode == "prod"
    assert C.ssl is None


def test_g6_validation_exceptions_propagate_as_is(monkeypatch, caplog):
    # an exception the hook or a custom validator raises is a bug in user
    # code, not a property of the values: the load crashes with it as is,
    # after an ERROR record keeps the crash visible in the log
    class ExplodingHook(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="MTX_G6_MODE", default="dev")

        def __validate__(self) -> dict:
            raise ZeroDivisionError("hook bug")

    with caplog.at_level(logging.ERROR, logger="advexp.configuration"):
        with pytest.raises(ZeroDivisionError, match="hook bug"):
            ExplodingHook.load_configuration()

    def no_empty(value: str) -> bool:
        if value == "":
            raise RuntimeError("validator bug")
        return True

    class ExplodingValidator(
        Configuration,
        options=env_source(),
    ):
        enabled: bool = environment_variable_setting(name="MTX_G6_ENABLED", default=False)
        mode: str = environment_variable_setting(
            name="MTX_G6_MODE", default="dev", validator=no_empty, when=enabled
        )

    monkeypatch.setenv("MTX_G6_ENABLED", "1")
    monkeypatch.setenv("MTX_G6_MODE", "")
    with caplog.at_level(logging.ERROR, logger="advexp.configuration"):
        with pytest.raises(RuntimeError, match="validator bug"):
            ExplodingValidator.load_configuration()

    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ]
    assert "validation exception in the cross-member checks of 'ExplodingHook': hook bug" in (
        error_messages
    )
    assert "validation exception for member 'mode': validator bug" in error_messages


def test_g7_a_hook_finding_that_survives_its_reset_aborts_the_load(monkeypatch, caplog):
    # the reset of the named member happens, the finding comes back —
    # the reset settled nothing, so the pass aborts and the class keeps
    # the state it had
    monkeypatch.setenv("CMX_G7_MODE", "prod")
    monkeypatch.setenv("CMX_G7_SSL", "maybe")

    class C(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="CMX_G7_MODE", default="dev")
        ssl: str = environment_variable_setting(name="CMX_G7_SSL", default="none")

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl != "on":
                return {"ssl": "ssl must be 'on' in production mode"}
            return {}

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            C.load_configuration()

    (entry,) = info.value.errors
    assert isinstance(entry, ConstraintViolationError)
    assert "no reset to the declared defaults settles it" in str(entry)
    assert C.mode == "dev"
    assert C.ssl == "none"
    messages = [record.getMessage() for record in caplog.records]
    assert any("resetting the members to their defaults: ssl" in m for m in messages)
    assert any("the pass is aborted" in m for m in messages)


def test_g8_a_required_participant_no_reset_reaches_aborts_the_load(monkeypatch, caplog):
    # the declared rule binds ceil to the required floor; floor holds
    # its loaded value with no default to reset to, and ceil already
    # stands at its default — the pass cannot settle the rule and aborts
    monkeypatch.setenv("CMX_G8_FLOOR", "5000")
    monkeypatch.setenv("CMX_G8_CEIL", "100")

    class C(
        Configuration,
        options=env_source(),
    ):
        floor: int = environment_variable_setting(name="CMX_G8_FLOOR", default=REQUIRED)
        ceil: int = environment_variable_setting(name="CMX_G8_CEIL", default=100, ge=floor)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            C.load_configuration()

    (entry,) = info.value.errors
    assert isinstance(entry, ConstraintViolationError)
    assert str(entry).startswith("member 'ceil' of 'C' violates its constraints")
    assert "no reset to the declared defaults settles it" in str(entry)
    assert any("has no default to reset to" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# H. The read-only contract: every write path is closed
# ---------------------------------------------------------------------------


def test_h1_class_member_assignment_raises():
    class C(Configuration):
        mode: str = constant_setting(default="x")

    with pytest.raises(TypeError, match="read-only"):
        C.mode = "y"


def test_h2_instance_member_writes_and_deletions_raise():
    class C(Configuration):
        mode: str = constant_setting(default="x")

    instance = C()

    with pytest.raises(TypeError, match="read-only"):
        instance.mode = "y"

    with pytest.raises(TypeError, match="read-only"):
        del instance.mode


def test_h3_to_dict_is_a_frozen_mapping():
    class C(Configuration):
        mode: str = constant_setting(default="x")

    snapshot = C.to_dict()

    with pytest.raises(TypeError):
        snapshot["mode"] = "y"  # type: ignore[index]

    mutable = dict(snapshot)
    mutable["mode"] = "ok"
    assert mutable == {"mode": "ok"}


def test_h4_to_object_accepts_no_attribute_writes():
    class C(Configuration):
        mode: str = constant_setting(default="x")

    state = C.to_object()

    # a member write hits the read-only guard; any other attribute hits
    # the snapshot's own frozen guard
    with pytest.raises(TypeError, match="read-only"):
        state.mode = "y"

    with pytest.raises(TypeError, match="frozen"):
        state.other = 1  # type: ignore[attr-defined]


def test_h5_the_class_has_no_write_back_methods():
    class C(Configuration):
        mode: str = constant_setting(default="x")

    write_back = (
        "save_settings",
        "save_setting",
        "delete_settings",
        "delete_setting",
        "update_from_dict",
        "update_from_object",
        "validate_settings",
        "reset_settings",
        "reset_setting",
    )
    for name in write_back:
        assert not hasattr(C, name)


def test_h6_load_configuration_is_the_one_writer(monkeypatch):
    monkeypatch.setenv("CMX_H6_MODE", "first")

    class C(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="CMX_H6_MODE", default="d")

    C.load_configuration()
    assert C.mode == "first"

    monkeypatch.setenv("CMX_H6_MODE", "second")
    C.load_configuration()
    assert C.mode == "second"


def test_h7_write_operations_of_every_bundled_source_refuse_loudly():
    # the write operations exist for the serializer contract alone: the
    # package's facade never calls them, and a caller that reaches one
    # hears the read-only refusal instead of a silent no-op
    serializers = [
        JSONSettingsSerializer(),
        TOMLSettingsSerializer(),
        EnvironmentVariablesSerializer(),
        DotenvSerializer(),
    ]
    for serializer in serializers:
        with pytest.raises(UserFacingError, match="read-only: it loads and never writes"):
            serializer.save("member", None, 1)
        with pytest.raises(UserFacingError, match="read-only: it loads and never deletes"):
            serializer.delete("member", None)


# ---------------------------------------------------------------------------
# I. Inheritance
# ---------------------------------------------------------------------------


def test_i1_subclass_loads_base_members_into_its_own_storage(monkeypatch):
    monkeypatch.setenv("CMX_I1_MODE", "env-value")

    class Base(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="CMX_I1_MODE", default="base-default")

    class Child(Base):
        extra: int = constant_setting(default=1)

    Child.load_configuration()

    assert Child.mode == "env-value"
    assert Base.mode == "base-default"


def test_i2_subclass_options_do_not_move_inherited_names(monkeypatch):
    monkeypatch.setenv("CMX_BASE_MODE", "from-base")
    monkeypatch.setenv("CMX_CHILD_OWN", "from-child")

    class Base(
        Configuration,
        options=env_source(name_prefix="CMX_BASE_", name_case=NameCase.UPPER),
    ):
        mode: str = environment_variable_setting(default="production")

    class Child(
        Base,
        options=env_source(name_prefix="CMX_CHILD_", name_case=NameCase.UPPER),
    ):
        own: str = environment_variable_setting(default="x")

    Child.load_configuration()

    assert Child.mode == "from-base"
    assert Child.own == "from-child"


def test_i3_a_redeclared_member_retunes_one_branch(monkeypatch):
    # the class options that retuned an ancestor's members are gone with
    # them; the seat that naming has now is a chain of the subclass's own
    # plus the member redeclared in it: the subclass's naming governs the
    # redeclared member, and the ancestor keeps its own variables
    monkeypatch.setenv("CMX_SAFE_MODE", "safe-value")
    monkeypatch.setenv("CMX_BASE_MODE", "base-value")

    class Base(
        Configuration,
        options=env_source(name_prefix="CMX_BASE_", name_case=NameCase.UPPER),
    ):
        mode: str = environment_variable_setting(default="production")

    class Branch(
        Base,
        options=env_source(name_prefix="CMX_SAFE_", name_case=NameCase.UPPER),
    ):
        mode: str = environment_variable_setting(default="production")

    Branch.load_configuration()
    assert Branch.mode == "safe-value"

    Base.load_configuration()
    assert Base.mode == "base-value"


# ---------------------------------------------------------------------------
# J. The dotenv file source
# ---------------------------------------------------------------------------


def test_j1_dotenv_source_reads_the_file(tmp_path):
    env_path = tmp_path / "app.env"
    env_path.write_text("CMX_J1_MODE=from-file\n", encoding="utf-8")

    class C(
        Configuration,
        options=dotenv_source(file=env_path),
    ):
        mode: str = dotenv_setting(name="CMX_J1_MODE", default="fallback")

    C.load_configuration()

    assert C.mode == "from-file"


def test_j2_missing_dotenv_file_is_treated_as_empty(tmp_path):
    env_path = tmp_path / "absent.env"

    class C(
        Configuration,
        options=dotenv_source(file=env_path),
    ):
        mode: str = dotenv_setting(name="CMX_J2_MODE", default="fallback")

    report = C.load_configuration()

    assert report == ()
    assert C.mode == "fallback"


# ---------------------------------------------------------------------------
# K. Source: TOML
# ---------------------------------------------------------------------------


def test_k1_missing_file_serves_defaults(tmp_path):
    path = tmp_path / "absent.toml"

    class C(
        Configuration,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="localhost")

    report = C.load_configuration()

    assert report == ()
    assert C.host == "localhost"


def test_k2_corrupt_file_aborts_even_for_an_optional_member(tmp_path):
    # a default must not mask the condition
    path = tmp_path / "corrupt.toml"
    path.write_text("[oops", encoding="utf-8")

    class C(
        Configuration,
        options=toml_source(file=path),
    ):
        opt: int = toml_setting(name="opt", default=1)

    with pytest.raises(ValueError, match="cannot parse the TOML configuration file"):
        C.load_configuration()


def test_k3_native_datetimes_arrive_converted(tmp_path):
    path = tmp_path / "k3.toml"
    path.write_text("stamp = 2026-10-09T12:30:00\n", encoding="utf-8")

    class C(
        Configuration,
        options=toml_source(file=path),
    ):
        stamp: datetime = toml_setting(name="stamp", default=datetime(2026, 1, 1))

    C.load_configuration()

    # the value is native TOML: the parser hands a datetime over, no string
    assert C.stamp == datetime(2026, 10, 9, 12, 30, 0)


def test_k4_dataclass_member_loads_from_the_toml_table(tmp_path):
    path = tmp_path / "k4.toml"
    path.write_text('[proxy]\nhost = "h"\nunknown = 1\n', encoding="utf-8")

    class C(
        Configuration,
        options=toml_source(file=path),
    ):
        proxy: Proxy = toml_setting(name="proxy", default=Proxy(host="seed"))

    C.load_configuration()

    assert C.proxy == Proxy(host="h")


def test_k5_pattern_names_read_from_the_tables_they_address(tmp_path):
    path = tmp_path / "k5.toml"

    class C(
        Configuration,
        options=toml_source(file=path),
    ):
        port: int = toml_setting(default=9000)  # the full pattern name
        host: str = toml_setting(name="host", default="localhost")

    # the dot is TOML's table separator: a pattern-built key lives at the
    # address it names — [module.Class] port — never a quoted flat key
    lines = ['host = "preset"', "", f"[{C.__module__}.{C.__name__}]", "port = 8080"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    C.load_configuration()
    assert C.host == "preset"
    assert C.port == 8080


def test_k6_undecodable_file_names_itself(tmp_path):
    path = tmp_path / "k6.toml"
    path.write_bytes('host = "ok"\n'.encode("utf-16"))

    class C(
        Configuration,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match="cannot read the TOML configuration file"):
        C.load_configuration()


def test_k7_bom_file_names_the_cause(tmp_path):
    path = tmp_path / "k7.toml"
    path.write_bytes(UTF8_BOM.encode("utf-8") + b'host = "ok"\n')

    class C(
        Configuration,
        options=toml_source(file=path),
    ):
        host: str = toml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match="it starts with a UTF-8 BOM"):
        C.load_configuration()


# ---------------------------------------------------------------------------
# M. Message completeness: the context every diagnostic carries
# ---------------------------------------------------------------------------


def test_m1_env_conversion_entry_and_log_name_everything(monkeypatch, caplog):
    monkeypatch.setenv("CMX_M1_RETRY_COUNT", "abc")

    class MatrixMsgConfig(
        Configuration,
        options=env_source(),
    ):
        retry_count: int = environment_variable_setting(name="CMX_M1_RETRY_COUNT", default=5)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        (entry,) = MatrixMsgConfig.load_configuration()

    storage = "environment variable 'CMX_M1_RETRY_COUNT'"
    assert_diagnostic_context(
        str(entry), member="retry_count", owner="MatrixMsgConfig", storage=storage
    )
    warning = caplog.records[0].getMessage()
    assert_diagnostic_context(
        warning, member="retry_count", owner="MatrixMsgConfig", storage=storage
    )


def test_m2_env_missing_required_names_everything(monkeypatch):
    monkeypatch.delenv("CMX_M2_API_TOKEN", raising=False)

    class MatrixMsgConfig(
        Configuration,
        options=env_source(),
    ):
        api_token: str = environment_variable_setting(name="CMX_M2_API_TOKEN")

    with pytest.raises(AggregateLoadError) as info:
        MatrixMsgConfig.load_configuration()

    entry_text = str(info.value.errors[0])
    assert_diagnostic_context(
        entry_text,
        member="api_token",
        owner="MatrixMsgConfig",
        storage="environment variable 'CMX_M2_API_TOKEN'",
    )
    # the aggregate's own message repeats each entry verbatim
    assert entry_text in str(info.value)


def test_m3_constraint_entry_names_everything(monkeypatch):
    monkeypatch.setenv("CMX_M3_RETRY_COUNT", "0")

    class MatrixMsgConfig(
        Configuration,
        options=env_source(),
    ):
        retry_count: int = environment_variable_setting(name="CMX_M3_RETRY_COUNT", default=5, ge=1)

    (entry,) = MatrixMsgConfig.load_configuration()

    assert_diagnostic_context(
        str(entry),
        member="retry_count",
        owner="MatrixMsgConfig",
        storage="environment variable 'CMX_M3_RETRY_COUNT'",
    )


def test_m4_json_entry_names_the_file_too(tmp_path):
    path = tmp_path / "m4.json"
    path.write_text('{"retry_count": "abc"}', encoding="utf-8")

    class MatrixMsgConfig(
        Configuration,
        options=json_source(file=path),
    ):
        retry_count: int = json_setting(name="retry_count", default=5)

    (entry,) = MatrixMsgConfig.load_configuration()

    assert_diagnostic_context(
        str(entry),
        member="retry_count",
        owner="MatrixMsgConfig",
        storage=f"key 'retry_count' in the JSON file {path}",
    )


def test_m5_source_failure_entry_names_member_and_class_but_not_the_source(caplog):
    # the exception entry names the member and its class but not the
    # source the member lives in; the ERROR log record carries the full
    # shape — the member's place and the source that raised — with no
    # tail, for the required member holds no default to fall back to (the
    # abort carries its channel words)
    class MatrixMsgConfig(
        Configuration,
        options=exploding_link(),
    ):
        api_token: str = exploding_setting()

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            MatrixMsgConfig.load_configuration()

    text = str(info.value.errors[0])
    assert "api_token" in text
    assert "MatrixMsgConfig" in text
    record = caplog.records[0].getMessage()
    assert record == (
        "member 'api_token' (test_configuration_usage_matrix.MatrixMsgConfig.api_token) "
        "of 'MatrixMsgConfig': its source raised RuntimeError (source exploded)"
    )


def test_m6_toml_entry_names_the_file_too(tmp_path):
    path = tmp_path / "m6.toml"
    path.write_text('retry_count = "abc"\n', encoding="utf-8")

    class MatrixMsgConfig(
        Configuration,
        options=toml_source(file=path),
    ):
        retry_count: int = toml_setting(name="retry_count", default=5)

    (entry,) = MatrixMsgConfig.load_configuration()

    assert_diagnostic_context(
        str(entry),
        member="retry_count",
        owner="MatrixMsgConfig",
        storage=f"key 'retry_count' in the TOML file {path}",
    )


# ---------------------------------------------------------------------------
# R. The repeated pass: a completed load rebuilds the state from a clean
#    slate, a failed one leaves the class as the call found it
# ---------------------------------------------------------------------------


def test_r1_a_completed_pass_leaves_no_value_of_an_earlier_one(monkeypatch):
    class C(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="CMX_R1_MODE", default="default-mode")

    monkeypatch.setenv("CMX_R1_MODE", "from-env")
    C.load_configuration()
    assert C.mode == "from-env"

    monkeypatch.delenv("CMX_R1_MODE", raising=False)
    assert C.load_configuration() == ()
    # the member's source came up empty: the earlier pass's value does not
    # survive, the declared default is what stands
    assert C.mode == "default-mode"


def test_r2_an_aborting_pass_leaves_the_class_as_it_found_it(monkeypatch):
    class C(
        Configuration,
        options=env_source(),
    ):
        token: str = environment_variable_setting(name="CMX_R2_TOKEN")
        mode: str = environment_variable_setting(name="CMX_R2_MODE", default="default-mode")

    monkeypatch.setenv("CMX_R2_TOKEN", "token-value")
    monkeypatch.setenv("CMX_R2_MODE", "first")
    C.load_configuration()

    monkeypatch.delenv("CMX_R2_TOKEN", raising=False)
    monkeypatch.setenv("CMX_R2_MODE", "second")
    with pytest.raises(AggregateLoadError):
        C.load_configuration()

    # nothing the failed pass produced is applied: the fresh 'second' rides
    # with the abort — the class keeps the state the earlier pass built
    assert C.mode == "first"
    assert C.token == "token-value"


def test_r3_a_user_facing_source_error_leaves_the_class_as_it_found_it(monkeypatch, tmp_path):
    path = tmp_path / "r3.toml"
    path.write_text("[not toml", encoding="utf-8")

    class C(
        Configuration,
        options=Sources(env_source(), toml_source(file=path)),
    ):
        mode: str = environment_variable_setting(name="CMX_R3_MODE", default="default-mode")
        port: int = toml_setting(name="port", default=8080)

    monkeypatch.setenv("CMX_R3_MODE", "from-env")
    with pytest.raises(ValueError, match="cannot parse the TOML configuration file"):
        C.load_configuration()

    # mode loaded before the source broke; the abort applies nothing
    assert C.mode == "default-mode"
    assert C.port == 8080


def test_r4_a_failing_optional_member_gets_its_default_not_the_old_value(monkeypatch):
    class C(
        Configuration,
        options=env_source(),
    ):
        count: int = environment_variable_setting(name="CMX_R4_COUNT", default=5)

    monkeypatch.setenv("CMX_R4_COUNT", "42")
    C.load_configuration()
    assert C.count == 42

    monkeypatch.setenv("CMX_R4_COUNT", "abc")
    C.load_configuration()

    # even a formally successful pass depends only on the declared defaults
    # and the current sources: the old value does not stand in
    assert C.count == 5


# ---------------------------------------------------------------------------
# V. Validation: every parameter, the two checkpoints a read-only class has
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
def test_v1_ordering_bounds(parameter: str, bound: int, bad: int, good: int, monkeypatch):
    constraints: dict[str, Any] = {parameter: bound}

    class C(
        Configuration,
        options=env_source(),
    ):
        member: int = environment_variable_setting(
            name="CMX_V1_MEMBER", default=good, **constraints
        )

    monkeypatch.setenv("CMX_V1_MEMBER", str(bad))
    (entry,) = C.load_configuration()
    assert isinstance(entry, ConstraintViolationError)
    assert C.member == good

    monkeypatch.setenv("CMX_V1_MEMBER", str(good))
    assert C.load_configuration() == ()
    assert C.member == good


def test_v2_eq_and_ne(monkeypatch):
    class C(
        Configuration,
        options=env_source(),
    ):
        pinned: int = environment_variable_setting(name="CMX_V2_A", default=5, eq=5)
        banned: int = environment_variable_setting(name="CMX_V2_B", default=6, ne=5)

    monkeypatch.setenv("CMX_V2_A", "6")
    monkeypatch.setenv("CMX_V2_B", "5")
    report = C.load_configuration()

    assert C.pinned == 5
    assert C.banned == 6
    assert len(report) == 2
    assert all(isinstance(entry, ConstraintViolationError) for entry in report)


def test_v3_length_bounds(monkeypatch):
    class C(
        Configuration,
        options=env_source(),
    ):
        name: str = environment_variable_setting(
            name="CMX_V3_A", default="ab", min_length=2, max_length=4
        )
        tags: List[str] = environment_variable_setting(
            name="CMX_V3_B", default=["seed"], min_length=1
        )

    monkeypatch.setenv("CMX_V3_A", "a")
    monkeypatch.setenv("CMX_V3_B", "[]")
    report = C.load_configuration()

    assert C.name == "ab"
    assert C.tags == ["seed"]
    assert len(report) == 2
    assert all(isinstance(entry, ConstraintViolationError) for entry in report)


def test_v4_regex_is_unanchored(monkeypatch):
    # the anchors are the declarer's: a bare pattern matches anywhere
    class C(
        Configuration,
        options=env_source(),
    ):
        anywhere: str = environment_variable_setting(name="CMX_V4_A", default="hello", regex="ell")
        exact: str = environment_variable_setting(name="CMX_V4_B", default="ell", regex=r"^ell$")

    monkeypatch.setenv("CMX_V4_A", "abc")
    monkeypatch.setenv("CMX_V4_B", "hello")
    report = C.load_configuration()

    assert C.anywhere == "hello"
    assert C.exact == "ell"
    assert len(report) == 2
    assert all(isinstance(entry, ConstraintViolationError) for entry in report)


def test_v5_validator_callable(monkeypatch):
    def even(value: int) -> bool:
        return value % 2 == 0

    class C(
        Configuration,
        options=env_source(),
    ):
        count: int = environment_variable_setting(name="CMX_V5_MEMBER", default=2, validator=even)

    monkeypatch.setenv("CMX_V5_MEMBER", "3")
    (entry,) = C.load_configuration()
    assert isinstance(entry, ConstraintViolationError)
    assert C.count == 2

    monkeypatch.setenv("CMX_V5_MEMBER", "4")
    assert C.load_configuration() == ()
    assert C.count == 4


def test_v6_none_passes_ordering_length_regex_and_ne():
    class C(
        Configuration,
        options=env_source(),
    ):
        bounded: Optional[int] = environment_variable_setting(name="CMX_V6_A", default=None, gt=0)
        texty: Optional[str] = environment_variable_setting(
            name="CMX_V6_B", default=None, regex="ell", min_length=1
        )
        banned: Optional[int] = environment_variable_setting(name="CMX_V6_C", default=None, ne=5)

    report = C.load_configuration()

    assert report == ()
    assert C.bounded is None
    assert C.texty is None
    assert C.banned is None


def test_v7_constraints_a_value_cannot_apply_to_are_violations():
    # reported as violations with their own messages, never as crashes
    with pytest.raises(TypeError, match="not comparable"):

        class BadOrdering(Configuration):
            member: object = constant_setting(default="text", gt=0)

    with pytest.raises(TypeError, match="no length"):

        class BadLength(Configuration):
            member: int = constant_setting(default=5, min_length=2)

    with pytest.raises(TypeError, match="not a string"):

        class BadRegex(Configuration):
            member: object = constant_setting(default=5, regex=r"\d+")


def test_v8_the_two_checkpoints_a_violation_meets(monkeypatch):
    # a read-only class has exactly two: class creation and the end of a load
    with pytest.raises(TypeError, match="invalid defaults"):

        class AtClassCreation(Configuration):
            member: int = constant_setting(default=0, ge=1)

    class C(
        Configuration,
        options=env_source(),
    ):
        member: int = environment_variable_setting(name="CMX_V8_MEMBER", default=5, ge=1)

    monkeypatch.setenv("CMX_V8_MEMBER", "0")
    (entry,) = C.load_configuration()
    assert isinstance(entry, ConstraintViolationError)
    assert C.member == 5


# ---------------------------------------------------------------------------
# N: aliases — several addresses of one member, first found wins
# ---------------------------------------------------------------------------


def test_n1_alias_order_primary_then_declaration_order(monkeypatch):
    for name in ("CMX_N1_PRIMARY", "CMX_N1_FIRST", "CMX_N1_SECOND"):
        monkeypatch.delenv(name, raising=False)

    class C(
        Configuration,
        options=env_source(),
    ):
        ttl: str = environment_variable_setting(
            name="CMX_N1_PRIMARY",
            aliases=["CMX_N1_FIRST", "CMX_N1_SECOND"],
            default="default",
        )

    monkeypatch.setenv("CMX_N1_SECOND", "second")
    C.load_configuration()
    assert C.ttl == "second"  # the last alias serves alone

    monkeypatch.setenv("CMX_N1_FIRST", "first")
    C.load_configuration()
    assert C.ttl == "first"  # the first declared alias wins

    monkeypatch.setenv("CMX_N1_PRIMARY", "primary")
    C.load_configuration()
    assert C.ttl == "primary"  # the primary address outranks every alias


def test_n2_json_alias_keys_land_under_the_same_path(tmp_path):
    path = tmp_path / "n2.json"

    class C(
        Configuration,
        options=json_source(file=path),
    ):
        host: str = json_setting(
            name="host", path="/net/proxy", aliases=["host_main"], default="localhost"
        )

    path.write_text('{"net": {"proxy": {"host_main": "alias.example"}}}', encoding="utf-8")
    C.load_configuration()
    assert C.host == "alias.example"


def test_n3_miss_diagnostics_list_every_address(monkeypatch):
    for name in ("CMX_N3_TOKEN", "CMX_N3_TOKEN_OLD"):
        monkeypatch.delenv(name, raising=False)

    class C(
        Configuration,
        options=env_source(),
    ):
        token: str = environment_variable_setting(
            name="CMX_N3_TOKEN", aliases=["CMX_N3_TOKEN_OLD"], default=REQUIRED
        )

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()

    assert "(environment variable 'CMX_N3_TOKEN' (aliases: 'CMX_N3_TOKEN_OLD'))" in str(
        info.value.errors[0]
    )


# ---------------------------------------------------------------------------
# S. The source chain: a layered class resolves through its links
# ---------------------------------------------------------------------------


BASE_DEFAULTS = {"token": "map-token", "host": "map-host", "extra": "unused"}


def test_s1_the_first_link_providing_a_value_wins(monkeypatch, tmp_path):
    # env holds the value, the file and the dictionary hold their own: the
    # chain reads top to bottom, the link above wins
    monkeypatch.setenv("CMX_S1_HOST", "env-host")
    app = tmp_path / "s1.json"
    app.write_text(json.dumps({"host": "json-host", "token": "json-token"}), encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_S1_", name_case=NameCase.UPPER),
            json_source(file=app, name_pattern="{FieldName}"),
            mapping_source(dict(BASE_DEFAULTS)),
        ),
    ):
        host: str = "default-host"
        token: str

    C.load_configuration()
    assert C.host == "env-host"
    assert C.token == "json-token"  # env missed, the file provided


def test_s2_a_miss_walks_down_and_the_default_is_the_last_layer(monkeypatch, tmp_path):
    # no link holds the value: the declared default is what stands in
    monkeypatch.delenv("CMX_S2_HOST", raising=False)
    app = tmp_path / "s2.json"
    app.write_text("{}", encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_S2_", name_case=NameCase.UPPER),
            json_source(file=app, name_pattern="{FieldName}"),
            mapping_source({}),
        ),
    ):
        host: str = "default-host"

    C.load_configuration()
    assert C.host == "default-host"


def test_s3_a_broken_link_ends_the_walk_not_the_masking_of_it(tmp_path):
    # a corrupt file is the pass's own condition: the layers below it —
    # a dictionary holding the value — never mask it
    app = tmp_path / "s3.json"
    app.write_text("{not json", encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            json_source(file=app),
            mapping_source({"host": "map-host"}),
        ),
    ):
        host: str

    with pytest.raises(ValueError, match="cannot parse the JSON configuration file"):
        C.load_configuration()


def test_s4_an_unconvertible_value_is_the_members_error_not_a_walk_down(monkeypatch):
    # the first value found converts once; a failed conversion is that
    # member's failure, the links below never take over
    monkeypatch.setenv("CMX_S4_PORT", "not-a-number")

    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_S4_", name_case=NameCase.UPPER),
            mapping_source({"port": 8080}),
        ),
    ):
        port: int

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()
    assert isinstance(info.value.errors[0], ConversionError)


def test_s5_the_link_path_prefixes_the_members_path(tmp_path):
    # the link anchors its keys inside a subtree; the member's own path
    # locates the key within it — and the prefix cannot be cancelled,
    # only escaped by another link over the same file
    app = tmp_path / "s5.json"
    app.write_text(
        json.dumps({"env": {"prod": {"server": {"url": "prod.example"}}, "other": 1}, "top": 2}),
        encoding="utf-8",
    )

    class C(
        Configuration,
        options=Sources(
            json_source(file=app, path="/env/prod"),
            json_source(file=app, path=""),
        ),
    ):
        url: str = json_setting(name="url", path="/server", default="fallback")
        top: int = json_setting(name="top", default=0)

    C.load_configuration()
    assert C.url == "prod.example"  # /env/prod + /server + url
    assert C.top == 2  # the second link: the same file from the root


def test_s6_the_mapping_link_speaks_member_names_alone(tmp_path, caplog):
    # the dictionary is keyed by member name: an explicit name= and the
    # declared aliases change nothing for it, and a key naming no member
    # drops out with a debug record
    class C(
        Configuration,
        options=mapping_source({"host": "map-host", "legacy": "old-host", "foreign": 42}),
    ):
        host: str = chain_setting(name="HOST", aliases=["OLD_HOST"], default="fallback")

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        C.load_configuration()
    assert C.host == "map-host"
    assert any("does not match any member" in record.getMessage() for record in caplog.records)


def test_s7_one_naming_seat_per_class_and_the_siblings_read_it(tmp_path):
    # the naming dictionary is declared on one environment link; the
    # dotenv sibling reads the same rules, and a second declaration
    # fails the class statement
    env_file = tmp_path / "s7.env"
    env_file.write_text("CMX_S7_TOKEN=file-token\n", encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_S7_", name_case=NameCase.UPPER),
            dotenv_source(file=env_file),
        ),
    ):
        token: str

    C.load_configuration()  # the file answered under the shared rules
    assert C.token == "file-token"

    with pytest.raises(TypeError, match="more than once"):

        class Bad(
            Configuration,
            options=Sources(
                env_source(name_prefix="A_"),
                dotenv_source(file=env_file, name_prefix="B_"),
            ),
        ):
            token: str


def test_s8_a_subclasses_chain_replaces_the_bases_for_it_alone(monkeypatch, tmp_path):
    monkeypatch.setenv("CMX_S8_HOST", "env-host")
    other = tmp_path / "s8.json"
    other.write_text(json.dumps({"host": "other-host"}), encoding="utf-8")

    class Base(
        Configuration,
        options=env_source(name_prefix="CMX_S8_", name_case=NameCase.UPPER),
    ):
        host: str = "default-host"

    class Child(
        Base,
        options=json_source(file=other, name_pattern="{FieldName}"),
    ):
        pass

    Child.load_configuration()
    Base.load_configuration()
    assert Child.host == "other-host"
    assert Base.host == "env-host"  # the base class keeps reading its own


def test_s9_a_lone_link_is_the_one_link_chain(tmp_path):
    app = tmp_path / "s9.json"
    app.write_text(json.dumps({"host": "json-host"}), encoding="utf-8")

    class Lone(
        Configuration,
        options=json_source(file=app, name_pattern="{FieldName}"),
    ):
        host: str = "default-host"

    class Wrapped(
        Configuration,
        options=Sources(json_source(file=app, name_pattern="{FieldName}")),
    ):
        host: str = "default-host"

    Lone.load_configuration()
    Wrapped.load_configuration()
    assert Lone.host == Wrapped.host == "json-host"


def test_s10_a_family_factory_reads_its_familys_links_in_chain_order(tmp_path):
    top = tmp_path / "s10-top.json"
    bottom = tmp_path / "s10-bottom.json"
    top.write_text(json.dumps({"port": 1}), encoding="utf-8")
    bottom.write_text(json.dumps({"port": 2}), encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            json_source(file=bottom, name_pattern="{FieldName}"),
            json_source(file=top, name_pattern="{FieldName}"),
        ),
    ):
        port: int = json_setting(default=0)

    C.load_configuration()
    assert C.port == 2  # the family's links in the chain's order, top first


def test_s11_a_required_miss_names_every_address_it_checked(monkeypatch, tmp_path):
    monkeypatch.delenv("CMX_S11_HOST", raising=False)
    app = tmp_path / "s11.json"
    app.write_text("{}", encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_S11_", name_case=NameCase.UPPER),
            json_source(file=app, name_pattern="{FieldName}"),
            mapping_source({}),
        ),
    ):
        host: str

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()
    message = str(info.value.errors[0])
    assert "environment variable 'CMX_S11_HOST'" in message
    assert f"key 'host' in the JSON file {app}" in message
    assert "member name 'host'" in message
    assert "no source of the chain provided a value" in message


def test_s12_the_live_form_serves_the_dictionary_set_before_the_load():
    # the live form's dictionary arrives at runtime: set() through the
    # resolver, and the next load reads what it holds
    class C(
        Configuration,
        options=Sources(mapping_source()),
    ):
        token: str = "fallback"

    mapping_source_for(C).set({"token": "dev-token"})
    C.load_configuration()
    assert C.token == "dev-token"


def test_s13_an_unset_live_dictionary_is_a_silent_miss(monkeypatch):
    # no set() ran: the layer holds nothing, and the walk moves below it
    # silently — the same miss an empty dictionary spells
    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_S13_", name_case=NameCase.UPPER),
            mapping_source(),
        ),
    ):
        token: str

    monkeypatch.setenv("CMX_S13_TOKEN", "env-token")
    C.load_configuration()
    assert C.token == "env-token"


def test_s14_set_replaces_the_dictionary_whole_and_shares_nothing():
    # set() is a full replace, not a merge, and the dictionary handed in
    # is copied — a mutation after the call changes nothing the class loads
    class C(
        Configuration,
        options=Sources(mapping_source()),
    ):
        token: str = "fallback"
        port: int = 0

    link = mapping_source_for(C)
    link.set({"token": "dev-token", "port": 8080})
    source = {"token": "prod-token"}
    link.set(source)
    source["token"] = "mutated-after-the-call"
    C.load_configuration()
    assert C.token == "prod-token"  # the replacement dropped 'port'
    assert C.port == 0


def test_s15_a_subclass_without_its_own_chain_shares_the_live_link():
    # the resolver reads the nearest chain: a subclass that declares none
    # shares its base's link — one dictionary, one set()
    class Base(
        Configuration,
        options=Sources(mapping_source()),
    ):
        token: str = "fallback"

    class Child(Base):
        pass

    assert mapping_source_for(Child) is mapping_source_for(Base)

    mapping_source_for(Child).set({"token": "child-token"})
    Base.load_configuration()
    assert Base.token == "child-token"


def test_s16_the_resolver_refuses_wrong_addresses_naming_the_class():
    # a class the family never built, a chain without the live link (the
    # form taking a dictionary keeps no fill handle), and a chain of two
    # are all refusals naming the class
    class Plain:
        pass

    with pytest.raises(TypeError, match="Plain is not a configuration class"):
        mapping_source_for(Plain)

    class Static(
        Configuration,
        options=Sources(mapping_source({"token": "static"})),
    ):
        token: str = "fallback"

    with pytest.raises(TypeError, match="Static.*contains no mapping source to fill"):
        mapping_source_for(Static)

    class TwoLive(
        Configuration,
        options=Sources(mapping_source(), mapping_source()),
    ):
        token: str = "fallback"

    with pytest.raises(TypeError, match="TwoLive contains 2 mapping sources to fill"):
        mapping_source_for(TwoLive)


# ---------------------------------------------------------------------------
# P. Plain declarations and the member factories of a layered class
# ---------------------------------------------------------------------------


def test_p1_a_bare_annotation_is_a_required_member():
    class C(
        Configuration,
        options=mapping_source({}),
    ):
        token: str

    with pytest.raises(AggregateLoadError) as info:
        C.load_configuration()
    assert isinstance(info.value.errors[0], MissingValueError)
    with pytest.raises(MemberLoadError, match="is required: no value was loaded"):
        C.token


def test_p2_an_annotated_assignment_declares_the_default():
    class C(
        Configuration,
        options=mapping_source({"port": 99}),
    ):
        ttl: timedelta = timedelta(minutes=30)
        port: int = 8080

    C.load_configuration()
    assert C.ttl == timedelta(minutes=30)
    assert C.port == 99


def test_p3_chain_setting_carries_constraints_and_default():
    class C(
        Configuration,
        options=mapping_source({"port": "70000"}),
    ):
        port: int = chain_setting(ge=1, le=65535, default=8080)

    report = C.load_configuration()
    assert C.port == 8080
    assert [type(entry) for entry in report] == [ConstraintViolationError]


def test_p4_a_classvar_is_not_a_member():
    from typing import ClassVar

    class C(
        Configuration,
        options=mapping_source({}),
    ):
        debug: ClassVar[bool] = True
        token: str = "declared"

    assert "debug" not in C.__settings_members__
    assert C.debug is True  # the plain class attribute it always was
    C.load_configuration()
    assert C.token == "declared"


def test_p5_a_constant_member_is_immune_to_sources_and_overrides(monkeypatch):
    monkeypatch.setenv("SCHEMA_VERSION", "v9")

    class C(
        Configuration,
        options=Sources(
            env_source(),
            mapping_source({"schema_version": "v3"}),
        ),
    ):
        schema_version: str = constant_setting(default="v2")

    C.load_configuration(overrides={"schema_version": "v4"})
    assert C.schema_version == "v2"
    C.load_configuration()
    assert C.schema_version == "v2"


def test_p6_a_constant_without_a_value_is_refused():
    with pytest.raises(TypeError, match="constant_setting.. declares a member"):
        constant_setting()


def test_p7_a_neutral_member_without_a_chain_fails_the_class_statement():
    with pytest.raises(
        TypeError,
        match="Bad.token is a neutral member, but the class declares no source chain",
    ):

        class Bad(Configuration):
            token: str


def test_p8_a_constant_member_stays_outside_the_chain():
    class C(
        Configuration,
        options=mapping_source({}),
    ):
        url: str = constant_setting(default="https://api.example")

    C.load_configuration()
    assert C.url == "https://api.example"


def test_p9_one_class_mixes_the_member_spellings():
    class C(
        Configuration,
        options=Sources(env_source(), mapping_source({"token": "map-token"})),
    ):
        token: str  # plain, required, the whole chain
        host: str = chain_setting(default="h")
        schema: str = constant_setting(default="v2")

    C.load_configuration()
    assert C.token == "map-token"
    assert C.host == "h"
    assert C.schema == "v2"


def test_p10_chain_setting_names_are_full_addresses_in_named_links(monkeypatch, tmp_path):
    monkeypatch.delenv("CMX_P10_OLD", raising=False)
    monkeypatch.setenv("CMX_P10_NEW", "renamed")
    app = tmp_path / "p10.json"
    app.write_text("{}", encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_S1_", name_case=NameCase.UPPER),
            json_source(file=app, name_pattern="{FieldName}"),
        ),
    ):
        token: str = chain_setting(name="CMX_P10_NEW", aliases=["CMX_P10_OLD"], default="fallback")

    C.load_configuration()
    assert C.token == "renamed"


# ---------------------------------------------------------------------------
# O. The load overrides: a layer above the whole chain
# ---------------------------------------------------------------------------


def test_o1_overrides_sit_above_the_whole_chain(monkeypatch, tmp_path):
    monkeypatch.setenv("CMX_O1_HOST", "env-host")
    app = tmp_path / "o1.json"
    app.write_text(json.dumps({"host": "json-host"}), encoding="utf-8")

    class C(
        Configuration,
        options=Sources(
            env_source(name_prefix="CMX_O1_", name_case=NameCase.UPPER),
            json_source(file=app, name_pattern="{FieldName}"),
        ),
    ):
        host: str = "default-host"

    C.load_configuration(overrides={"host": "override-host"})
    assert C.host == "override-host"


def test_o2_override_values_ride_the_conversion_and_constraints():
    class C(
        Configuration,
        options=mapping_source({}),
    ):
        ttl: timedelta = timedelta(minutes=30)
        port: int = chain_setting(ge=1, le=65535, default=8080)

    C.load_configuration(overrides={"ttl": "2:00:00"})
    assert C.ttl == timedelta(hours=2)

    report = C.load_configuration(overrides={"port": "70000"})
    assert C.port == 8080
    assert [type(entry) for entry in report] == [ConstraintViolationError]


def test_o3_keys_naming_no_member_are_ignored_with_a_debug_record(caplog):
    class C(
        Configuration,
        options=mapping_source({}),
    ):
        host: str = "default-host"

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        C.load_configuration(overrides={"host": "over", "foreign": 1})
    assert C.host == "over"
    assert any(
        "'foreign' does not match any member" in record.getMessage() for record in caplog.records
    )


def test_o4_constant_members_stay_out_of_the_overrides_reach(caplog):
    class C(
        Configuration,
        options=mapping_source({}),
    ):
        schema_version: str = constant_setting(default="v2")

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        C.load_configuration(overrides={"schema_version": "v9"})
    assert C.schema_version == "v2"
    assert any("which cannot be overridden" in record.getMessage() for record in caplog.records)


# -- T. Path parameters (#74) ------------------------------------------------
#
# A file link may spell its file as a template an environment variable
# fills; the rows walk the switching itself, the miss and the loud
# failures, the per-pass resolution and the builder's checks.


def test_t1_a_templated_link_reads_the_file_of_its_environment(monkeypatch, tmp_path):
    # one file per environment: the variable picks the link's file, and a
    # second pass with the variable switched reads the other environment
    (tmp_path / "settings-dev.json").write_text(
        json.dumps({"token": "dev-token"}), encoding="utf-8"
    )
    (tmp_path / "settings-prod.json").write_text(
        json.dumps({"token": "prod-token"}), encoding="utf-8"
    )
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

    class C(
        Configuration,
        options=json_source(
            file=tmp_path / "settings-{APP_ENV}.json",
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
    ):
        token: str

    monkeypatch.setenv("APP_ENV", "prod")
    C.load_configuration()
    assert C.token == "prod-token"
    monkeypatch.setenv("APP_ENV", "dev")
    C.load_configuration()
    assert C.token == "dev-token"


def test_t2_a_whitelisted_environment_without_a_file_is_a_plain_miss(monkeypatch, tmp_path):
    # the whitelist guards the variable, not the existence of the file:
    # a valid value over a missing file walks down the chain as any miss
    base = tmp_path / "app.json"
    base.write_text(json.dumps({"token": "base-token"}), encoding="utf-8")
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

    class C(
        Configuration,
        options=Sources(
            json_source(
                file=tmp_path / "settings-{APP_ENV}.json",
                name_pattern="{FieldName}",
                parameters=app_env,
            ),
            json_source(file=base, name_pattern="{FieldName}"),
        ),
    ):
        token: str

    monkeypatch.setenv("APP_ENV", "test")  # no settings-test.json anywhere
    C.load_configuration()
    assert C.token == "base-token"


def test_t3_an_unset_variable_without_a_default_breaks_the_link(monkeypatch, tmp_path):
    # no implicit environments: the load names the variable and the file,
    # and the links below never mask the broken one
    below = tmp_path / "app.json"
    below.write_text(json.dumps({"token": "base-token"}), encoding="utf-8")
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

    class C(
        Configuration,
        options=Sources(
            json_source(
                file=tmp_path / "settings-{APP_ENV}.json",
                name_pattern="{FieldName}",
                parameters=app_env,
            ),
            json_source(file=below),
        ),
    ):
        token: str

    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValueError, match="APP_ENV.*is not set.*no default"):
        C.load_configuration()


def test_t4_an_unset_variable_resolves_through_the_declared_default(monkeypatch, tmp_path):
    # the default is explicit in the declaration, so an unset variable is
    # a legitimate environment, not a failure
    (tmp_path / "settings-dev.json").write_text(
        json.dumps({"token": "dev-token"}), encoding="utf-8"
    )
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"), default="dev")

    class C(
        Configuration,
        options=json_source(
            file=tmp_path / "settings-{APP_ENV}.json",
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
    ):
        token: str

    monkeypatch.delenv("APP_ENV", raising=False)
    C.load_configuration()
    assert C.token == "dev-token"


def test_t5_a_value_outside_the_whitelist_fails_loudly(monkeypatch, tmp_path):
    # the typo is the loudest failure of the family: without the whitelist
    # check it would be a missing file, and the chain would walk past it
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

    class C(
        Configuration,
        options=json_source(
            file=tmp_path / "settings-{APP_ENV}.json",
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
    ):
        token: str

    monkeypatch.setenv("APP_ENV", "prodd")
    with pytest.raises(ValueError, match="'prodd'.*do not allow"):
        C.load_configuration()


def test_t6_each_pass_resolves_anew_and_records_the_file_it_read(monkeypatch, tmp_path, caplog):
    # the resolution is per pass: no cache outlives a pass, one pass reads
    # the variable once whatever it serves, and the debug record names the
    # variable, its value and the file
    (tmp_path / "settings-dev.json").write_text(
        json.dumps({"token": "dev-token", "host": "dev-host"}), encoding="utf-8"
    )
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

    class C(
        Configuration,
        options=json_source(
            file=tmp_path / "settings-{APP_ENV}.json",
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
    ):
        token: str
        host: str

    monkeypatch.setenv("APP_ENV", "dev")
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        C.load_configuration()
    assert C.token == "dev-token"
    assert C.host == "dev-host"
    records = [
        record.getMessage()
        for record in caplog.records
        if "settings-dev.json" in record.getMessage()
    ]
    assert records, "the resolution owes a debug record naming the file it read"
    assert len(records) == 1, "one pass resolves a variable once, one record says it"


def test_t7_slot_renames_the_slot_the_template_spells(monkeypatch, tmp_path):
    # the variable keeps its name, the template spells another: the slot
    # is what the checks go by
    (tmp_path / "settings-dev.json").write_text(
        json.dumps({"token": "dev-token"}), encoding="utf-8"
    )
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"), slot="env")

    class C(
        Configuration,
        options=json_source(
            file=tmp_path / "settings-{env}.json",
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
    ):
        token: str

    monkeypatch.setenv("APP_ENV", "dev")
    C.load_configuration()
    assert C.token == "dev-token"


def test_t8_the_builder_check_runs_in_both_directions():
    # a slot no parameter declares leaves the path unresolvable — with
    # parameters= absent altogether included; a parameter no slot reads
    # declares a variable nothing reads; a name mismatch is the first of
    # the two the call names. All are spelling mistakes the builder call
    # refuses
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))
    with pytest.raises(TypeError, match="no env_parameter declares"):
        json_source(file="settings-{APP_ENV}.json")
    with pytest.raises(TypeError, match="no slot in the template uses them"):
        json_source(file="settings.json", parameters=app_env)
    with pytest.raises(
        TypeError, match=r"uses the slot\(s\) \{OTHER\} in its template, but no env_parameter"
    ):
        json_source(file="settings-{OTHER}.json", parameters=app_env)


def test_t9_env_parameter_refuses_an_unusable_declaration():
    # no whitelist is the typo door left open; a default outside it and a
    # repeated value are declaration mistakes the builder names
    with pytest.raises(TypeError, match="declares no allowed values"):
        env_parameter("APP_ENV", choices=())
    with pytest.raises(TypeError, match="not one of the declared choices"):
        env_parameter("APP_ENV", choices=("dev", "prod"), default="test")
    with pytest.raises(TypeError, match="contains a duplicate value"):
        env_parameter("APP_ENV", choices=("dev", "dev"))
    with pytest.raises(TypeError, match="expects a slot name"):
        env_parameter("APP_ENV", choices=("dev",), slot="not a slot")


def test_t10_a_bare_file_keeps_the_unparameterized_behaviour(tmp_path):
    # a link without parameters is the spelling every chain used before:
    # braces that spell no identifier stay the literal file name
    odd = tmp_path / "curly-{}.json"
    odd.write_text(json.dumps({"token": "odd-token"}), encoding="utf-8")

    class C(
        Configuration,
        options=json_source(file=odd, name_pattern="{FieldName}"),
    ):
        token: str

    C.load_configuration()
    assert C.token == "odd-token"


def test_t11_the_file_families_take_parameters_each(monkeypatch, tmp_path):
    # the slot spelling is the file families' shared vocabulary: the
    # dotenv and TOML links unfold their files the JSON way
    (tmp_path / "env-dev").write_text("CMX_T11_TOKEN=dotenv-token\n", encoding="utf-8")
    (tmp_path / "conf-dev.toml").write_text('token = "toml-token"\n', encoding="utf-8")
    app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

    class FromDotenv(
        Configuration,
        options=dotenv_source(
            file=tmp_path / "env-{APP_ENV}",
            name_prefix="CMX_T11_",
            name_case=NameCase.UPPER,
            parameters=app_env,
        ),
    ):
        token: str

    class FromToml(
        Configuration,
        options=toml_source(
            file=tmp_path / "conf-{APP_ENV}.toml",
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
    ):
        token: str

    monkeypatch.setenv("APP_ENV", "dev")
    FromDotenv.load_configuration()
    assert FromDotenv.token == "dotenv-token"
    FromToml.load_configuration()
    assert FromToml.token == "toml-token"


# -- L. Dynamic settings: the reading side (#94) ---------------------------------
#
# The settings package writes a dynamic collection into its file; this
# package reads the writer's group back, read-only, through the dynamic
# plugins of advexp.configuration.plugins.json_dynamic_settings and its
# TOML twin.


def test_l1_the_json_reader_loads_the_group_the_settings_package_wrote(tmp_path):
    # one shared file: the writer's entries sit in their section, the reader
    # addresses them by the writer's group key
    import advexp.settings.plugins.json_dynamic_settings as writer_dynamic
    import advexp.settings.plugins.json_settings as writer_json
    from advexp.configuration.plugins.json_dynamic_settings import JSONDynamicSettingsPlugin
    from advexp.settings import Settings

    app = tmp_path / "l1.json"

    class Writer(
        Settings,
        options=writer_json.json_source(file=app),
    ):
        pass

    writer = Writer.get_plugin(writer_dynamic.JSONDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.set_setting("retries", 5)
    writer.save_settings()

    class Reader(
        Configuration,
        options=json_source(file=app, dynamic_of=f"{Writer.__module__}.{Writer.__name__}"),
    ):
        pass

    reader = Reader.get_plugin(JSONDynamicSettingsPlugin)
    reader.load_configuration()
    assert sorted(reader) == ["dark_mode", "retries"]
    assert reader.get_setting("dark_mode", default=False) is True
    assert reader.get_setting("retries", default=0) == 5


def test_l2_the_toml_reader_loads_the_group_the_settings_package_wrote(tmp_path):
    # the TOML twin: the group nests as tables, read the same way
    import advexp.settings.plugins.toml_dynamic_settings as writer_dynamic
    import advexp.settings.plugins.toml_settings as writer_toml
    from advexp.configuration.plugins.toml_dynamic_settings import TOMLDynamicSettingsPlugin
    from advexp.settings import Settings

    app = tmp_path / "l2.toml"

    class Writer(
        Settings,
        options=writer_toml.toml_source(file=app),
    ):
        pass

    writer = Writer.get_plugin(writer_dynamic.TOMLDynamicSettingsPlugin)
    writer.set_setting("feature_x", "on")
    writer.save_settings()

    class Reader(
        Configuration,
        options=toml_source(file=app, dynamic_of=f"{Writer.__module__}.{Writer.__name__}"),
    ):
        pass

    reader = Reader.get_plugin(TOMLDynamicSettingsPlugin)
    reader.load_configuration()
    assert reader.to_dict() == {"feature_x": "on"}


def test_l3_the_reader_follows_the_writers_flat_layout(tmp_path):
    # the writer disabled the section: the reader mirrors the parameter and reads
    # the D-prefixed full-name keys from the document root
    import advexp.settings.plugins.json_dynamic_settings as writer_dynamic
    import advexp.settings.plugins.json_settings as writer_json
    from advexp.configuration.plugins.json_dynamic_settings import JSONDynamicSettingsPlugin
    from advexp.settings import Settings

    app = tmp_path / "l3.json"

    class Writer(
        Settings,
        options=writer_json.json_source(file=app),
    ):
        pass

    writer = Writer.get_plugin(writer_dynamic.JSONDynamicSettingsPlugin)
    writer.dynamic_settings_section_name = None
    writer.set_setting("dark_mode", True)
    writer.save_settings()

    class Reader(
        Configuration,
        options=json_source(file=app, dynamic_of=f"{Writer.__module__}.{Writer.__name__}"),
    ):
        pass

    reader = Reader.get_plugin(JSONDynamicSettingsPlugin)
    reader.dynamic_settings_section_name = None
    reader.load_configuration()
    assert reader.to_dict() == {"dark_mode": True}


def test_l4_the_own_dynamic_file_serves_both_sides(tmp_path):
    # dynamic_file= moves the group into a file of its own on both sides:
    # the shared file keeps the static entries alone
    import advexp.settings.plugins.json_dynamic_settings as writer_dynamic
    import advexp.settings.plugins.json_settings as writer_json
    from advexp.configuration.plugins.json_dynamic_settings import JSONDynamicSettingsPlugin
    from advexp.settings import Settings

    shared = tmp_path / "l4.json"
    dynamic = tmp_path / "l4-dynamic.json"

    class Writer(
        Settings,
        options=writer_json.json_source(file=shared, dynamic_file=dynamic),
    ):
        pass

    writer = Writer.get_plugin(writer_dynamic.JSONDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    assert shared.exists() is False or not json.loads(shared.read_text(encoding="utf-8"))

    class Reader(
        Configuration,
        options=json_source(
            file=shared,
            dynamic_file=dynamic,
            dynamic_of=f"{Writer.__module__}.{Writer.__name__}",
        ),
    ):
        pass

    reader = Reader.get_plugin(JSONDynamicSettingsPlugin)
    reader.load_configuration()
    assert reader.to_dict() == {"dark_mode": True}


def test_l5_every_write_of_the_collection_refuses(tmp_path):
    # the collection is read-only: the mutating surface refuses with
    # TypeError, the guard the package holds over its members
    from advexp.configuration.plugins.json_dynamic_settings import JSONDynamicSettingsPlugin

    class Reader(
        Configuration,
        options=json_source(file="l5.json", dynamic_of="app.Writer"),
    ):
        pass

    reader = Reader.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(TypeError, match="read-only"):
        reader.set_setting("dark_mode", True)
    with pytest.raises(TypeError, match="read-only"):
        reader.save_settings()
    with pytest.raises(TypeError, match="has no setting metadata"):
        reader.get_setting_metadata("dark_mode", "k")


def test_l6_a_class_without_a_group_names_the_binding_in_the_error(tmp_path):
    # no dynamic_of= in options: the collection reads nothing, and the load
    # says exactly what is missing
    from advexp.configuration.plugins.json_dynamic_settings import JSONDynamicSettingsPlugin

    class Reader(
        Configuration,
        options=json_source(file=tmp_path / "l6.json"),
    ):
        pass

    reader = Reader.get_plugin(JSONDynamicSettingsPlugin)
    with pytest.raises(ValueError, match="reads no dynamic group"):
        reader.load_configuration()


def test_l8_the_handles_load_configuration_refreshes_what_the_class_pass_leaves(
    tmp_path,
):
    # the handle's load_configuration() refreshes the group's snapshot; the
    # class's own pass loads the declared members alone and leaves the
    # snapshot exactly as it was
    import advexp.settings.plugins.json_dynamic_settings as writer_dynamic
    import advexp.settings.plugins.json_settings as writer_json
    from advexp.configuration.plugins.json_dynamic_settings import JSONDynamicSettingsPlugin
    from advexp.settings import Settings

    app = tmp_path / "l8.json"

    class Writer(
        Settings,
        options=writer_json.json_source(file=app),
    ):
        pass

    group = f"{Writer.__module__}.{Writer.__name__}"
    writer = Writer.get_plugin(writer_dynamic.JSONDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()

    class Reader(
        Configuration,
        options=json_source(file=app, dynamic_of=group),
    ):
        retries: int = json_setting(default=3)

    reader = Reader.get_plugin(JSONDynamicSettingsPlugin)
    reader.load_configuration()
    assert reader.get_setting("dark_mode", default=False) is True

    # the file changes under both sides: the class pass serves the declared
    # member and keeps the stale snapshot, the handle's call refreshes it
    app.write_text(
        json.dumps(
            {f"{Reader.__module__}.Reader.retries": 9, "dynamic": {group: {"dark_mode": False}}}
        ),
        encoding="utf-8",
    )
    assert Reader.load_configuration() == ()
    assert Reader.retries == 9
    assert reader.get_setting("dark_mode", default=False) is True

    reader.load_configuration()
    assert reader.get_setting("dark_mode", default=False) is False


def test_l7_the_stored_layout_is_the_frozen_public_form(tmp_path):
    # the document form is the contract between the two distributions: the
    # section key, the class group inside it, the D-prefixed flat names —
    # spelled literally, because a change here migrates every stored file
    import advexp.settings.plugins.json_dynamic_settings as writer_dynamic
    import advexp.settings.plugins.json_settings as writer_json
    from advexp.settings import Settings

    app = tmp_path / "l7.json"

    class L7Writer(
        Settings,
        options=writer_json.json_source(file=app),
    ):
        pass

    group = f"{L7Writer.__module__}.L7Writer"
    writer = L7Writer.get_plugin(writer_dynamic.JSONDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    assert json.loads(app.read_text(encoding="utf-8")) == {"dynamic": {group: {"dark_mode": True}}}

    app.unlink()  # a fresh file: the flat pass must not find the section remains
    writer.dynamic_settings_section_name = None
    writer.save_settings()
    assert json.loads(app.read_text(encoding="utf-8")) == {f"D.{group}.dark_mode": True}


# ---------------------------------------------------------------------------
# Y. Источник: YAML
# ---------------------------------------------------------------------------


def test_y1_missing_file_serves_defaults(tmp_path):
    path = tmp_path / "absent.yaml"

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    report = C.load_configuration()

    assert report == ()
    assert C.host == "localhost"


def test_y2_corrupt_file_aborts_even_for_an_optional_member(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("{not yaml", encoding="utf-8")

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match=f"cannot parse the YAML configuration file {path}"):
        C.load_configuration()


def test_y3_a_blank_file_reads_as_an_empty_document(tmp_path):
    # a blank YAML file is valid and holds no keys: the load reads
    # nothing, the declared defaults serve — the parse error richer
    # formats make of an empty file has no counterpart here
    path = tmp_path / "blank.yaml"
    path.write_text("   \n", encoding="utf-8")

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    report = C.load_configuration()

    assert report == ()
    assert C.host == "localhost"


def test_y4_yaml_native_values_arrive_converted(tmp_path):
    # dates and timestamps native (no ISO strings), null as None,
    # true/false as booleans, yes/no as the strings YAML 1.2 makes of them
    path = tmp_path / "native.yaml"
    path.write_text(
        "launch_on: 2026-12-01\n"
        "started_at: 2026-12-01T09:30:00\n"
        "seen: true\n"
        "word: no\n"
        "hint: null\n",
        encoding="utf-8",
    )

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        launch_on: date = yaml_setting(name="launch_on", default=date(2026, 1, 1))
        started_at: datetime = yaml_setting(name="started_at", default=None)
        seen: bool = yaml_setting(name="seen", default=False)
        word: str = yaml_setting(name="word", default="yes")
        hint: Optional[str] = yaml_setting(name="hint", default="missing")

    C.load_configuration()
    assert C.launch_on == date(2026, 12, 1)
    assert C.started_at == datetime(2026, 12, 1, 9, 30, 0)
    assert C.seen is True
    assert C.word == "no"
    assert C.hint is None  # the stored null, not a missing key


def test_y5_path_walks_mappings_and_sequence_positions(tmp_path):
    path = tmp_path / "paths.yaml"
    path.write_text(
        "net:\n  proxy:\n    host: proxy.example\nmirrors:\n  - host: a\n  - host: b\n",
        encoding="utf-8",
    )

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", path="/net/proxy", default="x")
        mirror: str = yaml_setting(name="host", path="/mirrors/1", default="y")

    C.load_configuration()
    assert C.host == "proxy.example"
    assert C.mirror == "b"


def test_y6_foreign_keys_and_prose_are_ignored_not_touched(tmp_path):
    path = tmp_path / "foreign.yaml"
    text = "someone-elses-key: 42  # prose of the file's own\nhost: preset\n"
    path.write_text(text, encoding="utf-8")

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    C.load_configuration()
    assert C.host == "preset"
    # a read-only source: the file stays exactly as it was, comments too
    assert path.read_text(encoding="utf-8") == text


def test_y7_one_document_per_file_and_no_unknown_tags(tmp_path):
    path = tmp_path / "two-docs.yaml"
    path.write_text("host: a\n---\nhost: b\n", encoding="utf-8")

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    with pytest.raises(ValueError, match="expected a single document"):
        C.load_configuration()

    path.write_text("host: !!weird/value\n", encoding="utf-8")
    with pytest.raises(ValueError, match="could not determine a constructor"):
        C.load_configuration()


def test_y8_the_yml_spelling_serves_too(tmp_path):
    path = tmp_path / "short.yml"
    path.write_text("host: preset\n", encoding="utf-8")

    class C(
        Configuration,
        options=yaml_source(file=path),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    C.load_configuration()
    assert C.host == "preset"


def test_y9_the_yaml_reader_loads_the_group_the_settings_package_wrote(tmp_path):
    import advexp.settings.plugins.yaml_dynamic_settings as writer_dynamic
    import advexp.settings.plugins.yaml_settings as writer_static
    from advexp.settings import Settings

    app = tmp_path / "app-settings.yaml"

    class Y9Writer(
        Settings,
        options=writer_static.yaml_source(file=app),
    ):
        pass

    group = f"{Y9Writer.__module__}.Y9Writer"
    writer = Y9Writer.get_plugin(writer_dynamic.YAMLDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    assert app.read_text(encoding="utf-8") == (f"dynamic:\n  {group}:\n    dark_mode: true\n")
