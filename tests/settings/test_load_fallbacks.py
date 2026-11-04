"""The load pass of settings classes: fallbacks are reported, and required
members abort.

This is the seat of the one load pass of the family in the settings
package.

- A member with a default (the class default ``NO_DEFAULT``, or a value)
  never aborts a load. Its problems (an unconvertible or invalid value, or
  a failing storage) serve the effective default of the member and are
  logged. They also land in the report that ``load_settings`` returns.
- A member declared ``REQUIRED`` uses the other channel. Its problems abort
  the load with one aggregate error that carries every failure, with the
  optional fallbacks of the same run marked next to them.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest

from advexp.settings import (
    REQUIRED,
    AggregateLoadError,
    ConstraintViolationError,
    ConversionError,
    MissingValueError,
    Settings,
    SourceLoadError,
)
from advexp.settings.plugin_api import (
    NOT_FOUND,
    AttributeSerializerBinding,
    ISettingAttribute,
    LibraryConfiguration,
    SettingsAttribute,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings.plugins.environment import NameCase
from advexp.settings.plugins.environment.variables import env_source, environment_variable_setting


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
        return "Exploding"


LibraryConfiguration.register_settings_plugin(ExplodingPlugin)


class CorruptSetting(SettingsAttribute):
    """A test storage attribute whose loading fails the user-facing way."""


class CorruptSerializer(SettingsBaseSerializer):
    """A test storage serializer: load raises a user-facing error."""

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        raise UserFacingError(ValueError("corrupt storage"))

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """No-op: a test storage never writes."""

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: a test storage never deletes."""

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return False


class CorruptPlugin(SettingsBasePlugin):
    """A test storage plugin binding the corrupt pair."""

    binding = AttributeSerializerBinding(CorruptSetting, CorruptSerializer)

    @property
    def plugin_name(self) -> str:
        return "Corrupt"


LibraryConfiguration.register_settings_plugin(CorruptPlugin)


def exploding_setting(**kwargs: Any) -> Any:
    return ExplodingSetting(**kwargs)


@dataclasses.dataclass
class PhraseProxy:
    """A dataclass member for the phrase tests: one required field."""

    host: str


def corrupt_setting(**kwargs: Any) -> Any:
    return CorruptSetting(**kwargs)


class SoftSettings(Settings):
    mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")
    plain: str = environment_variable_setting(name="TEST_ASV_PLAIN")  # NO_DEFAULT → None
    limit: int = environment_variable_setting(name="TEST_ASV_LIMIT", default=7)
    port: int = environment_variable_setting(name="TEST_ASV_PORT", default=8080, ge=1)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("TEST_ASV_MODE", "TEST_ASV_PLAIN", "TEST_ASV_LIMIT", "TEST_ASV_PORT"):
        monkeypatch.delenv(name, raising=False)
    yield


def test_missing_value_serves_default():
    report = SoftSettings.load_settings()
    assert SoftSettings.mode == "default-mode"
    assert SoftSettings.plain is None  # no exception: NO_DEFAULT means None stands in
    # a plain miss is the default's normal way of happening: no entry
    assert report == ()


def test_missing_value_names_its_address_at_debug(caplog):
    # the miss stays out of the report and off the usual log levels, but
    # the debug record names the address that came up empty — the
    # debugging seat for a variable name that does not match
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        report = SoftSettings.load_settings()
    assert report == ()
    messages = [
        record.getMessage()
        for record in caplog.records
        if "using the default" in record.getMessage()
    ]
    assert any(
        "setting 'limit' (environment variable 'TEST_ASV_LIMIT') of 'SoftSettings': "
        "the process environment provided no value" in message
        for message in messages
    )


def test_unconvertible_value_serves_default(caplog, monkeypatch):
    monkeypatch.setenv("TEST_ASV_LIMIT", "not-a-number")
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = SoftSettings.load_settings()
    assert SoftSettings.limit == 7
    assert any("using the default value" in record.getMessage() for record in caplog.records)
    # the fallback is an entry of the returned report, naming the member,
    # its storage name, the class and the cause — the storage name in the
    # backend's own spelling, the variable the reader must provide
    assert [type(entry) for entry in report] == [ConversionError]
    assert (
        "setting 'limit' (environment variable 'TEST_ASV_LIMIT') of 'SoftSettings' "
        "fell back to its default: cannot convert 'not-a-number' to int" in str(report[0])
    )


def test_constraint_violation_serves_default(caplog, monkeypatch):
    monkeypatch.setenv("TEST_ASV_PORT", "0")  # below the declared ge=1
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = SoftSettings.load_settings()
    assert SoftSettings.port == 8080
    assert any("violates its constraints" in record.getMessage() for record in caplog.records)
    assert [type(entry) for entry in report] == [ConstraintViolationError]
    assert "fell back to its default: the value violates its constraints" in str(report[0])


def test_conversion_phrase_never_duplicates_itself(monkeypatch):
    # some conversion failures raise as the canonical statement itself
    # (timedelta's parse cannot name an inner cause): the report states
    # it once, not beside a copy of itself
    class TtlSettings(Settings):
        session_ttl: timedelta = environment_variable_setting(
            name="TEST_ASV_TTL", default=timedelta(minutes=90)
        )

    monkeypatch.setenv("TEST_ASV_TTL", "asd")
    report = TtlSettings.load_settings()

    assert [type(entry) for entry in report] == [ConversionError]
    message = str(report[0])
    assert "cannot convert 'asd' to timedelta" in message
    assert message.count("cannot convert") == 1
    assert TtlSettings.session_ttl == timedelta(minutes=90)


def test_conversion_phrase_of_an_optional_member_names_the_concrete_type(monkeypatch):
    # Optional[datetime] converts as datetime, and the conversion error
    # already opens with the canonical statement naming that concrete
    # type; the phrase must not staple the wrapper's own statement beside
    # it ("cannot convert 'x' to Union (cannot convert 'x' to datetime)")
    class StampSettings(Settings):
        started_at: Optional[datetime] = environment_variable_setting(
            name="TEST_ASV_STAMP", default=None
        )

    monkeypatch.setenv("TEST_ASV_STAMP", "not-a-timestamp")
    report = StampSettings.load_settings()

    assert [type(entry) for entry in report] == [ConversionError]
    message = str(report[0])
    assert message.count("cannot convert") == 1
    assert "cannot convert 'not-a-timestamp' to datetime" in message
    assert "Union" not in message
    assert StampSettings.started_at is None


def test_conversion_phrase_of_an_optional_int_composes_the_parsers_reason(monkeypatch):
    # the parser's own message is a real addition: it rides in
    # parentheses, and the target names the full Optional annotation
    class CountSettings(Settings):
        count: Optional[int] = environment_variable_setting(name="TEST_ASV_COUNT", default=7)

    monkeypatch.setenv("TEST_ASV_COUNT", "abc")
    report = CountSettings.load_settings()

    assert [type(entry) for entry in report] == [ConversionError]
    message = str(report[0])
    assert (
        "cannot convert 'abc' to Optional[int] "
        "(invalid literal for int() with base 10: 'abc')" in message
    )
    assert CountSettings.count == 7


def test_conversion_phrase_of_a_whole_container_failure_spells_the_annotation(monkeypatch):
    class SizesSettings(Settings):
        sizes: List[int] = environment_variable_setting(name="TEST_ASV_SIZES", default=[1])

    monkeypatch.setenv("TEST_ASV_SIZES", "abc")
    report = SizesSettings.load_settings()

    assert [type(entry) for entry in report] == [ConversionError]
    message = str(report[0])
    assert "fell back to its default: cannot convert 'abc' to List[int]" in message
    assert "typing." not in message
    assert SizesSettings.sizes == [1]


def test_conversion_phrase_of_a_failing_container_item_names_the_annotation(monkeypatch):
    # the item's parser error rides in parentheses; the target names the
    # full annotation in its declared spelling, not the bare alias
    # machinery ("to List")
    class DimsSettings(Settings):
        dims: List[int] = environment_variable_setting(name="TEST_ASV_DIMS", default=[1])

    monkeypatch.setenv("TEST_ASV_DIMS", '["abc"]')
    report = DimsSettings.load_settings()

    assert [type(entry) for entry in report] == [ConversionError]
    message = str(report[0])
    assert (
        "fell back to its default: cannot convert '[\"abc\"]' to List[int] "
        "(invalid literal for int() with base 10: 'abc')" in message
    )
    assert DimsSettings.dims == [1]


def test_conversion_phrase_of_a_dataclass_names_the_stored_form(monkeypatch):
    # the JSON document is decoded for the fields; the phrase names the
    # value as stored — one canonical layer with the missing field as its
    # detail, not a canonical statement wrapped around another
    class NetSettings(Settings):
        proxy: PhraseProxy = environment_variable_setting(
            name="TEST_ASV_PROXY", default=PhraseProxy("fallback-host")
        )

    monkeypatch.setenv("TEST_ASV_PROXY", '{"port": 1}')
    report = NetSettings.load_settings()

    assert [type(entry) for entry in report] == [ConversionError]
    message = str(report[0])
    assert message.count("cannot convert") == 1
    assert "cannot convert '{\"port\": 1}' to PhraseProxy: missing field 'host'" in message
    assert NetSettings.proxy == PhraseProxy("fallback-host")


def test_storage_failure_logs_and_skips(caplog):
    class ExplodingSettings(Settings):
        mode: str = exploding_setting(name="whatever", default="default-mode")

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        report = ExplodingSettings.load_settings()
    assert ExplodingSettings.mode == "default-mode"
    # the record carries the full fallback shape: the member's place, the
    # source that raised, and the fallback tail
    assert [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ] == [
        "setting 'mode' (whatever) of 'ExplodingSettings': "
        "its source raised RuntimeError (storage exploded); using the default value"
    ]
    # a plain storage failure keeps the log-and-continue policy, and joins
    # the report beside it
    assert [type(entry) for entry in report] == [SourceLoadError]
    assert "its source raised RuntimeError (storage exploded)" in str(report[0])


def test_single_setting_source_failure_serves_the_default(caplog):
    # the single-setting form follows the shared pass's soft policy: a
    # failing source leaves the full-shape ERROR record, the member stands
    # at its default, and the returned entry carries the same fallback the
    # class pass's report would
    class SingleSettings(Settings):
        mode: str = exploding_setting(name="whatever", default="default-mode")

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        error = SingleSettings.load_setting("mode")

    assert SingleSettings.mode == "default-mode"
    assert [record.getMessage() for record in caplog.records] == [
        "setting 'mode' (whatever) of 'SingleSettings': "
        "its source raised RuntimeError (storage exploded); using the default value"
    ]
    assert type(error) is SourceLoadError
    assert (
        "setting 'mode' (whatever) of 'SingleSettings' "
        "fell back to its default: its source raised RuntimeError (storage exploded)" in str(error)
    )
    # the entry keeps the source's own exception as its cause, the way the
    # class pass's report entry does
    assert isinstance(error.__cause__, RuntimeError)


def test_single_setting_clean_load_reports_nothing(monkeypatch):
    class LoadedSettings(Settings):
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")

    monkeypatch.setenv("TEST_ASV_MODE", "from-env")

    assert LoadedSettings.load_setting("mode") is None
    assert LoadedSettings.mode == "from-env"


def test_single_setting_miss_reports_nothing():
    # a miss is the default's normal way of happening: no entry, the same
    # silence the class pass's successful report keeps for a miss
    class MissedSettings(Settings):
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")

    assert MissedSettings.load_setting("mode") is None
    assert MissedSettings.mode == "default-mode"


def test_single_setting_conversion_failure_reports_the_fallback(monkeypatch):
    class SingleConversionSettings(Settings):
        limit: int = environment_variable_setting(name="TEST_ASV_LIMIT", default=7)

    monkeypatch.setenv("TEST_ASV_LIMIT", "not-a-number")
    error = SingleConversionSettings.load_setting("limit")

    assert SingleConversionSettings.limit == 7
    assert type(error) is ConversionError
    assert (
        "setting 'limit' (environment variable 'TEST_ASV_LIMIT') of "
        "'SingleConversionSettings' fell back to its default: "
        "cannot convert 'not-a-number' to int" in str(error)
    )


def test_single_setting_constraint_violation_reports_the_fallback(monkeypatch):
    class SingleConstraintSettings(Settings):
        port: int = environment_variable_setting(name="TEST_ASV_PORT", default=8080, ge=1)

    monkeypatch.setenv("TEST_ASV_PORT", "0")  # below the declared ge=1
    error = SingleConstraintSettings.load_setting("port")

    assert SingleConstraintSettings.port == 8080
    assert type(error) is ConstraintViolationError
    assert (
        "setting 'port' (environment variable 'TEST_ASV_PORT') of "
        "'SingleConstraintSettings' fell back to its default: "
        "the value violates its constraints" in str(error)
    )


def test_single_setting_source_failure_of_a_required_member_raises(caplog):
    # a required member holds no default to serve: the record carries the
    # place and the cause without the fallback tail, and the exception
    # itself is what the caller sees
    class SingleRequiredSettings(Settings):
        token: str = exploding_setting(name="whatever", default=REQUIRED)

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        with pytest.raises(RuntimeError, match="storage exploded"):
            SingleRequiredSettings.load_setting("token")

    assert [record.getMessage() for record in caplog.records] == [
        "setting 'token' (whatever) of 'SingleRequiredSettings': "
        "its source raised RuntimeError (storage exploded)"
    ]


def test_single_setting_user_facing_error_arrives_unwrapped():
    # the family unwraps a user-facing condition into the inner exception:
    # the caller sees the source's own error, the wrapper riding as the
    # cause — the single-setting form behaves like the class form
    class CorruptSettings(Settings):
        mode: str = corrupt_setting(name="whatever", default="default-mode")

    with pytest.raises(ValueError, match="corrupt storage") as info:
        CorruptSettings.load_setting("mode")

    assert isinstance(info.value.__cause__, UserFacingError)


def test_required_member_aborts_the_load(monkeypatch):
    class WithRequired(Settings):
        token: str = environment_variable_setting(name="TEST_ASV_TOKEN", default=REQUIRED)
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")

    monkeypatch.delenv("TEST_ASV_TOKEN", raising=False)
    with pytest.raises(AggregateLoadError) as info:
        WithRequired.load_settings()

    assert [type(entry) for entry in info.value.errors] == [MissingValueError]
    assert "is required: the process environment provided no value" in str(info.value.errors[0])
    # the abort names its package: the channel of the distribution that
    # ran the pass opens the message, so a printed abort is never anonymous
    assert str(info.value).startswith("advexp.settings error: the load failed for")
    # the optional member beside it loaded
    assert WithRequired.mode == "default-mode"


def test_mixed_class_marks_the_fallbacks_in_the_abort(monkeypatch):
    monkeypatch.setenv("TEST_ASV_LIMIT", "not-a-number")
    monkeypatch.delenv("TEST_ASV_TOKEN", raising=False)

    class Mixed(Settings):
        token: str = environment_variable_setting(name="TEST_ASV_TOKEN", default=REQUIRED)
        limit: int = environment_variable_setting(name="TEST_ASV_LIMIT", default=7)

    with pytest.raises(AggregateLoadError) as info:
        Mixed.load_settings()

    # the required failure is the abort; the optional fallback of the same
    # run rides it, marked structurally
    assert [type(entry) for entry in info.value.errors] == [MissingValueError]
    assert [type(entry) for entry in info.value.fallbacks] == [ConversionError]
    assert "1 optional member fell back to its default" in str(info.value)
    assert Mixed.limit == 7


def test_abort_reports_the_optional_misses_beside_the_failure(monkeypatch):
    # the look of a storage matching none of the class's addresses: the
    # required member aborts, and the optional member's silent default
    # rides the abort, so the reader sees the whole class at once
    class Mismatched(Settings):
        token: str = environment_variable_setting(name="TEST_ASV_TOKEN", default=REQUIRED)
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")

    monkeypatch.delenv("TEST_ASV_TOKEN", raising=False)
    monkeypatch.delenv("TEST_ASV_MODE", raising=False)
    with pytest.raises(AggregateLoadError) as info:
        Mismatched.load_settings()

    assert [type(entry) for entry in info.value.errors] == [MissingValueError]
    assert [type(entry) for entry in info.value.misses] == [MissingValueError]
    assert "is required: the process environment provided no value" in str(info.value.errors[0])
    assert (
        "setting 'mode' (environment variable 'TEST_ASV_MODE') of 'Mismatched': "
        "the process environment provided no value" in str(info.value.misses[0])
    )
    assert "1 optional member served its default (the source provided no value)" in str(info.value)
    assert Mismatched.mode == "default-mode"


def test_abort_separates_the_fallbacks_from_the_misses(monkeypatch):
    # one abort, three channels: the required miss in errors, the optional
    # unconvertible value in fallbacks, the optional plain miss in misses
    monkeypatch.setenv("TEST_ASV_LIMIT", "not-a-number")
    monkeypatch.delenv("TEST_ASV_TOKEN", raising=False)
    monkeypatch.delenv("TEST_ASV_MODE", raising=False)

    class SplitReport(Settings):
        token: str = environment_variable_setting(name="TEST_ASV_TOKEN", default=REQUIRED)
        limit: int = environment_variable_setting(name="TEST_ASV_LIMIT", default=7)
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")

    with pytest.raises(AggregateLoadError) as info:
        SplitReport.load_settings()

    assert [type(entry) for entry in info.value.errors] == [MissingValueError]
    assert [type(entry) for entry in info.value.fallbacks] == [ConversionError]
    assert [type(entry) for entry in info.value.misses] == [MissingValueError]
    assert "1 optional member fell back to its default" in str(info.value)
    assert "1 optional member served its default" in str(info.value)


def test_user_facing_storage_error_aborts_the_pass():
    class CorruptSetting(SettingsAttribute):
        """A test storage attribute served by the corrupt serializer."""

    class CorruptSerializer(SettingsBaseSerializer):
        """A test storage serializer whose load signals a user-facing break."""

        def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
            raise UserFacingError(RuntimeError("the file is corrupt"))

        def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
            """No-op: a test storage never writes."""

        def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
            """No-op: a test storage never deletes."""

        def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
            return False

    class CorruptPlugin(SettingsBasePlugin):
        binding = AttributeSerializerBinding(CorruptSetting, CorruptSerializer)

        @property
        def plugin_name(self) -> str:
            return "Corrupt"

    LibraryConfiguration.register_settings_plugin(CorruptPlugin)

    class FileSettings(Settings):
        mode: str = CorruptSetting(name="whatever", default="default-mode")

    # a served default must not mask a broken storage: the source's own
    # condition aborts the pass as itself, even on an optional member
    with pytest.raises(RuntimeError, match="the file is corrupt"):
        FileSettings.load_settings()


# ---------------------------------------------------------------------------
# the fallback warning quotes the storage's own name (ISettingNameDescriber)
# ---------------------------------------------------------------------------


class DescribingSetting(SettingsAttribute):
    """A test storage attribute served by the describing serializer."""


class DescribingSerializer(SettingsBaseSerializer):
    """A test storage serializer: one dict, names spelled with a partition."""

    data: Dict[str, Any] = {}

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        return self.data.get(setting_name, NOT_FOUND)

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """No-op: a test storage never writes."""

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: a test storage never deletes."""

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return setting_name in self.data

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        return f"test partition '{setting_name}'"


class DescribingPlugin(SettingsBasePlugin):
    """A test storage plugin binding the describing pair."""

    binding = AttributeSerializerBinding(DescribingSetting, DescribingSerializer)

    @property
    def plugin_name(self) -> str:
        return "Describing"


LibraryConfiguration.register_settings_plugin(DescribingPlugin)


def describing_setting(**kwargs: Any) -> Any:
    return DescribingSetting(**kwargs)


def test_described_name_reaches_the_fallback_warning(caplog):
    class DescribingSettings(Settings):
        port: int = describing_setting(name="TEST_DESC_PORT", default=8080)

    DescribingSerializer.data["TEST_DESC_PORT"] = "not-a-number"
    try:
        with caplog.at_level(logging.WARNING, logger="advexp.settings"):
            DescribingSettings.load_settings()
    finally:
        DescribingSerializer.data.clear()
    assert DescribingSettings.port == 8080
    messages = [
        record.getMessage()
        for record in caplog.records
        if "using the default value" in record.getMessage()
    ]
    assert any("setting 'port' (test partition 'TEST_DESC_PORT')" in m for m in messages)


def test_env_backend_spells_the_built_variable_name(caplog):
    # the env backend implements ISettingNameDescriber: a member without
    # name= gets its variable from the class's naming options, and the
    # diagnostics quote that built spelling — the pattern-built storage
    # name is a string the environment never sees
    class BuiltSettings(
        Settings,
        options=env_source(name_prefix="TEST_BUILT_", name_case=NameCase.UPPER),
    ):
        limit: int = environment_variable_setting(default=7)

    os.environ["TEST_BUILT_LIMIT"] = "not-a-number"
    try:
        with caplog.at_level(logging.WARNING, logger="advexp.settings"):
            report = BuiltSettings.load_settings()
    finally:
        del os.environ["TEST_BUILT_LIMIT"]
    messages = [
        record.getMessage()
        for record in caplog.records
        if "using the default value" in record.getMessage()
    ]
    assert any(
        "setting 'limit' (environment variable 'TEST_BUILT_LIMIT') of 'BuiltSettings'" in m
        for m in messages
    )
    assert "fell back to its default: cannot convert 'not-a-number' to int" in str(report[0])


def test_required_member_without_name_names_the_built_variable(monkeypatch):
    # the reporter's scenario: a required member, no name=, the variable
    # built from the options — the abort must tell the variable the
    # environment is missing, not the pattern-built storage name
    class SessionSettings(
        Settings,
        options=env_source(name_prefix="APP_", name_case=NameCase.UPPER),
    ):
        session_ttl: int = environment_variable_setting(default=REQUIRED)

    monkeypatch.delenv("APP_SESSION_TTL", raising=False)
    with pytest.raises(AggregateLoadError) as info:
        SessionSettings.load_settings()

    message = str(info.value.errors[0])
    assert "(environment variable 'APP_SESSION_TTL')" in message
    assert "is required: the process environment provided no value" in message


# ---------------------------------------------------------------------------
# the repeated pass: a completed load builds the state from a clean slate,
# a failed one leaves the class exactly as the call found it
# ---------------------------------------------------------------------------


def test_a_completed_reload_builds_the_state_from_a_clean_slate(monkeypatch):
    # the second pass's storages alone decide the state: a member whose
    # variable is gone stands at its declared default — the value of the
    # earlier pass never survives, so one class can be reused across loads
    class ReloadedSettings(Settings):
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")

    monkeypatch.setenv("TEST_ASV_MODE", "from-env")
    ReloadedSettings.load_settings()
    assert ReloadedSettings.mode == "from-env"

    monkeypatch.delenv("TEST_ASV_MODE", raising=False)
    assert ReloadedSettings.load_settings() == ()
    assert ReloadedSettings.mode == "default-mode"


def test_an_aborting_reload_leaves_the_class_as_the_call_found_it(monkeypatch):
    # the failed pass applies nothing — not the values it loaded, not the
    # defaults of its misses: a reload that stumbles keeps the process on
    # the configuration it already runs with
    class StableSettings(Settings):
        token: str = environment_variable_setting(name="TEST_ASV_TOKEN", default=REQUIRED)
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")

    monkeypatch.setenv("TEST_ASV_TOKEN", "token-value")
    monkeypatch.setenv("TEST_ASV_MODE", "from-env")
    StableSettings.load_settings()
    StableSettings.mode = "manual"  # a value the "previous life" left

    monkeypatch.delenv("TEST_ASV_TOKEN", raising=False)
    with pytest.raises(AggregateLoadError):
        StableSettings.load_settings()

    # the failed pass would have served mode 'from-env'; the class keeps
    # what it had — the manual value, not the fresh one, and the token of
    # the last working load stays readable
    assert StableSettings.mode == "manual"
    assert StableSettings.token == "token-value"


def test_a_user_facing_source_error_leaves_the_class_as_the_call_found_it(monkeypatch):
    # a broken source aborts the pass mid-walk; whatever the members before
    # the failing one produced rides with the pass, and the class keeps its
    # state — a served default must not mask the break, and neither may a
    # half-applied load
    class CorruptReloadSettings(Settings):
        mode: str = environment_variable_setting(name="TEST_ASV_MODE", default="default-mode")
        token: str = corrupt_setting(name="whatever", default="fallback")

    monkeypatch.setenv("TEST_ASV_MODE", "from-env")
    with pytest.raises(ValueError, match="corrupt storage"):
        CorruptReloadSettings.load_settings()

    # mode loaded before the source broke — the abort applies nothing
    assert CorruptReloadSettings.mode == "default-mode"


def test_a_failing_optional_member_gets_its_default_not_the_old_value(monkeypatch):
    # even a formally successful pass depends only on the declared defaults
    # and the current storages: a member whose variable turned unconvertible
    # stands at its default, not at the value an earlier load left
    class RenewedSettings(Settings):
        limit: int = environment_variable_setting(name="TEST_ASV_LIMIT", default=7)

    monkeypatch.setenv("TEST_ASV_LIMIT", "42")
    RenewedSettings.load_settings()
    assert RenewedSettings.limit == 42

    monkeypatch.setenv("TEST_ASV_LIMIT", "not-a-number")
    report = RenewedSettings.load_settings()

    assert RenewedSettings.limit == 7
    assert [type(entry) for entry in report] == [ConversionError]
