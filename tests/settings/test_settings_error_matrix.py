"""The error-message matrix: every form of failure on every bundled attribute
type.

One class shape walks through every backend that the package bundles. The
class has four members that cover the declaration states:

- a ``REQUIRED`` member;
- the own default of the package (a bare member serves ``None``);
- a declared value;
- a required member that the storage holds.

So one run shows the healthy load next to the failures.

The scenarios replay the user-facing failures against that shape:

- values that are missing, present, or stored under an address that the
  library does not read;
- a corrupt or unreadable storage;
- a serializer that breaks;
- values that no conversion can take;
- several sources that share one class.

The tests pin the message itself, that is, the exact line that the load
raises or logs. The wording (the member, its storage address, its class, and
the channel of the package) is the product that this suite watches.

The backend table at the top is the single axis of variation of the suite: a
new bundled attribute type joins it by adding one ``Backend`` row (or a pair
in ``DYNAMIC_BACKENDS`` for a dynamic collection). The closing test walks
the plugin modules of the package and refuses a module that the table does
not know, so the matrix cannot silently miss a new source.
"""

from __future__ import annotations

import importlib
import json
import logging
import pkgutil
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

import pytest

import advexp.settings.plugins as settings_plugins
from advexp.settings import (
    REQUIRED,
    AggregateLoadError,
    ConversionError,
    MemberLoadError,
    MissingValueError,
    Settings,
    SourceLoadError,
)
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment import NameCase
from advexp.settings.plugins.environment.dotenv import (
    DotenvSerializer,
    dotenv_setting,
    dotenv_source,
)
from advexp.settings.plugins.environment.variables import (
    EnvironmentVariablesSerializer,
    env_source,
    environment_variable_setting,
)
from advexp.settings.plugins.json_dynamic_settings import (
    JSONDynamicSettingsPlugin,
)
from advexp.settings.plugins.json_settings import (
    JSONSettingsSerializer,
    json_setting,
    json_source,
)
from advexp.settings.plugins.toml_dynamic_settings import (
    TOMLDynamicSettingsPlugin,
)
from advexp.settings.plugins.toml_settings import (
    TOMLSettingsSerializer,
    toml_setting,
    toml_source,
)
from advexp.settings.plugins.yaml_dynamic_settings import (
    YAMLDynamicSettingsPlugin,
)
from advexp.settings.plugins.yaml_settings import (
    YAMLSettingsSerializer,
    yaml_setting,
    yaml_source,
)

# the paid editions' plugin modules join the coverage walk through a
# private module the public repository does not carry
try:
    from _error_matrix_private_modules import PRIVATE_PLUGIN_MODULES
except ImportError:
    PRIVATE_PLUGIN_MODULES = {}

# the package's channel and its word for a member, spelled out once: every
# expected message below is built from them (the aggregate's own section
# headings say "member" in both packages of the family, whatever the
# package's term for one is)
CHANNEL = "advexp.settings"
TERM = "setting"
AGGREGATE_NOUN = "member"

# the four members of the matrix class: a required one the scenarios break
# (ANSWER), the package's own default (PLAIN), a declared value (KNOWN) and
# a required one the storage always holds (CONTROL)
ANSWER = "answer"
PLAIN = "plain"
KNOWN = "known"
CONTROL = "control"
DEFAULT_VALUE = 7

MEMBER_STATES: Dict[str, Any] = {
    ANSWER: REQUIRED,
    PLAIN: NO_DEFAULT,
    KNOWN: DEFAULT_VALUE,
    CONTROL: REQUIRED,
}
REQUIRED_ONLY_STATES: Dict[str, Any] = {ANSWER: REQUIRED, CONTROL: REQUIRED}
GOOD_VALUES: Dict[str, int] = {ANSWER: 11, PLAIN: 22, KNOWN: 33, CONTROL: 44}
CLASS_NAME = "ErrorMatrixSettings"

ENV_PREFIX = "EMX_"


def _env_name(member: str) -> str:
    return f"{ENV_PREFIX}{member.upper()}"


def _plain_name(member: str) -> str:
    return member


def _store_env(monkeypatch: pytest.MonkeyPatch, path: Path, values: Dict[str, Any]) -> None:
    for member, value in values.items():
        monkeypatch.setenv(_env_name(member), str(value))


def _store_dotenv(monkeypatch: pytest.MonkeyPatch, path: Path, values: Dict[str, Any]) -> None:
    lines = [f"{_env_name(member)}={value}" for member, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _store_json(monkeypatch: pytest.MonkeyPatch, path: Path, values: Dict[str, Any]) -> None:
    document = {_plain_name(member): value for member, value in values.items()}
    path.write_text(json.dumps(document), encoding="utf-8")


def _store_toml(monkeypatch: pytest.MonkeyPatch, path: Path, values: Dict[str, Any]) -> None:
    lines = [
        f"{_plain_name(member)} = {json.dumps(value) if isinstance(value, str) else value}"
        for member, value in values.items()
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _store_yaml(monkeypatch: pytest.MonkeyPatch, path: Path, values: Dict[str, Any]) -> None:
    lines = [
        f"{_plain_name(member)}: {json.dumps(value) if isinstance(value, str) else value}"
        for member, value in values.items()
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Backend:
    """One bundled attribute type: how its storage is declared, filled, and broken.

    - ``name_of`` spells the storage address of a member.
    - ``address`` is the address phrase that a message carries (with the file,
      when the storage is a file).
    - ``source`` is the phrase that a cause blames.
    - ``corrupt`` makes the storage corrupt. It is ``None`` where the storage
      has no corrupt form that is worth an abort (the process environment; a
      dotenv line that python-dotenv skips is the softer form of the dotenv
      backend itself, and its own test pins it).
    """

    def __init__(
        self,
        marker: str,
        name_of: Callable[[str], str],
        declare: Callable[..., Any],
        bind: Callable[[Path], Any],
        store: Callable[[pytest.MonkeyPatch, Path, Dict[str, Any]], None],
        serializer: type,
        address: Callable[[str, Path], str],
        source: str,
        corrupt: Optional[Callable[[Path], None]] = None,
        corrupt_text: str = "",
    ) -> None:
        self.marker = marker
        self.name_of = name_of
        self.declare = declare
        self.bind = bind
        self.store = store
        self.serializer = serializer
        self.address = address
        self.source = source
        self.corrupt = corrupt
        self.corrupt_text = corrupt_text

    def break_storage(self, path: Path) -> None:
        assert self.corrupt is not None, "the backend declares no corrupt form"
        self.corrupt(path)


def _corrupt_json(path: Path) -> None:
    path.write_text("{not json", encoding="utf-8")


def _corrupt_toml(path: Path) -> None:
    path.write_text("[not toml", encoding="utf-8")


def _corrupt_yaml(path: Path) -> None:
    path.write_text("{not yaml", encoding="utf-8")


ENV_BACKEND = Backend(
    marker="env",
    name_of=_env_name,
    declare=lambda member, **kwargs: environment_variable_setting(name=_env_name(member), **kwargs),
    bind=lambda path: None,
    store=_store_env,
    serializer=EnvironmentVariablesSerializer,
    address=lambda member, path: f"environment variable '{_env_name(member)}'",
    source="the process environment",
)
DOTENV_BACKEND = Backend(
    marker="dotenv",
    name_of=_env_name,
    declare=lambda member, **kwargs: dotenv_setting(name=_env_name(member), **kwargs),
    bind=lambda path: dotenv_source(file=path),
    store=_store_dotenv,
    serializer=DotenvSerializer,
    address=lambda member, path: (
        f"environment variable '{_env_name(member)}' in the dotenv file {path}"
    ),
    source="the dotenv file",
)
JSON_BACKEND = Backend(
    marker="json",
    name_of=_plain_name,
    declare=lambda member, **kwargs: json_setting(name=_plain_name(member), **kwargs),
    bind=lambda path: json_source(file=path),
    store=_store_json,
    serializer=JSONSettingsSerializer,
    address=lambda member, path: f"key '{_plain_name(member)}' in the JSON file {path}",
    source="the JSON file",
    corrupt=_corrupt_json,
    corrupt_text="{not json",
)
TOML_BACKEND = Backend(
    marker="toml",
    name_of=_plain_name,
    declare=lambda member, **kwargs: toml_setting(name=_plain_name(member), **kwargs),
    bind=lambda path: toml_source(file=path),
    store=_store_toml,
    serializer=TOMLSettingsSerializer,
    address=lambda member, path: f"key '{_plain_name(member)}' in the TOML file {path}",
    source="the TOML file",
    corrupt=_corrupt_toml,
    corrupt_text="[not toml",
)
YAML_BACKEND = Backend(
    marker="yaml",
    name_of=_plain_name,
    declare=lambda member, **kwargs: yaml_setting(name=_plain_name(member), **kwargs),
    bind=lambda path: yaml_source(file=path),
    store=_store_yaml,
    serializer=YAMLSettingsSerializer,
    address=lambda member, path: f"key '{_plain_name(member)}' in the YAML file {path}",
    source="the YAML file",
    corrupt=_corrupt_yaml,
    corrupt_text="{not yaml",
)

BACKENDS = [ENV_BACKEND, DOTENV_BACKEND, JSON_BACKEND, TOML_BACKEND, YAML_BACKEND]
# the storages that live in a file (and can therefore be unreadable)
FILE_BACKENDS = [DOTENV_BACKEND, JSON_BACKEND, TOML_BACKEND, YAML_BACKEND]
# the storages whose corruption aborts a pass (a dotenv line python-dotenv
# cannot parse is skipped with a warning instead — the backend's own test)
CORRUPTIBLE_BACKENDS = [JSON_BACKEND, TOML_BACKEND, YAML_BACKEND]


def clear_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the matrix variables a leaking outer environment might hold."""
    for member in MEMBER_STATES:
        monkeypatch.delenv(_env_name(member), raising=False)


def make_class(
    backend: Backend,
    path: Path,
    states: Dict[str, Any] = MEMBER_STATES,
    name: str = CLASS_NAME,
) -> Type[Settings]:
    """The matrix class on one backend: one int member per declaration state."""
    namespace: Dict[str, Any] = {"__annotations__": {}}
    for member, default in states.items():
        namespace["__annotations__"][member] = int
        namespace[member] = backend.declare(member, default=default)
    options = backend.bind(path)
    if options is None:
        return type(name, (Settings,), namespace)
    return type(name, (Settings,), namespace, options=options)


def prepared(
    backend: Backend, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stored: Dict[str, Any]
) -> tuple:
    """The matrix class with its storage holding ``stored`` alone."""
    path = tmp_path / f"{backend.marker}.storage"
    clear_environment(monkeypatch)
    if stored:
        backend.store(monkeypatch, path, stored)
    return make_class(backend, path), path


def required_text(backend: Backend, path: Path, member: str, cause: str) -> str:
    where = f"{TERM} '{member}' ({backend.address(member, path)}) of '{CLASS_NAME}'"
    return f"{where} is required: {cause}"


def miss_text(backend: Backend, path: Path, member: str) -> str:
    where = f"{TERM} '{member}' ({backend.address(member, path)}) of '{CLASS_NAME}'"
    return f"{where}: {backend.source} provided no value"


def fallback_text(backend: Backend, path: Path, member: str, cause: str) -> str:
    where = f"{TERM} '{member}' ({backend.address(member, path)}) of '{CLASS_NAME}'"
    return f"{where} fell back to its default: {cause}"


def source_failure_record(
    backend: Backend, path: Path, member: str, cause: str, *, fallback: bool
) -> str:
    """Return the ERROR log record of the source failure of a member. It has the
    full fallback shape at the error level: the tail announces the fallback of
    an optional member, and it is absent for a required member.
    """
    where = f"{TERM} '{member}' ({backend.address(member, path)}) of '{CLASS_NAME}'"
    tail = "; using the default value" if fallback else ""
    return f"{where}: {cause}{tail}"


# ---------------------------------------------------------------------------
# The healthy baseline: every state present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_every_state_present_loads_cleanly(backend, monkeypatch, tmp_path, caplog):
    klass, path = prepared(backend, monkeypatch, tmp_path, GOOD_VALUES)

    with caplog.at_level(logging.WARNING, logger=CHANNEL):
        report = klass.load_settings()

    assert report == ()
    assert not caplog.records
    assert klass.answer == 11
    assert klass.plain == 22
    assert klass.known == 33
    assert klass.control == 44


# ---------------------------------------------------------------------------
# Missing values: the declaration states decide the channel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_missing_states_report_through_the_aggregate(backend, monkeypatch, tmp_path):
    klass, path = prepared(backend, monkeypatch, tmp_path, {CONTROL: 44})

    with pytest.raises(AggregateLoadError) as info:
        klass.load_settings()

    aggregate = info.value
    (terminal,) = aggregate.errors
    assert isinstance(terminal, MissingValueError)
    assert str(terminal) == required_text(
        backend, path, ANSWER, f"{backend.source} provided no value"
    )
    # the optional misses ride the abort: the reader of the failure sees
    # which members stood at their defaults
    assert [str(miss) for miss in aggregate.misses] == [
        miss_text(backend, path, PLAIN),
        miss_text(backend, path, KNOWN),
    ]
    message = str(aggregate)
    assert f"{CHANNEL} error: the load failed for 1 {AGGREGATE_NOUN}:" in message
    assert (
        f"2 optional {AGGREGATE_NOUN}s served their defaults "
        "(their sources provided no value):" in message
    )
    assert str(terminal) in message
    # the abort leaves the class as the call found it: nothing the failed
    # pass produced is applied, so an optional member reads its declared
    # default and a required one holds nothing
    assert klass.plain is None
    assert klass.known == DEFAULT_VALUE
    with pytest.raises(MemberLoadError, match="is required"):
        _ = klass.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = klass.answer


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_nothing_stored_reports_every_required_member(backend, monkeypatch, tmp_path):
    klass, path = prepared(backend, monkeypatch, tmp_path, {})

    with pytest.raises(AggregateLoadError) as info:
        klass.load_settings()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    assert f"the load failed for 2 {AGGREGATE_NOUN}s:" in str(info.value)
    assert str(info.value.errors[0]) == required_text(
        backend, path, ANSWER, f"{backend.source} provided no value"
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_values_under_addresses_the_library_does_not_read_are_misses(
    backend, monkeypatch, tmp_path, caplog
):
    # the storage is full, but under names the class never asks for: the
    # wrong prefix or case of an environment family name, a foreign key of
    # a file — the load sees the same emptiness either way
    klass, path = prepared(backend, monkeypatch, tmp_path, {})
    wrong = {f"typo_{member}": value for member, value in GOOD_VALUES.items()}
    backend.store(monkeypatch, path, wrong)

    with caplog.at_level(logging.DEBUG, logger=CHANNEL):
        with pytest.raises(AggregateLoadError) as info:
            klass.load_settings()

    # the failure names the address to provide, in the spelling the class
    # reads — the debugging seat for a name that does not match (both
    # required members miss: the storage holds nothing they answer to)
    terminal = info.value.errors[0]
    assert str(terminal) == required_text(
        backend, path, ANSWER, f"{backend.source} provided no value"
    )
    # the stored addresses nobody reads stay out of the report
    assert "typo_" not in str(info.value)
    assert backend.address(ANSWER, path) in str(info.value)
    debug = [record.getMessage() for record in caplog.records]
    assert any(
        backend.address(PLAIN, path) in entry and "; using the default value" in entry
        for entry in debug
    )
    assert klass.known == DEFAULT_VALUE


def test_an_env_name_the_pattern_does_not_build_is_a_miss(monkeypatch, caplog):
    monkeypatch.delenv("EMX_MODE", raising=False)
    monkeypatch.setenv("emx_mode", "debug")  # the wrong case
    monkeypatch.setenv("MODE", "debug")  # the missing prefix

    class PatternSettings(
        Settings,
        options=env_source(name_prefix="EMX_", name_case=NameCase.UPPER),
    ):
        mode: str = environment_variable_setting(default="production")

    with caplog.at_level(logging.DEBUG, logger=CHANNEL):
        report = PatternSettings.load_settings()

    assert PatternSettings.mode == "production"
    assert report == ()
    debug = [record.getMessage() for record in caplog.records]
    assert any(
        "environment variable 'EMX_MODE'" in entry and "; using the default value" in entry
        for entry in debug
    )


# ---------------------------------------------------------------------------
# Conversion failures: the value is there, the type is not
# ---------------------------------------------------------------------------

UNCONVERTIBLE = "cannot convert 'abc' to int (invalid literal for int() with base 10: 'abc')"


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_an_unconvertible_required_member_aborts(backend, monkeypatch, tmp_path):
    stored = dict(GOOD_VALUES)
    stored[ANSWER] = "abc"
    klass, path = prepared(backend, monkeypatch, tmp_path, stored)

    with pytest.raises(AggregateLoadError) as info:
        klass.load_settings()

    (terminal,) = info.value.errors
    assert isinstance(terminal, ConversionError)
    assert str(terminal) == required_text(backend, path, ANSWER, UNCONVERTIBLE)
    # the abort leaves the class as the call found it: the healthy members'
    # loaded values ride with the failed pass, nothing is applied
    assert klass.plain is None
    assert klass.known == DEFAULT_VALUE
    with pytest.raises(MemberLoadError, match="is required"):
        _ = klass.control


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_unconvertible_required_members_report_through_the_aggregate(
    backend, monkeypatch, tmp_path
):
    stored = dict(GOOD_VALUES)
    stored[ANSWER] = "abc"
    stored[CONTROL] = "abc"
    klass, path = prepared(backend, monkeypatch, tmp_path, stored)

    with pytest.raises(AggregateLoadError) as info:
        klass.load_settings()

    # every required member that cannot convert names its own error: one
    # abort carries both, in declaration order, and the healthy optional
    # members' values ride with the failed pass
    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        required_text(backend, path, ANSWER, UNCONVERTIBLE),
        required_text(backend, path, CONTROL, UNCONVERTIBLE),
    ]
    assert f"{CHANNEL} error: the load failed for 2 {AGGREGATE_NOUN}s:" in str(info.value)
    assert klass.plain is None
    assert klass.known == DEFAULT_VALUE
    with pytest.raises(MemberLoadError, match="is required"):
        _ = klass.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = klass.control


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_unconvertible_optional_members_fall_back_with_a_report(
    backend, monkeypatch, tmp_path, caplog
):
    stored = dict(GOOD_VALUES)
    stored[PLAIN] = "abc"
    stored[KNOWN] = "abc"
    klass, path = prepared(backend, monkeypatch, tmp_path, stored)

    with caplog.at_level(logging.WARNING, logger=CHANNEL):
        report = klass.load_settings()

    assert {type(entry) for entry in report} == {ConversionError}
    texts = [str(entry) for entry in report]
    assert fallback_text(backend, path, PLAIN, UNCONVERTIBLE) in texts
    assert fallback_text(backend, path, KNOWN, UNCONVERTIBLE) in texts
    warnings = [record.getMessage() for record in caplog.records]
    assert any(
        backend.address(PLAIN, path) in entry and "; using the default value" in entry
        for entry in warnings
    )
    assert any(
        backend.address(KNOWN, path) in entry and "; using the default value" in entry
        for entry in warnings
    )
    # no abort happened: the required members loaded, the optional stood at
    # their defaults
    assert klass.answer == 11
    assert klass.plain is None
    assert klass.known == DEFAULT_VALUE
    assert klass.control == 44


# ---------------------------------------------------------------------------
# A broken serializer: the source itself fails
# ---------------------------------------------------------------------------


def _exploding_load(self, setting_name: str, attr: Any) -> Any:
    raise RuntimeError("serializer exploded")


@pytest.mark.parametrize("backend", BACKENDS, ids=lambda backend: backend.marker)
def test_a_broken_serializer_keeps_the_log_and_continue_policy(
    backend, monkeypatch, tmp_path, caplog
):
    monkeypatch.setattr(backend.serializer, "load", _exploding_load)
    klass, path = prepared(backend, monkeypatch, tmp_path, {})

    with caplog.at_level(logging.WARNING, logger=CHANNEL):
        with pytest.raises(AggregateLoadError) as info:
            klass.load_settings()

    # the exception is logged per member in the full fallback shape: the
    # member's place (member, storage address, class) and the source that
    # raised, the tail announcing the fallback of an optional member
    cause = f"{backend.source} raised RuntimeError (serializer exploded)"
    errors_logged = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert source_failure_record(backend, path, ANSWER, cause, fallback=False) in errors_logged
    assert source_failure_record(backend, path, PLAIN, cause, fallback=True) in errors_logged
    # the required members collected their source errors, the optional
    # ones stood at their defaults with a report entry each
    assert len(info.value.errors) == 2
    terminal = info.value.errors[0]
    assert isinstance(terminal, SourceLoadError)
    assert str(terminal) == required_text(
        backend,
        path,
        ANSWER,
        f"{backend.source} raised RuntimeError (serializer exploded)",
    )
    assert isinstance(terminal.__cause__, RuntimeError)
    assert {str(entry) for entry in info.value.fallbacks} == {
        fallback_text(
            backend,
            path,
            PLAIN,
            f"{backend.source} raised RuntimeError (serializer exploded)",
        ),
        fallback_text(
            backend,
            path,
            KNOWN,
            f"{backend.source} raised RuntimeError (serializer exploded)",
        ),
    }
    assert klass.plain is None
    assert klass.known == DEFAULT_VALUE


# ---------------------------------------------------------------------------
# A broken storage: corrupt, unreadable, the wrong shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", CORRUPTIBLE_BACKENDS, ids=lambda backend: backend.marker)
def test_a_corrupt_storage_of_required_members_collects_source_errors(backend, tmp_path):
    path = tmp_path / f"{backend.marker}.storage"
    backend.break_storage(path)
    klass = make_class(backend, path, states=REQUIRED_ONLY_STATES)

    with pytest.raises(AggregateLoadError) as info:
        klass.load_settings()

    # every required member reports the failed source, the parser's own
    # words carried in the cause (the parser's detail is its own wording,
    # so the check stops at the prefix the library composes)
    assert len(info.value.errors) == 2
    terminal = info.value.errors[0]
    assert isinstance(terminal, SourceLoadError)
    assert str(terminal).startswith(
        required_text(backend, path, ANSWER, f"{backend.source} raised ValueError (")
    )
    assert "cannot parse the" in str(terminal)
    assert "cannot parse the" in str(terminal.__cause__)
    assert str(path) in str(terminal.__cause__)


@pytest.mark.parametrize("backend", CORRUPTIBLE_BACKENDS, ids=lambda backend: backend.marker)
def test_a_corrupt_storage_with_an_optional_member_reraises_as_is(backend, tmp_path):
    # a served default must not mask a corrupt file: on the first optional
    # member the parser's error leaves the pass unchanged, still naming
    # the file it cannot read
    path = tmp_path / f"{backend.marker}.storage"
    backend.break_storage(path)
    klass = make_class(backend, path)

    with pytest.raises(ValueError, match=f"cannot parse the {backend.marker.upper()}"):
        klass.load_settings()


@pytest.mark.parametrize("backend", FILE_BACKENDS, ids=lambda backend: backend.marker)
def test_an_unreadable_storage_collects_a_source_error(backend, tmp_path):
    directory = tmp_path / "storage-directory"
    directory.mkdir()
    klass = make_class(backend, directory, states=REQUIRED_ONLY_STATES)

    with pytest.raises(AggregateLoadError) as info:
        klass.load_settings()

    terminal = info.value.errors[0]
    assert isinstance(terminal, SourceLoadError)
    assert f"{backend.source} raised IsADirectoryError" in str(terminal)
    assert backend.address(ANSWER, directory) in str(terminal)
    assert isinstance(terminal.__cause__, OSError)


def test_a_json_array_at_the_top_level_is_refused(tmp_path):
    path = tmp_path / "array.json"
    path.write_text("[]", encoding="utf-8")

    klass = make_class(JSON_BACKEND, path)

    with pytest.raises(ValueError, match="must contain an object at the top level"):
        klass.load_settings()


def test_a_line_dotenv_cannot_parse_warns_and_misses(tmp_path, caplog):
    # the dotenv backend's own corrupt form: the line python-dotenv skips
    # is reported beside the file's path, the members it addressed miss,
    # and the pass itself does not abort over it
    path = tmp_path / "broken.env"
    path.write_text("??? no binding here\nEMX_CONTROL=44\n", encoding="utf-8")

    class DotenvBrokenSettings(
        Settings,
        options=dotenv_source(file=path),
    ):
        answer: int = dotenv_setting(name="EMX_ANSWER", default=REQUIRED)
        control: int = dotenv_setting(name="EMX_CONTROL", default=REQUIRED)

    with caplog.at_level(logging.WARNING, logger=CHANNEL):
        with pytest.raises(AggregateLoadError) as info:
            DotenvBrokenSettings.load_settings()

    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass — the class keeps the state it had
    with pytest.raises(MemberLoadError, match="is required"):
        _ = DotenvBrokenSettings.control
    (terminal,) = info.value.errors
    assert isinstance(terminal, MissingValueError)
    assert any(f"the dotenv file {path}:" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("backend", CORRUPTIBLE_BACKENDS, ids=lambda backend: backend.marker)
def test_saving_into_a_corrupt_file_aborts_the_save_pass(backend, tmp_path):
    path = tmp_path / f"{backend.marker}.storage"
    backend.break_storage(path)
    klass = make_class(backend, path, states={KNOWN: DEFAULT_VALUE})

    with pytest.raises(ValueError, match="cannot parse the"):
        klass.save_settings()

    # the pass wrote nothing over the file it could not read
    assert path.read_text(encoding="utf-8") == backend.corrupt_text


# ---------------------------------------------------------------------------
# Several sources in one class
# ---------------------------------------------------------------------------


def test_several_sources_report_each_in_its_own_words(monkeypatch, tmp_path):
    json_path = tmp_path / "multi.json"
    toml_path = tmp_path / "multi.toml"
    dotenv_path = tmp_path / "multi.env"
    monkeypatch.delenv("EMX_ENV_ANSWER", raising=False)
    monkeypatch.setenv("EMX_ENV_KNOWN", "abc")  # the env source: an unconvertible value
    # the JSON and dotenv sources stay empty; the TOML source holds its value
    toml_path.write_text("toml_control = 44\n", encoding="utf-8")

    class MultiSourceSettings(
        Settings,
        options=(
            json_source(file=json_path),
            toml_source(file=toml_path),
            dotenv_source(file=dotenv_path),
        ),
    ):
        env_answer: int = environment_variable_setting(name="EMX_ENV_ANSWER", default=REQUIRED)
        env_known: int = environment_variable_setting(name="EMX_ENV_KNOWN", default=7)
        json_plain: int = json_setting(name="json_plain", default=NO_DEFAULT)
        dotenv_extra: int = dotenv_setting(name="EMX_DOTENV_EXTRA", default=5)
        toml_control: int = toml_setting(name="toml_control", default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        MultiSourceSettings.load_settings()

    (terminal,) = info.value.errors
    assert str(terminal) == (
        f"{TERM} 'env_answer' (environment variable 'EMX_ENV_ANSWER') "
        f"of 'MultiSourceSettings' is required: the process environment "
        "provided no value"
    )
    (fallback,) = info.value.fallbacks
    assert "environment variable 'EMX_ENV_KNOWN'" in str(fallback) and UNCONVERTIBLE in str(
        fallback
    )
    misses = [str(miss) for miss in info.value.misses]
    assert any(f"key 'json_plain' in the JSON file {json_path}" in miss for miss in misses)
    assert any(
        f"environment variable 'EMX_DOTENV_EXTRA' in the dotenv file {dotenv_path}" in miss
        for miss in misses
    )
    # the abort leaves the class as the call found it: what every source
    # served rides with the failed pass, nothing is applied
    with pytest.raises(MemberLoadError, match="is required"):
        _ = MultiSourceSettings.toml_control
    assert MultiSourceSettings.json_plain is None
    assert MultiSourceSettings.env_known == 7
    assert MultiSourceSettings.dotenv_extra == 5


# ---------------------------------------------------------------------------
# Dynamic collections: the settings without a declaration
# ---------------------------------------------------------------------------

DYNAMIC_BACKENDS = [
    pytest.param(
        JSONDynamicSettingsPlugin,
        lambda path: json_source(file=path, dynamic_file=path),
        json_setting,
        "{not json",
        id="json-dynamic",
    ),
    pytest.param(
        TOMLDynamicSettingsPlugin,
        lambda path: toml_source(file=path, dynamic_file=path),
        toml_setting,
        "[not toml",
        id="toml-dynamic",
    ),
    pytest.param(
        YAMLDynamicSettingsPlugin,
        lambda path: yaml_source(file=path, dynamic_file=path),
        yaml_setting,
        "{not yaml",
        id="yaml-dynamic",
    ),
]


def make_dynamic_class(plugin_class, bind, member_factory, path):
    namespace: Dict[str, Any] = {
        "__annotations__": {"member": int},
        "member": member_factory(name="member", default=1),
    }
    return type(
        "ErrorMatrixDynamicSettings",
        (Settings,),
        namespace,
        options=bind(path),
    )


@pytest.mark.parametrize(
    "plugin_class,bind,member_factory,corrupt_text",
    DYNAMIC_BACKENDS,
)
def test_a_corrupt_storage_aborts_the_dynamic_rebuild(
    plugin_class, bind, member_factory, corrupt_text, tmp_path
):
    path = tmp_path / "dynamic.storage"
    path.write_text(corrupt_text, encoding="utf-8")
    klass = make_dynamic_class(plugin_class, bind, member_factory, path)
    plugin = klass.get_plugin(plugin_class)

    with pytest.raises(ValueError, match="cannot parse the"):
        plugin.load_settings()


@pytest.mark.parametrize(
    "plugin_class,bind,member_factory,corrupt_text",
    DYNAMIC_BACKENDS,
)
def test_dynamic_names_and_conversion_report_through_the_plugin(
    plugin_class, bind, member_factory, corrupt_text, tmp_path, caplog
):
    path = tmp_path / "dynamic.storage"
    klass = make_dynamic_class(plugin_class, bind, member_factory, path)
    plugin = klass.get_plugin(plugin_class)

    # a name the collection does not hold names itself
    with pytest.raises(KeyError, match="no dynamic setting 'missing'"):
        plugin.get_setting("missing")

    # a value the default's type cannot take warns and serves the default
    plugin.set_setting("flag", "abc")
    plugin.save_settings()
    plugin.load_settings()
    with caplog.at_level(logging.WARNING, logger=CHANNEL):
        value = plugin.get_setting("flag", default=7)
    assert value == 7
    assert any(
        "cannot convert the value of dynamic setting 'flag'" in record.getMessage()
        and "using the default value" in record.getMessage()
        for record in caplog.records
    )

    # saving a name the collection never took names the fix
    with pytest.raises(KeyError, match="has no value to save"):
        plugin.save_setting("ghost")


# ---------------------------------------------------------------------------
# The matrix's own coverage: a new plugin must join the table
# ---------------------------------------------------------------------------

# every module under the package's plugins, mapped to the matrix row that
# covers it — None marks a module that deliberately carries no attribute
# type of its own
KNOWN_PLUGIN_MODULES = {
    "environment.variables": "env",
    "environment.dotenv": "dotenv",
    "json_settings": "json",
    "toml_settings": "toml",
    "yaml_settings": "yaml",
    "json_dynamic_settings": "json-dynamic",
    "toml_dynamic_settings": "toml-dynamic",
    "yaml_dynamic_settings": "yaml-dynamic",
    "mapping_source": None,  # a storage with no attribute type of its own
}
# the paid editions' own plugin rows arrive from the private add-on
KNOWN_PLUGIN_MODULES.update(PRIVATE_PLUGIN_MODULES)


def _plugin_modules():
    # a plugin sits on the top level of plugins/, or one level deeper under
    # a grouping package (the environment family); the modules beside a
    # plugin are its implementation, not plugins of their own
    names = []
    for _, name, ispkg in pkgutil.iter_modules(settings_plugins.__path__):
        if not ispkg:
            names.append(name)
            continue
        package = importlib.import_module(f"advexp.settings.plugins.{name}")
        sub_packages = [
            sub_name
            for _, sub_name, sub_ispkg in pkgutil.iter_modules(package.__path__)
            if sub_ispkg
        ]
        if sub_packages:
            names.extend(f"{name}.{sub_name}" for sub_name in sub_packages)
        else:
            names.append(name)
    return names


def test_every_bundled_attribute_type_joins_the_matrix():
    found = _plugin_modules()
    assert set(found) == set(KNOWN_PLUGIN_MODULES), (
        "a plugin module appeared or disappeared under advexp.settings.plugins: "
        "give its attribute type a Backend row in BACKENDS (or a pair in "
        "DYNAMIC_BACKENDS) and update KNOWN_PLUGIN_MODULES of this suite"
    )
    covered = {backend.marker for backend in BACKENDS} | {param.id for param in DYNAMIC_BACKENDS}
    assert covered == {marker for marker in KNOWN_PLUGIN_MODULES.values() if marker is not None}
