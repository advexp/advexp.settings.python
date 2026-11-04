"""JSONSettings source tests (file backend through tmp_path)."""

from __future__ import annotations

import dataclasses
import enum
import json
import logging
import re
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, List, Optional

import pytest

from advexp.configuration import AggregateLoadError, Configuration, LibraryConfiguration, Sources
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.json_settings import (
    JSONSetting,
    JSONSettingsPlugin,
    JSONSettingsSerializer,
    json_setting,
    json_source,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.sources import SOURCE_CHAIN_METADATA


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


CONFIGURED_NAME = "configuration.json"
"""The declared link's file: the fixture retargets it to its own tmp path."""


def _retarget(path: Path) -> None:
    for klass in (
        StoreConfiguration,
        EndpointConfiguration,
        ProxyPathConfiguration,
        AliasKeyConfiguration,
    ):
        klass.__settings_context__.set_class_metadata(
            SOURCE_CHAIN_METADATA, Sources(json_source(file=path))
        )


class StoreConfiguration(
    Configuration,
    options=json_source(file=CONFIGURED_NAME),
):
    host: str = json_setting(name="host", default="localhost")
    port: int = json_setting(default=9000)
    debug: bool = json_setting(name="debug", default=False)
    theme: Color = json_setting(name="theme", default=Color.RED)
    started_at: Optional[datetime] = json_setting(name="started_at", default=None)
    tags: List[str] = json_setting(name="tags", default=[])

    # a None value reads back as null, like any other value
    secret_hint: Optional[str] = json_setting(name="secret_hint", default=None)


@dataclasses.dataclass
class Endpoint:
    host: str
    port: int = 80
    since: Optional[datetime] = None


class EndpointConfiguration(
    Configuration,
    options=json_source(file=CONFIGURED_NAME),
):
    primary: Optional[Endpoint] = json_setting(name="primary", default=None)
    mirrors: List[Endpoint] = json_setting(name="mirrors", default=[])


class ProxyPathConfiguration(
    Configuration,
    options=json_source(file=CONFIGURED_NAME),
):
    host: str = json_setting(name="host", path="/net/proxy", default="proxy.example")
    port: int = json_setting(name="port", path="/net/proxy", default=3128)
    retries: int = json_setting(name="retries", path="/net", default=3)


@pytest.fixture(autouse=True)
def configured_file(tmp_path) -> Iterator[Path]:
    path = tmp_path / "configuration.json"
    _retarget(path)
    yield path


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(JSONSetting) is not None
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None
    assert JSONSettingsPlugin in LibraryConfiguration.registered_plugin_classes()


def test_load_missing_file_applies_defaults(configured_file):
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "localhost"
    assert StoreConfiguration.port == 9000
    assert StoreConfiguration.debug is False
    assert StoreConfiguration.theme == Color.RED
    assert StoreConfiguration.started_at is None


def test_missing_file_names_itself_at_debug(configured_file, caplog):
    # the miss phrase of the pass cannot tell an absent file from a key
    # the document does not carry: this record is what separates the two
    # for a reader debugging an empty load
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        StoreConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the JSON file {configured_file} does not exist, treating it as empty" in messages


def test_keyless_document_names_itself_at_debug(configured_file, caplog):
    # an empty object in a file that is there is its own case, apart from
    # an absent file: its record says the file is there and holds no
    # keys, and the absent-file record stays out
    configured_file.write_text("{}", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        StoreConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the JSON file {configured_file} contains no keys" in messages
    assert not any("does not exist" in message for message in messages)


def test_diagnostics_name_the_full_path_of_a_relative_file(tmp_path, monkeypatch):
    # a relative file names a place in the working directory; the message
    # quotes the full path, so the exact file is not left to guess
    monkeypatch.chdir(tmp_path)

    class RelativeConfiguration(
        Configuration,
        options=json_source(file=Path("relative.json")),
    ):
        entry: str = json_setting(name="entry")

    with pytest.raises(AggregateLoadError) as report:
        RelativeConfiguration.load_configuration()
    message = str(report.value.errors[0])
    assert f"key 'entry' in the JSON file {tmp_path / 'relative.json'}" in message
    assert "is required: the JSON file provided no value" in message


def test_load_reads_explicit_and_pattern_names(configured_file):
    module = StoreConfiguration.__module__
    configured_file.write_text(
        json.dumps({"host": "preset", f"{module}.StoreConfiguration.port": 8080}),
        encoding="utf-8",
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "preset"
    assert StoreConfiguration.port == 8080
    assert StoreConfiguration.debug is False  # the rest keep their defaults


def test_load_converts_native_json_values(configured_file):
    configured_file.write_text(
        json.dumps(
            {
                "debug": True,
                "theme": "BLUE",
                "started_at": "2026-09-06T12:30:00",
                "tags": ["a", "b"],
                "secret_hint": None,
            }
        ),
        encoding="utf-8",
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.debug is True
    assert StoreConfiguration.theme is Color.BLUE
    assert StoreConfiguration.started_at == datetime(2026, 9, 6, 12, 30, 0)
    assert StoreConfiguration.tags == ["a", "b"]
    assert StoreConfiguration.secret_hint is None  # the stored null, not a missing key


def test_unconvertible_value_falls_back_to_default(configured_file):
    configured_file.write_text(json.dumps({"port": "not-a-number"}), encoding="utf-8")
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.port == 9000


def test_foreign_keys_are_ignored_not_touched(configured_file):
    configured_file.write_text(
        json.dumps({"someone-elses-key": 42, "host": "preset"}), encoding="utf-8"
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "preset"
    # a read-only source: the document stays exactly as it was
    assert json.loads(configured_file.read_text(encoding="utf-8")) == {
        "someone-elses-key": 42,
        "host": "preset",
    }


def test_dataclass_members_parse_from_file(configured_file):
    configured_file.write_text(
        json.dumps(
            {
                "primary": {"host": "a.example", "port": 8443, "since": "2026-09-06T12:30:00"},
                "mirrors": [{"host": "b.example"}, {"host": "c.example", "port": 8080}],
            }
        ),
        encoding="utf-8",
    )
    EndpointConfiguration.load_configuration()
    # stored as plain JSON objects of the fields, no type tags
    assert EndpointConfiguration.primary == Endpoint(
        "a.example", 8443, datetime(2026, 9, 6, 12, 30)
    )
    assert isinstance(EndpointConfiguration.primary, Endpoint)
    assert EndpointConfiguration.mirrors == [Endpoint("b.example"), Endpoint("c.example", 8080)]
    assert all(isinstance(mirror, Endpoint) for mirror in EndpointConfiguration.mirrors)


# ---------------------------------------------------------------------------
# document paths (path=, a JSON Pointer)
# ---------------------------------------------------------------------------


def test_path_reads_through_nested_objects(configured_file):
    configured_file.write_text(
        json.dumps({"net": {"proxy": {"host": "cache.example", "port": 3128}, "retries": 3}}),
        encoding="utf-8",
    )
    ProxyPathConfiguration.load_configuration()
    assert ProxyPathConfiguration.host == "cache.example"
    assert ProxyPathConfiguration.port == 3128
    assert ProxyPathConfiguration.retries == 3


def test_path_without_leading_slash_raises_at_declaration():
    with pytest.raises(ValueError, match="must start with '/'"):
        JSONSetting(name="host", path="net/proxy")


def test_dotted_name_is_a_plain_root_key(configured_file):
    class DottedNameConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        host: str = json_setting(name="net.host", default="proxy.example")

    configured_file.write_text(json.dumps({"net.host": "dotted"}), encoding="utf-8")
    DottedNameConfiguration.load_configuration()
    assert DottedNameConfiguration.host == "dotted"


def test_load_path_blocked_by_scalar_applies_default(configured_file):
    configured_file.write_text(json.dumps({"net": 42}), encoding="utf-8")
    ProxyPathConfiguration.load_configuration()
    assert ProxyPathConfiguration.host == "proxy.example"


def test_index_path_reads_list_elements(configured_file):
    class MirrorPathConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        host: str = json_setting(name="host", path="/mirrors/1", default="mirror-b")
        timeout: int = json_setting(name="timeout", path="/mirrors/0/net", default=5)

    configured_file.write_text(
        json.dumps({"mirrors": [{"net": {"timeout": 9}}, {"host": "old"}]}),
        encoding="utf-8",
    )
    MirrorPathConfiguration.load_configuration()
    assert MirrorPathConfiguration.host == "old"
    assert MirrorPathConfiguration.timeout == 9


def test_index_path_out_of_range_applies_default(configured_file):
    class ShortListConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        host: str = json_setting(name="host", path="/mirrors/2", default="fallback")
        absent: str = json_setting(name="absent", path="/nosuch/0", default="fallback")

    configured_file.write_text(json.dumps({"mirrors": [{"host": "a"}]}), encoding="utf-8")
    ShortListConfiguration.load_configuration()
    assert ShortListConfiguration.host == "fallback"
    assert ShortListConfiguration.absent == "fallback"


def test_index_path_blocked_by_scalar_element_applies_default(configured_file):
    class ScalarElementConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        host: str = json_setting(name="host", path="/mirrors/0", default="fallback")

    configured_file.write_text(json.dumps({"mirrors": ["plain-string"]}), encoding="utf-8")
    ScalarElementConfiguration.load_configuration()
    assert ScalarElementConfiguration.host == "fallback"


def test_empty_path_means_the_document_root(configured_file):
    class EmptyPathConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        nested: int = json_setting(name="x", path="", default=1)
        plain: int = json_setting(name="y", default=2)

    configured_file.write_text(json.dumps({"x": 10, "y": 20}), encoding="utf-8")
    EmptyPathConfiguration.load_configuration()
    # the empty pointer is the whole document: the key sits at the root
    assert EmptyPathConfiguration.nested == 10
    assert EmptyPathConfiguration.plain == 20


# ---------------------------------------------------------------------------
# errors that must reach the caller
# ---------------------------------------------------------------------------


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(
        ValueError, match=re.escape(f"cannot parse the JSON configuration file {configured_file}")
    ):
        StoreConfiguration.load_configuration()


def test_undecodable_file_raises_to_caller(configured_file):
    # a file in another encoding (UTF-16, say) is the read-side sibling
    # of a corrupt one: the load names the library and the file instead
    # of surfacing the bare codec message
    configured_file.write_bytes('{\n  "host": "ok"\n}\n'.encode("utf-16"))
    with pytest.raises(
        ValueError, match=re.escape(f"cannot read the JSON configuration file {configured_file}")
    ):
        StoreConfiguration.load_configuration()


def test_load_tolerates_a_bom(configured_file):
    # the storing side of the family keeps a file's BOM through its
    # saves, so the reading side tolerates one too
    configured_file.write_bytes(UTF8_BOM.encode("utf-8") + b'{\n  "host": "remote"\n}\n')

    class BomConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        host: str = json_setting(name="host", default="localhost")

    BomConfiguration.load_configuration()

    assert BomConfiguration.host == "remote"


def test_empty_file_raises_to_caller_with_the_file_path(configured_file):
    # an empty file is not an absent one: the load names the library that
    # failed and the file it cannot parse instead of surfacing the bare
    # parser message
    configured_file.write_text("", encoding="utf-8")
    expected = (
        f"{StoreConfiguration.__logger_name__}: cannot parse "
        f"the JSON configuration file {configured_file}"
    )
    with pytest.raises(ValueError, match=re.escape(expected)):
        StoreConfiguration.load_configuration()


def test_non_object_root_raises_to_caller(configured_file):
    configured_file.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="object at the top level"):
        StoreConfiguration.load_configuration()


def test_broken_storage_path_reaches_caller(tmp_path):
    # a regular file sitting where the configuration directory belongs breaks
    # every read; the error must reach the caller, not end up in the log
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a directory", encoding="utf-8")

    class BlockedConfiguration(
        Configuration,
        options=json_source(file=blocker / "configuration.json"),
    ):
        host: str = json_setting(name="host", default="localhost")

    with pytest.raises(OSError):
        BlockedConfiguration.load_configuration()


# ---------------------------------------------------------------------------
# mutable value isolation
# ---------------------------------------------------------------------------


def test_mutable_default_survives_in_place_mutation(configured_file):
    StoreConfiguration.load_configuration()  # no file: members get default copies
    StoreConfiguration.tags.append("mutated")  # in-place change of the stored copy

    StoreConfiguration.load_configuration()  # defaults come from the attribute again
    assert StoreConfiguration.tags == []  # the declared default was not corrupted


# ---------------------------------------------------------------------------
# per-class file bindings
# ---------------------------------------------------------------------------


def test_each_class_in_own_file(tmp_path):
    # each class's link names its own file, nothing module-wide exists
    class ServerFileConfiguration(
        Configuration,
        options=json_source(file=tmp_path / "server.json"),
    ):
        host: str = json_setting(name="host", default="localhost")

    class WindowFileConfiguration(
        Configuration,
        options=json_source(file=tmp_path / "window.json"),
    ):
        width: int = json_setting(name="width", default=800)

    (tmp_path / "server.json").write_text(json.dumps({"host": "db.example.com"}), encoding="utf-8")
    (tmp_path / "window.json").write_text(json.dumps({"width": 1024}), encoding="utf-8")

    ServerFileConfiguration.load_configuration()
    WindowFileConfiguration.load_configuration()
    assert ServerFileConfiguration.host == "db.example.com"
    assert WindowFileConfiguration.width == 1024


def test_the_chain_is_the_classs_own_and_inherits(tmp_path, configured_file):
    own = tmp_path / "own.json"
    own.write_text(json.dumps({"host": "from-own"}), encoding="utf-8")

    class BoundConfiguration(
        Configuration,
        options=json_source(file=own),
    ):
        host: str = json_setting(name="host", default="localhost")

    BoundConfiguration.load_configuration()
    assert BoundConfiguration.host == "from-own"

    # a subclass without its own chain inherits the nearest one above
    class ChildConfiguration(BoundConfiguration):
        pass

    ChildConfiguration.load_configuration()
    assert ChildConfiguration.host == "from-own"

    # a subclass with its own chain switches to it alone: the base class
    # keeps reading its own file
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"host": "from-other"}), encoding="utf-8")

    class SwitchedConfiguration(
        BoundConfiguration,
        options=json_source(file=other),
    ):
        pass

    SwitchedConfiguration.load_configuration()
    assert SwitchedConfiguration.host == "from-other"
    BoundConfiguration.load_configuration()
    assert BoundConfiguration.host == "from-own"


def test_invalid_binding_fails_the_builder_call():
    # the link's file is the builder's own parameter: an invalid one fails
    # at the call, before any class statement
    with pytest.raises(TypeError, match="invalid JSON source file: must be a file path"):
        json_source(file=None)


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


def test_mixed_attribute_classes_read_one_document(configured_file, tagged_attribute):
    # both serializer classes over one file read the same shared document
    # inside the pass brackets, each finding its own keys
    class MixedConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        plain: int = json_setting(name="plain", default=1)
        custom: int = tagged_json_setting(name="custom", tagged=True, default=2)

    configured_file.write_text(
        json.dumps({"plain": 10, "tagged": {"custom": 20}}), encoding="utf-8"
    )
    MixedConfiguration.load_configuration()
    assert MixedConfiguration.plain == 10
    assert MixedConfiguration.custom == 20


def test_later_pass_re_reads_the_file(configured_file):
    # the shared document lives only inside the pass brackets: an external
    # edit between passes must be seen by the next one
    class RereadConfiguration(
        Configuration,
        options=json_source(file=configured_file),
    ):
        plain: int = json_setting(name="plain", default=1)

    configured_file.write_text(json.dumps({"plain": 1}), encoding="utf-8")
    RereadConfiguration.load_configuration()
    assert RereadConfiguration.plain == 1

    configured_file.write_text(json.dumps({"plain": 99}), encoding="utf-8")
    RereadConfiguration.load_configuration()
    assert RereadConfiguration.plain == 99


def test_module_is_self_sufficient(tmp_path):
    """The source's own module carries everything an application needs."""
    script = textwrap.dedent(
        """
        import os
        from pathlib import Path

        import advexp.configuration.plugins.json_settings as js
        from advexp.configuration import Configuration

        os.chdir(r"{workdir}")


        class SelfSufficientConfig(
            Configuration, options=js.json_source(file="self-sufficient.json")
        ):
            port: int = js.json_setting(default=8080)


        SelfSufficientConfig.load_configuration()
        assert SelfSufficientConfig.port == 8080
        assert not Path("self-sufficient.json").exists()  # read-only: no file written
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# aliases: several keys of one member, first found wins
# ---------------------------------------------------------------------------


class AliasKeyConfiguration(
    Configuration,
    options=json_source(file=CONFIGURED_NAME),
):
    port: int = json_setting(name="port", aliases=["port_main", "PORT"], default=80)
    host: str = json_setting(
        name="host", path="/net/proxy", aliases=["host_main"], default="localhost"
    )


@pytest.fixture
def alias_file(configured_file: Path) -> Path:
    return configured_file


def test_alias_loads_when_primary_key_is_missing(alias_file: Path):
    alias_file.write_text(json.dumps({"port_main": 9000}), encoding="utf-8")
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.port == 9000


def test_alias_order_primary_then_declaration_order(alias_file: Path):
    alias_file.write_text(json.dumps({"PORT": 1, "port_main": 2}), encoding="utf-8")
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.port == 2  # the first declared alias wins

    alias_file.write_text(json.dumps({"port": 3, "port_main": 2}), encoding="utf-8")
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.port == 3  # the primary key outranks every alias


def test_alias_lands_under_the_same_path(alias_file: Path):
    # every alias key is placed by the member's path=, like the primary one
    alias_file.write_text(
        json.dumps({"net": {"proxy": {"host_main": "alias.example"}}}), encoding="utf-8"
    )
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.host == "alias.example"
