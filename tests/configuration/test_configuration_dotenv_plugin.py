"""Dotenv source tests (file source through tmp_path)."""

from __future__ import annotations

import dataclasses
import logging
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest

from advexp.configuration import AggregateLoadError, Configuration, LibraryConfiguration, Sources
from advexp.configuration.plugins.environment.dotenv import (
    DotenvPlugin,
    DotenvSetting,
    dotenv_setting,
    dotenv_source,
)
from advexp.configuration.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.settings_base.loading import member_where
from advexp.settings_base.name_case import NameCase
from advexp.settings_base.sources import SOURCE_CHAIN_METADATA

CONFIGURED_NAME = "configuration.env"
"""The declared link's file: the fixture retargets it to its own tmp path."""


def _retarget(path: Path) -> None:
    for klass in (
        FileConfiguration,
        ProxyConfiguration,
        AliasFileConfiguration,
        AnyCaseFileConfiguration,
        LowerCaseFileConfiguration,
        NestedConfiguration,
    ):
        klass.__settings_context__.set_class_metadata(
            SOURCE_CHAIN_METADATA, Sources(_link_for(klass, path))
        )


def _link_for(klass: type, path: Path) -> Any:
    """Return the rebuilt link of the class. The naming that each class declared is
    kept.
    """
    if klass is AnyCaseFileConfiguration:
        return dotenv_source(file=path, name_case=NameCase.ANY)
    if klass is LowerCaseFileConfiguration:
        return dotenv_source(file=path, name_case=NameCase.LOWER)
    if klass is NestedConfiguration:
        return dotenv_source(
            file=path,
            name_prefix="TEST_ACD_",
            name_case=NameCase.UPPER,
            nested_delimiter="__",
        )
    return dotenv_source(file=path)


class FileConfiguration(
    Configuration,
    options=dotenv_source(file=CONFIGURED_NAME),
):
    # Optional[str]: this source has no null form, so None (unset) is a
    # regular value of the member
    text: Optional[str] = dotenv_setting(name="TEST_ACD_TEXT", default="default-text")
    flag: bool = dotenv_setting(name="TEST_ACD_FLAG", default=False)
    count: int = dotenv_setting(name="TEST_ACD_COUNT", default=0)
    when: Optional[datetime] = dotenv_setting(name="TEST_ACD_WHEN", default=None)
    plain: str = dotenv_setting(default="plain-default")  # name = member name


@dataclasses.dataclass
class Proxy:
    host: str
    port: int = 3128


class ProxyConfiguration(
    Configuration,
    options=dotenv_source(file=CONFIGURED_NAME),
):
    proxy: Optional[Proxy] = dotenv_setting(name="TEST_ACD_PROXY", default=None)


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


class NestedConfiguration(
    Configuration,
    options=dotenv_source(
        file=CONFIGURED_NAME,
        name_prefix="TEST_ACD_",
        name_case=NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    conn: Db = dotenv_setting(default=Db(host="declared-host"))


class RequiredNestedConfiguration(NestedConfiguration):
    reader: Db = dotenv_setting()  # required: assembled by fields


@pytest.fixture(autouse=True)
def configured_file(tmp_path) -> Iterator[Path]:
    path = tmp_path / "configuration.env"
    _retarget(path)
    yield path


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(DotenvSetting) is not None
    # the base attribute class itself stays unregistered
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None


def test_load_missing_file_applies_defaults(configured_file):
    FileConfiguration.load_configuration()
    assert FileConfiguration.text == "default-text"
    assert FileConfiguration.flag is False
    assert FileConfiguration.count == 0
    assert FileConfiguration.when is None
    assert FileConfiguration.plain == "plain-default"


def test_missing_file_names_itself_at_debug(configured_file, caplog):
    # the miss phrase of the pass cannot tell an absent file from a
    # variable the file does not carry: this record is what separates
    # the two for a reader debugging an empty load
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        FileConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the dotenv file {configured_file} does not exist, treating it as empty" in messages


def test_variableless_file_names_itself_at_debug(configured_file, caplog):
    # a file of comments alone is its own case, apart from an absent
    # file: its record says the file is there and holds no variables,
    # and the absent-file record stays out
    configured_file.write_text("# only a comment\n", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        FileConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the dotenv file {configured_file} contains no variables" in messages
    assert not any("does not exist" in message for message in messages)


def test_unparsable_line_warns_in_the_family_channel(configured_file, caplog):
    # python-dotenv skips a line it cannot parse and warns into its own
    # channel; the load hands the warning over, and it lands beside the
    # file's path in the family's channel — not as a stray foreign record
    configured_file.write_text("TEST_ACD_COUNT and no assignment\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        FileConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert (
        f"the dotenv file {configured_file}: "
        "python-dotenv could not parse statement starting at line 1" in messages
    )
    # the broken line is not an empty file: the variableless record stays out
    assert not any("contains no variables" in message for message in messages)


def test_load_string_value(configured_file):
    configured_file.write_text("TEST_ACD_TEXT=from-file\n", encoding="utf-8")
    FileConfiguration.load_configuration()
    assert FileConfiguration.text == "from-file"


def test_load_converts_bool_int_and_datetime(configured_file):
    configured_file.write_text(
        "TEST_ACD_FLAG=True\nTEST_ACD_COUNT=42\nTEST_ACD_WHEN=2026-09-03T10:15:30\n",
        encoding="utf-8",
    )
    FileConfiguration.load_configuration()
    assert FileConfiguration.flag is True
    assert FileConfiguration.count == 42
    assert FileConfiguration.when == datetime(2026, 9, 3, 10, 15, 30)


def test_unconvertible_value_falls_back_to_default(configured_file):
    configured_file.write_text("TEST_ACD_COUNT=not-a-number\n", encoding="utf-8")
    FileConfiguration.load_configuration()
    assert FileConfiguration.count == 0


def test_constraint_violating_value_falls_back_to_default(configured_file):
    class BoundedConfiguration(
        Configuration,
        options=dotenv_source(file=configured_file),
    ):
        count: int = dotenv_setting(name="TEST_ACD_COUNT", default=10, ge=10)

    configured_file.write_text("TEST_ACD_COUNT=5\n", encoding="utf-8")
    BoundedConfiguration.load_configuration()
    assert BoundedConfiguration.count == 10


def test_member_name_fallback(configured_file):
    configured_file.write_text("plain=plain-value\n", encoding="utf-8")
    FileConfiguration.load_configuration()
    assert FileConfiguration.plain == "plain-value"


def test_dataclass_parses_from_file(configured_file):
    # a dataclass is one JSON-encoded variable; a field default fills the gap
    configured_file.write_text('TEST_ACD_PROXY={"host": "other.example"}\n', encoding="utf-8")
    ProxyConfiguration.load_configuration()
    assert ProxyConfiguration.proxy == Proxy("other.example", 3128)
    assert isinstance(ProxyConfiguration.proxy, Proxy)


def test_missing_required_member_aborts_the_load(configured_file):
    class RequiredConfiguration(
        Configuration,
        options=dotenv_source(file=configured_file),
    ):
        host: str = dotenv_setting(name="TEST_ACD_HOST")

    with pytest.raises(AggregateLoadError) as report:
        RequiredConfiguration.load_configuration()
    # the message names the variable and the file to provide it in
    message = str(report.value.errors[0])
    assert "environment variable 'TEST_ACD_HOST' in" in message
    assert configured_file.name in message


def test_diagnostics_name_the_full_path_of_a_relative_file(tmp_path, monkeypatch):
    # a relative file names a place in the working directory; the message
    # quotes the full path, so the exact file is not left to guess
    monkeypatch.chdir(tmp_path)

    class RelativeConfiguration(
        Configuration,
        options=dotenv_source(file=Path("relative.env")),
    ):
        host: str = dotenv_setting(name="TEST_ACD_HOST")

    with pytest.raises(AggregateLoadError) as report:
        RelativeConfiguration.load_configuration()
    full_path = tmp_path / "relative.env"
    message = str(report.value.errors[0])
    assert f"environment variable 'TEST_ACD_HOST' in the dotenv file {full_path}" in message
    assert "is required: the dotenv file provided no value" in message
    # the file shows up once: the address carries it, the cause does not repeat it
    assert message.count(str(full_path)) == 1


def test_the_class_anchors_one_file_until_reconfigured(tmp_path, monkeypatch):
    # the class's first access anchors the file for its whole life: the
    # passes — reads, diagnostics — stay with one file even when the
    # working directory moves; the plugin's file_path parameter reanchors, the
    # next access resolving the new spelling against the working
    # directory of that moment
    home = tmp_path / "home"
    away = tmp_path / "away"
    home.mkdir()
    away.mkdir()
    monkeypatch.chdir(home)

    class AnchoredConfiguration(
        Configuration,
        options=dotenv_source(file=Path("app.env")),
    ):
        token: str = dotenv_setting(name="TEST_ACD_ANCHOR", default="")

    # the member's diagnostic line names the exact file — the anchor
    # this test observes through, composed the way a real message does
    member = AnchoredConfiguration.__settings_members__["token"]

    def where(serializer: DotenvSerializer) -> str:
        return member_where(AnchoredConfiguration, member, [serializer], "TEST_ACD_ANCHOR")

    anchored = (
        f"member 'token' (environment variable 'TEST_ACD_ANCHOR' "
        f"in the dotenv file {home / 'app.env'}) of 'AnchoredConfiguration'"
    )

    def link_serializer(link: Any) -> DotenvSerializer:
        serializer = DotenvSerializer()
        serializer.set_serializer_params(AnchoredConfiguration.__settings_context__)
        serializer.set_source_link(link)
        return serializer

    link = dotenv_source(file=Path("app.env")).link
    assert where(link_serializer(link)) == anchored

    monkeypatch.chdir(away)
    assert where(link_serializer(link)) == anchored

    retuned = dotenv_source(file=Path("other.env")).link
    assert where(link_serializer(retuned)) == (
        f"member 'token' (environment variable 'TEST_ACD_ANCHOR' "
        f"in the dotenv file {away / 'other.env'}) of 'AnchoredConfiguration'"
    )


def test_naming_options_prefix_and_case(configured_file):
    configured_file.write_text("TEST_ACD_CONN__PORT=6543\n", encoding="utf-8")
    NestedConfiguration.load_configuration()
    assert NestedConfiguration.conn == Db(host="declared-host", port=6543)


def test_nested_partial_update_and_required_assembly(configured_file):
    configured_file.write_text(
        "TEST_ACD_CONN__PORT=6543\n"
        "TEST_ACD_CONN__POOL__HEALTH__TIMEOUT=2.5\n"
        "TEST_ACD_READER__HOST=reader.example.com\n"
        "TEST_ACD_READER__POOL__SIZE=5\n",
        encoding="utf-8",
    )
    NestedConfiguration.load_configuration()
    RequiredNestedConfiguration.load_configuration()
    # conn declares a default: the addressed fields move, the rest keeps the
    # declared values
    assert NestedConfiguration.conn == Db(
        host="declared-host", port=6543, pool=Pool(health=Health(timeout=2.5))
    )
    # reader is required: the file assembles its object from the field
    # variables alone, the untouched branches taking the field defaults
    assert RequiredNestedConfiguration.reader == Db(host="reader.example.com", pool=Pool(size=5))


def test_nested_whole_object_form(configured_file):
    configured_file.write_text(
        'TEST_ACD_CONN={"host": "json-host", "port": 1}\n',
        encoding="utf-8",
    )
    NestedConfiguration.load_configuration()
    assert NestedConfiguration.conn == Db(host="json-host", port=1, pool=Pool())


def test_undecodable_file_fails_the_load(configured_file):
    # a file that is not text must reach the caller, not silently report
    # every member missing
    configured_file.write_bytes(b"TEST_ACD_TEXT=\xff\xfe\n")
    with pytest.raises(UnicodeDecodeError):
        FileConfiguration.load_configuration()


def test_the_chain_is_the_classs_own_and_inherits(tmp_path, configured_file):
    own = tmp_path / "own.env"
    own.write_text("TEST_ACD_TEXT=from-own\n", encoding="utf-8")

    class BoundConfiguration(
        Configuration,
        options=dotenv_source(file=own),
    ):
        text: str = dotenv_setting(name="TEST_ACD_TEXT", default="")

    BoundConfiguration.load_configuration()
    assert BoundConfiguration.text == "from-own"

    # a subclass without its own chain inherits the nearest one above
    class ChildConfiguration(BoundConfiguration):
        pass

    ChildConfiguration.load_configuration()
    assert ChildConfiguration.text == "from-own"

    # a subclass with its own chain switches to it alone: the base class
    # keeps reading its own file
    other = tmp_path / "other.env"
    other.write_text("TEST_ACD_TEXT=from-other\n", encoding="utf-8")

    class SwitchedConfiguration(
        BoundConfiguration,
        options=dotenv_source(file=other),
    ):
        pass

    SwitchedConfiguration.load_configuration()
    assert SwitchedConfiguration.text == "from-other"
    BoundConfiguration.load_configuration()
    assert BoundConfiguration.text == "from-own"


def test_invalid_binding_fails_the_builder_call():
    # the link's file is the builder's own parameter: an invalid one fails
    # at the call, before any class statement
    with pytest.raises(TypeError, match="invalid dotenv source file: must be a file path"):
        dotenv_source(file=None)


def test_broken_storage_path_reaches_caller(tmp_path):
    # a regular file sitting where the configuration directory belongs breaks
    # every read; the error must reach the caller, not end up in the log
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a directory", encoding="utf-8")

    class BlockedConfiguration(
        Configuration,
        options=dotenv_source(file=blocker / "configuration.env"),
    ):
        text: str = dotenv_setting(name="TEST_ACD_TEXT", default="")

    with pytest.raises(OSError):
        BlockedConfiguration.load_configuration()


def test_get_plugin_bound_to_class():
    plugin = FileConfiguration.get_plugin(DotenvPlugin)
    assert plugin.plugin_name == "Dotenv"
    assert plugin.context.settings_class is FileConfiguration


def test_dotenv_module_is_self_sufficient(tmp_path):
    """The source's own module carries the naming options beside its factory."""
    script = textwrap.dedent(
        """
        import os
        import sys

        import advexp.configuration.plugins.environment.dotenv as dotenv
        from advexp.configuration import Configuration

        os.chdir(r"{workdir}")


        class SelfSufficientConfig(
            Configuration,
            options=dotenv.dotenv_source(file="self-sufficient.env"),
        ):
            # PORT, an explicit address in the file
            port: int = dotenv.dotenv_setting(name="PORT", default=8080)

            # timeout, the member name as the file key
            timeout: int = dotenv.dotenv_setting(default=30)


        SelfSufficientConfig.load_configuration()
        assert SelfSufficientConfig.port == 8080
        assert SelfSufficientConfig.timeout == 30
        assert dotenv.NameCase is not None and dotenv.dotenv_source is not None

        # the source came in alone: the variables sibling never loaded
        assert not any("environment.variables" in name for name in sys.modules)
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# -- name_case=NameCase.ANY in the dotenv file ------------------------------


class AnyCaseFileConfiguration(
    Configuration,
    options=dotenv_source(file=CONFIGURED_NAME, name_case=NameCase.ANY),
):
    host: str = dotenv_setting()  # host, required
    legacy: str = dotenv_setting(name="legacy_flag", default="off")


def test_any_loads_any_spelling_from_the_file(configured_file):
    configured_file.write_text("HOST=any.example.com\n", encoding="utf-8")
    AnyCaseFileConfiguration.load_configuration()
    assert AnyCaseFileConfiguration.host == "any.example.com"


def test_any_two_folded_spellings_in_the_file_fail_the_load(configured_file):
    configured_file.write_text("HOST=one\nHost=two\n", encoding="utf-8")
    with pytest.raises(
        AggregateLoadError,
        match=f"the dotenv file '{configured_file}' holds two differently-cased "
        "spellings of the environment variable \\('HOST' and 'Host'\\)",
    ):
        AnyCaseFileConfiguration.load_configuration()


# -- name_case=NameCase.LOWER in the dotenv file -----------------------------


class LowerCaseFileConfiguration(
    Configuration,
    options=dotenv_source(file=CONFIGURED_NAME, name_case=NameCase.LOWER),
):
    Mode: str = dotenv_setting(default="production")


def test_lower_case_reads_the_recast_name_from_the_file(configured_file):
    configured_file.write_text("mode=lowered\n", encoding="utf-8")
    LowerCaseFileConfiguration.load_configuration()
    assert LowerCaseFileConfiguration.Mode == "lowered"


# ---------------------------------------------------------------------------
# aliases: several addresses of one member, first found wins
# ---------------------------------------------------------------------------


class AliasFileConfiguration(
    Configuration,
    options=dotenv_source(file=CONFIGURED_NAME),
):
    ttl: str = dotenv_setting(
        name="TEST_ACD_PRIMARY",
        aliases=["TEST_ACD_FIRST", "TEST_ACD_SECOND"],
        default="default-ttl",
    )


def test_alias_loads_when_primary_is_missing(configured_file):
    configured_file.write_text("TEST_ACD_SECOND=from-old-name\n", encoding="utf-8")
    AliasFileConfiguration.load_configuration()
    assert AliasFileConfiguration.ttl == "from-old-name"


def test_alias_order_primary_then_declaration_order(configured_file):
    configured_file.write_text("TEST_ACD_SECOND=second\n", encoding="utf-8")
    AliasFileConfiguration.load_configuration()
    assert AliasFileConfiguration.ttl == "second"  # the last alias serves alone

    configured_file.write_text("TEST_ACD_FIRST=first\nTEST_ACD_SECOND=second\n", encoding="utf-8")
    AliasFileConfiguration.load_configuration()
    assert AliasFileConfiguration.ttl == "first"

    configured_file.write_text(
        "TEST_ACD_PRIMARY=primary\nTEST_ACD_SECOND=second\n", encoding="utf-8"
    )
    AliasFileConfiguration.load_configuration()
    assert AliasFileConfiguration.ttl == "primary"
