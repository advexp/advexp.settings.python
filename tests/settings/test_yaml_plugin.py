"""YAMLSettings plugin tests (file backend through tmp_path)."""

from __future__ import annotations

import dataclasses
import enum
import logging
import re
import stat
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, List, Optional

import pytest
from ruamel.yaml import YAML

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugins.yaml_settings import (
    YAMLSetting,
    YAMLSettingsConfiguration,
    YAMLSettingsPlugin,
    yaml_setting,
    yaml_source,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.sources import YAML_SOURCE_METADATA


def _load(path: Path) -> Any:
    """The file's document, read the way the reading distribution does."""
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class StoreSettings(Settings):
    host: str = yaml_setting(name="host", default="localhost")
    port: int = yaml_setting(default=9000)
    debug: bool = yaml_setting(name="debug", default=False)
    theme: Color = yaml_setting(name="theme", default=Color.RED)
    started_at: Optional[datetime] = yaml_setting(name="started_at", default=None)
    tags: List[str] = yaml_setting(name="tags", default=[])

    # a None value is stored as the document's null, like any other value
    secret_hint: Optional[str] = yaml_setting(name="secret_hint", default=None)


@dataclasses.dataclass
class Endpoint:
    host: str
    port: int = 80
    since: Optional[datetime] = None


class EndpointSettings(Settings):
    primary: Optional[Endpoint] = yaml_setting(name="primary", default=None)
    mirrors: List[Endpoint] = yaml_setting(name="mirrors", default=[])


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.yaml"
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", path)
    yield path


@pytest.fixture(autouse=True)
def reset_values():
    # settings classes keep values in class storage; start each test clean
    StoreSettings.reset_settings()
    ProxyPathSettings.reset_settings()
    yield


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(YAMLSetting) is not None
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None
    assert YAMLSettingsPlugin in LibraryConfiguration.registered_plugin_classes()


def test_load_missing_file_applies_defaults(configured_file):
    StoreSettings.load_settings()
    assert StoreSettings.host == "localhost"
    assert StoreSettings.port == 9000
    assert StoreSettings.debug is False
    assert StoreSettings.theme == Color.RED
    assert StoreSettings.started_at is None


def test_missing_file_names_itself_at_debug(configured_file, caplog):
    # the miss phrase of the pass cannot tell an absent file from a key
    # the document does not carry: this record is what separates the two
    # for a reader debugging an empty load
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the YAML file {configured_file} does not exist, treating it as empty" in messages


def test_keyless_document_names_itself_at_debug(configured_file, caplog):
    # a blank file in a file that is there is its own case, apart from an
    # absent file: its record says the file is there and holds no keys,
    # and the absent-file record stays out
    configured_file.write_text("", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the YAML file {configured_file} contains no keys" in messages
    assert not any("does not exist" in message for message in messages)


def test_save_writes_full_names_and_explicit_names(configured_file):
    StoreSettings.save_settings()
    document = _load(configured_file)
    module = StoreSettings.__module__
    assert document == {
        "host": "localhost",
        f"{module}.StoreSettings.port": 9000,
        "debug": False,
        "theme": "RED",
        "tags": [],
        # None-valued members are saved too — as the document's null
        "started_at": None,
        "secret_hint": None,
    }


def test_a_fresh_file_takes_the_libraries_layout(configured_file):
    # a fresh file is born with the library's own layout: two spaces per
    # mapping level, a sequence's dashes two spaces into it — the file
    # shape a reader can rely on
    StoreSettings.tags = ["one", "two"]
    StoreSettings.save_settings()
    module = StoreSettings.__module__
    assert configured_file.read_text(encoding="utf-8") == (
        "host: localhost\n"
        f"{module}.StoreSettings.port: 9000\n"
        "debug: false\n"
        "theme: RED\n"
        "started_at:\n"
        "tags:\n"
        "  - one\n"
        "  - two\n"
        "secret_hint:\n"
    )


def test_save_keeps_the_files_key_order(configured_file):
    # the file's layout belongs to its reader: a save does not alphabetize
    # the document — the keys the file already has stay where the file
    # keeps them (a foreign nested object included), and the pass's new
    # ones append at their container's end
    configured_file.write_text(
        "z_first: 1  # belongs before everything the pass writes\n"
        "foreign:\n"
        "  inner: kept\n"
        "host: elsewhere\n"
        f"{StoreSettings.__module__}.StoreSettings.port: 1\n",
        encoding="utf-8",
    )
    StoreSettings.load_settings()
    StoreSettings.port = 1234
    StoreSettings.save_settings()
    assert list(_load(configured_file)) == [
        "z_first",
        "foreign",
        "host",
        f"{StoreSettings.__module__}.StoreSettings.port",
        "debug",
        "theme",
        "started_at",
        "tags",
        "secret_hint",
    ]


def test_save_keeps_the_files_comments(configured_file):
    # the comments the file already carries — above a key, beside a value,
    # above the document — survive the save; the pass writes values, not
    # prose
    configured_file.write_text(
        "# the file's own header\n"
        "host: elsewhere  # inline beside the value\n"
        "# the port lives below\n"
        "port: 1\n",
        encoding="utf-8",
    )
    StoreSettings.load_settings()
    StoreSettings.port = 4321
    StoreSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "# the file's own header" in text
    assert "host: elsewhere  # inline beside the value" in text
    assert "# the port lives below" in text


def test_save_keeps_the_files_quoting_style(configured_file):
    # a key or value the file spells in single or double quotes keeps its
    # spelling: the style belongs to the file, not to the value
    configured_file.write_text(
        "'host': elsewhere\n\"debug\": true\n",
        encoding="utf-8",
    )
    StoreSettings.load_settings()
    StoreSettings.port = 7
    StoreSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "'host': elsewhere" in text
    assert '"debug": true' in text


def test_save_keeps_the_files_anchors(configured_file):
    # an anchor the file declares on keys the pass does not own, and a
    # reference to it, survive the save; the pass rewrites its own values
    # and leaves the file's alias structure alone
    configured_file.write_text(
        "primary: &p mirror.example.com\nsecondary: *p\nhost: elsewhere\n",
        encoding="utf-8",
    )
    StoreSettings.load_settings()
    StoreSettings.port = 7
    StoreSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "primary: &p mirror.example.com" in text
    assert "secondary: *p" in text


def test_save_keeps_the_files_flow_style(configured_file):
    # a mapping or sequence the file spells inline stays inline
    configured_file.write_text(
        "host: elsewhere\nforeign: {a: 1, b: [x, y]}\n",
        encoding="utf-8",
    )
    StoreSettings.load_settings()
    StoreSettings.port = 7
    StoreSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "foreign: {a: 1, b: [x, y]}" in text


def test_save_keeps_long_values_on_one_line(configured_file):
    # a long value stays on its line: a wrapped secret token would stop
    # being copy-pasteable
    StoreSettings.host = "t" * 200
    StoreSettings.save_settings()
    lines = configured_file.read_text(encoding="utf-8").splitlines()
    (host_line,) = [line for line in lines if line.startswith("host:")]
    assert host_line == f"host: {'t' * 200}"


def test_a_fresh_sequence_takes_the_libraries_dash_indent(configured_file):
    # a sequence the pass itself writes goes behind a dash two spaces into
    # its key, the fresh-file layout
    configured_file.write_text("host: elsewhere\n", encoding="utf-8")
    StoreSettings.load_settings()
    StoreSettings.tags = ["a", "b"]
    StoreSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "tags:\n  - a\n  - b\n" in text


def test_save_keeps_the_files_bom(configured_file):
    configured_file.write_text(
        UTF8_BOM + "host: elsewhere\n",
        encoding="utf-8",
    )
    StoreSettings.load_settings()
    StoreSettings.port = 7
    StoreSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert text.startswith(UTF8_BOM)
    assert "port: 7" in text


def test_save_keeps_the_files_crlf(configured_file):
    # line endings are the file's own too: a CRLF file keeps them, so a
    # diff of the pass names the value's line, not every line of the file
    configured_file.write_bytes(b"host: elsewhere\r\n")

    class CrlfSettings(Settings):
        host: str = yaml_setting(name="host", default="x")
        added: str = yaml_setting(name="added", default="a")

    CrlfSettings.load_settings()
    CrlfSettings.added = "b"
    CrlfSettings.save_settings()
    assert configured_file.read_bytes() == b"host: elsewhere\r\nadded: b\r\n"


def test_save_keeps_the_files_permission_mode(configured_file):
    # the atomic replace re-creates the file: the permission bits must
    # ride along, or a hand-set mode would not survive the save
    configured_file.write_text("host: elsewhere\n", encoding="utf-8")
    configured_file.chmod(0o600)
    StoreSettings.load_settings()
    StoreSettings.port = 7
    StoreSettings.save_settings()
    assert stat.S_IMODE(configured_file.stat().st_mode) == 0o600


def test_round_trip_through_file(configured_file):
    StoreSettings.host = "example.com"
    StoreSettings.port = 8080
    StoreSettings.debug = True
    StoreSettings.theme = Color.BLUE
    StoreSettings.tags = ["a", "b"]
    StoreSettings.secret_hint = None
    StoreSettings.save_settings()

    StoreSettings.reset_settings()
    StoreSettings.load_settings()
    assert StoreSettings.host == "example.com"
    assert StoreSettings.port == 8080
    assert StoreSettings.debug is True
    assert StoreSettings.theme == Color.BLUE
    assert StoreSettings.tags == ["a", "b"]
    assert StoreSettings.secret_hint is None


# ---------------------------------------------------------------------------
# YAML-native values
# ---------------------------------------------------------------------------


class NativeSettings(Settings):
    launch_date: date = yaml_setting(name="launch_date", default=date(2026, 11, 1))
    window: timedelta = yaml_setting(name="window", default=timedelta(minutes=30))
    amount: int = yaml_setting(name="amount", default=1000)
    seen: bool = yaml_setting(name="seen", default=False)


@pytest.fixture(autouse=True)
def reset_native_values():
    NativeSettings.reset_settings()
    yield


def test_dates_and_datetimes_stay_native_in_the_file(configured_file):
    # YAML itself carries dates and timestamps: the file holds the plain
    # calendar spelling, and the loaded value comes back the same type —
    # no ISO strings between the two sides
    NativeSettings.launch_date = date(2027, 1, 15)
    NativeSettings.save_settings()
    assert "launch_date: 2027-01-15\n" in configured_file.read_text(encoding="utf-8")
    NativeSettings.reset_settings()
    NativeSettings.load_settings()
    assert NativeSettings.launch_date == date(2027, 1, 15)


def test_the_file_may_carry_dates_in_its_own_spellings(configured_file):
    # a reader may write a timestamp with a timezone or a time part: the
    # parser resolves it, and the annotation converts the result
    configured_file.write_text(
        "launch_date: 2026-12-01\nwindow: 0:45:00\namount: 2_500\nseen: true\n",
        encoding="utf-8",
    )
    NativeSettings.load_settings()
    assert NativeSettings.launch_date == date(2026, 12, 1)
    assert NativeSettings.window == timedelta(minutes=45)
    assert NativeSettings.amount == 2500
    assert NativeSettings.seen is True


def test_yaml_12_words_stay_strings(configured_file):
    # YAML 1.2 spells its booleans true and false alone: yes and no stay
    # strings, whatever YAML 1.1 made of them
    configured_file.write_text(
        "launch_date: 2026-12-01\nwindow: 0:30:00\nseen: no\n",
        encoding="utf-8",
    )
    NativeSettings.load_settings()
    assert NativeSettings.seen is False


def test_yaml_12_bool_words_convert_like_strings(configured_file):
    # a yes/no text converts by the string contract, not by YAML 1.1
    # booleans: the member's own conversion rules apply
    configured_file.write_text(
        "launch_date: 2026-12-01\nwindow: 0:30:00\nseen: true\n",
        encoding="utf-8",
    )
    NativeSettings.load_settings()
    assert NativeSettings.seen is True


# ---------------------------------------------------------------------------
# path= — the JSON Pointer over the document tree
# ---------------------------------------------------------------------------


class ProxyPathSettings(Settings):
    host: str = yaml_setting(name="host", default="fallback", path="/net/proxy")
    port: int = yaml_setting(name="port", default=80, path="/net/proxy")


def test_path_round_trips_through_nested_objects(configured_file):
    ProxyPathSettings.host = "example.com"
    ProxyPathSettings.port = 8080
    ProxyPathSettings.save_settings()
    assert _load(configured_file) == {"net": {"proxy": {"host": "example.com", "port": 8080}}}

    ProxyPathSettings.reset_settings()
    ProxyPathSettings.load_settings()
    assert ProxyPathSettings.host == "example.com"
    assert ProxyPathSettings.port == 8080


def test_path_without_explicit_name_keeps_pattern_key(configured_file):
    # the name builds from the pattern as usual; the path only places it
    class PatternedPathSettings(Settings):
        port: int = yaml_setting(default=8080, path="/net/proxy")

    PatternedPathSettings.save_settings()
    assert _load(configured_file) == {
        "net": {"proxy": {f"{PatternedPathSettings.__module__}.PatternedPathSettings.port": 8080}}
    }


def test_dotted_name_is_a_plain_root_key(configured_file):
    # a name holding a dot stays one flat key, like every name of this
    # backend — nesting is what path= is for
    class DottedNameSettings(Settings):
        first: str = yaml_setting(name="a.b.c", default="v")

    DottedNameSettings.save_settings()
    assert _load(configured_file) == {"a.b.c": "v"}


def test_delete_prunes_emptied_path_objects(configured_file):
    ProxyPathSettings.host = "example.com"
    ProxyPathSettings.port = 8080
    ProxyPathSettings.save_settings()
    ProxyPathSettings.delete_settings()
    assert _load(configured_file) == {}


def test_none_save_stores_the_null_and_delete_prunes(configured_file):
    # None is a value like any other: it is stored as the document's null
    # (not as a dropped key), and the delete still prunes the emptied path
    class OptionalPathSettings(Settings):
        hint: Optional[str] = yaml_setting(name="hint", default=None, path="/net/proxy")

    OptionalPathSettings.hint = None
    OptionalPathSettings.save_settings()
    assert _load(configured_file) == {"net": {"proxy": {"hint": None}}}

    OptionalPathSettings.delete_settings()
    assert _load(configured_file) == {}


def test_save_refuses_to_overwrite_scalar_on_path(configured_file):
    # a scalar on the path is data the library does not own: replacing it
    # silently would destroy it
    configured_file.write_text("net: 404\n", encoding="utf-8")
    ProxyPathSettings.host = "example.com"
    with pytest.raises(ValueError, match="not a mapping"):
        ProxyPathSettings.save_settings()


def test_load_path_blocked_by_scalar_applies_default(configured_file):
    configured_file.write_text("net: 404\n", encoding="utf-8")
    ProxyPathSettings.load_settings()
    assert ProxyPathSettings.host == "fallback"


def test_path_without_leading_slash_raises_at_declaration():
    with pytest.raises(ValueError, match="must start with '/'"):

        class BrokenPathSettings(Settings):
            first: str = yaml_setting(name="first", default="v", path="net/proxy")


def test_empty_path_means_the_document_root(configured_file):
    class RootPathSettings(Settings):
        first: str = yaml_setting(name="first", default="v", path="")

    RootPathSettings.save_settings()
    assert _load(configured_file) == {"first": "v"}


# ---------------------------------------------------------------------------
# index paths — digits-only segments over sequences
# ---------------------------------------------------------------------------


class IndexPathSettings(Settings):
    host: str = yaml_setting(name="host", default="mirror-b", path="/mirrors/1")
    timeout: int = yaml_setting(name="timeout", default=5, path="/mirrors/0/net")


@pytest.fixture(autouse=True)
def reset_index_values():
    IndexPathSettings.reset_settings()
    yield


def test_index_path_round_trips_through_sequence_elements(configured_file):
    configured_file.write_text(
        "mirrors:\n  - net:\n      timeout: 9\n  - host: old\n",
        encoding="utf-8",
    )
    IndexPathSettings.load_settings()
    assert IndexPathSettings.host == "old"
    assert IndexPathSettings.timeout == 9

    IndexPathSettings.host = "changed"
    IndexPathSettings.save_settings()
    assert _load(configured_file) == {"mirrors": [{"net": {"timeout": 9}}, {"host": "changed"}]}

    # a later pass re-reads the file
    IndexPathSettings.reset_settings()
    IndexPathSettings.load_settings()
    assert IndexPathSettings.host == "changed"
    assert IndexPathSettings.contains_setting("host") is True


def test_index_path_round_trips_through_nested_sequences(configured_file):
    class GridSettings(Settings):
        cell: int = yaml_setting(name="cell", default=0, path="/grid/1/2")

    GridSettings.cell = 7
    GridSettings.save_settings()
    # the missing sequences grow with nulls up to the indexed positions
    assert _load(configured_file) == {"grid": [None, [None, None, {"cell": 7}]]}

    GridSettings.reset_settings()
    GridSettings.load_settings()
    assert GridSettings.cell == 7


def test_index_path_read_out_of_range_applies_default(configured_file):
    class ShortSequenceSettings(Settings):
        host: str = yaml_setting(name="host", default="fallback", path="/mirrors/2")
        absent: str = yaml_setting(name="absent", default="fallback", path="/nosuch/0")

    configured_file.write_text("mirrors:\n  - host: a\n", encoding="utf-8")
    ShortSequenceSettings.load_settings()
    assert ShortSequenceSettings.host == "fallback"
    assert ShortSequenceSettings.absent == "fallback"
    assert ShortSequenceSettings.contains_setting("host") is False
    assert ShortSequenceSettings.contains_setting("absent") is False


def test_index_path_blocked_by_scalar_element_applies_default(configured_file):
    class ScalarElementSettings(Settings):
        host: str = yaml_setting(name="host", default="fallback", path="/mirrors/0")

    configured_file.write_text("mirrors:\n  - plain-string\n", encoding="utf-8")
    ScalarElementSettings.load_settings()
    assert ScalarElementSettings.host == "fallback"
    assert ScalarElementSettings.contains_setting("host") is False


def test_index_path_write_grows_sequences_with_nulls(configured_file):
    class TailSettings(Settings):
        host: str = yaml_setting(name="host", default="fallback", path="/mirrors/1")

    TailSettings.host = "second"
    TailSettings.save_settings()
    assert _load(configured_file) == {"mirrors": [None, {"host": "second"}]}


def test_missing_container_kind_follows_the_next_segment(configured_file):
    # what a missing container becomes follows the next segment: a
    # digits-only one (short of the leaf) makes a sequence, any other one
    # a mapping
    class NestedIndexSettings(Settings):
        first: str = yaml_setting(name="first", default="v", path="/a/0/b")

    NestedIndexSettings.save_settings()
    assert _load(configured_file) == {"a": [{"b": {"first": "v"}}]}


def test_save_refuses_to_overwrite_scalar_where_sequence_needed(configured_file):
    configured_file.write_text("mirrors: 404\n", encoding="utf-8")
    IndexPathSettings.host = "changed"
    with pytest.raises(ValueError, match="holds a int, not a sequence"):
        IndexPathSettings.save_settings()


def test_delete_nulls_emptied_element_and_keeps_sibling_positions(configured_file):
    class PairSettings(Settings):
        first: str = yaml_setting(name="first", default="v", path="/mirrors/0")
        second: str = yaml_setting(name="second", default="v", path="/mirrors/1")

    configured_file.write_text(
        "mirrors:\n  - first: a\n  - second: b\n  - foreign: keep\n",
        encoding="utf-8",
    )
    PairSettings.load_settings()
    PairSettings.delete_setting("second")
    # the emptied slot turns into a null: its siblings keep their positions
    assert _load(configured_file) == {"mirrors": [{"first": "a"}, None, {"foreign": "keep"}]}


def test_delete_drops_sequence_whose_every_element_is_null(configured_file):
    class PairSettings(Settings):
        first: str = yaml_setting(name="first", default="v", path="/mirrors/0")
        second: str = yaml_setting(name="second", default="v", path="/mirrors/1")

    configured_file.write_text(
        "mirrors:\n  - first: a\n  - second: b\n",
        encoding="utf-8",
    )
    PairSettings.load_settings()
    PairSettings.delete_settings()
    assert _load(configured_file) == {}


def test_delete_of_missing_indexed_setting_is_a_no_op(configured_file):
    class MissingIndexSettings(Settings):
        host: str = yaml_setting(name="host", path="/mirrors/3", default="fallback")

    configured_file.write_text("mirrors: 42\n", encoding="utf-8")
    MissingIndexSettings.delete_setting("host")  # no error, the file stays
    assert _load(configured_file) == {"mirrors": 42}


# ---------------------------------------------------------------------------
# keys with special characters
# ---------------------------------------------------------------------------


def test_key_with_a_dot_round_trips(configured_file):
    class DottedSettings(Settings):
        first: str = yaml_setting(name="a.b", default="v")
        second: str = yaml_setting(name="plain", default="w")

    DottedSettings.save_settings()
    assert _load(configured_file) == {"a.b": "v", "plain": "w"}

    DottedSettings.reset_settings()
    DottedSettings.load_settings()
    assert DottedSettings.first == "v"


def test_pointer_escapes_round_trip(configured_file):
    # ~1 escapes / and ~0 escapes ~ in a path segment
    class EscapedSettings(Settings):
        first: str = yaml_setting(name="first", default="v", path="/a~1b/c~0d")

    EscapedSettings.save_settings()
    assert _load(configured_file) == {"a/b": {"c~d": {"first": "v"}}}


def test_empty_key_round_trips(configured_file):
    # a path of the root alone puts the name key inside an empty-string
    # key — the name itself may hold any characters, including none
    class EmptyKeySettings(Settings):
        host: str = yaml_setting(name="host", default="fallback", path="/")

    EmptyKeySettings.host = "changed"
    EmptyKeySettings.save_settings()
    assert _load(configured_file) == {"": {"host": "changed"}}

    EmptyKeySettings.reset_settings()
    EmptyKeySettings.load_settings()
    assert EmptyKeySettings.host == "changed"


def test_digits_segment_is_a_mapping_key_on_a_mapping(configured_file):
    # whether a digits-only segment indexes a sequence or names a key is
    # decided by the node it steps into, not by the syntax — a quoted
    # number key is a string key, and the pass reads and rewrites it there
    class NumberedSettings(Settings):
        first: str = yaml_setting(name="first", default="v", path="/ports/80")

    configured_file.write_text("ports:\n  '80':\n    first: old\n", encoding="utf-8")
    NumberedSettings.load_settings()
    assert NumberedSettings.first == "old"

    NumberedSettings.first = "new"
    NumberedSettings.save_settings()
    assert _load(configured_file) == {"ports": {"80": {"first": "new"}}}


def test_unquoted_number_key_of_the_file_is_not_a_string_key(configured_file):
    # a key YAML itself parses as a number (the unquoted 80:) is a
    # number key of the document, not the string key a path addresses:
    # the path comes up empty, the way any other unknown key does
    class NumberedSettings(Settings):
        first: str = yaml_setting(name="first", default="fallback", path="/ports/80")

    configured_file.write_text("ports:\n  80:\n    first: old\n", encoding="utf-8")
    NumberedSettings.load_settings()
    assert NumberedSettings.first == "fallback"
    assert NumberedSettings.contains_setting("first") is False


def test_key_that_looks_like_a_bool_round_trips(configured_file):
    # a value the plain form would read back as another type is quoted on
    # write: the string 'true' stays a string
    class TrickySettings(Settings):
        word: str = yaml_setting(name="word", default="true")
        number: str = yaml_setting(name="number", default="123")
        date_word: str = yaml_setting(name="date_word", default="2026-11-01")

    TrickySettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "word: 'true'" in text
    assert "number: '123'" in text
    assert "date_word: '2026-11-01'" in text

    TrickySettings.reset_settings()
    TrickySettings.load_settings()
    assert TrickySettings.word == "true"
    assert TrickySettings.number == "123"
    assert TrickySettings.date_word == "2026-11-01"


# ---------------------------------------------------------------------------
# containers and dataclasses
# ---------------------------------------------------------------------------


def test_dataclass_round_trip_through_file(configured_file):
    EndpointSettings.primary = Endpoint(host="example.com", port=8080)
    EndpointSettings.mirrors = [Endpoint("m1"), Endpoint("m2", 8081)]
    EndpointSettings.save_settings()
    assert _load(configured_file) == {
        "primary": {"host": "example.com", "port": 8080, "since": None},
        "mirrors": [
            {"host": "m1", "port": 80, "since": None},
            {"host": "m2", "port": 8081, "since": None},
        ],
    }

    EndpointSettings.reset_settings()
    EndpointSettings.load_settings()
    assert EndpointSettings.primary == Endpoint(host="example.com", port=8080)
    assert EndpointSettings.mirrors == [Endpoint("m1"), Endpoint("m2", 8081)]


def test_none_value_round_trips_through_file(configured_file):
    # the document's null is a value of the storage: it survives the file
    # as None, apart from a missing key
    StoreSettings.secret_hint = None
    StoreSettings.save_settings()

    StoreSettings.reset_settings()
    StoreSettings.load_settings()
    assert StoreSettings.secret_hint is None


# ---------------------------------------------------------------------------
# delete, contains, foreign keys
# ---------------------------------------------------------------------------


def test_delete_settings_removes_keys(configured_file):
    StoreSettings.save_settings()
    StoreSettings.delete_settings()
    assert _load(configured_file) == {}


def test_delete_keeps_foreign_keys(configured_file):
    configured_file.write_text("foreign: keep\nhost: elsewhere\n", encoding="utf-8")
    StoreSettings.load_settings()
    StoreSettings.delete_settings()
    assert _load(configured_file) == {"foreign": "keep"}


def test_contains_setting(configured_file):
    assert StoreSettings.contains_setting("host") is False
    StoreSettings.save_settings()
    assert StoreSettings.contains_setting("host") is True
    StoreSettings.delete_setting("host")
    assert StoreSettings.contains_setting("host") is False


def test_foreign_keys_preserved(configured_file):
    configured_file.write_text(
        "# a foreign comment\nforeign:\n  nested: keep\nhost: elsewhere\n",
        encoding="utf-8",
    )
    StoreSettings.load_settings()
    StoreSettings.port = 1
    StoreSettings.save_settings()
    document = _load(configured_file)
    assert document["foreign"] == {"nested": "keep"}
    assert document["host"] == "elsewhere"  # the pass rewrote its own key alone
    assert "# a foreign comment" in configured_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# broken files
# ---------------------------------------------------------------------------


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("{not yaml", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match=re.escape(f"cannot parse the YAML settings file {configured_file}"),
    ):
        StoreSettings.load_settings()


def test_corrupt_file_through_the_single_setting_passes(configured_file):
    # the bundled backend's corrupt-file condition reaches the caller of
    # every single-setting pass unwrapped: the inner ValueError the class
    # passes give, never the user-facing wrapper riding alone
    configured_file.write_text("{not yaml", encoding="utf-8")
    expected = f"cannot parse the YAML settings file {configured_file}"
    for call in (
        lambda: StoreSettings.load_setting("host"),
        lambda: StoreSettings.save_setting("host"),
        lambda: StoreSettings.contains_setting("host"),
    ):
        with pytest.raises(ValueError, match=re.escape(expected)):
            call()


def test_second_document_in_the_file_refused(configured_file):
    # a save must not drop what sits beyond the separator: a second
    # document in the stream fails the parse
    configured_file.write_text("host: elsewhere\n---\nother: document\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a single document"):
        StoreSettings.load_settings()


def test_unknown_tag_refused(configured_file):
    # the settings file is data, not code: a tag the YAML core schema does
    # not know fails the parse, and nothing gets constructed
    configured_file.write_text(
        "host: !!python/object/apply:os.system ['echo no']\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="could not determine a constructor"):
        StoreSettings.load_settings()


def test_blank_file_loads_as_an_empty_document(configured_file):
    # a blank YAML file is valid YAML: a load reads no keys from it and
    # the declared defaults serve — no parse error, unlike richer formats
    configured_file.write_text("", encoding="utf-8")
    StoreSettings.load_settings()
    assert StoreSettings.host == "localhost"


def test_whitespace_file_loads_as_an_empty_document(configured_file):
    configured_file.write_text("   \n\n", encoding="utf-8")
    StoreSettings.load_settings()
    assert StoreSettings.host == "localhost"


def test_save_pass_starts_a_blank_file_as_an_empty_document(configured_file, caplog):
    # a save may build its document from scratch: a blank file holds
    # nothing a write could lose
    configured_file.write_text("", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.save_settings()
    assert StoreSettings.contains_setting("host")
    messages = [record.getMessage() for record in caplog.records]
    assert f"the YAML file {configured_file} contains no keys" in messages


def test_save_pass_refuses_a_corrupt_file(configured_file):
    configured_file.write_text("{not yaml", encoding="utf-8")
    with pytest.raises(
        ValueError, match=re.escape(f"cannot parse the YAML settings file {configured_file}")
    ):
        StoreSettings.save_settings()


def test_non_mapping_root_raises_to_caller(configured_file):
    configured_file.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping at the top level, got a sequence"):
        StoreSettings.load_settings()


def test_scalar_root_raises_to_caller(configured_file):
    configured_file.write_text("just a scalar\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping at the top level, got a str scalar"):
        StoreSettings.load_settings()


def test_unset_file_path_raises_to_caller(tmp_path, monkeypatch):
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", None)
    with pytest.raises(ValueError, match="file_path"):
        StoreSettings.load_settings()


def test_missing_parent_directory_created(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "deeper" / "settings.yaml"
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", path)
    StoreSettings.save_settings()
    assert path.exists()


# ---------------------------------------------------------------------------
# the values the storage hands out
# ---------------------------------------------------------------------------


def test_mutable_default_survives_in_place_mutation(configured_file):
    StoreSettings.save_settings()
    StoreSettings.tags.append("first")
    StoreSettings.save_settings()

    StoreSettings.reset_settings()
    StoreSettings.load_settings()
    assert StoreSettings.tags == ["first"]


def test_save_converts_at_save_time_no_live_reference(configured_file):
    # the stored form is built at save time; a later mutation of the live
    # value does not reach the document
    StoreSettings.tags = ["a"]
    StoreSettings.save_settings()
    StoreSettings.tags.append("b")
    assert _load(configured_file)["tags"] == ["a"]


# ---------------------------------------------------------------------------
# the plugin's file_path property
# ---------------------------------------------------------------------------


def test_class_file_binding_wins_over_module_default(tmp_path, configured_file):
    own = tmp_path / "own.yaml"

    class FileSettings(
        Settings,
        options=yaml_source(file=own),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    FileSettings.save_settings()
    assert _load(own) == {"host": "localhost"}
    assert not configured_file.exists()  # the module default was untouched

    # the plugin property reads the declared binding, chain-resolved
    assert FileSettings.get_plugin(YAMLSettingsPlugin).file_path == own

    # the property setter is the imperative spelling of the same binding;
    # assigning re-aims the class itself
    FileSettings.get_plugin(YAMLSettingsPlugin).file_path = configured_file
    assert FileSettings.get_plugin(YAMLSettingsPlugin).file_path == configured_file
    FileSettings.save_settings()
    assert _load(configured_file) == {"host": "localhost"}

    # the seat's flat key is the same entry at runtime; removing it falls
    # back to the module default
    FileSettings.set_class_metadata(
        YAML_SOURCE_METADATA, yaml_source(file=own)[YAML_SOURCE_METADATA]
    )
    assert FileSettings.get_plugin(YAMLSettingsPlugin).file_path == own
    assert FileSettings.delete_class_metadata(YAML_SOURCE_METADATA) is True
    assert FileSettings.get_plugin(YAMLSettingsPlugin).file_path is None


def test_binding_inherited_by_subclass(tmp_path):
    base_file = tmp_path / "base.yaml"

    class BaseFileSettings(
        Settings,
        options=yaml_source(file=base_file),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    class DerivedFileSettings(BaseFileSettings):
        extra: int = yaml_setting(name="extra", default=1)

    # a subclass without its own binding inherits the nearest one above,
    # and the property shows the inherited one
    assert DerivedFileSettings.get_plugin(YAMLSettingsPlugin).file_path == base_file
    DerivedFileSettings.save_settings()
    assert _load(base_file) == {"host": "localhost", "extra": 1}


def test_plugin_file_path_rejects_invalid_values(configured_file):
    plugin = StoreSettings.get_plugin(YAMLSettingsPlugin)
    with pytest.raises(TypeError, match="invalid YAML source file"):
        plugin.file_path = ""
