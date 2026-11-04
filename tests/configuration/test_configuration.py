"""Configuration facade tests: the class, its surface and the read-only guard."""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
import textwrap
from typing import Any, Optional, Sequence, Tuple

import pytest

import advexp.configuration
from advexp.configuration import (
    REQUIRED,
    AggregateLoadError,
    Configuration,
    ConstraintViolationError,
    ConversionError,
    MemberLoadError,
    MissingValueError,
    SourceLoadError,
    Sources,
)
from advexp.configuration.plugin_api import (
    NO_DEFAULT,
    AttributeSerializerBinding,
    ConfigurationAttribute,
    ISettingAttribute,
    LibraryConfiguration,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    SourceBinding,
    SourceLink,
)
from advexp.configuration.plugins.environment.variables import (
    EnvironmentVariablesPlugin,
    env_source,
    environment_variable_setting,
)
from advexp.configuration.plugins.json_settings import json_setting, json_source

PLUGIN_MODULES = [
    "advexp.configuration.plugins.json_settings",
    "advexp.configuration.plugins.environment.variables",
]


class UnregisteredSetting(ConfigurationAttribute):
    """An attribute class that no plugin of this package registers."""


def unregistered_setting(**kwargs: Any) -> Any:
    return UnregisteredSetting(**kwargs)


class ExplodingSetting(ConfigurationAttribute):
    """A test source attribute that derives from the base of the package, as the
    author of a third-party source would do. Its storage always fails to load.
    """


class ExplodingSerializer(SettingsBaseSerializer):
    """A test source serializer: load raises, the rest is inert."""

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        raise RuntimeError("storage exploded")

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """No-op: a test source never writes."""

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: a test source never deletes."""

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return False


class ExplodingPlugin(SettingsBasePlugin):
    """A test source plugin that binds the exploding pair."""

    binding = AttributeSerializerBinding(ExplodingSetting, ExplodingSerializer)

    @property
    def plugin_name(self) -> str:
        return "Exploding"


LibraryConfiguration.register_settings_plugin(ExplodingPlugin)


def exploding_setting(**kwargs: Any) -> Any:
    return ExplodingSetting(**kwargs)


def exploding_source() -> Any:
    # the third-party source's own chain spelling: a link of its family,
    # the way a bundled source's options module builds one
    return SourceBinding(SourceLink(attribute_class=ExplodingSetting))


class EnvConfig(
    Configuration,
    options=env_source(),
):
    text: Optional[str] = environment_variable_setting(name="TEST_ACF_TEXT", default="default-text")
    plain: str = environment_variable_setting(default="")  # the member name is the key


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("TEST_ACF_TEXT", "plain"):
        monkeypatch.delenv(name, raising=False)
    yield


def test_version_is_exposed():
    assert advexp.configuration.__version__


def test_plugins_importable():
    for module_name in PLUGIN_MODULES:
        module = importlib.import_module(module_name)
        assert module.__doc__, f"{module_name} is missing a docstring"


def test_no_default_is_plugin_api_only():
    # the application spelling of "no default" is an omitted ``default=``;
    # the sentinel itself stays with the source authors' plugin_api
    assert not hasattr(advexp.configuration, "NO_DEFAULT")
    assert hasattr(advexp.configuration.plugin_api, "NO_DEFAULT")


def test_required_is_shared_with_plugin_api():
    # both audiences read the marker: applications declare a required
    # member with it, source authors meet it as a declared default
    assert hasattr(advexp.configuration, "REQUIRED")
    assert hasattr(advexp.configuration.plugin_api, "REQUIRED")


def test_facade_has_no_write_back():
    # the package's identity line: sources are only ever read, and the
    # loaded values have no in-memory write layer either
    for name in (
        "save_settings",
        "save_setting",
        "delete_settings",
        "delete_setting",
        "reset_settings",
        "update_from_dict",
        "update_from_object",
    ):
        assert not hasattr(Configuration, name), name


def test_logger_channel_is_the_distribution_root():
    assert EnvConfig.__settings_context__.logger.name == "advexp.configuration"


def test_load_missing_variables_apply_defaults():
    EnvConfig.load_configuration()
    assert EnvConfig.text == "default-text"
    assert EnvConfig.plain == ""


def test_load_reads_environment(monkeypatch):
    monkeypatch.setenv("TEST_ACF_TEXT", "from-env")
    monkeypatch.setenv("plain", "plain-value")
    EnvConfig.load_configuration()
    assert EnvConfig.text == "from-env"
    assert EnvConfig.plain == "plain-value"


def test_load_is_the_one_writer(monkeypatch):
    # a guard-rejected write leaves the loaded value in place; the next
    # load is what brings new values in
    monkeypatch.setenv("TEST_ACF_TEXT", "first")
    EnvConfig.load_configuration()
    assert EnvConfig.text == "first"

    with pytest.raises(TypeError, match="read-only member"):
        EnvConfig.text = "blocked"

    monkeypatch.setenv("TEST_ACF_TEXT", "second")
    EnvConfig.load_configuration()
    assert EnvConfig.text == "second"


def test_members_compose_over_inheritance(monkeypatch):
    monkeypatch.setenv("TEST_ACF_TEXT", "base-value")

    class DerivedConfig(EnvConfig):
        extra: str = environment_variable_setting(name="TEST_ACF_EXTRA", default="extra-default")

    monkeypatch.setenv("TEST_ACF_EXTRA", "derived-value")
    DerivedConfig.load_configuration()
    assert DerivedConfig.text == "base-value"  # the base's member, own storage
    assert DerivedConfig.extra == "derived-value"

    monkeypatch.delenv("TEST_ACF_TEXT")
    EnvConfig.load_configuration()
    assert EnvConfig.text == "default-text"  # the base class reads its own sources
    assert DerivedConfig.text == "base-value"  # the derived class keeps its own storage


def test_unregistered_attribute_fails_the_class_statement():
    # the chain is where a source-less member surfaces now: the class
    # statement names the member and the family, before any pass runs
    with pytest.raises(
        TypeError,
        match="MixedConfig.foreign is declared with UnregisteredSetting, but "
        "the class's source chain has no link of that family",
    ):

        class MixedConfig(
            Configuration,
            options=env_source(),
        ):
            text: str = environment_variable_setting(name="TEST_ACF_TEXT", default="")
            foreign: bool = unregistered_setting(default=False)


# ---------------------------------------------------------------------------
# required members: declared without a default, must come from a source
# ---------------------------------------------------------------------------


class RequiredEnvConfig(
    Configuration,
    options=env_source(),
):
    mode: str = environment_variable_setting(name="TEST_ACF_MODE")  # required: no default


def test_required_member_loads_from_source(monkeypatch):
    monkeypatch.setenv("TEST_ACF_MODE", "dev")
    RequiredEnvConfig.load_configuration()
    assert RequiredEnvConfig.mode == "dev"


def test_required_member_missing_aborts_load(monkeypatch):
    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    with pytest.raises(
        AggregateLoadError, match="is required: the process environment provided no value"
    ) as info:
        RequiredEnvConfig.load_configuration()
    (entry,) = info.value.errors
    assert type(entry) is MissingValueError
    assert isinstance(entry, MemberLoadError)
    # the abort names its package: the channel of the distribution that
    # ran the pass opens the message
    assert str(info.value).startswith("advexp.configuration error: the load failed for")
    assert "environment variable 'TEST_ACF_MODE'" in str(info.value)
    assert "RequiredEnvConfig" in str(info.value)


def test_required_member_unconvertible_value_aborts_load(monkeypatch):
    class PortConfig(
        Configuration,
        options=env_source(),
    ):
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT")

    monkeypatch.setenv("TEST_ACF_LIMIT", "not-a-number")
    with pytest.raises(AggregateLoadError, match="cannot convert 'not-a-number' to int") as info:
        PortConfig.load_configuration()
    assert [type(entry) for entry in info.value.errors] == [ConversionError]
    assert isinstance(info.value.errors[0], MemberLoadError)
    assert "environment variable 'TEST_ACF_LIMIT'" in str(info.value)
    assert "PortConfig" in str(info.value)


def test_required_member_constraint_violation_aborts_load(monkeypatch):
    class BoundedConfig(
        Configuration,
        options=env_source(),
    ):
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT", ge=10)

    monkeypatch.setenv("TEST_ACF_LIMIT", "5")
    with pytest.raises(AggregateLoadError, match="violates its constraints") as info:
        BoundedConfig.load_configuration()
    assert [type(entry) for entry in info.value.errors] == [ConstraintViolationError]
    assert isinstance(info.value.errors[0], MemberLoadError)
    assert "environment variable 'TEST_ACF_LIMIT'" in str(info.value)


def test_required_member_source_failure_aborts_with_cause():
    # no default= spelled at all: the package's attribute base makes the
    # member required, exactly like the bundled sources — a third-party
    # author gets that for free by deriving ConfigurationAttribute
    class BrokenConfig(
        Configuration,
        options=exploding_source(),
    ):
        mode: str = exploding_setting()

    with pytest.raises(AggregateLoadError, match="storage exploded") as info:
        BrokenConfig.load_configuration()
    assert [type(entry) for entry in info.value.errors] == [SourceLoadError]
    message = str(info.value)
    assert "'mode'" in message and "BrokenConfig" in message
    assert "RuntimeError" in message
    assert isinstance(info.value.errors[0], MemberLoadError)


def test_optional_member_source_failure_logs_and_skips(caplog):
    # NO_DEFAULT on the package's attribute base is the opt-out spelling:
    # the member is optional, the failure is logged and skipped
    class SoftBrokenConfig(
        Configuration,
        options=exploding_source(),
    ):
        mode: Optional[str] = exploding_setting(name="whatever", default=NO_DEFAULT)

    with caplog.at_level(logging.ERROR, logger="advexp.configuration"):
        report = SoftBrokenConfig.load_configuration()
    assert SoftBrokenConfig.mode is None
    # the record carries the full fallback shape: the member's place, the
    # source that raised, and the fallback tail
    assert [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ] == [
        "member 'mode' (whatever) of 'SoftBrokenConfig': "
        "its source raised RuntimeError (storage exploded); using the default value"
    ]
    # the fallback is an entry of the returned report beside the log record
    assert [type(entry) for entry in report] == [SourceLoadError]
    assert "fell back to its default: its source raised" in str(report[0])


def test_clean_load_returns_an_empty_report(monkeypatch):
    monkeypatch.setenv("TEST_ACF_MODE", "set")

    class QuietConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT", default=7)

    assert QuietConfig.load_configuration() == ()


def test_optional_member_garbage_lands_in_the_returned_report(monkeypatch):
    class SoftConfig(
        Configuration,
        options=env_source(),
    ):
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT2", default=7)
        plain: Optional[str] = environment_variable_setting(name="TEST_ACF_PLAIN", default=None)

    monkeypatch.setenv("TEST_ACF_LIMIT2", "not-a-number")
    report = SoftConfig.load_configuration()

    # no required member failed: no abort, the fallbacks are the report;
    # the member's word is this package's own — a configuration class
    # holds members, its records never say "setting"
    assert [type(entry) for entry in report] == [ConversionError]
    assert (
        "member 'limit' (environment variable 'TEST_ACF_LIMIT2') of 'SoftConfig' "
        "fell back to its default: cannot convert 'not-a-number' to int" in str(report[0])
    )
    assert SoftConfig.limit == 7


def test_mixed_class_marks_the_fallbacks_in_the_abort(monkeypatch):
    monkeypatch.setenv("TEST_ACF_LIMIT3", "not-a-number")
    monkeypatch.delenv("TEST_ACF_MODE", raising=False)

    class MixedConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT3", default=7)

    with pytest.raises(AggregateLoadError) as info:
        MixedConfig.load_configuration()

    # the required failure is the abort; the optional fallback of the same
    # run rides it, marked structurally
    assert [type(entry) for entry in info.value.errors] == [MissingValueError]
    assert [type(entry) for entry in info.value.fallbacks] == [ConversionError]
    assert "1 optional member fell back to its default" in str(info.value)
    assert MixedConfig.limit == 7


def test_abort_reports_the_optional_misses_beside_the_failure(monkeypatch):
    # one abort, three channels: the required miss in errors, the optional
    # unconvertible value in fallbacks, the optional plain miss in misses —
    # the look of a source matching none of the class's addresses
    monkeypatch.setenv("TEST_ACF_LIMIT3", "not-a-number")
    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    monkeypatch.delenv("TEST_ACF_PLAIN2", raising=False)

    class SplitConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT3", default=7)
        plain: Optional[str] = environment_variable_setting(name="TEST_ACF_PLAIN2", default=None)

    with pytest.raises(AggregateLoadError) as info:
        SplitConfig.load_configuration()

    assert [type(entry) for entry in info.value.errors] == [MissingValueError]
    assert [type(entry) for entry in info.value.fallbacks] == [ConversionError]
    assert [type(entry) for entry in info.value.misses] == [MissingValueError]
    assert "1 optional member fell back to its default" in str(info.value)
    assert "1 optional member served its default (the source provided no value)" in str(info.value)
    assert (
        "member 'plain' (environment variable 'TEST_ACF_PLAIN2') of 'SplitConfig': "
        "the process environment provided no value" in str(info.value.misses[0])
    )
    assert SplitConfig.plain is None


def test_the_load_taxonomy_is_shared_with_the_settings_package():
    import advexp.settings

    # one family, one load pass, one error taxonomy: the names both
    # packages export are the base classes
    assert advexp.settings.AggregateLoadError is AggregateLoadError
    assert advexp.settings.MissingValueError is MissingValueError
    assert advexp.settings.MemberLoadError is MemberLoadError
    assert advexp.settings.ConversionError is ConversionError
    assert advexp.settings.ConstraintViolationError is ConstraintViolationError
    assert advexp.settings.SourceLoadError is SourceLoadError


def test_required_errors_share_one_parent():
    for error_class in (
        MissingValueError,
        ConversionError,
        ConstraintViolationError,
        SourceLoadError,
        AggregateLoadError,
    ):
        assert issubclass(error_class, MemberLoadError)
    assert issubclass(MemberLoadError, ValueError)


# ---------------------------------------------------------------------------
# several failing members: one abort reports them all at once
# ---------------------------------------------------------------------------


def test_several_required_failures_report_all_at_once(monkeypatch):
    # the user's seat: three variables missing, one value unconvertible —
    # one exception names all four members, no run-fix-rerun loop
    class BrokenAppConfig(
        Configuration,
        options=env_source(),
    ):
        host: str = environment_variable_setting(name="TEST_ACF_HOST")
        port: int = environment_variable_setting(name="TEST_ACF_PORT")
        token: str = environment_variable_setting(name="TEST_ACF_TOKEN")
        retries: int = environment_variable_setting(name="TEST_ACF_RETRIES")

    for name in ("TEST_ACF_HOST", "TEST_ACF_PORT", "TEST_ACF_TOKEN", "TEST_ACF_RETRIES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TEST_ACF_RETRIES", "not-a-number")

    with pytest.raises(AggregateLoadError) as info:
        BrokenAppConfig.load_configuration()

    error = info.value
    assert isinstance(error, MemberLoadError)
    assert isinstance(error, ValueError)
    assert [type(member_error) for member_error in error.errors] == [
        MissingValueError,
        MissingValueError,
        MissingValueError,
        ConversionError,
    ]
    message = str(error)
    assert "the load failed for 4 members" in message
    for variable in ("TEST_ACF_HOST", "TEST_ACF_PORT", "TEST_ACF_TOKEN", "TEST_ACF_RETRIES"):
        assert f"environment variable '{variable}'" in message
    assert "BrokenAppConfig" in message
    # each member's line is the member's own error, verbatim
    for member_error in error.errors:
        assert str(member_error) in message


def test_every_failure_class_collects_into_one_abort(monkeypatch):
    # all four member errors ride one abort: a miss, a conversion, a
    # constraint violation and a source failure
    class MixedFailureConfig(
        Configuration,
        options=Sources(env_source(), exploding_source()),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT")
        bounded: int = environment_variable_setting(name="TEST_ACF_BOUNDED", ge=10)
        broken: str = exploding_setting()

    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    monkeypatch.setenv("TEST_ACF_LIMIT", "not-a-number")
    monkeypatch.setenv("TEST_ACF_BOUNDED", "5")

    with pytest.raises(AggregateLoadError) as info:
        MixedFailureConfig.load_configuration()
    assert [type(member_error) for member_error in info.value.errors] == [
        MissingValueError,
        ConversionError,
        ConstraintViolationError,
        SourceLoadError,
    ]


def test_single_failure_rides_the_aggregate_too(monkeypatch):
    # one failure or five — the abort is always AggregateLoadError: the
    # exception type never depends on the failure count, no surprise
    # exception kind for the caller to guess
    class OneFailureConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")
        tail: str = environment_variable_setting(name="TEST_ACF_TAIL", default="tail-default")

    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    with pytest.raises(AggregateLoadError) as info:
        OneFailureConfig.load_configuration()
    assert [type(entry) for entry in info.value.errors] == [MissingValueError]
    assert "the load failed for 1 member" in str(info.value)


def test_required_member_over_broken_source_collects(monkeypatch, tmp_path):
    # one JSON member in a class of environment members: a corrupt file is
    # that member's failed source, not a pass abort — failures of both
    # sources ride one aggregate
    tmp_path.joinpath("config.json").write_text("{not json", encoding="utf-8")

    class MixedSourceConfig(
        Configuration,
        options=Sources(env_source(), json_source(file=tmp_path / "config.json")),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")
        entry: str = json_setting(name="entry")

    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    with pytest.raises(AggregateLoadError) as info:
        MixedSourceConfig.load_configuration()

    missing, source_error = info.value.errors
    assert type(missing) is MissingValueError
    assert type(source_error) is SourceLoadError
    assert "'entry'" in str(source_error)
    assert "cannot parse the JSON configuration file" in str(source_error)


def test_optional_member_over_broken_source_aborts_as_itself(monkeypatch, tmp_path):
    # a served default must not mask a corrupt file: the source's own
    # user-facing error aborts the pass as itself
    tmp_path.joinpath("config.json").write_text("{not json", encoding="utf-8")

    class SoftSourceConfig(
        Configuration,
        options=json_source(file=tmp_path / "config.json"),
    ):
        entry: str = json_setting(name="entry", default="stand-in")

    with pytest.raises(ValueError, match="cannot parse the JSON configuration file"):
        SoftSourceConfig.load_configuration()


def test_optional_member_garbage_falls_back_with_warning(monkeypatch, caplog):
    class SoftConfig(
        Configuration,
        options=env_source(),
    ):
        limit: int = environment_variable_setting(name="TEST_ACF_LIMIT", default=7)

    monkeypatch.setenv("TEST_ACF_LIMIT", "not-a-number")
    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        SoftConfig.load_configuration()
    assert SoftConfig.limit == 7
    # the fallback warning fires only when a default is really served — and
    # names the member, its storage address, the class and the cause
    reports = [r for r in caplog.records if "using the default value" in r.getMessage()]
    assert reports
    assert "member 'limit' (environment variable 'TEST_ACF_LIMIT')" in reports[0].getMessage()
    assert "cannot convert 'not-a-number' to int" in reports[0].getMessage()


def test_load_is_retryable_after_required_abort(monkeypatch):
    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    with pytest.raises(AggregateLoadError):
        RequiredEnvConfig.load_configuration()

    monkeypatch.setenv("TEST_ACF_MODE", "later")
    RequiredEnvConfig.load_configuration()
    assert RequiredEnvConfig.mode == "later"


def test_failed_members_do_not_block_the_rest_of_the_pass(monkeypatch):
    # the pass walks every member — the report of the abort names them all;
    # the class itself keeps the state it had before the call: the healthy
    # tail holds nothing the failed pass loaded, and the failed member
    # raises on read; the next pass brings the values in
    class OrderedConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")
        tail: str = environment_variable_setting(name="TEST_ACF_TAIL", default="tail-default")

    monkeypatch.setenv("TEST_ACF_TAIL", "tail-value")
    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    with pytest.raises(AggregateLoadError):
        OrderedConfig.load_configuration()
    assert OrderedConfig.tail == "tail-default"  # untouched: nothing applied
    with pytest.raises(MemberLoadError, match="no value was loaded"):
        OrderedConfig.mode

    monkeypatch.setenv("TEST_ACF_MODE", "ok")
    OrderedConfig.load_configuration()
    assert OrderedConfig.mode == "ok"
    assert OrderedConfig.tail == "tail-value"


def test_required_member_read_before_load_raises():
    # a fresh class, never loaded: no stand-in value exists to read, and the
    # reason is unknown at read time — the parent error itself, not one of
    # the load-time classes
    class NeverLoadedConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")

    with pytest.raises(MemberLoadError, match="is required: no value was loaded") as info:
        NeverLoadedConfig.mode
    # the record speaks this package's vocabulary: a configuration class
    # holds members, never "settings"
    assert "member 'mode' is required: no value was loaded" in str(info.value)
    assert type(info.value) is MemberLoadError
    with pytest.raises(MemberLoadError):
        NeverLoadedConfig().mode
    with pytest.raises(MemberLoadError):
        NeverLoadedConfig.to_dict()
    with pytest.raises(MemberLoadError):
        NeverLoadedConfig.to_object()


class InterfaceMember(ISettingAttribute):
    """A member attribute that implements the contract alone.

    It has no base class: it inherits nothing but ``object``. The fields of the
    contract are properties over private instance storage, so the class carries
    nothing of the machinery of the packages.
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = REQUIRED,
        aliases: Optional[Sequence[str]] = None,
    ) -> None:
        self._name: Optional[str] = name
        self._default: Any = default
        self._aliases: Tuple[str, ...] = tuple(aliases) if aliases else ()
        self._bound_name: Optional[str] = None
        self._declaring_class: Optional[type] = None

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def default(self) -> Any:
        return self._default

    @property
    def aliases(self) -> Tuple[str, ...]:
        return self._aliases

    @property
    def bound_name(self) -> Optional[str]:
        return self._bound_name

    @bound_name.setter
    def bound_name(self, value: Optional[str]) -> None:
        self._bound_name = value

    @property
    def declaring_class(self) -> Optional[type]:
        return self._declaring_class

    @declaring_class.setter
    def declaring_class(self, value: Optional[type]) -> None:
        self._declaring_class = value


def test_contract_only_attribute_words_errors_with_the_class_term():
    # the term is the class's declaration alone: an attribute implementing
    # the interface without any package base inherits the class's package
    # vocabulary the same way a bundled one does
    class ContractConfig(Configuration):
        mode: str = InterfaceMember(name="TEST_ACF_MODE")

    with pytest.raises(MemberLoadError) as info:
        ContractConfig.mode
    assert "member 'mode' is required: no value was loaded" in str(info.value)


def test_class_member_cannot_be_deleted():
    # the deletion twin of the read-only guard: no advice to call the
    # settings package's delete_setting — this package carries no such
    # method, and a member of a configuration class is never deletable
    class GuardedConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE", default="x")

    with pytest.raises(TypeError, match="'mode' is a read-only member of GuardedConfig"):
        del GuardedConfig.mode
    assert GuardedConfig.mode == "x"


def test_explicit_none_default_is_not_required(monkeypatch):
    class WithNoneDefault(
        Configuration,
        options=env_source(),
    ):
        value: Optional[str] = environment_variable_setting(name="TEST_ACF_OPT", default=None)

    monkeypatch.delenv("TEST_ACF_OPT", raising=False)
    WithNoneDefault.load_configuration()
    assert WithNoneDefault.value is None


def test_required_member_is_inherited(monkeypatch):
    class BaseConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="TEST_ACF_MODE")

    class DerivedConfig(BaseConfig):
        extra: str = environment_variable_setting(name="TEST_ACF_EXTRA", default="extra-default")

    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    with pytest.raises(AggregateLoadError, match="of 'DerivedConfig' is required"):
        DerivedConfig.load_configuration()

    monkeypatch.setenv("TEST_ACF_MODE", "set")
    DerivedConfig.load_configuration()
    assert DerivedConfig.mode == "set"


def test_explicit_no_default_serves_none(monkeypatch):
    # NO_DEFAULT keeps its family-wide meaning in a configuration class:
    # the member is optional, None stands in — the exact opposite of the
    # package's attribute base, whose default is REQUIRED
    class NoDefaultConfig(
        Configuration,
        options=env_source(),
    ):
        mode: Optional[str] = environment_variable_setting(name="TEST_ACF_MODE", default=NO_DEFAULT)

    monkeypatch.delenv("TEST_ACF_MODE", raising=False)
    assert NoDefaultConfig.mode is None  # a never-loaded member serves None too
    NoDefaultConfig.load_configuration()
    assert NoDefaultConfig.mode is None

    monkeypatch.setenv("TEST_ACF_MODE", "set")
    NoDefaultConfig.load_configuration()
    assert NoDefaultConfig.mode == "set"


def test_no_default_member_rejecting_none_fails_class_creation():
    # the family rule: the None a NO_DEFAULT member stands in with faces
    # the member's constraints at class creation; Advexp.Configuration
    # shares the machinery, so the class statement fails here too
    with pytest.raises(TypeError, match="invalid defaults in BadStandInConfig") as info:

        class BadStandInConfig(Configuration):
            mode: Optional[str] = environment_variable_setting(
                name="TEST_ACF_MODE", default=NO_DEFAULT, eq="prod"
            )

    assert "mode" in str(info.value)
    assert "value None must be equal to 'prod'" in str(info.value)


def test_required_default_is_not_a_default_in_use():
    member = RequiredEnvConfig.__settings_members__["mode"]
    assert member.attribute.default_in_use is False
    valued = EnvConfig.__settings_members__["text"]
    assert valued.attribute.default_in_use is True


def test_required_marker_is_public():
    # both import sites hand the marker over: applications spell it in
    # declarations, source authors default their factories to it
    assert advexp.configuration.REQUIRED is advexp.configuration.plugin_api.REQUIRED


# ---------------------------------------------------------------------------
# the read-only guard
# ---------------------------------------------------------------------------


def test_class_member_assignment_raises():
    with pytest.raises(TypeError, match="'text' is a read-only member"):
        EnvConfig.text = "blocked"
    assert EnvConfig.text == "default-text"  # the blocked write never landed


def test_instance_member_assignment_raises():
    EnvConfig.load_configuration()
    instance = EnvConfig()
    with pytest.raises(TypeError, match="'text' is a read-only member"):
        instance.text = "blocked"
    with pytest.raises(TypeError, match="'text' is a read-only member"):
        del instance.text
    assert instance.text == "default-text"  # reads still share the class storage
    assert EnvConfig.text == "default-text"


def test_snapshot_is_frozen_outright():
    EnvConfig.load_configuration()
    snapshot = EnvConfig.to_object()
    with pytest.raises(TypeError, match="'plain' is a read-only member"):
        snapshot.plain = "blocked"
    # not even a non-member lands on a snapshot
    with pytest.raises(TypeError, match="is frozen"):
        snapshot.arbitrary = 1
    with pytest.raises(TypeError, match="'plain' is a read-only member"):
        del snapshot.plain
    with pytest.raises(TypeError, match="is frozen"):
        del snapshot.arbitrary
    assert snapshot.plain == ""
    assert snapshot.text == "default-text"


def test_non_member_attributes_stay_writable():
    # the guard covers declared members only; plain attributes are none of
    # the library's business — on an ordinary instance. A to_object
    # snapshot is the exception: it is frozen outright
    EnvConfig.custom_nonsense = "fine"
    assert EnvConfig.custom_nonsense == "fine"
    del EnvConfig.custom_nonsense

    instance = EnvConfig()
    instance.arbitrary = 1
    assert instance.arbitrary == 1


def test_to_dict_is_frozen_and_isolated():
    EnvConfig.load_configuration()
    snapshot = EnvConfig.to_dict()
    assert snapshot == {"text": "default-text", "plain": ""}

    # the mapping is read-only: item writes raise, like member writes do
    with pytest.raises(TypeError):
        snapshot["text"] = "blocked"
    with pytest.raises(TypeError):
        del snapshot["plain"]
    assert EnvConfig.text == "default-text"

    # dict(...) gives the mutable copy; it shares nothing with the class
    mutable = dict(snapshot)
    mutable["text"] = "mutated"
    assert snapshot["text"] == "default-text"
    assert EnvConfig.text == "default-text"


def test_to_object_reads_detached_from_the_class():
    EnvConfig.load_configuration()
    snapshot = EnvConfig.to_object()
    assert isinstance(snapshot, EnvConfig)
    assert snapshot.text == "default-text"

    # class-side loads never reach an already-taken snapshot
    EnvConfig.load_configuration()
    assert snapshot.text == "default-text"


def test_get_plugin_bound_to_class():
    plugin = EnvConfig.get_plugin(EnvironmentVariablesPlugin)
    assert plugin.plugin_name == "EnvironmentVariables"
    assert plugin.context.settings_class is EnvConfig


# ---------------------------------------------------------------------------
# rules across members: references, when= and the __validate__ hook, in the
# package's own error shape — one entry per member of the load abort


def test_member_reference_defaults_fail_the_class_statement():
    with pytest.raises(TypeError) as info:

        class BadRanges(Configuration):
            low: int = environment_variable_setting(default=100)
            high: int = environment_variable_setting(default=10, ge=low)

    assert "invalid defaults in BadRanges" in str(info.value)
    assert "must be greater than or equal to the value of 'low' (100)" in str(info.value)


def test_member_reference_violation_is_an_entry_of_the_load_report(monkeypatch):
    monkeypatch.setenv("ADVEXP_CV_LO", "2000")
    monkeypatch.setenv("ADVEXP_CV_HI", "1500")

    class Ranges(
        Configuration,
        options=env_source(),
    ):
        low: int = environment_variable_setting(name="ADVEXP_CV_LO", default=1024)
        high: int = environment_variable_setting(name="ADVEXP_CV_HI", default=65535, ge=low)

    report = Ranges.load_configuration()

    # optional members never abort the load: the violation is an entry of
    # the returned report, and the members of the violated rule fall back
    # to their defaults — a consistent state
    assert [type(entry) for entry in report] == [ConstraintViolationError]
    assert "value 1500 must be greater than or equal to the value of 'low' (2000)" in str(report[0])
    assert (Ranges.low, Ranges.high) == (1024, 65535)


def test_a_rule_whose_required_neighbor_failed_its_load_waits():
    # the neighbor holds no value at all: there is nothing to compare with,
    # so the rule does not pile a second error onto the member's own one
    with pytest.raises(AggregateLoadError) as info:

        class Waiting(
            Configuration,
            options=env_source(),
        ):
            floor: int = environment_variable_setting()  # no variable, required
            ceil: int = environment_variable_setting(default=100, ge=floor)

        Waiting.load_configuration()

    assert [type(entry) for entry in info.value.errors] == [MissingValueError]


def test_when_gates_the_constraints_during_the_load(monkeypatch):
    monkeypatch.setenv("ADVEXP_CV_TAG", "q")  # shorter than min_length allows

    class Gated(
        Configuration,
        options=env_source(),
    ):
        flag: bool = environment_variable_setting(default=False)
        tag: str = environment_variable_setting(
            name="ADVEXP_CV_TAG", default="xx", min_length=2, when=flag
        )

    Gated.load_configuration()  # flag is False: the loaded violation is gated off
    assert Gated.tag == "q"

    monkeypatch.setenv("ADVEXP_CV_TAG2", "q")

    class Awake(
        Configuration,
        options=env_source(),
    ):
        flag: bool = environment_variable_setting(default=True)
        # required: a gated violation that is awake has no default to fall
        # back to, so it is the member's own abort entry
        tag: str = environment_variable_setting(name="ADVEXP_CV_TAG2", min_length=2, when=flag)

    with pytest.raises(AggregateLoadError) as info:
        Awake.load_configuration()  # flag is True now: the stored violation applies

    assert [type(entry) for entry in info.value.errors] == [ConstraintViolationError]


def test_hook_findings_that_no_reset_settles_abort_the_load(monkeypatch):
    monkeypatch.setenv("ADVEXP_CV_MODE", "prod")

    class Hooked(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(name="ADVEXP_CV_MODE", default="dev")
        ssl: Optional[str] = environment_variable_setting(name="ADVEXP_CV_SSL", default=None)

        def __validate__(self) -> dict:
            if self.mode == "prod" and self.ssl is None:
                return {"ssl": "ssl is required when mode is 'prod'"}
            return {}

    # the finding names ssl, and ssl already stands at its default: no
    # reset can settle the violation, so the pass aborts and the class
    # keeps the state it had — a completed load is either consistent or
    # did not complete
    with pytest.raises(AggregateLoadError) as info:
        Hooked.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        "member 'ssl' of 'Hooked' violates its constraints "
        "(ssl is required when mode is 'prod'); "
        "no reset to the declared defaults settles it"
    )
    assert Hooked.mode == "dev"
    assert Hooked.ssl is None

    # the condition satisfied, the same class loads quietly
    monkeypatch.setenv("ADVEXP_CV_SSL", "on")
    assert Hooked.load_configuration() == ()
    assert Hooked.ssl == "on"


def test_hook_reading_a_member_without_value_is_an_entry_not_a_crash():
    class Probe(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting()  # required, nothing loaded

        def __validate__(self) -> dict:
            return {"mode": f"hook saw {self.mode!r}"}

    with pytest.raises(AggregateLoadError) as info:
        Probe.load_configuration()

    # the hook read a member that holds no value: that reading error rides
    # the aggregate like any member failure, and the pass still reports
    # every member at once
    kinds = [type(entry) for entry in info.value.errors]
    assert MissingValueError in kinds
    assert all(issubclass(kind, MemberLoadError) for kind in kinds)


def test_a_consistent_cross_rule_class_loads_quietly(monkeypatch):
    monkeypatch.setenv("ADVEXP_CV_LO2", "2000")
    monkeypatch.setenv("ADVEXP_CV_HI2", "9000")

    class Ranges(
        Configuration,
        options=env_source(),
    ):
        low: int = environment_variable_setting(name="ADVEXP_CV_LO2", default=1024)
        high: int = environment_variable_setting(name="ADVEXP_CV_HI2", default=65535, ge=low)

        def __validate__(self) -> dict:
            if self.high - self.low > 100000:
                return {"high": "the range is too wide"}
            return {}

    Ranges.load_configuration()
    assert (Ranges.low, Ranges.high) == (2000, 9000)


def test_the_core_import_is_self_sufficient():
    """The facade alone declares a working class: setting holds its default."""
    script = textwrap.dedent(
        """
        from advexp.configuration import (
            Configuration,
            constant_setting,
        )


        class Constants(Configuration):
            url: str = constant_setting(default="https://api.example")
            port: int = constant_setting(default=8080, le=65535)


        # the declared defaults, read-only, with the package's own rule:
        # a constant without a value refuses its declaration outright
        Constants.load_configuration()
        assert Constants.url == "https://api.example"
        assert Constants.port == 8080
        try:
            Constants.port = 9090
            raise SystemExit("the write guard did not fire")
        except TypeError:
            pass


        try:
            class Required(Configuration):
                must: str = constant_setting()
            raise SystemExit("the constant without a value got declared")
        except TypeError:
            pass
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
