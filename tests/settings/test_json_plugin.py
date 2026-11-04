"""JSONSettings plugin tests (file backend through tmp_path)."""

from __future__ import annotations

import dataclasses
import enum
import json
import logging
import re
import stat
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import pytest

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import NO_DEFAULT, UserFacingError
from advexp.settings.plugins.json_settings import (
    JSON_FILE_METADATA,
    JSONSetting,
    JSONSettingsConfiguration,
    JSONSettingsPlugin,
    JSONSettingsSerializer,
    json_setting,
    json_source,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.sources import JSON_SOURCE_METADATA


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class StoreSettings(Settings):
    host: str = json_setting(name="host", default="localhost")
    port: int = json_setting(default=9000)
    debug: bool = json_setting(name="debug", default=False)
    theme: Color = json_setting(name="theme", default=Color.RED)
    started_at: Optional[datetime] = json_setting(name="started_at", default=None)
    tags: List[str] = json_setting(name="tags", default=[])

    # a None value is stored as null, like any other value
    secret_hint: Optional[str] = json_setting(name="secret_hint", default=None)


@dataclasses.dataclass
class Endpoint:
    host: str
    port: int = 80
    since: Optional[datetime] = None


class EndpointSettings(Settings):
    primary: Optional[Endpoint] = json_setting(name="primary", default=None)
    mirrors: List[Endpoint] = json_setting(name="mirrors", default=[])


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", path)
    yield path


@pytest.fixture(autouse=True)
def reset_values():
    # settings classes keep values in class storage; start each test clean
    StoreSettings.reset_settings()
    ProxyPathSettings.reset_settings()
    yield


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(JSONSetting) is not None
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None
    assert JSONSettingsPlugin in LibraryConfiguration.registered_plugin_classes()


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
    assert f"the JSON file {configured_file} does not exist, treating it as empty" in messages


def test_keyless_document_names_itself_at_debug(configured_file, caplog):
    # an empty object in a file that is there is its own case, apart from
    # an absent file: its record says the file is there and holds no
    # keys, and the absent-file record stays out
    configured_file.write_text("{}", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.load_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the JSON file {configured_file} contains no keys" in messages
    assert not any("does not exist" in message for message in messages)


def test_save_writes_full_names_and_explicit_names(configured_file):
    StoreSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    module = StoreSettings.__module__
    assert document == {
        "host": "localhost",
        f"{module}.StoreSettings.port": 9000,
        "debug": False,
        "theme": "RED",
        "tags": [],
        # None-valued members are saved too — as null
        "started_at": None,
        "secret_hint": None,
    }


def test_save_keeps_the_files_key_order(configured_file):
    # the file's layout belongs to its reader: a save does not alphabetize
    # the document — the keys the file already has stay where the file
    # keeps them (a foreign nested object included), and the pass's new
    # ones append at their container's end
    configured_file.write_text(
        textwrap.dedent(
            """\
            {
              "zebra": 1,
              "known": 5,
              "yield": {"z": 1, "a": 2}
            }
            """
        ),
        encoding="utf-8",
    )

    class OrderSettings(Settings):
        known: int = json_setting(name="known", default=0)
        new_one: str = json_setting(name="new_one", default="x")
        new_two: str = json_setting(name="new_two", default="y")

    OrderSettings.load_settings()
    OrderSettings.known = 6
    OrderSettings.save_settings()

    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert list(document) == ["zebra", "known", "yield", "new_one", "new_two"]
    assert list(document["yield"]) == ["z", "a"]


def test_save_writes_a_new_document_in_declaration_order(configured_file):
    # a fresh document takes the members as the class declares them, and a
    # dict value keeps its own order too — nothing here is alphabetized
    class FreshOrderSettings(Settings):
        host: str = json_setting(name="host", default="localhost")
        port: int = json_setting(name="port", default=8080)
        limits: Dict[str, int] = json_setting(name="limits", default={})

    FreshOrderSettings.limits = {"z": 1, "a": 2}
    FreshOrderSettings.save_settings()

    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert list(document) == ["host", "port", "limits"]
    assert list(document["limits"]) == ["z", "a"]


def test_save_keeps_the_files_indent(configured_file):
    # the width the file already uses is the one a save writes with: four
    # spaces here, and the pass's new key joins at the same width
    configured_file.write_text('{\n    "known": 5\n}\n', encoding="utf-8")

    class FourSpaceSettings(Settings):
        known: int = json_setting(name="known", default=0)
        added: str = json_setting(name="added", default="x")

    FourSpaceSettings.load_settings()
    FourSpaceSettings.known = 6
    FourSpaceSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == (
        '{\n    "known": 6,\n    "added": "x"\n}\n'
    )


def test_save_keeps_tab_indent(configured_file):
    # a tab-indented file keeps its tabs
    configured_file.write_text('{\n\t"known": 5\n}\n', encoding="utf-8")

    class TabSettings(Settings):
        known: int = json_setting(name="known", default=0)

    TabSettings.load_settings()
    TabSettings.known = 6
    TabSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == '{\n\t"known": 6\n}\n'


def test_save_keeps_a_one_line_file_compact(configured_file):
    # a file laid out on one line stays one line
    configured_file.write_text('{"known": 5}\n', encoding="utf-8")

    class OneLineSettings(Settings):
        known: int = json_setting(name="known", default=0)
        added: str = json_setting(name="added", default="x")

    OneLineSettings.load_settings()
    OneLineSettings.known = 6
    OneLineSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == '{"known": 6, "added": "x"}\n'


def test_save_of_a_new_file_uses_two_spaces(configured_file):
    # no file to inherit a layout from: the fresh file takes two spaces
    class FreshIndentSettings(Settings):
        host: str = json_setting(name="host", default="localhost")

    FreshIndentSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == '{\n  "host": "localhost"\n}\n'


def test_save_keeps_raw_non_ascii_text(configured_file):
    # a file that already holds raw non-ASCII keeps it raw: the values
    # stay readable instead of turning into \u escapes
    configured_file.write_text('{\n  "host": "пример.local"\n}\n', encoding="utf-8")

    class RawUnicodeSettings(Settings):
        host: str = json_setting(name="host", default="")

    RawUnicodeSettings.load_settings()
    RawUnicodeSettings.host = "другой"
    RawUnicodeSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == '{\n  "host": "другой"\n}\n'


def test_save_keeps_escapes_of_an_ascii_file(configured_file):
    # an ASCII-only file keeps the escaped form: its \u escapes are the
    # file's own spelling, and a new value lands escaped in step
    configured_file.write_text(
        '{\n  "host": "\\u043f\\u0440\\u0438\\u043c\\u0435\\u0440"\n}\n', encoding="utf-8"
    )

    class EscapedUnicodeSettings(Settings):
        host: str = json_setting(name="host", default="")

    EscapedUnicodeSettings.load_settings()
    assert EscapedUnicodeSettings.host == "пример"
    EscapedUnicodeSettings.host = "другой"
    EscapedUnicodeSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == (
        '{\n  "host": "\\u0434\\u0440\\u0443\\u0433\\u043e\\u0439"\n}\n'
    )


def test_save_of_a_new_file_writes_raw_non_ascii(configured_file):
    # no file to inherit the unicode form from: a fresh document is born
    # raw, in step with the dotenv and TOML backends
    class FreshUnicodeSettings(Settings):
        host: str = json_setting(name="host", default="пример")

    FreshUnicodeSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == '{\n  "host": "пример"\n}\n'


def test_save_keeps_raw_non_ascii_keys_too(configured_file):
    # the form is decided by the whole file's text, keys included: a raw
    # Cyrillic key keeps the raw form for the document, and a pass that
    # changed nothing writes the very same bytes
    configured_file.write_text('{\n  "хост": "пример"\n}\n', encoding="utf-8")

    class RawKeySettings(Settings):
        host: str = json_setting(name="хост", default="")

    RawKeySettings.load_settings()
    assert RawKeySettings.host == "пример"
    RawKeySettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == '{\n  "хост": "пример"\n}\n'


def test_save_of_a_file_mixing_forms_goes_raw_whole(configured_file):
    # one raw value anywhere names the form for the whole document: the
    # escaped member goes raw in step — the form is the file's, not a
    # member's
    configured_file.write_text(
        '{\n  "escaped": "\\u043f\\u0440",\n  "raw": "пример"\n}\n', encoding="utf-8"
    )

    class MixedFormSettings(Settings):
        escaped: str = json_setting(name="escaped", default="")

    MixedFormSettings.load_settings()
    assert MixedFormSettings.escaped == "пр"
    MixedFormSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == (
        '{\n  "escaped": "пр",\n  "raw": "пример"\n}\n'
    )


def test_save_keeps_raw_non_ascii_of_unknown_keys(configured_file):
    # the form covers keys the library does not know: a foreign value's
    # raw spelling survives a save it took no part in
    configured_file.write_text('{\n  "примечание": "заметка",\n  "known": 5\n}\n', encoding="utf-8")

    class ForeignRawSettings(Settings):
        known: int = json_setting(name="known", default=0)

    ForeignRawSettings.load_settings()
    ForeignRawSettings.known = 6
    ForeignRawSettings.save_settings()

    assert configured_file.read_text(encoding="utf-8") == (
        '{\n  "примечание": "заметка",\n  "known": 6\n}\n'
    )


def test_undecodable_file_names_itself(configured_file):
    # a file in another encoding (UTF-16, say) must reach the user as the
    # library's own read error, not a bare codec message
    configured_file.write_bytes('{\n  "host": "ok"\n}\n'.encode("utf-16"))

    class Utf16FileSettings(Settings):
        host: str = json_setting(name="host", default="fallback")

    with pytest.raises(ValueError, match="cannot read the JSON settings file"):
        Utf16FileSettings.load_settings()


def test_save_keeps_the_files_bom(configured_file):
    # a file that starts with a UTF-8 BOM keeps it: the load strips it
    # for the parser, the flush writes it back
    configured_file.write_bytes(UTF8_BOM.encode("utf-8") + b'{\n  "host": "ok"\n}\n')

    class BomSettings(Settings):
        host: str = json_setting(name="host", default="")

    BomSettings.load_settings()
    assert BomSettings.host == "ok"
    BomSettings.host = "new"
    BomSettings.save_settings()

    assert configured_file.read_bytes() == UTF8_BOM.encode("utf-8") + b'{\n  "host": "new"\n}\n'


def test_save_keeps_the_files_crlf(configured_file):
    # line endings are the file's own too: a CRLF file keeps them, so a
    # diff of the pass names the value's line, not every line of the file
    configured_file.write_bytes(b'{\r\n  "known": 5\r\n}\r\n')

    class CrlfSettings(Settings):
        known: int = json_setting(name="known", default=0)
        added: str = json_setting(name="added", default="x")

    CrlfSettings.load_settings()
    CrlfSettings.known = 6
    CrlfSettings.save_settings()

    assert configured_file.read_bytes() == b'{\r\n  "known": 6,\r\n  "added": "x"\r\n}\r\n'


def test_save_keeps_the_files_permission_mode(configured_file):
    # the replace re-creates the file: the write hands the old mode to
    # the temp one, or a hand-set one would not survive the save
    configured_file.write_text('{"known": 5}\n', encoding="utf-8")
    configured_file.chmod(0o600)

    class ModeSettings(Settings):
        known: int = json_setting(name="known", default=0)

    ModeSettings.load_settings()
    ModeSettings.known = 6
    ModeSettings.save_settings()

    assert stat.S_IMODE(configured_file.stat().st_mode) == 0o600


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


# ---------------------------------------------------------------------------
# document paths (path=, a JSON Pointer)
# ---------------------------------------------------------------------------


class ProxyPathSettings(Settings):
    host: str = json_setting(name="host", path="/net/proxy", default="proxy.example")
    port: int = json_setting(name="port", path="/net/proxy", default=3128)
    retries: int = json_setting(name="retries", path="/net", default=3)


def test_path_round_trips_through_nested_objects(configured_file):
    ProxyPathSettings.load_settings()
    ProxyPathSettings.host = "cache.example"
    ProxyPathSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
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
        port: int = json_setting(path="/net", default=3128)

    PatternPathSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    module = PatternPathSettings.__module__
    assert document == {"net": {f"{module}.PatternPathSettings.port": 3128}}


def test_dotted_name_is_a_plain_root_key(configured_file):
    class DottedNameSettings(Settings):
        host: str = json_setting(name="net.host", default="proxy.example")

    DottedNameSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    # the name is a key, not a path: no nesting happens
    assert document == {"net.host": "proxy.example"}


def test_delete_prunes_emptied_path_objects(configured_file):
    configured_file.write_text(json.dumps({"net": {"foreign": 1}}), encoding="utf-8")

    ProxyPathSettings.save_settings()
    ProxyPathSettings.delete_setting("host")
    ProxyPathSettings.delete_setting("port")  # "net.proxy" empties and goes
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document == {"net": {"retries": 3, "foreign": 1}}

    ProxyPathSettings.delete_settings()  # the class's own keys only
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document == {"net": {"foreign": 1}}


def test_none_save_stores_json_null_and_delete_prunes(configured_file):
    class OptionalPathSettings(Settings):
        retries: Optional[int] = json_setting(name="retries", path="/net", default=None)

    OptionalPathSettings.retries = 3
    OptionalPathSettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"net": {"retries": 3}}

    # None is a value: it stays in the document as null
    OptionalPathSettings.retries = None
    OptionalPathSettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"net": {"retries": None}}

    # removal is delete's job — the emptied path object goes with it
    OptionalPathSettings.delete_setting("retries")
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {}


def test_save_refuses_to_overwrite_scalar_on_path(configured_file):
    configured_file.write_text(json.dumps({"net": 42}), encoding="utf-8")
    with pytest.raises(ValueError, match="not an object"):
        ProxyPathSettings.save_settings()


def test_load_path_blocked_by_scalar_applies_default(configured_file):
    configured_file.write_text(json.dumps({"net": 42}), encoding="utf-8")
    ProxyPathSettings.load_settings()
    assert ProxyPathSettings.host == "proxy.example"
    assert ProxyPathSettings.contains_setting("host") is False


def test_path_without_leading_slash_raises_at_declaration():
    with pytest.raises(ValueError, match="must start with '/'"):
        JSONSetting(name="host", path="net/proxy")


def test_empty_path_means_the_document_root(configured_file):
    class EmptyPathSettings(Settings):
        nested: int = json_setting(name="x", path="", default=1)
        plain: int = json_setting(name="y", default=2)

    EmptyPathSettings.nested = 10
    EmptyPathSettings.plain = 20
    EmptyPathSettings.save_settings()
    # the empty pointer is the whole document: the key sits at the root
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"x": 10, "y": 20}


# ---------------------------------------------------------------------------
# array elements and special keys (contextual path segments)
# ---------------------------------------------------------------------------


def test_index_path_round_trips_through_list_elements(configured_file):
    class MirrorPathSettings(Settings):
        host: str = json_setting(name="host", path="/mirrors/1", default="mirror-b")
        timeout: int = json_setting(name="timeout", path="/mirrors/0/net", default=5)

    configured_file.write_text(
        json.dumps({"mirrors": [{"net": {"timeout": 9}}, {"host": "old"}]}),
        encoding="utf-8",
    )
    MirrorPathSettings.load_settings()
    assert MirrorPathSettings.host == "old"
    assert MirrorPathSettings.timeout == 9

    MirrorPathSettings.host = "changed"
    MirrorPathSettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "mirrors": [{"net": {"timeout": 9}}, {"host": "changed"}]
    }

    # a later pass re-reads the file
    MirrorPathSettings.reset_settings()
    MirrorPathSettings.load_settings()
    assert MirrorPathSettings.host == "changed"
    assert MirrorPathSettings.contains_setting("host") is True


def test_index_path_round_trips_through_nested_lists(configured_file):
    class GridSettings(Settings):
        cell: int = json_setting(name="cell", path="/grid/1/2", default=0)

    GridSettings.cell = 7
    GridSettings.save_settings()
    # the missing arrays grow with nulls up to the indexed positions
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "grid": [None, [None, None, {"cell": 7}]]
    }

    GridSettings.reset_settings()
    GridSettings.load_settings()
    assert GridSettings.cell == 7


def test_index_path_read_out_of_range_applies_default(configured_file):
    class ShortListSettings(Settings):
        host: str = json_setting(name="host", path="/mirrors/2", default="fallback")
        absent: str = json_setting(name="absent", path="/nosuch/0", default="fallback")

    configured_file.write_text(json.dumps({"mirrors": [{"host": "a"}]}), encoding="utf-8")
    ShortListSettings.load_settings()
    assert ShortListSettings.host == "fallback"
    assert ShortListSettings.absent == "fallback"
    assert ShortListSettings.contains_setting("host") is False
    assert ShortListSettings.contains_setting("absent") is False


def test_index_path_blocked_by_scalar_element_applies_default(configured_file):
    class ScalarElementSettings(Settings):
        host: str = json_setting(name="host", path="/mirrors/0", default="fallback")

    configured_file.write_text(json.dumps({"mirrors": ["plain-string"]}), encoding="utf-8")
    ScalarElementSettings.load_settings()
    assert ScalarElementSettings.host == "fallback"
    assert ScalarElementSettings.contains_setting("host") is False


def test_index_path_write_grows_arrays_with_nulls(configured_file):
    class GrownListSettings(Settings):
        late: int = json_setting(name="x", path="/a/3", default=0)
        fresh: int = json_setting(name="x", path="/b/1", default=0)

    configured_file.write_text(json.dumps({"a": [1, 2]}), encoding="utf-8")
    GrownListSettings.late = 7
    GrownListSettings.fresh = 8
    GrownListSettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "a": [1, 2, None, {"x": 7}],
        "b": [None, {"x": 8}],
    }


def test_missing_container_kind_follows_the_next_segment(configured_file):
    class CreatedContainersSettings(Settings):
        into_array: int = json_setting(name="x", path="/a/1", default=0)
        into_object: int = json_setting(name="x", path="/c/d", default=0)

    CreatedContainersSettings.into_array = 7
    CreatedContainersSettings.into_object = 8
    CreatedContainersSettings.save_settings()
    # the next segment decides: a digits-only one (short of the leaf) an
    # array, otherwise an object
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "a": [None, {"x": 7}],
        "c": {"d": {"x": 8}},
    }


def test_save_refuses_to_overwrite_scalar_where_array_needed(configured_file):
    class ScalarArraySettings(Settings):
        host: str = json_setting(name="host", path="/mirrors/0/net", default="fallback")

    configured_file.write_text(json.dumps({"mirrors": 42}), encoding="utf-8")
    with pytest.raises(ValueError, match="not an array"):
        ScalarArraySettings.save_settings()


def test_delete_nulls_emptied_element_and_keeps_sibling_positions(configured_file):
    class MirrorDeleteSettings(Settings):
        host: str = json_setting(name="host", path="/net/mirrors/0", default="fallback")

    configured_file.write_text(
        json.dumps({"net": {"mirrors": [{"host": "a"}, {"host": "b"}]}}),
        encoding="utf-8",
    )
    MirrorDeleteSettings.load_settings()
    MirrorDeleteSettings.delete_setting("host")
    # the emptied element turns into a null; the sibling keeps its position
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "net": {"mirrors": [None, {"host": "b"}]}
    }


def test_delete_drops_array_whose_every_element_is_null(configured_file):
    class LastMirrorSettings(Settings):
        host: str = json_setting(name="host", path="/net/mirrors/0", default="fallback")

    configured_file.write_text(
        json.dumps({"net": {"mirrors": [{"host": "a"}], "keep": 1}}),
        encoding="utf-8",
    )
    LastMirrorSettings.load_settings()
    LastMirrorSettings.delete_setting("host")
    # [None] counts as emptied: the array goes; net survives thanks to "keep"
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"net": {"keep": 1}}


def test_delete_from_nested_lists_prunes_the_chain(configured_file):
    class GridDeleteSettings(Settings):
        cell: int = json_setting(name="cell", path="/grid/0/0", default=0)

    configured_file.write_text(json.dumps({"grid": [[{"cell": 1}]]}), encoding="utf-8")
    GridDeleteSettings.load_settings()
    GridDeleteSettings.delete_setting("cell")
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {}


def test_delete_of_missing_indexed_setting_is_a_no_op(configured_file):
    class MissingIndexSettings(Settings):
        host: str = json_setting(name="host", path="/mirrors/3", default="fallback")

    configured_file.write_text(json.dumps({"mirrors": 42}), encoding="utf-8")
    MissingIndexSettings.delete_setting("host")  # no error, the file stays
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"mirrors": 42}


def test_key_with_a_dot_round_trips(configured_file):
    class EndpointPathSettings(Settings):
        host: str = json_setting(name="host", path="/endpoints/api.internal", default="fallback")

    configured_file.write_text(
        json.dumps({"endpoints": {"api.internal": {"host": "old"}}}),
        encoding="utf-8",
    )
    EndpointPathSettings.load_settings()
    assert EndpointPathSettings.host == "old"

    EndpointPathSettings.host = "changed"
    EndpointPathSettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "endpoints": {"api.internal": {"host": "changed"}}
    }

    # a later pass re-reads the file
    EndpointPathSettings.reset_settings()
    EndpointPathSettings.load_settings()
    assert EndpointPathSettings.host == "changed"
    assert EndpointPathSettings.contains_setting("host") is True


def test_key_with_a_dot_mixes_with_other_segments(configured_file):
    class MixedPathSettings(Settings):
        region: str = json_setting(name="region", path="/clusters/c.db/1", default="eu")
        # a dotted key may also lead the path: the document root is an object
        leaf: str = json_setting(name="leaf", path="/a.b/c", default="x")

    MixedPathSettings.region = "us"
    MixedPathSettings.leaf = "y"
    MixedPathSettings.save_settings()
    # the missing containers are created along the way, the array grown with nulls
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "clusters": {"c.db": [None, {"region": "us"}]},
        "a.b": {"c": {"leaf": "y"}},
    }

    MixedPathSettings.reset_settings()
    MixedPathSettings.load_settings()
    assert MixedPathSettings.region == "us"
    assert MixedPathSettings.leaf == "y"


def test_pointer_escapes_round_trip(configured_file):
    class EscapedKeySettings(Settings):
        slash: str = json_setting(name="x", path="/endpoints/a~1b", default="fallback")
        tilde: str = json_setting(name="x", path="/endpoints/a~0b", default="fallback")
        # ~1 unescapes before ~0: "~01" names the key "~1", not "/"
        tilde_one: str = json_setting(name="x", path="/endpoints/a~01b", default="fallback")

    EscapedKeySettings.slash = "s"
    EscapedKeySettings.tilde = "t"
    EscapedKeySettings.tilde_one = "to"
    EscapedKeySettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "endpoints": {"a/b": {"x": "s"}, "a~b": {"x": "t"}, "a~1b": {"x": "to"}}
    }

    EscapedKeySettings.reset_settings()
    EscapedKeySettings.load_settings()
    assert EscapedKeySettings.slash == "s"
    assert EscapedKeySettings.tilde == "t"
    assert EscapedKeySettings.tilde_one == "to"


def test_empty_key_round_trips(configured_file):
    class EmptyKeySettings(Settings):
        host: str = json_setting(name="host", path="/", default="fallback")

    EmptyKeySettings.host = "changed"
    EmptyKeySettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"": {"host": "changed"}}

    EmptyKeySettings.reset_settings()
    EmptyKeySettings.load_settings()
    assert EmptyKeySettings.host == "changed"


def test_digits_segment_is_an_object_key_on_an_object(configured_file):
    class NumericKeySettings(Settings):
        by_key: str = json_setting(name="x", path="/m/0", default="fallback")
        zero_one: str = json_setting(name="x", path="/m/01", default="fallback")

    configured_file.write_text(
        json.dumps({"m": {"0": {"x": "key"}, "01": {"x": "zero-one"}}}),
        encoding="utf-8",
    )
    NumericKeySettings.load_settings()
    assert NumericKeySettings.by_key == "key"  # the "0" object key
    assert NumericKeySettings.zero_one == "zero-one"
    assert NumericKeySettings.contains_setting("by_key") is True


def test_digits_segment_is_an_index_on_an_array(configured_file):
    class NumericIndexSettings(Settings):
        by_index: str = json_setting(name="x", path="/m/1", default="fallback")
        # "01" is not an RFC 6901 array index: it stays a key and finds nothing
        zero_one: str = json_setting(name="x", path="/m/01", default="fallback")

    configured_file.write_text(
        json.dumps({"m": [{"x": "zero"}, {"x": "one"}]}),
        encoding="utf-8",
    )
    NumericIndexSettings.load_settings()
    assert NumericIndexSettings.by_index == "one"
    assert NumericIndexSettings.zero_one == "fallback"
    assert NumericIndexSettings.contains_setting("by_index") is True
    assert NumericIndexSettings.contains_setting("zero_one") is False


def test_key_with_a_dot_read_blocked_applies_default(configured_file):
    class BlockedKeySettings(Settings):
        host: str = json_setting(name="host", path="/endpoints/api.internal", default="fallback")
        absent: str = json_setting(name="absent", path="/nosuch/k", default="fallback")

    # a scalar where the key steps into an object
    configured_file.write_text(json.dumps({"endpoints": "plain-string"}), encoding="utf-8")
    BlockedKeySettings.load_settings()
    assert BlockedKeySettings.host == "fallback"
    assert BlockedKeySettings.absent == "fallback"
    assert BlockedKeySettings.contains_setting("host") is False
    assert BlockedKeySettings.contains_setting("absent") is False


def test_save_refuses_to_overwrite_array_where_key_needs_object(configured_file):
    class KeyArraySettings(Settings):
        host: str = json_setting(name="host", path="/endpoints/api.internal", default="fallback")

    configured_file.write_text(json.dumps({"endpoints": [1]}), encoding="utf-8")
    with pytest.raises(ValueError, match="not an object"):
        KeyArraySettings.save_settings()


def test_delete_of_dotted_key_setting_prunes_emptied_objects(configured_file):
    class DottedDeleteSettings(Settings):
        host: str = json_setting(name="host", path="/endpoints/api.internal", default="fallback")

    configured_file.write_text(
        json.dumps({"endpoints": {"api.internal": {"host": "a"}, "keep": 1}}),
        encoding="utf-8",
    )
    DottedDeleteSettings.load_settings()
    DottedDeleteSettings.delete_setting("host")
    # the emptied "api.internal" object goes, endpoints survives thanks to "keep"
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"endpoints": {"keep": 1}}


def test_delete_of_missing_dotted_key_setting_is_a_no_op(configured_file):
    class MissingDottedSettings(Settings):
        host: str = json_setting(name="host", path="/endpoints/api.internal", default="fallback")

    configured_file.write_text(json.dumps({"endpoints": 42}), encoding="utf-8")
    MissingDottedSettings.delete_setting("host")  # no error, the file stays
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"endpoints": 42}


def test_dataclass_round_trip_through_file(configured_file):
    EndpointSettings.reset_settings()
    EndpointSettings.primary = Endpoint("a.example", 8443, datetime(2026, 9, 6, 12, 30))
    EndpointSettings.mirrors = [Endpoint("b.example"), Endpoint("c.example", 8080)]
    EndpointSettings.save_settings()

    # stored as plain JSON objects of the fields, no type tags
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document["primary"] == {
        "host": "a.example",
        "port": 8443,
        "since": "2026-09-06T12:30:00",
    }
    assert document["mirrors"][1] == {"host": "c.example", "port": 8080, "since": None}

    EndpointSettings.reset_settings()
    assert EndpointSettings.primary is None
    EndpointSettings.load_settings()
    assert EndpointSettings.primary == Endpoint("a.example", 8443, datetime(2026, 9, 6, 12, 30))
    assert isinstance(EndpointSettings.primary, Endpoint)
    assert EndpointSettings.mirrors == [Endpoint("b.example"), Endpoint("c.example", 8080)]
    assert all(isinstance(mirror, Endpoint) for mirror in EndpointSettings.mirrors)


def test_none_value_round_trips_through_file(configured_file):
    StoreSettings.secret_hint = None
    StoreSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document["secret_hint"] is None
    assert StoreSettings.contains_setting("secret_hint") is True  # null, not missing

    StoreSettings.reset_settings()
    StoreSettings.load_settings()
    assert StoreSettings.secret_hint is None  # the stored null, not a missing key


def test_delete_settings_removes_keys(configured_file):
    StoreSettings.save_settings()
    StoreSettings.delete_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {}
    # deleting again (no file keys) is not an error
    StoreSettings.delete_settings()


def test_contains_setting(configured_file):
    assert StoreSettings.contains_setting("host") is False
    StoreSettings.save_settings()
    assert StoreSettings.contains_setting("host") is True
    StoreSettings.delete_setting("host")
    assert StoreSettings.contains_setting("host") is False


def test_foreign_keys_preserved(configured_file):
    document = {"someone-elses-key": 42, "host": "preset"}
    configured_file.write_text(json.dumps(document), encoding="utf-8")

    StoreSettings.load_settings()
    assert StoreSettings.host == "preset"

    StoreSettings.port = 7000
    StoreSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document["someone-elses-key"] == 42


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(
        ValueError, match=re.escape(f"cannot parse the JSON settings file {configured_file}")
    ):
        StoreSettings.load_settings()


def test_corrupt_file_through_the_single_setting_passes(configured_file):
    # the bundled backend's corrupt-file condition reaches the caller of
    # every single-setting pass unwrapped: the inner ValueError the class
    # passes give, never the user-facing wrapper riding alone
    configured_file.write_text("{not json", encoding="utf-8")
    expected = f"cannot parse the JSON settings file {configured_file}"
    for call in (
        lambda: StoreSettings.load_setting("host"),
        lambda: StoreSettings.save_setting("host"),
        lambda: StoreSettings.contains_setting("host"),
    ):
        with pytest.raises(ValueError, match=re.escape(expected)) as info:
            call()
        assert isinstance(info.value.__cause__, UserFacingError)


def test_empty_file_raises_to_caller_with_the_file_path(configured_file):
    # an empty file is not an absent one: the load names the library that
    # failed and the file it cannot parse instead of surfacing the bare
    # parser message
    configured_file.write_text("", encoding="utf-8")
    expected = (
        f"{StoreSettings.__logger_name__}: cannot parse the JSON settings file {configured_file}"
    )
    with pytest.raises(ValueError, match=re.escape(expected)):
        StoreSettings.load_settings()


def test_save_pass_starts_a_blank_file_as_an_empty_document(configured_file, caplog):
    # a save builds the document it writes: a blank file holds nothing a
    # write could lose, so the pass starts it over instead of failing
    configured_file.write_text("", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        StoreSettings.save_settings()
    messages = [record.getMessage() for record in caplog.records]
    assert (
        f"the JSON file {configured_file} is blank; the save pass will start it "
        "as an empty document" in messages
    )
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document["host"] == "localhost"
    module = StoreSettings.__module__
    assert document[f"{module}.StoreSettings.port"] == 9000


def test_save_pass_starts_a_whitespace_file_as_a_blank_one(configured_file):
    configured_file.write_text(" \n  \n", encoding="utf-8")
    StoreSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document["host"] == "localhost"


def test_save_pass_refuses_a_corrupt_file(configured_file):
    # a corrupt file with bytes in it may hold someone's data in its
    # broken text: the save does not overwrite it silently
    configured_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot parse the JSON settings file"):
        StoreSettings.save_settings()


def test_non_object_root_raises_to_caller(configured_file):
    configured_file.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="object at the top level"):
        StoreSettings.load_settings()


def test_unset_file_path_raises_to_caller(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    with pytest.raises(ValueError, match="file_path"):
        StoreSettings.load_settings()


def test_missing_parent_directory_created(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "dir" / "settings.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", path)

    StoreSettings.save_settings()
    assert path.is_file()
    assert "host" in json.loads(path.read_text(encoding="utf-8"))


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

    document = json.loads(configured_file.read_text(encoding="utf-8"))
    assert document["tags"] == ["a"]  # the file keeps the value from save time


# ---------------------------------------------------------------------------
# per-class file bindings
# ---------------------------------------------------------------------------


def test_each_class_in_own_file(tmp_path, monkeypatch):
    # class bindings work without any module-level default
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)

    class ServerFileSettings(
        Settings,
        options=json_source(file=tmp_path / "server.json"),
    ):
        host: str = json_setting(name="host", default="localhost")

    class WindowFileSettings(
        Settings,
        options=json_source(file=tmp_path / "window.json"),
    ):
        width: int = json_setting(name="width", default=800)

    ServerFileSettings.host = "db.example.com"
    ServerFileSettings.save_settings()
    WindowFileSettings.save_settings()

    assert ServerFileSettings.contains_setting("host") is True
    assert WindowFileSettings.contains_setting("width") is True

    server_document = json.loads((tmp_path / "server.json").read_text(encoding="utf-8"))
    window_document = json.loads((tmp_path / "window.json").read_text(encoding="utf-8"))
    assert server_document == {"host": "db.example.com"}
    assert window_document == {"width": 800}


def test_class_file_binding_wins_over_module_default(tmp_path, configured_file):
    own = tmp_path / "own.json"

    class FileSettings(
        Settings,
        options=json_source(file=own),
    ):
        host: str = json_setting(name="host", default="localhost")

    FileSettings.save_settings()
    assert json.loads(own.read_text(encoding="utf-8")) == {"host": "localhost"}
    assert not configured_file.exists()  # the module default was untouched

    # the plugin property reads the declared binding, chain-resolved
    assert FileSettings.get_plugin(JSONSettingsPlugin).file_path == own

    # the property setter is the imperative spelling of the same binding;
    # assigning re-aims the class itself
    FileSettings.get_plugin(JSONSettingsPlugin).file_path = configured_file
    assert FileSettings.get_plugin(JSONSettingsPlugin).file_path == configured_file
    FileSettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {"host": "localhost"}

    # the seat's flat key is the same entry at runtime; removing it falls
    # back to the module default
    FileSettings.set_class_metadata(
        JSON_SOURCE_METADATA, json_source(file=own)[JSON_SOURCE_METADATA]
    )
    assert FileSettings.get_plugin(JSONSettingsPlugin).file_path == own
    assert FileSettings.delete_class_metadata(JSON_SOURCE_METADATA) is True
    assert FileSettings.get_plugin(JSONSettingsPlugin).file_path is None


def test_binding_inherited_by_subclass(tmp_path):
    base_file = tmp_path / "base.json"

    class BaseFileSettings(
        Settings,
        options=json_source(file=base_file),
    ):
        host: str = json_setting(name="host", default="localhost")

    class DerivedFileSettings(BaseFileSettings):
        extra: int = json_setting(name="extra", default=1)

    # a subclass without its own binding inherits the nearest one above,
    # and the property shows the inherited one
    assert DerivedFileSettings.get_plugin(JSONSettingsPlugin).file_path == base_file
    DerivedFileSettings.save_settings()
    document = json.loads(base_file.read_text(encoding="utf-8"))
    assert document == {"host": "localhost", "extra": 1}


def test_subclass_own_binding_wins_and_base_keeps_its_file(tmp_path):
    base_file = tmp_path / "base.json"
    child_file = tmp_path / "child.json"

    class BaseOwnSettings(
        Settings,
        options=json_source(file=base_file),
    ):
        host: str = json_setting(name="host", default="localhost")

    class ChildOwnSettings(
        BaseOwnSettings,
        options=json_source(file=child_file),
    ):
        extra: int = json_setting(name="extra", default=1)

    ChildOwnSettings.save_settings()
    assert not base_file.exists()  # the child's binding wins entirely
    child_document = json.loads(child_file.read_text(encoding="utf-8"))
    assert child_document == {"host": "localhost", "extra": 1}
    # the base class keeps reading its own file
    assert BaseOwnSettings.get_plugin(JSONSettingsPlugin).file_path == base_file


def test_invalid_binding_fails_class_statement():
    with pytest.raises(TypeError, match=f"{JSON_FILE_METADATA}.*must be a file path"):

        class BrokenSettings(
            Settings,
            options={JSON_FILE_METADATA: 42},
        ):
            host: str = json_setting(name="host", default="localhost")


def test_invalid_path_fails_at_helper_call():
    with pytest.raises(TypeError, match="invalid JSON source file"):
        json_source(file="")


def test_invalid_path_fails_at_property_assignment():
    # the property setter is the same validated channel; nothing is stored
    class PropertySettings(Settings):
        host: str = json_setting(name="host", default="localhost")

    with pytest.raises(TypeError, match="invalid JSON source file"):
        PropertySettings.get_plugin(JSONSettingsPlugin).file_path = 42
    assert PropertySettings.get_plugin(JSONSettingsPlugin).file_path is None


def test_broken_storage_path_reaches_caller(tmp_path, monkeypatch):
    # a regular file sitting where the settings directory belongs breaks
    # every storage step; the error must reach the caller, not end up in the log
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", blocker / "settings.json")

    with pytest.raises(OSError):
        StoreSettings.save_settings()


# ---------------------------------------------------------------------------
# one shared document per file (mixed attribute classes)
# ---------------------------------------------------------------------------


class TaggedJSONSetting(JSONSetting):
    """A registered ``JSONSetting`` subclass with a placement parameter of its own."""

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


def tagged_json_setting(
    *,
    name: Optional[str] = None,
    default: Any = NO_DEFAULT,
    path: Optional[str] = None,
    tagged: bool = False,
) -> Any:
    return TaggedJSONSetting(name=name, default=default, path=path, tagged=tagged)


class TaggedJSONSerializer(JSONSettingsSerializer):
    """The stock serializer, extended to relocate tagged members under one object."""

    def _setting_segments(self, setting_name: str, attr: Any) -> List[str]:
        setting = self.attribute_of(attr, TaggedJSONSetting)
        if setting is not None and setting.tagged:
            return ["tagged", setting_name]
        return super()._setting_segments(setting_name, attr)


@pytest.fixture()
def tagged_attribute() -> Iterator[type]:
    # the registry lookup is exact: the pair resolves to its own serializer
    # class, next to the stock JSONSetting registration
    LibraryConfiguration.register_settings_attribute(TaggedJSONSetting, TaggedJSONSerializer)
    yield TaggedJSONSetting
    LibraryConfiguration._attribute_serializers.pop(TaggedJSONSetting, None)


def test_mixed_attribute_classes_keep_each_others_keys(configured_file, tagged_attribute):
    # regression: two serializer classes over one file used to cache private
    # document views, and the last flush dropped the other's keys
    class MixedSettings(Settings):
        plain: int = json_setting(name="plain", default=1)
        custom: int = tagged_json_setting(name="custom", tagged=True, default=2)

    MixedSettings.save_settings()
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "plain": 1,
        "tagged": {"custom": 2},
    }


def test_mixed_attribute_classes_single_setting_passes_keep_keys(configured_file, tagged_attribute):
    # a single-member pass runs one serializer only; it re-reads the shared
    # document, so the other attribute class's keys survive it too
    class MixedSingleSettings(Settings):
        plain: int = json_setting(name="plain", default=1)
        custom: int = tagged_json_setting(name="custom", tagged=True, default=2)

    MixedSingleSettings.save_settings()
    MixedSingleSettings.plain = 10
    MixedSingleSettings.save_setting("plain")
    MixedSingleSettings.custom = 20
    MixedSingleSettings.save_setting("custom")
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "plain": 10,
        "tagged": {"custom": 20},
    }


def test_later_pass_re_reads_the_file_after_mixed_save(configured_file, tagged_attribute):
    # the shared document lives only inside the pass brackets: an external
    # edit between passes must be seen by the next one
    class MixedRereadSettings(Settings):
        plain: int = json_setting(name="plain", default=1)
        custom: int = tagged_json_setting(name="custom", tagged=True, default=2)

    MixedRereadSettings.save_settings()
    document = json.loads(configured_file.read_text(encoding="utf-8"))
    document["plain"] = 99
    configured_file.write_text(json.dumps(document), encoding="utf-8")

    MixedRereadSettings.load_settings()
    assert MixedRereadSettings.plain == 99
    assert MixedRereadSettings.custom == 2


def test_module_is_self_sufficient(tmp_path):
    """The backend's own module carries everything an application needs."""
    script = textwrap.dedent(
        """
        import os

        import advexp.settings.plugins.json_settings as js
        from advexp.settings import Settings

        os.chdir(r"{workdir}")


        class SelfSufficientSettings(
            Settings,
            options=js.json_source(file="self-sufficient.json"),
        ):
            port: int = js.json_setting(default=8080)


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
# aliases: several keys of one member, first found wins
# ---------------------------------------------------------------------------


class AliasKeySettings(Settings):
    port: int = json_setting(name="port", aliases=["port_main", "PORT"], default=80)
    host: str = json_setting(
        name="host", path="/net/proxy", aliases=["host_main"], default="localhost"
    )


@pytest.fixture
def alias_file(configured_file: Path) -> Path:
    AliasKeySettings.reset_settings()
    return configured_file


def test_alias_loads_when_primary_key_is_missing(alias_file: Path):
    alias_file.write_text(json.dumps({"port_main": 9000}), encoding="utf-8")
    AliasKeySettings.load_settings()
    assert AliasKeySettings.port == 9000


def test_alias_order_primary_then_declaration_order(alias_file: Path):
    alias_file.write_text(json.dumps({"PORT": 1, "port_main": 2}), encoding="utf-8")
    AliasKeySettings.load_settings()
    assert AliasKeySettings.port == 2  # the first declared alias wins

    alias_file.write_text(json.dumps({"port": 3, "port_main": 2}), encoding="utf-8")
    AliasKeySettings.load_settings()
    assert AliasKeySettings.port == 3  # the primary key outranks every alias


def test_alias_lands_under_the_same_path(alias_file: Path):
    # every alias key is placed by the member's path=, like the primary one
    alias_file.write_text(
        json.dumps({"net": {"proxy": {"host_main": "alias.example"}}}), encoding="utf-8"
    )
    AliasKeySettings.load_settings()
    assert AliasKeySettings.host == "alias.example"


def test_alias_contains_matches_any_key(alias_file: Path):
    assert AliasKeySettings.contains_setting("port") is False
    alias_file.write_text(json.dumps({"PORT": 1}), encoding="utf-8")
    assert AliasKeySettings.contains_setting("port") is True


def test_alias_save_writes_the_primary_key_alone(alias_file: Path):
    alias_file.write_text(json.dumps({"port_main": 2}), encoding="utf-8")
    AliasKeySettings.load_settings()

    AliasKeySettings.port = 9000
    AliasKeySettings.save_setting("port")
    document = json.loads(alias_file.read_text(encoding="utf-8"))
    # the primary key is written; the alias key is a foreign line the save
    # leaves as written (delete is the pass that clears the alias keys)
    assert document == {"port": 9000, "port_main": 2}


def test_alias_delete_removes_every_key(alias_file: Path):
    alias_file.write_text(json.dumps({"port": 3, "port_main": 2, "PORT": 1}), encoding="utf-8")
    AliasKeySettings.load_settings()

    AliasKeySettings.delete_setting("port")
    document = json.loads(alias_file.read_text(encoding="utf-8"))
    # an alias left behind would resurrect the value at the next load
    assert document == {}
