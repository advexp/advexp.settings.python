"""TOMLSettings plugin tests (file backend through tmp_path)."""

from __future__ import annotations

import dataclasses
import enum
import logging
import re
import stat
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, List, Optional

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import tomlkit

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.toml_settings import (
    TOML_FILE_METADATA,
    TOMLSetting,
    TOMLSettingsConfiguration,
    TOMLSettingsPlugin,
    TOMLSettingsSerializer,
    toml_setting,
    toml_source,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.sources import TOML_SOURCE_METADATA
from advexp.settings_base.toml_options import TOML_TABLE_SEPARATOR


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class StoreSettings(Settings):
    host: str = toml_setting(name="host", default="localhost")
    port: int = toml_setting(default=9000)
    debug: bool = toml_setting(name="debug", default=False)
    theme: Color = toml_setting(name="theme", default=Color.RED)
    started_at: Optional[datetime] = toml_setting(name="started_at", default=None)
    tags: List[str] = toml_setting(name="tags", default=[])

    # TOML has no null: a None value drops the entry, the load falls back
    secret_hint: Optional[str] = toml_setting(name="secret_hint", default=None)


@dataclasses.dataclass
class Endpoint:
    host: str
    port: int = 80
    since: Optional[datetime] = None


class EndpointSettings(Settings):
    primary: Optional[Endpoint] = toml_setting(name="primary", default=None)
    mirrors: List[Endpoint] = toml_setting(name="mirrors", default=[])


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.toml"
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", path)
    yield path


@pytest.fixture(autouse=True)
def reset_values():
    # settings classes keep values in class storage; start each test clean
    StoreSettings.reset_settings()
    ProxyPathSettings.reset_settings()
    yield


def write_document(path: Path, document: Any) -> None:
    path.write_text(tomlkit.dumps(document), encoding="utf-8")


def read_document(path: Path) -> Any:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def nested(key: str, value: Any) -> Any:
    """The value that is placed at the dotted address: a table for each key level.

    This is the address spelling that the document carries. Every part of the key
    that is separated by the table separator is a table level, and the last part
    is the key. The serializer stores the value at the address that the name
    spells, so a dotted name never appears in the file as one quoted key.
    """
    levels = key.split(TOML_TABLE_SEPARATOR)
    for level in reversed(levels[1:]):
        value = {level: value}
    return {levels[0]: value}


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(TOMLSetting) is not None
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None
    assert TOMLSettingsPlugin in LibraryConfiguration.registered_plugin_classes()


def test_load_missing_file_applies_defaults(configured_file):
    StoreSettings.load_settings()
    assert StoreSettings.host == "localhost"
    assert StoreSettings.port == 9000
    assert StoreSettings.debug is False
    assert StoreSettings.theme is Color.RED
    assert StoreSettings.started_at is None


def test_missing_file_names_itself_at_debug(configured_file, caplog):
    # the miss phrase of the pass cannot tell an absent file from a key
    # the document does not carry: this record is what separates the two
    # for a reader debugging an empty load
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the TOML file {configured_file} does not exist, treating it as empty" in messages


def test_keyless_document_names_itself_at_debug(configured_file, caplog):
    # a keyless document in a file that is there is its own case, apart
    # from an absent file: its record says the file is there and holds no
    # keys, and the absent-file record stays out
    configured_file.write_text("# nothing but a comment\n", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the TOML file {configured_file} contains no keys" in messages
    assert not any("does not exist" in message for message in messages)


def test_save_writes_nested_pattern_keys_and_plain_explicit_names(configured_file):
    StoreSettings.save_settings()
    document = read_document(configured_file)
    module = StoreSettings.__module__
    assert document == {
        "host": "localhost",
        **nested(f"{module}.StoreSettings.port", 9000),
        "debug": False,
        "theme": "RED",
        "tags": [],
        # None-valued members have no TOML form: their entries are dropped
        # and the next load falls back to the default
    }


def test_round_trip_through_file(configured_file):
    StoreSettings.load_settings()
    StoreSettings.host = "example.com"
    StoreSettings.port = 8080
    StoreSettings.debug = True
    StoreSettings.theme = Color.BLUE
    StoreSettings.started_at = datetime(2026, 9, 6, 12, 30, 0)
    StoreSettings.tags = ["a", "b"]
    StoreSettings.save_settings()

    # a later pass re-reads the file (fresh serializer, fresh document)
    StoreSettings.reset_settings()
    StoreSettings.load_settings()
    assert StoreSettings.host == "example.com"
    assert StoreSettings.port == 8080
    assert StoreSettings.debug is True
    assert StoreSettings.theme is Color.BLUE
    assert StoreSettings.started_at == datetime(2026, 9, 6, 12, 30, 0)
    assert StoreSettings.tags == ["a", "b"]


def test_native_datetime_stays_native_in_the_file(configured_file):
    # the datetime form TOML itself carries, no ISO string: the parsed
    # value comes back as a datetime, and the file holds it unquoted
    StoreSettings.started_at = datetime(2026, 9, 6, 12, 30, 0)
    StoreSettings.save_settings()
    assert read_document(configured_file)["started_at"] == datetime(2026, 9, 6, 12, 30, 0)
    text = configured_file.read_text(encoding="utf-8")
    assert 'started_at = "2026-09-06' not in text
    assert "started_at = 2026-09-06T12:30:00" in text


def test_save_preserves_the_file_it_writes_into(configured_file):
    # the editor is format-preserving: the file's comments, blank lines and
    # key order survive a save, and a new key joins the end of the root's
    # leaf keys — the diff of a pass names only what the pass touched.
    # The file is the author's as much as the library's: hand comments
    # carry knowledge no rewrite may drop
    configured_file.write_text(
        "# the shop's own keys, commented by hand\n"
        "zebra = 1\n"
        "\n"
        "# alpha stays below zebra, by the author's decision\n"
        "alpha = 2\n",
        encoding="utf-8",
    )
    StoreSettings.host = "example.com"
    StoreSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "# the shop's own keys, commented by hand\n" in text
    assert "# alpha stays below zebra, by the author's decision\n" in text
    assert text.index("zebra = 1") < text.index("alpha = 2") < text.index('host = "example.com"')


def test_a_value_the_pass_rewrites_keeps_its_line_comment(configured_file):
    # an overwritten value is the one line a pass owns: the file's comment
    # on it stays — the comment describes the key, not the old value
    configured_file.write_text('host = "old"  # where the shop lives\n', encoding="utf-8")
    StoreSettings.host = "example.com"
    StoreSettings.save_settings()
    assert 'host = "example.com"  # where the shop lives\n' in configured_file.read_text(
        encoding="utf-8"
    )


def test_an_unchanged_value_keeps_the_files_own_spelling(configured_file):
    # the pass skips a value already there, spelling and all: a hand-built
    # form (a multiline array, say) survives a save that does not change it
    configured_file.write_text(
        'tags = [\n    "primary",\n    "eu",\n]\n',
        encoding="utf-8",
    )
    StoreSettings.tags = ["primary", "eu"]
    StoreSettings.save_settings()
    assert "tags = [\n" in configured_file.read_text(encoding="utf-8")


def test_a_second_pass_writes_the_same_bytes(configured_file):
    # a rewrite changes no formatting of its own: a pass over the same
    # values writes the very same bytes, so a diff between runs is empty
    StoreSettings.host = "example.com"
    StoreSettings.tags = ["a", "b"]
    StoreSettings.save_settings()
    written = configured_file.read_text(encoding="utf-8")
    StoreSettings.save_settings()
    assert configured_file.read_text(encoding="utf-8") == written


# ---------------------------------------------------------------------------
# document paths (path=, a JSON Pointer)
# ---------------------------------------------------------------------------


class ProxyPathSettings(Settings):
    host: str = toml_setting(name="host", path="/net/proxy", default="proxy.example")
    port: int = toml_setting(name="port", path="/net/proxy", default=3128)
    retries: int = toml_setting(name="retries", path="/net", default=3)


def test_path_round_trips_through_nested_tables(configured_file):
    ProxyPathSettings.load_settings()
    ProxyPathSettings.host = "cache.example"
    ProxyPathSettings.save_settings()
    document = read_document(configured_file)
    assert document["net"] == {
        "proxy": {"host": "cache.example", "port": 3128},
        "retries": 3,
    }

    # a later pass re-reads the file
    ProxyPathSettings.reset_settings()
    ProxyPathSettings.load_settings()
    assert ProxyPathSettings.host == "cache.example"
    assert ProxyPathSettings.port == 3128
    assert ProxyPathSettings.retries == 3
    assert ProxyPathSettings.contains_setting("host") is True


def test_path_without_explicit_name_keeps_pattern_key(configured_file):
    class PatternPathSettings(Settings):
        port: int = toml_setting(path="/net", default=3128)

    PatternPathSettings.save_settings()
    document = read_document(configured_file)
    module = PatternPathSettings.__module__
    assert document == {"net": nested(f"{module}.PatternPathSettings.port", 3128)}


def test_dotted_name_nests_tables(configured_file):
    # the dot is TOML's table separator: the name is the setting's
    # address, written bare — [net] host — never a quoted flat key
    class DottedNameSettings(Settings):
        host: str = toml_setting(name="net.host", default="proxy.example")

    DottedNameSettings.save_settings()
    assert read_document(configured_file) == {"net": {"host": "proxy.example"}}

    DottedNameSettings.reset_settings()
    DottedNameSettings.load_settings()
    assert DottedNameSettings.host == "proxy.example"
    assert DottedNameSettings.contains_setting("host")


def test_save_refuses_a_scalar_over_a_nested_members_table(configured_file):
    # two members whose addresses collide — one's name a level of the
    # other's: the scalar write over the table refuses, exactly a scalar
    # on a path does
    class CollidingSettings(Settings):
        deep: str = toml_setting(name="net.proxy.host", default="x")
        plain: str = toml_setting(name="net.proxy", default="y")

    CollidingSettings.deep = "set"
    CollidingSettings.save_setting(lambda s: s.deep)
    # the single-setting pass unwraps the user-facing refusal into the
    # inner ValueError, the way every pass of the family does
    with pytest.raises(ValueError, match="holds a table or an array"):
        CollidingSettings.save_setting(lambda s: s.plain)
    assert read_document(configured_file)["net"]["proxy"] == {"host": "set"}


def test_save_refuses_a_nested_member_over_a_scalar(configured_file):
    # the mirror of the collision: the table write through a scalar leaf
    # of another member hits the path guard
    class CollidingSettings(Settings):
        deep: str = toml_setting(name="net.proxy.host", default="x")
        plain: str = toml_setting(name="net.proxy", default="y")

    CollidingSettings.save_setting(lambda s: s.plain)
    with pytest.raises(ValueError, match="not an object"):
        CollidingSettings.save_setting(lambda s: s.deep)
    assert read_document(configured_file) == {"net": {"proxy": "y"}}


def test_delete_prunes_emptied_path_tables(configured_file):
    write_document(configured_file, {"net": {"foreign": 1}})

    ProxyPathSettings.save_settings()
    ProxyPathSettings.delete_setting("host")
    ProxyPathSettings.delete_setting("port")  # "net.proxy" empties and goes
    document = read_document(configured_file)
    assert document == {"net": {"retries": 3, "foreign": 1}}

    ProxyPathSettings.delete_settings()  # the class's own keys only
    document = read_document(configured_file)
    assert document == {"net": {"foreign": 1}}


def test_none_save_removes_the_entry_and_delete_prunes(configured_file):
    class OptionalPathSettings(Settings):
        retries: Optional[int] = toml_setting(name="retries", path="/net", default=None)

    OptionalPathSettings.retries = 3
    OptionalPathSettings.save_settings()
    assert read_document(configured_file) == {"net": {"retries": 3}}

    # TOML has no null: a None value drops the entry — removal is what a
    # null-less storage does with it, and the next load falls back to the
    # default
    OptionalPathSettings.retries = None
    OptionalPathSettings.save_settings()
    assert read_document(configured_file) == {}

    OptionalPathSettings.retries = 3
    OptionalPathSettings.save_settings()
    OptionalPathSettings.delete_setting("retries")
    assert read_document(configured_file) == {}


def test_save_refuses_to_overwrite_scalar_on_path(configured_file):
    write_document(configured_file, {"net": 42})
    with pytest.raises(ValueError, match="not an object"):
        ProxyPathSettings.save_settings()


def test_load_path_blocked_by_scalar_applies_default(configured_file):
    write_document(configured_file, {"net": 42})
    ProxyPathSettings.load_settings()
    assert ProxyPathSettings.host == "proxy.example"
    assert ProxyPathSettings.contains_setting("host") is False


def test_path_without_leading_slash_raises_at_declaration():
    with pytest.raises(ValueError, match="must start with '/'"):
        TOMLSetting(name="host", path="net/proxy")


def test_empty_path_means_the_document_root(configured_file):
    class EmptyPathSettings(Settings):
        nested: int = toml_setting(name="x", path="", default=1)
        plain: int = toml_setting(name="y", default=2)

    EmptyPathSettings.nested = 10
    EmptyPathSettings.plain = 20
    EmptyPathSettings.save_settings()
    # the empty pointer is the whole document: the key sits at the root
    assert read_document(configured_file) == {"x": 10, "y": 20}


# ---------------------------------------------------------------------------
# array elements and special keys (contextual path segments)
# ---------------------------------------------------------------------------


def test_index_path_round_trips_through_list_elements(configured_file):
    class MirrorPathSettings(Settings):
        host: str = toml_setting(name="host", path="/mirrors/1", default="mirror-b")
        timeout: int = toml_setting(name="timeout", path="/mirrors/0/net", default=5)

    write_document(configured_file, {"mirrors": [{"net": {"timeout": 9}}, {"host": "old"}]})
    MirrorPathSettings.load_settings()
    assert MirrorPathSettings.host == "old"
    assert MirrorPathSettings.timeout == 9

    MirrorPathSettings.host = "changed"
    MirrorPathSettings.save_settings()
    assert read_document(configured_file) == {
        "mirrors": [{"net": {"timeout": 9}}, {"host": "changed"}]
    }

    # a later pass re-reads the file
    MirrorPathSettings.reset_settings()
    MirrorPathSettings.load_settings()
    assert MirrorPathSettings.host == "changed"
    assert MirrorPathSettings.contains_setting("host") is True


def test_index_path_round_trips_through_nested_lists(configured_file):
    # the arrays exist already: a write into them touches elements in
    # place (TOML has no null, so a missing array cannot grow through gaps)
    class GridSettings(Settings):
        cell: int = toml_setting(name="cell", path="/grid/1/2", default=0)

    write_document(configured_file, {"grid": [[], [{}, {}, {}]]})
    GridSettings.cell = 7
    GridSettings.save_settings()
    assert read_document(configured_file) == {"grid": [[], [{}, {}, {"cell": 7}]]}

    GridSettings.reset_settings()
    GridSettings.load_settings()
    assert GridSettings.cell == 7


def test_index_path_write_appends_at_the_array_tail(configured_file):
    # an array grows by exactly one element — the position the write
    # fills itself; no gap ever opens
    class TailSettings(Settings):
        fresh: int = toml_setting(name="x", path="/a/0", default=0)
        grown: int = toml_setting(name="x", path="/b/2", default=0)

    write_document(configured_file, {"b": [1, 2]})
    TailSettings.fresh = 7
    TailSettings.grown = 8
    TailSettings.save_settings()
    assert read_document(configured_file) == {"a": [{"x": 7}], "b": [1, 2, {"x": 8}]}


def test_index_path_write_refuses_a_gap_in_the_array(configured_file):
    # a position past the array's tail would need a gap between the
    # elements, and TOML has no null to fill one with
    class GapSettings(Settings):
        late: int = toml_setting(name="x", path="/a/3", default=0)
        fresh: int = toml_setting(name="x", path="/b/1", default=0)

    write_document(configured_file, {"a": [1, 2]})
    GapSettings.late = 7
    GapSettings.fresh = 8
    with pytest.raises(ValueError, match="cannot grow to position 3"):
        GapSettings.save_settings()


def test_missing_container_kind_follows_the_next_segment(configured_file):
    class CreatedContainersSettings(Settings):
        into_array: int = toml_setting(name="x", path="/a/0", default=0)
        into_object: int = toml_setting(name="x", path="/c/d", default=0)

    CreatedContainersSettings.into_array = 7
    CreatedContainersSettings.into_object = 8
    CreatedContainersSettings.save_settings()
    # the next segment decides: a digits-only one (short of the leaf) an
    # array, otherwise a table
    assert read_document(configured_file) == {
        "a": [{"x": 7}],
        "c": {"d": {"x": 8}},
    }


def test_new_path_array_takes_the_rows_spelling(configured_file):
    # a new array of table slots is written as [[rows]] — the form TOML
    # itself gives a list of tables — beside the tables already in the file
    class SlotSettings(Settings):
        host: str = toml_setting(name="host", path="/slots/0", default="a")

    write_document(configured_file, {"app": {"x": 1}})
    SlotSettings.host = "core.example"
    SlotSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "[[slots]]" in text
    assert "slots = [" not in text
    assert "\n\n[[slots]]" in text  # the block opens with a blank line
    assert tomllib.loads(text)["slots"] == [{"host": "core.example"}]


def test_new_path_array_opens_the_file_when_it_is_first(configured_file):
    # the file did not exist: the rows start the file, no blank line above
    class FirstSlotSettings(Settings):
        host: str = toml_setting(name="host", path="/slots/0", default="a")

    FirstSlotSettings.host = "core.example"
    FirstSlotSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert text.startswith("[[slots]]\n")
    assert tomllib.loads(text)["slots"] == [{"host": "core.example"}]


def test_inline_array_keeps_its_own_spelling_as_it_grows(configured_file):
    # the file's own inline array stays inline at the tail: the save does
    # not rewrite the form the file's author chose
    class InlineTailSettings(Settings):
        host: str = toml_setting(name="host", path="/slots/1", default="b")

    configured_file.write_text('app = {x = 1}\nslots = [{host = "a"}]\n', encoding="utf-8")
    InlineTailSettings.host = "second.example"
    InlineTailSettings.save_settings()
    text = configured_file.read_text(encoding="utf-8")
    assert "slots = [" in text
    assert "second.example" in text
    assert tomllib.loads(text)["slots"][1]["host"] == "second.example"


def test_matrix_address_keeps_the_inline_spelling(configured_file):
    # a slot that is itself an array: only the inline spelling can hold it
    class MatrixSettings(Settings):
        cell: int = toml_setting(name="cell", path="/grid/0/0", default=0)

    write_document(configured_file, {"app": {"x": 1}})
    MatrixSettings.cell = 7
    MatrixSettings.save_settings()
    assert read_document(configured_file) == {
        "app": {"x": 1},
        "grid": [[{"cell": 7}]],
    }


def test_save_refuses_to_overwrite_scalar_where_array_needed(configured_file):
    class ScalarArraySettings(Settings):
        host: str = toml_setting(name="host", path="/mirrors/0/net", default="fallback")

    write_document(configured_file, {"mirrors": 42})
    with pytest.raises(ValueError, match="not an array"):
        ScalarArraySettings.save_settings()


def test_delete_keeps_emptied_element_and_sibling_positions(configured_file):
    class MirrorDeleteSettings(Settings):
        host: str = toml_setting(name="host", path="/net/mirrors/0", default="fallback")

    write_document(configured_file, {"net": {"mirrors": [{"host": "a"}, {"host": "b"}]}})
    MirrorDeleteSettings.load_settings()
    MirrorDeleteSettings.delete_setting("host")
    # the emptied element stays as the empty table it becomes: an array
    # slot cannot hold a no-value marker, and the sibling keeps its position
    assert read_document(configured_file) == {"net": {"mirrors": [{}, {"host": "b"}]}}


def test_delete_drops_array_whose_every_element_is_emptied(configured_file):
    class LastMirrorSettings(Settings):
        host: str = toml_setting(name="host", path="/net/mirrors/0", default="fallback")

    write_document(configured_file, {"net": {"mirrors": [{"host": "a"}], "keep": 1}})
    LastMirrorSettings.load_settings()
    LastMirrorSettings.delete_setting("host")
    # [{}] counts as emptied: the array goes; net survives thanks to "keep"
    assert read_document(configured_file) == {"net": {"keep": 1}}


def test_delete_from_nested_lists_prunes_the_chain(configured_file):
    class GridDeleteSettings(Settings):
        cell: int = toml_setting(name="cell", path="/grid/0/0", default=0)

    write_document(configured_file, {"grid": [[{"cell": 1}]]})
    GridDeleteSettings.load_settings()
    GridDeleteSettings.delete_setting("cell")
    assert read_document(configured_file) == {}


def test_delete_of_missing_indexed_setting_is_a_no_op(configured_file):
    class MissingIndexSettings(Settings):
        host: str = toml_setting(name="host", path="/mirrors/3", default="fallback")

    write_document(configured_file, {"mirrors": 42})
    MissingIndexSettings.delete_setting("host")  # no error, the file stays
    assert read_document(configured_file) == {"mirrors": 42}


def test_key_with_a_dot_round_trips(configured_file):
    class EndpointPathSettings(Settings):
        host: str = toml_setting(name="host", path="/endpoints/api.internal", default="fallback")

    write_document(configured_file, {"endpoints": {"api.internal": {"host": "old"}}})
    EndpointPathSettings.load_settings()
    assert EndpointPathSettings.host == "old"

    EndpointPathSettings.host = "changed"
    EndpointPathSettings.save_settings()
    assert read_document(configured_file) == {"endpoints": {"api.internal": {"host": "changed"}}}

    # a later pass re-reads the file
    EndpointPathSettings.reset_settings()
    EndpointPathSettings.load_settings()
    assert EndpointPathSettings.host == "changed"
    assert EndpointPathSettings.contains_setting("host") is True


def test_key_with_a_dot_mixes_with_other_segments(configured_file):
    class MixedPathSettings(Settings):
        region: str = toml_setting(name="region", path="/clusters/c.db/1", default="eu")
        # a dotted key may also lead the path: the document root is a table
        leaf: str = toml_setting(name="leaf", path="/a.b/c", default="x")

    # the "c.db" array holds one element: the write lands at its tail
    write_document(configured_file, {"clusters": {"c.db": [{}]}})
    MixedPathSettings.region = "us"
    MixedPathSettings.leaf = "y"
    MixedPathSettings.save_settings()
    assert read_document(configured_file) == {
        "clusters": {"c.db": [{}, {"region": "us"}]},
        "a.b": {"c": {"leaf": "y"}},
    }

    MixedPathSettings.reset_settings()
    MixedPathSettings.load_settings()
    assert MixedPathSettings.region == "us"
    assert MixedPathSettings.leaf == "y"


def test_pointer_escapes_round_trip(configured_file):
    class EscapedKeySettings(Settings):
        slash: str = toml_setting(name="x", path="/endpoints/a~1b", default="fallback")
        tilde: str = toml_setting(name="x", path="/endpoints/a~0b", default="fallback")
        # ~1 unescapes before ~0: "~01" names the key "~1", not "/"
        tilde_one: str = toml_setting(name="x", path="/endpoints/a~01b", default="fallback")

    EscapedKeySettings.slash = "s"
    EscapedKeySettings.tilde = "t"
    EscapedKeySettings.tilde_one = "to"
    EscapedKeySettings.save_settings()
    assert read_document(configured_file) == {
        "endpoints": {"a/b": {"x": "s"}, "a~b": {"x": "t"}, "a~1b": {"x": "to"}}
    }

    EscapedKeySettings.reset_settings()
    EscapedKeySettings.load_settings()
    assert EscapedKeySettings.slash == "s"
    assert EscapedKeySettings.tilde == "t"
    assert EscapedKeySettings.tilde_one == "to"


def test_empty_key_round_trips(configured_file):
    class EmptyKeySettings(Settings):
        host: str = toml_setting(name="host", path="/", default="fallback")

    EmptyKeySettings.host = "changed"
    EmptyKeySettings.save_settings()
    assert read_document(configured_file) == {"": {"host": "changed"}}

    EmptyKeySettings.reset_settings()
    EmptyKeySettings.load_settings()
    assert EmptyKeySettings.host == "changed"


def test_digits_segment_is_a_table_key_on_a_table(configured_file):
    class NumericKeySettings(Settings):
        by_key: str = toml_setting(name="x", path="/m/0", default="fallback")
        zero_one: str = toml_setting(name="x", path="/m/01", default="fallback")

    write_document(configured_file, {"m": {"0": {"x": "key"}, "01": {"x": "zero-one"}}})
    NumericKeySettings.load_settings()
    assert NumericKeySettings.by_key == "key"  # the "0" object key
    assert NumericKeySettings.zero_one == "zero-one"
    assert NumericKeySettings.contains_setting("by_key") is True


def test_digits_segment_is_an_index_on_an_array(configured_file):
    class NumericIndexSettings(Settings):
        by_index: str = toml_setting(name="x", path="/m/1", default="fallback")
        # "01" is not an RFC 6901 array index: it stays a key and finds nothing
        zero_one: str = toml_setting(name="x", path="/m/01", default="fallback")

    write_document(configured_file, {"m": [{"x": "zero"}, {"x": "one"}]})
    NumericIndexSettings.load_settings()
    assert NumericIndexSettings.by_index == "one"
    assert NumericIndexSettings.zero_one == "fallback"
    assert NumericIndexSettings.contains_setting("by_index") is True
    assert NumericIndexSettings.contains_setting("zero_one") is False


def test_key_with_a_dot_read_blocked_applies_default(configured_file):
    class BlockedKeySettings(Settings):
        host: str = toml_setting(name="host", path="/endpoints/api.internal", default="fallback")
        absent: str = toml_setting(name="absent", path="/nosuch/k", default="fallback")

    # a scalar where the key steps into a table
    write_document(configured_file, {"endpoints": "plain-string"})
    BlockedKeySettings.load_settings()
    assert BlockedKeySettings.host == "fallback"
    assert BlockedKeySettings.absent == "fallback"
    assert BlockedKeySettings.contains_setting("host") is False
    assert BlockedKeySettings.contains_setting("absent") is False


def test_save_refuses_to_overwrite_array_where_key_needs_table(configured_file):
    class KeyArraySettings(Settings):
        host: str = toml_setting(name="host", path="/endpoints/api.internal", default="fallback")

    write_document(configured_file, {"endpoints": [1]})
    with pytest.raises(ValueError, match="not an object"):
        KeyArraySettings.save_settings()


def test_delete_of_dotted_key_setting_prunes_emptied_tables(configured_file):
    class DottedDeleteSettings(Settings):
        host: str = toml_setting(name="host", path="/endpoints/api.internal", default="fallback")

    write_document(configured_file, {"endpoints": {"api.internal": {"host": "a"}, "keep": 1}})
    DottedDeleteSettings.load_settings()
    DottedDeleteSettings.delete_setting("host")
    # the emptied "api.internal" table goes, endpoints survives thanks to "keep"
    assert read_document(configured_file) == {"endpoints": {"keep": 1}}


def test_delete_of_missing_dotted_key_setting_is_a_no_op(configured_file):
    class MissingDottedSettings(Settings):
        host: str = toml_setting(name="host", path="/endpoints/api.internal", default="fallback")

    write_document(configured_file, {"endpoints": 42})
    MissingDottedSettings.delete_setting("host")  # no error, the file stays
    assert read_document(configured_file) == {"endpoints": 42}


def test_dataclass_round_trip_through_file(configured_file):
    EndpointSettings.reset_settings()
    EndpointSettings.primary = Endpoint("a.example", 8443, datetime(2026, 9, 6, 12, 30))
    EndpointSettings.mirrors = [
        Endpoint("b.example", since=datetime(2026, 1, 2, 3, 4)),
        Endpoint("c.example", 8080, datetime(2026, 2, 3, 4, 5)),
    ]
    EndpointSettings.save_settings()

    # stored as plain TOML tables of the fields, no type tags; the
    # datetime field stays native
    document = read_document(configured_file)
    assert document["primary"] == {
        "host": "a.example",
        "port": 8443,
        "since": datetime(2026, 9, 6, 12, 30),
    }
    assert document["mirrors"][1] == {
        "host": "c.example",
        "port": 8080,
        "since": datetime(2026, 2, 3, 4, 5),
    }

    EndpointSettings.reset_settings()
    assert EndpointSettings.primary is None
    EndpointSettings.load_settings()
    assert EndpointSettings.primary == Endpoint("a.example", 8443, datetime(2026, 9, 6, 12, 30))
    assert isinstance(EndpointSettings.primary, Endpoint)
    assert EndpointSettings.mirrors == [
        Endpoint("b.example", since=datetime(2026, 1, 2, 3, 4)),
        Endpoint("c.example", 8080, datetime(2026, 2, 3, 4, 5)),
    ]
    assert all(isinstance(mirror, Endpoint) for mirror in EndpointSettings.mirrors)


def test_none_value_drops_the_entry_and_load_falls_back(configured_file):
    StoreSettings.secret_hint = "kept"
    StoreSettings.save_settings()
    assert StoreSettings.contains_setting("secret_hint") is True

    # TOML has no null: a None value removes the entry — the JSON null
    # distinction between "stored None" and "missing" has no TOML form
    StoreSettings.secret_hint = None
    StoreSettings.save_settings()
    assert "secret_hint" not in read_document(configured_file)
    assert StoreSettings.contains_setting("secret_hint") is False

    StoreSettings.reset_settings()
    StoreSettings.load_settings()
    assert StoreSettings.secret_hint is None  # the default, not a stored value


def test_none_save_names_the_removal_at_debug(configured_file, caplog):
    # the drop is the contract's rule, but a reader debugging a vanished
    # entry needs the record that names it
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.save_settings()  # secret_hint holds None
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "cannot hold a None value under the key 'secret_hint'" in message for message in messages
    )


def test_none_nested_in_a_container_is_logged_and_skipped(configured_file, caplog):
    # a dropped position inside an array would change every sibling's
    # address: a None nested in a value is refused, not silently trimmed —
    # the save pass names the member and skips it, as any storage failure
    class NestedNoneSettings(Settings):
        chain: List[Optional[Color]] = toml_setting(name="chain", default=[])

    NestedNoneSettings.chain = [Color.RED, None]
    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        NestedNoneSettings.save_settings()
    assert any(
        "setting 'chain'" in record.message and "TOML has no null" in record.message
        for record in caplog.records
    )
    # the skipped member left nothing behind: no file was ever written
    assert not configured_file.exists()


def test_non_utf8_bytes_are_logged_and_skipped(configured_file, caplog):
    # every TOML string is UTF-8: a bytes payload beyond UTF-8 text has no
    # TOML form; the save pass names the member and skips it
    class BinarySettings(Settings):
        payload: bytes = toml_setting(name="payload", default=b"")

    BinarySettings.payload = b"\xff\x00binary"
    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        BinarySettings.save_settings()
    assert any(
        "setting 'payload'" in record.message and "always UTF-8" in record.message
        for record in caplog.records
    )
    # the skipped member left nothing behind: no file was ever written
    assert not configured_file.exists()


def test_delete_settings_removes_keys(configured_file):
    StoreSettings.save_settings()
    StoreSettings.delete_settings()
    assert read_document(configured_file) == {}
    # deleting again (no file keys) is not an error
    StoreSettings.delete_settings()


def test_contains_setting(configured_file):
    assert StoreSettings.contains_setting("host") is False
    StoreSettings.save_settings()
    assert StoreSettings.contains_setting("host") is True
    StoreSettings.delete_setting("host")
    assert StoreSettings.contains_setting("host") is False


def test_foreign_keys_preserved(configured_file):
    write_document(configured_file, {"someone-elses-key": 42, "host": "preset"})

    StoreSettings.load_settings()
    assert StoreSettings.host == "preset"

    StoreSettings.port = 7000
    StoreSettings.save_settings()
    document = read_document(configured_file)
    assert document["someone-elses-key"] == 42


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("[not toml", encoding="utf-8")
    with pytest.raises(
        ValueError, match=re.escape(f"cannot parse the TOML settings file {configured_file}")
    ):
        StoreSettings.load_settings()


def test_undecodable_file_raises_to_caller(configured_file):
    # a file in another encoding (UTF-16, say) is the read-side sibling
    # of a corrupt one: the load names the library and the file instead
    # of surfacing the bare codec message
    configured_file.write_bytes('host = "ok"\n'.encode("utf-16"))
    with pytest.raises(
        ValueError, match=re.escape(f"cannot read the TOML settings file {configured_file}")
    ):
        StoreSettings.load_settings()


def test_bom_file_names_the_cause(configured_file):
    # a BOM-prefixed file is refused with the BOM named as the cause —
    # not with the parser's own puzzle about an empty key
    configured_file.write_bytes(UTF8_BOM.encode("utf-8") + b'host = "ok"\n')
    with pytest.raises(
        ValueError,
        match=re.escape(f"cannot read the TOML settings file {configured_file}")
        + ": it starts with a UTF-8 BOM",
    ):
        StoreSettings.load_settings()


def test_save_keeps_the_files_crlf(configured_file):
    # line endings are part of the preserved layout: a CRLF file keeps
    # them through a save, the untouched comment line included
    configured_file.write_bytes(b'# comment\r\nhost = "ok"\r\nport = 1\r\n')

    class CrlfSettings(Settings):
        host: str = toml_setting(name="host", default="")
        port: int = toml_setting(name="port", default=0)

    CrlfSettings.load_settings()
    CrlfSettings.port = 2
    CrlfSettings.save_settings()

    assert configured_file.read_bytes() == b'# comment\r\nhost = "ok"\r\nport = 2\r\n'


def test_save_keeps_the_files_permission_mode(configured_file):
    # the replace re-creates the file: the write hands the old mode to
    # the temp one, or a hand-set one would not survive the save
    configured_file.write_text('host = "ok"\n', encoding="utf-8")
    configured_file.chmod(0o600)

    class ModeSettings(Settings):
        host: str = toml_setting(name="host", default="")

    ModeSettings.load_settings()
    ModeSettings.host = "new"
    ModeSettings.save_settings()

    assert stat.S_IMODE(configured_file.stat().st_mode) == 0o600


def test_empty_file_is_a_valid_empty_document(configured_file):
    # unlike JSON, a blank TOML file parses to the empty document: a load
    # over it applies the defaults, and a save starts writing normally
    configured_file.write_text("", encoding="utf-8")
    StoreSettings.load_settings()
    assert StoreSettings.host == "localhost"

    StoreSettings.host = "example.com"
    StoreSettings.save_settings()
    assert read_document(configured_file)["host"] == "example.com"


def test_save_pass_refuses_a_corrupt_file(configured_file):
    # a corrupt file with bytes in it may hold someone's data in its
    # broken text: the save does not overwrite it silently
    configured_file.write_text("[not toml", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot parse the TOML settings file"):
        StoreSettings.save_settings()


def test_bare_scalar_root_raises_to_caller(configured_file):
    # a TOML document is always a table; a bare scalar is a parse error
    configured_file.write_text("5", encoding="utf-8")
    expected = (
        f"{StoreSettings.__logger_name__}: cannot parse the TOML settings file {configured_file}"
    )
    with pytest.raises(ValueError, match=re.escape(expected)):
        StoreSettings.load_settings()


def test_unset_file_path_raises_to_caller(tmp_path, monkeypatch):
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)
    with pytest.raises(ValueError, match="file_path"):
        StoreSettings.load_settings()


def test_missing_parent_directory_created(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "dir" / "settings.toml"
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", path)

    StoreSettings.save_settings()
    assert path.is_file()
    assert "host" in read_document(path)


# ---------------------------------------------------------------------------
# mutable value isolation
# ---------------------------------------------------------------------------


def test_mutable_default_survives_in_place_mutation(configured_file):
    StoreSettings.load_settings()  # no file yet: members get default copies
    StoreSettings.tags.append("mutated")  # in-place change of the stored copy

    StoreSettings.reset_settings()  # defaults come from the attribute again
    assert StoreSettings.tags == []  # the declared default was not corrupted


def test_save_converts_at_save_time_no_live_reference(configured_file):
    StoreSettings.tags = ["a"]
    StoreSettings.save_settings()

    StoreSettings.tags.append("b")  # never saved
    StoreSettings.port = 7000
    StoreSettings.save_setting(lambda s: s.port)  # a later pass re-reads the file

    document = read_document(configured_file)
    assert document["tags"] == ["a"]  # the file keeps the value from save time


# ---------------------------------------------------------------------------
# per-class file bindings
# ---------------------------------------------------------------------------


def test_each_class_in_own_file(tmp_path, monkeypatch):
    # class bindings work without any module-level default
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)

    class ServerFileSettings(
        Settings,
        options=toml_source(file=tmp_path / "server.toml"),
    ):
        host: str = toml_setting(name="host", default="localhost")

    class WindowFileSettings(
        Settings,
        options=toml_source(file=tmp_path / "window.toml"),
    ):
        width: int = toml_setting(name="width", default=800)

    ServerFileSettings.host = "db.example.com"
    ServerFileSettings.save_settings()
    WindowFileSettings.save_settings()

    assert ServerFileSettings.contains_setting("host") is True
    assert WindowFileSettings.contains_setting("width") is True

    assert read_document(tmp_path / "server.toml") == {"host": "db.example.com"}
    assert read_document(tmp_path / "window.toml") == {"width": 800}


def test_class_file_binding_wins_over_module_default(tmp_path, configured_file):
    own = tmp_path / "own.toml"

    class FileSettings(
        Settings,
        options=toml_source(file=own),
    ):
        host: str = toml_setting(name="host", default="localhost")

    FileSettings.save_settings()
    assert read_document(own) == {"host": "localhost"}
    assert not configured_file.exists()  # the module default was untouched

    # the plugin property reads the declared binding, chain-resolved
    assert FileSettings.get_plugin(TOMLSettingsPlugin).file_path == own

    # the property setter is the imperative spelling of the same binding;
    # assigning re-aims the class itself
    FileSettings.get_plugin(TOMLSettingsPlugin).file_path = configured_file
    assert FileSettings.get_plugin(TOMLSettingsPlugin).file_path == configured_file
    FileSettings.save_settings()
    assert read_document(configured_file) == {"host": "localhost"}

    # the seat's flat key is the same entry at runtime; removing it falls
    # back to the module default
    FileSettings.set_class_metadata(
        TOML_SOURCE_METADATA, toml_source(file=own)[TOML_SOURCE_METADATA]
    )
    assert FileSettings.get_plugin(TOMLSettingsPlugin).file_path == own
    assert FileSettings.delete_class_metadata(TOML_SOURCE_METADATA) is True
    assert FileSettings.get_plugin(TOMLSettingsPlugin).file_path is None


def test_binding_inherited_by_subclass(tmp_path):
    base_file = tmp_path / "base.toml"

    class BaseFileSettings(
        Settings,
        options=toml_source(file=base_file),
    ):
        host: str = toml_setting(name="host", default="localhost")

    class DerivedFileSettings(BaseFileSettings):
        extra: int = toml_setting(name="extra", default=1)

    # a subclass without its own binding inherits the nearest one above,
    # and the property shows the inherited one
    assert DerivedFileSettings.get_plugin(TOMLSettingsPlugin).file_path == base_file
    DerivedFileSettings.save_settings()
    assert read_document(base_file) == {"host": "localhost", "extra": 1}


def test_subclass_own_binding_wins_and_base_keeps_its_file(tmp_path):
    base_file = tmp_path / "base.toml"
    child_file = tmp_path / "child.toml"

    class BaseOwnSettings(
        Settings,
        options=toml_source(file=base_file),
    ):
        host: str = toml_setting(name="host", default="localhost")

    class ChildOwnSettings(
        BaseOwnSettings,
        options=toml_source(file=child_file),
    ):
        extra: int = toml_setting(name="extra", default=1)

    ChildOwnSettings.save_settings()
    assert not base_file.exists()  # the child's binding wins entirely
    assert read_document(child_file) == {"host": "localhost", "extra": 1}
    # the base class keeps reading its own file
    assert BaseOwnSettings.get_plugin(TOMLSettingsPlugin).file_path == base_file


def test_invalid_binding_fails_class_statement():
    with pytest.raises(TypeError, match=f"{TOML_FILE_METADATA}.*must be a file path"):

        class BrokenSettings(
            Settings,
            options={TOML_FILE_METADATA: 42},
        ):
            host: str = toml_setting(name="host", default="localhost")


def test_invalid_path_fails_at_helper_call():
    with pytest.raises(TypeError, match="invalid TOML source file"):
        toml_source(file="")


def test_invalid_path_fails_at_property_assignment():
    # the property setter is the same validated channel; nothing is stored
    class PropertySettings(Settings):
        host: str = toml_setting(name="host", default="localhost")

    with pytest.raises(TypeError, match="invalid TOML source file"):
        PropertySettings.get_plugin(TOMLSettingsPlugin).file_path = 42
    assert PropertySettings.get_plugin(TOMLSettingsPlugin).file_path is None


def test_broken_storage_path_reaches_caller(tmp_path, monkeypatch):
    # a regular file sitting where the settings directory belongs breaks
    # every storage step; the error must reach the caller, not end up in the log
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", blocker / "settings.toml")

    with pytest.raises(OSError):
        StoreSettings.save_settings()


# ---------------------------------------------------------------------------
# one shared document per file (mixed attribute classes)
# ---------------------------------------------------------------------------


class TaggedTOMLSetting(TOMLSetting):
    """A registered ``TOMLSetting`` subclass with a placement parameter of its own."""

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = NO_DEFAULT,
        path: Optional[str] = None,
        tagged: bool = False,
    ) -> None:
        super().__init__(name=name, default=default, path=path)
        self.tagged: bool = tagged


def tagged_toml_setting(
    *,
    name: Optional[str] = None,
    default: Any = NO_DEFAULT,
    path: Optional[str] = None,
    tagged: bool = False,
) -> Any:
    return TaggedTOMLSetting(name=name, default=default, path=path, tagged=tagged)


class TaggedTOMLSerializer(TOMLSettingsSerializer):
    """The stock serializer relocating tagged members under one table."""

    def _setting_segments(self, setting_name: str, attr: Any) -> List[str]:
        setting = self.attribute_of(attr, TaggedTOMLSetting)
        if setting is not None and setting.tagged:
            return ["tagged", setting_name]
        return super()._setting_segments(setting_name, attr)


@pytest.fixture()
def tagged_attribute() -> Iterator[type]:
    # the registry lookup is exact: the pair resolves to its own serializer
    # class, next to the stock TOMLSetting registration
    LibraryConfiguration.register_settings_attribute(TaggedTOMLSetting, TaggedTOMLSerializer)
    yield TaggedTOMLSetting
    LibraryConfiguration._attribute_serializers.pop(TaggedTOMLSetting, None)


def test_mixed_attribute_classes_keep_each_others_keys(configured_file, tagged_attribute):
    # regression: two serializer classes over one file used to cache private
    # document views, and the last flush dropped the other's keys
    class MixedSettings(Settings):
        plain: int = toml_setting(name="plain", default=1)
        custom: int = tagged_toml_setting(name="custom", tagged=True, default=2)

    MixedSettings.save_settings()
    assert read_document(configured_file) == {
        "plain": 1,
        "tagged": {"custom": 2},
    }


def test_mixed_attribute_classes_single_setting_passes_keep_keys(configured_file, tagged_attribute):
    # a single-member pass runs one serializer only; it re-reads the shared
    # document, so the other attribute class's keys survive it too
    class MixedSingleSettings(Settings):
        plain: int = toml_setting(name="plain", default=1)
        custom: int = tagged_toml_setting(name="custom", tagged=True, default=2)

    MixedSingleSettings.save_settings()
    MixedSingleSettings.plain = 10
    MixedSingleSettings.save_setting("plain")
    MixedSingleSettings.custom = 20
    MixedSingleSettings.save_setting("custom")
    assert read_document(configured_file) == {
        "plain": 10,
        "tagged": {"custom": 20},
    }


def test_later_pass_re_reads_the_file_after_mixed_save(configured_file, tagged_attribute):
    # the shared document lives only inside the pass brackets: an external
    # edit between passes must be seen by the next one
    class MixedRereadSettings(Settings):
        plain: int = toml_setting(name="plain", default=1)
        custom: int = tagged_toml_setting(name="custom", tagged=True, default=2)

    MixedRereadSettings.save_settings()
    document = read_document(configured_file)
    document["plain"] = 99
    write_document(configured_file, document)

    MixedRereadSettings.load_settings()
    assert MixedRereadSettings.plain == 99
    assert MixedRereadSettings.custom == 2


def test_module_is_self_sufficient(tmp_path):
    """The backend's own module carries everything an application needs."""
    script = textwrap.dedent(
        """
        import os

        import advexp.settings.plugins.toml_settings as ts
        from advexp.settings import Settings

        os.chdir(r"{workdir}")


        class SelfSufficientSettings(
            Settings,
            options=ts.toml_source(file="self-sufficient.toml"),
        ):
            port: int = ts.toml_setting(default=8080)


        SelfSufficientSettings.load_settings()
        assert SelfSufficientSettings.port == 8080
        SelfSufficientSettings.port = 9090
        SelfSufficientSettings.save_settings()

        # the round trip through the file, not the in-memory value
        SelfSufficientSettings.load_settings()
        assert SelfSufficientSettings.port == 9090
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# aliases: several addresses of one member, first found wins
# ---------------------------------------------------------------------------


class AliasAddressSettings(Settings):
    port: int = toml_setting(name="net.port", aliases=["port_main", "PORT"], default=80)


@pytest.fixture
def alias_file(configured_file: Path) -> Path:
    AliasAddressSettings.reset_settings()
    return configured_file


def test_alias_loads_when_primary_address_is_missing(alias_file: Path):
    # an alias is a full address: its dots nest into tables on their own
    alias_file.write_text("port_main = 9000\n", encoding="utf-8")
    AliasAddressSettings.load_settings()
    assert AliasAddressSettings.port == 9000


def test_alias_order_primary_then_declaration_order(alias_file: Path):
    alias_file.write_text("PORT = 1\nport_main = 2\n", encoding="utf-8")
    AliasAddressSettings.load_settings()
    assert AliasAddressSettings.port == 2  # the first declared alias wins

    alias_file.write_text("[net]\nport = 3\nport_main = 2\n", encoding="utf-8")
    AliasAddressSettings.load_settings()
    assert AliasAddressSettings.port == 3  # the primary address outranks every alias


def test_alias_save_writes_the_primary_address_alone(alias_file: Path):
    alias_file.write_text("port_main = 2\n", encoding="utf-8")
    AliasAddressSettings.load_settings()

    AliasAddressSettings.port = 9000
    AliasAddressSettings.save_setting("port")
    text = alias_file.read_text(encoding="utf-8")
    assert "port = 9000" in text
    assert "port_main = 2" in text  # aliases are read addresses: not written


def test_alias_delete_removes_every_address(alias_file: Path):
    alias_file.write_text("PORT = 1\nport_main = 2\n[net]\nport = 3\n", encoding="utf-8")
    AliasAddressSettings.load_settings()

    AliasAddressSettings.delete_setting("port")
    # an alias left behind would resurrect the value at the next load
    document = tomllib.loads(alias_file.read_text(encoding="utf-8"))
    assert document == {}
