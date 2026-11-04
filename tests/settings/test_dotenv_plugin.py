"""Dotenv plugin tests (file backend through tmp_path)."""

from __future__ import annotations

import dataclasses
import logging
import stat
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import pytest

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugins.environment import NameCase
from advexp.settings.plugins.environment.dotenv import (
    DOTENV_FILE_METADATA,
    DotenvConfiguration,
    DotenvPlugin,
    DotenvSetting,
    dotenv_setting,
    dotenv_source,
)
from advexp.settings.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.settings.plugins.environment.variables import env_source
from advexp.settings_base.sources import DOTENV_SOURCE_METADATA

# read before any fixture patches the class: the stock module default is
# the ecosystem's conventional file name
_STOCK_FILE_PATH = DotenvConfiguration.file_path


class FileSettings(Settings):
    # Optional[str]: this storage has no null form, so None (unset) is a
    # regular value of the member
    text: Optional[str] = dotenv_setting(name="TEST_ASD_TEXT", default="default-text")
    flag: bool = dotenv_setting(name="TEST_ASD_FLAG", default=False)
    count: int = dotenv_setting(name="TEST_ASD_COUNT", default=0)
    when: Optional[datetime] = dotenv_setting(name="TEST_ASD_WHEN", default=None)
    plain: str = dotenv_setting()  # falls back to the member name


@dataclasses.dataclass
class Proxy:
    host: str
    port: int = 3128


class ProxySettings(Settings):
    proxy: Optional[Proxy] = dotenv_setting(name="TEST_ASD_PROXY", default=None)


@dataclasses.dataclass
class Health:
    enabled: bool = True
    timeout: float = 5.0


@dataclasses.dataclass
class Pool:
    size: int = 10
    health: Health = dataclasses.field(default_factory=Health)


@dataclasses.dataclass
class Db:
    host: str = "localhost"
    port: int = 5432
    pool: Pool = dataclasses.field(default_factory=Pool)


class NestedSettings(
    Settings,
    options=env_source(
        name_prefix="TEST_ASD_",
        name_case=NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    db: Db = dotenv_setting(default=Db(host="declared-host"))


class WorkerSettings(
    Settings,
    options=env_source(name_prefix="TEST_ASD_WORKER_", name_case=NameCase.UPPER),
):
    mode: str = dotenv_setting(default="standby")  # TEST_ASD_WORKER_MODE
    legacy: str = dotenv_setting(name="legacy_flag", default="off")  # explicit name=


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.env"
    monkeypatch.setattr(DotenvConfiguration, "file_path", path)
    yield path


@pytest.fixture(autouse=True)
def reset_values():
    # settings classes keep values in class storage; start each test clean
    FileSettings.reset_settings()
    ProxySettings.reset_settings()
    NestedSettings.reset_settings()
    WorkerSettings.reset_settings()
    AnyCaseFileSettings.reset_settings()
    yield


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(DotenvSetting) is not None
    # the base attribute class itself stays unregistered
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None


def test_load_missing_file_applies_defaults(configured_file):
    FileSettings.load_settings()
    assert FileSettings.text == "default-text"
    assert FileSettings.flag is False
    assert FileSettings.count == 0
    assert FileSettings.when is None


def test_missing_file_names_itself_at_debug(configured_file, caplog):
    # the miss phrase of the pass cannot tell an absent file from a
    # variable the file does not carry: this record is what separates
    # the two for a reader debugging an empty load
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        FileSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the dotenv file {configured_file} does not exist, treating it as empty" in messages


def test_variableless_file_names_itself_at_debug(configured_file, caplog):
    # a file the save pass left empty — or one of comments alone — is its
    # own case, apart from an absent file: its record says the file is
    # there and holds no variables, and the absent-file record stays out
    configured_file.write_text("# only a comment\n", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        FileSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the dotenv file {configured_file} contains no variables" in messages
    assert not any("does not exist" in message for message in messages)


def test_unparsable_line_warns_in_the_family_channel(configured_file, caplog):
    # python-dotenv skips a line it cannot parse and warns into its own
    # channel; the load hands the warning over, and it lands beside the
    # file's path in the family's channel — not as a stray foreign record
    configured_file.write_text("TEST_ASD_COUNT and no assignment\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        FileSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert (
        f"the dotenv file {configured_file}: "
        "python-dotenv could not parse statement starting at line 1" in messages
    )
    # the takeover closes the foreign channel's propagation: the warning
    # is not printed twice
    assert not [r for r in caplog.records if r.name == "dotenv.main"]
    # the broken line is not an empty file: the variableless record stays out
    assert not any("contains no variables" in message for message in messages)


def test_unparsable_line_leaves_the_rest_readable(configured_file, caplog):
    # a broken line costs its own variable alone: the lines around it
    # parse and serve their members
    configured_file.write_text(
        "TEST_ASD_COUNT=42\nTEST_ASD_TEXT and no assignment\n", encoding="utf-8"
    )
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        FileSettings.load_settings()
    assert FileSettings.count == 42
    assert FileSettings.text == "default-text"
    assert any(
        "python-dotenv could not parse statement starting at line 2" in r.getMessage()
        for r in caplog.records
    )


def test_load_string_value(configured_file):
    configured_file.write_text("TEST_ASD_TEXT=from-file\n", encoding="utf-8")
    FileSettings.load_settings()
    assert FileSettings.text == "from-file"


def test_load_converts_bool_int_and_datetime(configured_file):
    configured_file.write_text(
        "TEST_ASD_FLAG=True\nTEST_ASD_COUNT=42\nTEST_ASD_WHEN=2026-09-03T10:15:30\n",
        encoding="utf-8",
    )
    FileSettings.load_settings()
    assert FileSettings.flag is True
    assert FileSettings.count == 42
    assert FileSettings.when == datetime(2026, 9, 3, 10, 15, 30)


def test_unconvertible_value_falls_back_to_default(configured_file):
    configured_file.write_text("TEST_ASD_COUNT=not-a-number\n", encoding="utf-8")
    FileSettings.load_settings()
    assert FileSettings.count == 0


def test_save_writes_file(configured_file):
    FileSettings.flag = True
    FileSettings.count = 7
    FileSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "TEST_ASD_FLAG='True'" in text
    assert "TEST_ASD_COUNT='7'" in text


def test_save_none_unsets_variable(configured_file):
    # this storage has no null form: None and absence coincide
    configured_file.write_text("TEST_ASD_TEXT=stale\n", encoding="utf-8")
    FileSettings.text = None
    FileSettings.save_setting("text")
    assert "TEST_ASD_TEXT" not in configured_file.read_text(encoding="utf-8")


def test_save_creates_missing_file(configured_file):
    FileSettings.count = 3
    FileSettings.save_settings()
    assert configured_file.exists()
    assert "TEST_ASD_COUNT='3'" in configured_file.read_text(encoding="utf-8")


def test_save_without_storable_values_creates_an_empty_file_and_warns(configured_file, caplog):
    # a member without a default resolves to None, and None is no line in
    # this storage: the save pass leaves an empty file marking the place
    # and a warning naming the reason — the reader expecting a file gets
    # both, not silence. The empty-file debug records stay a reading
    # pass's voice: a save tells its own story, and the file it did not
    # find is not news beside the warning about it
    class BareSettings(Settings):
        token: Optional[str] = dotenv_setting(name="TEST_ASD_BARE")

    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        BareSettings.save_settings()
    assert configured_file.exists()
    assert configured_file.read_text(encoding="utf-8") == ""
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        f"the save pass wrote no variables to the dotenv file {configured_file}" in message
        for message in messages
    )
    assert not any("does not exist" in message for message in messages)
    assert not any("contains no variables" in message for message in messages)


def test_save_without_storable_values_keeps_an_existing_file_as_written(configured_file, caplog):
    # the empty pass creates nothing over a file that is already there:
    # its comments and blank lines are lines the library does not know,
    # and they stay exactly as written
    class BareSettings(Settings):
        token: Optional[str] = dotenv_setting(name="TEST_ASD_BARE")

    configured_file.write_text("# deployed by hand\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        BareSettings.save_settings()
    assert configured_file.read_text(encoding="utf-8") == "# deployed by hand\n"
    assert any(
        "wrote no variables to the dotenv file" in record.getMessage() for record in caplog.records
    )


def test_save_with_storable_values_stays_quiet(configured_file, caplog):
    # a pass that writes its values is the normal outcome: no warning —
    # and no reading-pass records either, for the file it creates and
    # fills is the whole story
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        FileSettings.save_settings()
    assert configured_file.exists()
    messages = [record.getMessage() for record in caplog.records]
    assert not any("wrote no variables" in message for message in messages)
    assert not any("does not exist" in message for message in messages)


def test_save_removing_the_last_line_stays_quiet(configured_file, caplog):
    # None over an existing line removes it: the pass has real work — the
    # line leaves the file — and a warning would misread that as silence
    class OneTextSettings(Settings):
        text: Optional[str] = dotenv_setting(name="TEST_ASD_TEXT", default=None)

    configured_file.write_text("TEST_ASD_TEXT=stale\n", encoding="utf-8")
    OneTextSettings.load_settings()
    OneTextSettings.text = None
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        OneTextSettings.save_settings()
    assert "TEST_ASD_TEXT" not in configured_file.read_text(encoding="utf-8")
    assert not [r for r in caplog.records if "wrote no variables" in r.getMessage()]


def test_save_keeps_foreign_lines_as_written(configured_file):
    # comments and variables no member claims stay exactly as written
    configured_file.write_text(
        "# deployed by hand\nexport OTHER_TOOL=13\n\nTEST_ASD_COUNT=5  # inline\n",
        encoding="utf-8",
    )
    FileSettings.flag = True
    FileSettings.save_setting("flag")  # one member saved: only its line moves
    text = configured_file.read_text(encoding="utf-8")
    assert "TEST_ASD_FLAG='True'" in text
    assert "# deployed by hand" in text
    assert "export OTHER_TOOL=13" in text
    assert "TEST_ASD_COUNT=5  # inline" in text  # untouched: its value did not move


def test_save_rewrites_a_line_in_the_editors_own_spelling(configured_file):
    # the replaced line carries python-dotenv's spelling: the value in
    # single quotes, the key without an export prefix — even where the
    # old line had one
    configured_file.write_text("export TEST_ASD_TEXT=stale\n", encoding="utf-8")
    FileSettings.load_settings()
    FileSettings.text = "fresh"
    FileSettings.save_setting("text")
    assert configured_file.read_text(encoding="utf-8") == "TEST_ASD_TEXT='fresh'\n"


def test_save_keeps_the_files_crlf(configured_file):
    # the line editor writes LF; a CRLF file gets its endings restored
    # after the edit — the foreign line included
    configured_file.write_bytes(b"# comment\r\nTEST_ASD_TEXT=stale\r\nOTHER=keep\r\n")
    FileSettings.load_settings()
    FileSettings.text = "fresh"
    FileSettings.save_setting("text")
    assert configured_file.read_bytes() == b"# comment\r\nTEST_ASD_TEXT='fresh'\r\nOTHER=keep\r\n"


def test_save_keeps_the_files_permission_mode(configured_file):
    # python-dotenv's own editor preserves the mode through its rewrites;
    # the restore pass above must not lose it either
    configured_file.write_text("TEST_ASD_TEXT=stale\n", encoding="utf-8")
    configured_file.chmod(0o600)
    FileSettings.load_settings()
    FileSettings.text = "fresh"
    FileSettings.save_setting("text")
    assert stat.S_IMODE(configured_file.stat().st_mode) == 0o600


def test_member_name_fallback(configured_file):
    configured_file.write_text("plain=plain-value\n", encoding="utf-8")
    FileSettings.load_settings()
    assert FileSettings.plain == "plain-value"


def test_contains_setting(configured_file):
    assert FileSettings.contains_setting("text") is False
    configured_file.write_text("TEST_ASD_TEXT=here\n", encoding="utf-8")
    assert FileSettings.contains_setting("text") is True


def test_delete_setting(configured_file):
    configured_file.write_text("TEST_ASD_TEXT=value\n", encoding="utf-8")
    FileSettings.load_settings()
    assert FileSettings.text == "value"

    FileSettings.delete_setting("text")
    assert "TEST_ASD_TEXT" not in configured_file.read_text(encoding="utf-8")
    assert FileSettings.text == "default-text"  # reset to default


def test_round_trip_save_then_load(configured_file):
    FileSettings.flag = True
    FileSettings.count = 99
    FileSettings.text = "saved"
    FileSettings.save_settings()

    FileSettings.reset_settings()
    assert FileSettings.flag is False

    FileSettings.load_settings()
    assert FileSettings.flag is True
    assert FileSettings.count == 99
    assert FileSettings.text == "saved"


def test_the_class_anchors_one_file_until_reconfigured(tmp_path, monkeypatch):
    # the class's first access anchors the file for its whole life: the
    # passes — reads, diagnostics, writes — stay with one file even when
    # the working directory moves; the plugin's file_path parameter reanchors,
    # the next access resolving the new spelling against the working
    # directory of that moment
    home = tmp_path / "home"
    away = tmp_path / "away"
    home.mkdir()
    away.mkdir()
    monkeypatch.chdir(home)

    class AnchoredSettings(
        Settings,
        options=dotenv_source(file=Path("app.env")),
    ):
        token: str = dotenv_setting(default="")

    serializer = DotenvSerializer()
    serializer.set_serializer_params(AnchoredSettings.__settings_context__)
    # the designation reports the pair: the phrase and the exact file
    assert serializer.describe_source(None) == ("the dotenv file", str(home / "app.env"))

    monkeypatch.chdir(away)
    fresh = DotenvSerializer()
    fresh.set_serializer_params(AnchoredSettings.__settings_context__)
    assert fresh.describe_source(None) == ("the dotenv file", str(home / "app.env"))

    AnchoredSettings.get_plugin(DotenvPlugin).file_path = Path("other.env")
    assert fresh.describe_source(None) == ("the dotenv file", str(away / "other.env"))


def test_a_source_without_a_file_reads_the_module_default(configured_file):
    # a builder called without a file keeps the class on the module
    # default, the promise of dotenv_source's docstring; the naming
    # entry the same call declares must not break the resolution
    configured_file.write_text("PORT=9090\n")

    class SeatedSettings(
        Settings,
        options=dotenv_source(name_case=NameCase.UPPER),
    ):
        port: int = dotenv_setting(default=80)

    SeatedSettings.load_settings()
    assert SeatedSettings.port == 9090


def test_interpolation_expands_variables(configured_file, monkeypatch):
    # python-dotenv's own semantics ride along: ${...} expands from the
    # process environment and the file's own earlier variables
    monkeypatch.setenv("TEST_ASD_ROOT", "root-value")
    configured_file.write_text("TEST_ASD_TEXT=${TEST_ASD_ROOT}/sub\n", encoding="utf-8")
    FileSettings.load_settings()
    assert FileSettings.text == "root-value/sub"


def test_dataclass_round_trip_through_file(configured_file):
    ProxySettings.reset_settings()
    ProxySettings.proxy = Proxy("proxy.example", 8080)
    ProxySettings.save_settings()
    # a dataclass is one JSON-encoded variable
    assert 'TEST_ASD_PROXY=\'{"host":"proxy.example","port":8080}\'' in (
        configured_file.read_text(encoding="utf-8")
    )

    ProxySettings.reset_settings()
    assert ProxySettings.proxy is None
    ProxySettings.load_settings()
    assert ProxySettings.proxy == Proxy("proxy.example", 8080)
    assert isinstance(ProxySettings.proxy, Proxy)

    # an externally written variable parses the same way; a field default
    # fills the gap
    configured_file.write_text('TEST_ASD_PROXY={"host": "other.example"}\n', encoding="utf-8")
    ProxySettings.load_settings()
    assert ProxySettings.proxy == Proxy("other.example", 3128)


def test_single_setting_save_and_load(configured_file):
    configured_file.write_text("TEST_ASD_TEXT=old\n", encoding="utf-8")
    FileSettings.text = "new"
    FileSettings.save_setting("text")
    FileSettings.text = "ignored"
    FileSettings.load_setting("text")
    assert FileSettings.text == "new"


def test_naming_options_prefix_and_case(configured_file):
    configured_file.write_text("TEST_ASD_WORKER_MODE=running\n", encoding="utf-8")
    WorkerSettings.load_settings()
    assert WorkerSettings.mode == "running"
    WorkerSettings.mode = "idle"
    WorkerSettings.save_settings()
    assert "TEST_ASD_WORKER_MODE='idle'" in configured_file.read_text(encoding="utf-8")
    # an explicit name= is the full address: the prefix never touches it
    assert WorkerSettings.legacy == "off"


def test_nested_partial_update_and_field_save(configured_file):
    configured_file.write_text(
        "TEST_ASD_DB__PORT=6543\nTEST_ASD_DB__POOL__HEALTH__TIMEOUT=2.5\n",
        encoding="utf-8",
    )
    NestedSettings.load_settings()
    assert NestedSettings.db == Db(
        host="declared-host", port=6543, pool=Pool(health=Health(timeout=2.5))
    )

    NestedSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    # each leaf field lands in its own variable, the whole-object forms go;
    # a line whose value did not move keeps its original spelling
    assert "TEST_ASD_DB__HOST='declared-host'" in text
    assert "TEST_ASD_DB__PORT=6543\n" in text
    assert "TEST_ASD_DB__POOL__SIZE='10'" in text
    assert "TEST_ASD_DB__POOL__HEALTH__ENABLED='True'" in text
    assert "TEST_ASD_DB__POOL__HEALTH__TIMEOUT=2.5\n" in text


def test_nested_whole_object_form(configured_file):
    configured_file.write_text(
        'TEST_ASD_DB={"host": "json-host", "port": 1}\n',
        encoding="utf-8",
    )
    NestedSettings.load_settings()
    assert NestedSettings.db == Db(host="json-host", port=1, pool=Pool())


def test_nested_delete_drops_the_whole_subtree(configured_file):
    NestedSettings.save_settings()
    assert "TEST_ASD_DB__HOST" in configured_file.read_text(encoding="utf-8")

    NestedSettings.delete_settings()
    assert configured_file.read_text(encoding="utf-8") == ""


def test_class_file_binding_wins_over_module_default(tmp_path, configured_file):
    own = tmp_path / "own.env"
    own.write_text("TEST_ASD_TEXT=from-own\n", encoding="utf-8")
    configured_file.write_text("TEST_ASD_TEXT=from-module-default\n", encoding="utf-8")

    class BoundSettings(
        Settings,
        options=dotenv_source(file=own),
    ):
        text: str = dotenv_setting(name="TEST_ASD_TEXT", default="")

    # the plugin property reads the declared binding, chain-resolved
    assert BoundSettings.get_plugin(DotenvPlugin).file_path == own

    BoundSettings.load_settings()
    assert BoundSettings.text == "from-own"
    # the module default file stays untouched by the bound class
    assert "TEST_ASD_TEXT" in configured_file.read_text(encoding="utf-8")

    # the plugin property is the imperative spelling of the same binding:
    # assigning re-aims the class, and it lands in the same metadata entry
    BoundSettings.get_plugin(DotenvPlugin).file_path = configured_file
    assert BoundSettings.get_plugin(DotenvPlugin).file_path == configured_file
    BoundSettings.load_settings()
    assert BoundSettings.text == "from-module-default"

    # the seat's flat key addresses the same entry at runtime
    BoundSettings.set_class_metadata(
        DOTENV_SOURCE_METADATA, dotenv_source(file=own)[DOTENV_SOURCE_METADATA]
    )
    BoundSettings.load_settings()
    assert BoundSettings.text == "from-own"

    # removing the entry falls back to the module default
    assert BoundSettings.delete_class_metadata(DOTENV_SOURCE_METADATA) is True
    assert BoundSettings.get_plugin(DotenvPlugin).file_path is None
    BoundSettings.load_settings()
    assert BoundSettings.text == "from-module-default"


def test_binding_inherited_by_subclass(tmp_path, configured_file):
    own = tmp_path / "inherited.env"

    class Base(
        Settings,
        options=dotenv_source(file=own),
    ):
        text: str = dotenv_setting(name="TEST_ASD_TEXT", default="")

    class Child(Base):
        pass

    Child.text = "written-by-child"
    Child.save_settings()
    assert "TEST_ASD_TEXT='written-by-child'" in own.read_text(encoding="utf-8")


def test_subclass_own_binding_wins_and_base_keeps_its_file(tmp_path, configured_file):
    base_file = tmp_path / "base.env"
    child_file = tmp_path / "child.env"
    base_file.write_text("TEST_ASD_TEXT=from-base\n", encoding="utf-8")
    child_file.write_text("TEST_ASD_TEXT=from-child\n", encoding="utf-8")

    class Base(
        Settings,
        options=dotenv_source(file=base_file),
    ):
        text: str = dotenv_setting(name="TEST_ASD_TEXT", default="")

    class Child(
        Base,
        options=dotenv_source(file=child_file),
    ):
        pass

    Child.load_settings()
    assert Child.text == "from-child"
    # the base class keeps reading its own file
    Base.load_settings()
    assert Base.text == "from-base"


def test_invalid_binding_fails_class_statement():
    with pytest.raises(TypeError, match=f"{DOTENV_FILE_METADATA}.*must be a file path"):

        class Broken(
            Settings,
            options={DOTENV_FILE_METADATA: 42},
        ):
            text: str = dotenv_setting(default="")


def test_invalid_path_fails_at_helper_call():
    with pytest.raises(TypeError, match="invalid dotenv source file"):
        dotenv_source(file="")


def test_invalid_path_fails_at_property_assignment():
    # the property setter is the same validated channel; nothing is stored
    with pytest.raises(TypeError, match="invalid dotenv source file"):
        FileSettings.get_plugin(DotenvPlugin).file_path = 42
    assert FileSettings.get_plugin(DotenvPlugin).file_path is None


def test_default_module_path_is_the_conventional_file():
    assert _STOCK_FILE_PATH == ".env"


def test_undecodable_file_fails_the_load(configured_file):
    # a file that is not text must reach the caller, not silently serve
    # the defaults
    configured_file.write_bytes(b"TEST_ASD_TEXT=\xff\xfe\n")
    with pytest.raises(UnicodeDecodeError):
        FileSettings.load_settings()


def test_broken_storage_path_reaches_caller(tmp_path, monkeypatch):
    # a regular file sitting where the settings directory belongs breaks
    # every storage step; the error must reach the caller, not end up in the log
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    monkeypatch.setattr(DotenvConfiguration, "file_path", blocker / "settings.env")

    with pytest.raises(OSError):
        FileSettings.save_settings()


def test_get_plugin_bound_to_class():
    plugin = FileSettings.get_plugin(DotenvPlugin)
    assert plugin.plugin_name == "Dotenv"
    assert plugin.context.settings_class is FileSettings


def test_dotenv_module_is_self_sufficient(tmp_path):
    """The backend's own module carries the naming options beside its factory."""
    script = textwrap.dedent(
        """
        import os
        import sys

        import advexp.settings.plugins.environment.dotenv as dotenv
        from advexp.settings import Settings

        os.chdir(r"{workdir}")


        class SelfSufficientSettings(
            Settings,
            options=dotenv.dotenv_source(file="self-sufficient.env"),
        ):
            # PORT, built by the imported options' default naming
            port: int = dotenv.dotenv_setting(name="PORT", default=8080)

            # timeout, the member name as the file key
            timeout: int = dotenv.dotenv_setting(default=30)


        SelfSufficientSettings.load_settings()
        assert SelfSufficientSettings.port == 8080
        assert SelfSufficientSettings.timeout == 30
        assert dotenv.NameCase is not None and dotenv.dotenv_source is not None

        # the backend came in alone: the variables sibling never loaded
        assert not any("environment.variables" in name for name in sys.modules)
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# aliases: several addresses of one member, first found wins
# ---------------------------------------------------------------------------


class AliasFileSettings(Settings):
    ttl: str = dotenv_setting(
        name="TEST_ASD_PRIMARY",
        aliases=["TEST_ASD_FIRST", "TEST_ASD_SECOND"],
        default="default-ttl",
    )


@pytest.fixture
def alias_file(configured_file: Path) -> Path:
    AliasFileSettings.reset_settings()
    return configured_file


def test_alias_loads_when_primary_is_missing(alias_file: Path):
    alias_file.write_text("TEST_ASD_SECOND=from-old-name\n", encoding="utf-8")
    AliasFileSettings.load_settings()
    assert AliasFileSettings.ttl == "from-old-name"


def test_alias_order_primary_then_declaration_order(alias_file: Path):
    alias_file.write_text("TEST_ASD_SECOND=second\n", encoding="utf-8")
    AliasFileSettings.load_settings()
    assert AliasFileSettings.ttl == "second"  # the last alias serves alone

    alias_file.write_text("TEST_ASD_FIRST=first\nTEST_ASD_SECOND=second\n", encoding="utf-8")
    AliasFileSettings.load_settings()
    assert AliasFileSettings.ttl == "first"

    alias_file.write_text("TEST_ASD_PRIMARY=primary\nTEST_ASD_SECOND=second\n", encoding="utf-8")
    AliasFileSettings.load_settings()
    assert AliasFileSettings.ttl == "primary"


def test_alias_save_writes_the_primary_line_alone(alias_file: Path):
    alias_file.write_text("TEST_ASD_SECOND=old-value\n", encoding="utf-8")
    AliasFileSettings.load_settings()

    AliasFileSettings.ttl = "saved"
    AliasFileSettings.save_settings()
    text = alias_file.read_text(encoding="utf-8")
    assert "TEST_ASD_PRIMARY='saved'" in text
    assert "TEST_ASD_SECOND=old-value" in text  # aliases are read addresses


def test_alias_delete_removes_every_line(alias_file: Path):
    alias_file.write_text(
        "TEST_ASD_PRIMARY=primary\nTEST_ASD_FIRST=first\nTEST_ASD_SECOND=second\n",
        encoding="utf-8",
    )
    AliasFileSettings.load_settings()

    AliasFileSettings.delete_setting("ttl")
    text = alias_file.read_text(encoding="utf-8")
    # an alias left behind would resurrect the value at the next load
    assert "TEST_ASD_" not in text


# -- name_case=NameCase.ANY in the dotenv file ------------------------------


class AnyCaseFileSettings(
    Settings,
    options=env_source(name_case=NameCase.ANY),
):
    mode: str = dotenv_setting(default="production")
    legacy: str = dotenv_setting(name="legacy_flag", default="off")


@pytest.mark.parametrize("spelling", ["MODE", "Mode"])
def test_any_loads_any_spelling_from_the_file(configured_file, spelling):
    configured_file.write_text(f"{spelling}=from-file\n", encoding="utf-8")
    AnyCaseFileSettings.load_settings()
    assert AnyCaseFileSettings.mode == "from-file"


def test_any_loads_any_spelling_of_an_explicit_name_from_the_file(configured_file):
    configured_file.write_text("LEGACY_FLAG=on\n", encoding="utf-8")
    AnyCaseFileSettings.load_settings()
    assert AnyCaseFileSettings.legacy == "on"


def test_any_exact_spelling_in_the_file_wins(configured_file):
    configured_file.write_text("mode=exact\nMODE=folded\n", encoding="utf-8")
    AnyCaseFileSettings.load_settings()
    assert AnyCaseFileSettings.mode == "exact"


def test_any_two_folded_spellings_in_the_file_fail_the_load(configured_file):
    configured_file.write_text("MODE=one\nMode=two\n", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match=f"the dotenv file '{configured_file}' holds two differently-cased "
        "spellings of the environment variable \\('MODE' and 'Mode'\\)",
    ):
        AnyCaseFileSettings.load_settings()


def test_any_save_touches_the_found_spelling_in_the_file(configured_file):
    configured_file.write_text("MODE=stale\n", encoding="utf-8")
    AnyCaseFileSettings.load_settings()

    AnyCaseFileSettings.mode = "staging"
    AnyCaseFileSettings.save_settings()

    text = configured_file.read_text(encoding="utf-8")
    assert "MODE='staging'" in text
    assert "mode=" not in text


# -- name_case=NameCase.LOWER in the dotenv file -----------------------------


class LowerCaseFileSettings(
    Settings,
    options=env_source(name_case=NameCase.LOWER),
):
    Mode: str = dotenv_setting(default="production")


def test_lower_case_reads_the_recast_name_from_the_file(configured_file):
    configured_file.write_text("mode=lowered\n", encoding="utf-8")
    LowerCaseFileSettings.load_settings()
    assert LowerCaseFileSettings.Mode == "lowered"
