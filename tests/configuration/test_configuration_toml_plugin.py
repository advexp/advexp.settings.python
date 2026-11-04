"""TOMLSettings source tests (file backend through tmp_path)."""

from __future__ import annotations

import dataclasses
import enum
import logging
import re
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

from advexp.configuration import AggregateLoadError, Configuration, LibraryConfiguration, Sources
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.toml_settings import (
    TOMLSetting,
    TOMLSettingsPlugin,
    TOMLSettingsSerializer,
    toml_setting,
    toml_source,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.sources import SOURCE_CHAIN_METADATA


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


CONFIGURED_NAME = "configuration.toml"
"""The declared link's file: the fixture retargets it to its own tmp path."""


def _retarget(path: Path) -> None:
    for klass in (
        StoreConfiguration,
        EndpointConfiguration,
        ProxyPathConfiguration,
        AliasAddressConfiguration,
    ):
        klass.__settings_context__.set_class_metadata(
            SOURCE_CHAIN_METADATA, Sources(toml_source(file=path))
        )


class StoreConfiguration(
    Configuration,
    options=toml_source(file=CONFIGURED_NAME),
):
    host: str = toml_setting(name="host", default="localhost")
    port: int = toml_setting(default=9000)
    debug: bool = toml_setting(name="debug", default=False)
    theme: Color = toml_setting(name="theme", default=Color.RED)
    started_at: Optional[datetime] = toml_setting(name="started_at", default=None)
    tags: List[str] = toml_setting(name="tags", default=[])

    # TOML has no null: an absent key is the only miss this member can read
    secret_hint: Optional[str] = toml_setting(name="secret_hint", default=None)


@dataclasses.dataclass
class Endpoint:
    host: str
    port: int = 80
    since: Optional[datetime] = None


class EndpointConfiguration(
    Configuration,
    options=toml_source(file=CONFIGURED_NAME),
):
    primary: Optional[Endpoint] = toml_setting(name="primary", default=None)
    mirrors: List[Endpoint] = toml_setting(name="mirrors", default=[])


class ProxyPathConfiguration(
    Configuration,
    options=toml_source(file=CONFIGURED_NAME),
):
    host: str = toml_setting(name="host", path="/net/proxy", default="proxy.example")
    port: int = toml_setting(name="port", path="/net/proxy", default=3128)
    retries: int = toml_setting(name="retries", path="/net", default=3)


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "configuration.toml"
    _retarget(path)
    yield path


def read_document(configured_file) -> Any:
    return tomllib.loads(configured_file.read_text(encoding="utf-8"))


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(TOMLSetting) is not None
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None
    assert TOMLSettingsPlugin in LibraryConfiguration.registered_plugin_classes()


def test_load_missing_file_applies_defaults(configured_file):
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "localhost"
    assert StoreConfiguration.port == 9000
    assert StoreConfiguration.debug is False
    assert StoreConfiguration.theme is Color.RED
    assert StoreConfiguration.started_at is None


def test_missing_file_names_itself_at_debug(configured_file, caplog):
    # the miss phrase of the pass cannot tell an absent file from a key
    # the document does not carry: this record is what separates the two
    # for a reader debugging an empty load
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        StoreConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the TOML file {configured_file} does not exist, treating it as empty" in messages


def test_keyless_document_names_itself_at_debug(configured_file, caplog):
    # a keyless document in a file that is there is its own case, apart
    # from an absent file: its record says the file is there and holds no
    # keys, and the absent-file record stays out
    configured_file.write_text("# nothing but a comment\n", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        StoreConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the TOML file {configured_file} contains no keys" in messages
    assert not any("does not exist" in message for message in messages)


def test_empty_file_is_a_valid_empty_document(configured_file):
    # unlike JSON, a blank TOML file parses to the empty document: it is
    # no anomaly, and the members keep their defaults
    configured_file.write_text("", encoding="utf-8")
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "localhost"
    assert StoreConfiguration.port == 9000


def test_diagnostics_name_the_full_path_of_a_relative_file(tmp_path, monkeypatch):
    # a relative file names a place in the working directory; the message
    # quotes the full path, so the exact file is not left to guess
    monkeypatch.chdir(tmp_path)

    class RelativeConfiguration(
        Configuration,
        options=toml_source(file=Path("relative.toml")),
    ):
        entry: str = toml_setting(name="entry")

    with pytest.raises(AggregateLoadError) as report:
        RelativeConfiguration.load_configuration()
    message = str(report.value.errors[0])
    assert f"key 'entry' in the TOML file {tmp_path / 'relative.toml'}" in message
    assert "is required: the TOML file provided no value" in message


def test_load_reads_explicit_and_pattern_names(configured_file):
    module = StoreConfiguration.__module__
    configured_file.write_text(
        f'host = "preset"\n\n[{module}.StoreConfiguration]\nport = 8080\n',
        encoding="utf-8",
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "preset"
    assert StoreConfiguration.port == 8080
    assert StoreConfiguration.debug is False  # the rest keep their defaults


def test_load_converts_native_toml_values(configured_file):
    configured_file.write_text(
        "\n".join(
            (
                "debug = true",
                'theme = "BLUE"',
                "started_at = 2026-09-06T12:30:00",
                'tags = ["a", "b"]',
            )
        ),
        encoding="utf-8",
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.debug is True
    assert StoreConfiguration.theme is Color.BLUE
    # the datetime is native TOML: the parser hands the value over as is
    assert StoreConfiguration.started_at == datetime(2026, 9, 6, 12, 30, 0)
    assert StoreConfiguration.tags == ["a", "b"]
    assert StoreConfiguration.secret_hint is None  # no key: the default stands


def test_unconvertible_value_falls_back_to_default(configured_file):
    configured_file.write_text('port = "not-a-number"\n', encoding="utf-8")
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.port == 9000


def test_foreign_keys_are_ignored_not_touched(configured_file):
    configured_file.write_text(
        'someone-elses-key = 42\nhost = "preset"\n',
        encoding="utf-8",
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "preset"
    # a read-only source: the document stays exactly as it was
    assert read_document(configured_file) == {
        "someone-elses-key": 42,
        "host": "preset",
    }


def test_dataclass_members_parse_from_file(configured_file):
    configured_file.write_text(
        "[primary]\n"
        'host = "a.example"\n'
        "port = 8443\n"
        'since = "2026-09-06T12:30:00"\n'
        "\n"
        "[[mirrors]]\n"
        'host = "b.example"\n'
        "\n"
        "[[mirrors]]\n"
        'host = "c.example"\n'
        "port = 8080\n",
        encoding="utf-8",
    )
    EndpointConfiguration.load_configuration()
    # stored as plain TOML tables of the fields, no type tags
    assert EndpointConfiguration.primary == Endpoint(
        "a.example", 8443, datetime(2026, 9, 6, 12, 30)
    )
    assert isinstance(EndpointConfiguration.primary, Endpoint)
    assert EndpointConfiguration.mirrors == [Endpoint("b.example"), Endpoint("c.example", 8080)]
    assert all(isinstance(mirror, Endpoint) for mirror in EndpointConfiguration.mirrors)


# ---------------------------------------------------------------------------
# document paths (path=, a JSON Pointer)
# ---------------------------------------------------------------------------


def test_path_reads_through_nested_tables(configured_file):
    configured_file.write_text(
        '[net]\nretries = 3\n\n[net.proxy]\nhost = "cache.example"\nport = 3128\n',
        encoding="utf-8",
    )
    ProxyPathConfiguration.load_configuration()
    assert ProxyPathConfiguration.host == "cache.example"
    assert ProxyPathConfiguration.port == 3128
    assert ProxyPathConfiguration.retries == 3


def test_path_without_leading_slash_raises_at_declaration():
    with pytest.raises(ValueError, match="must start with '/'"):
        TOMLSetting(name="host", path="net/proxy")


def test_dotted_name_nests_tables(configured_file):
    # the dot is TOML's table separator: the name is the member's
    # address, and the source reads it from the tables the name spells
    class DottedNameConfiguration(
        Configuration,
        options=toml_source(file=configured_file),
    ):
        host: str = toml_setting(name="net.host", default="proxy.example")

    configured_file.write_text('[net]\nhost = "dotted"\n', encoding="utf-8")
    DottedNameConfiguration.load_configuration()
    assert DottedNameConfiguration.host == "dotted"


def test_load_path_blocked_by_scalar_applies_default(configured_file):
    configured_file.write_text("net = 42\n", encoding="utf-8")
    ProxyPathConfiguration.load_configuration()
    assert ProxyPathConfiguration.host == "proxy.example"


def test_index_path_reads_list_elements(configured_file):
    class MirrorPathConfiguration(
        Configuration,
        options=toml_source(file=configured_file),
    ):
        host: str = toml_setting(name="host", path="/mirrors/1", default="mirror-b")
        timeout: int = toml_setting(name="timeout", path="/mirrors/0/net", default=5)

    configured_file.write_text(
        '[[mirrors]]\n[mirrors.net]\ntimeout = 9\n\n[[mirrors]]\nhost = "old"\n',
        encoding="utf-8",
    )
    MirrorPathConfiguration.load_configuration()
    assert MirrorPathConfiguration.host == "old"
    assert MirrorPathConfiguration.timeout == 9


def test_index_path_out_of_range_applies_default(configured_file):
    class ShortListConfiguration(
        Configuration,
        options=toml_source(file=configured_file),
    ):
        host: str = toml_setting(name="host", path="/mirrors/2", default="fallback")
        absent: str = toml_setting(name="absent", path="/nosuch/0", default="fallback")

    configured_file.write_text('[[mirrors]]\nhost = "a"\n', encoding="utf-8")
    ShortListConfiguration.load_configuration()
    assert ShortListConfiguration.host == "fallback"
    assert ShortListConfiguration.absent == "fallback"


def test_index_path_blocked_by_scalar_element_applies_default(configured_file):
    class ScalarElementConfiguration(
        Configuration,
        options=toml_source(file=configured_file),
    ):
        host: str = toml_setting(name="host", path="/mirrors/0", default="fallback")

    configured_file.write_text('mirrors = ["plain-string"]\n', encoding="utf-8")
    ScalarElementConfiguration.load_configuration()
    assert ScalarElementConfiguration.host == "fallback"


def test_empty_path_means_the_document_root(configured_file):
    class EmptyPathConfiguration(
        Configuration,
        options=toml_source(file=configured_file),
    ):
        nested: int = toml_setting(name="x", path="", default=1)
        plain: int = toml_setting(name="y", default=2)

    configured_file.write_text("x = 10\ny = 20\n", encoding="utf-8")
    EmptyPathConfiguration.load_configuration()
    # the empty pointer is the whole document: the key sits at the root
    assert EmptyPathConfiguration.nested == 10
    assert EmptyPathConfiguration.plain == 20


# ---------------------------------------------------------------------------
# errors that must reach the caller
# ---------------------------------------------------------------------------


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("[not toml", encoding="utf-8")
    with pytest.raises(
        ValueError, match=re.escape(f"cannot parse the TOML configuration file {configured_file}")
    ):
        StoreConfiguration.load_configuration()


def test_undecodable_file_raises_to_caller(configured_file):
    # a file in another encoding (UTF-16, say) is the read-side sibling
    # of a corrupt one: the load names the library and the file instead
    # of surfacing the bare codec message
    configured_file.write_bytes('host = "ok"\n'.encode("utf-16"))
    with pytest.raises(
        ValueError, match=re.escape(f"cannot read the TOML configuration file {configured_file}")
    ):
        StoreConfiguration.load_configuration()


def test_bom_file_names_the_cause(configured_file):
    # a BOM-prefixed file is refused with the BOM named as the cause —
    # not with the parser's own puzzle about an empty key
    configured_file.write_bytes(UTF8_BOM.encode("utf-8") + b'host = "ok"\n')
    with pytest.raises(
        ValueError,
        match=re.escape(f"cannot read the TOML configuration file {configured_file}")
        + ": it starts with a UTF-8 BOM",
    ):
        StoreConfiguration.load_configuration()


def test_bare_scalar_root_raises_to_caller(configured_file):
    # a TOML document is always a table; a bare scalar is a parse error the
    # caller hears named with the library, the file and the pass
    configured_file.write_text("5", encoding="utf-8")
    expected = (
        f"{StoreConfiguration.__logger_name__}: cannot parse "
        f"the TOML configuration file {configured_file}"
    )
    with pytest.raises(ValueError, match=re.escape(expected)):
        StoreConfiguration.load_configuration()


def test_broken_storage_path_reaches_caller(tmp_path):
    # a regular file sitting where the configuration directory belongs breaks
    # every read; the error must reach the caller, not end up in the log
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a directory", encoding="utf-8")

    class BlockedConfiguration(
        Configuration,
        options=toml_source(file=blocker / "configuration.toml"),
    ):
        host: str = toml_setting(name="host", default="localhost")

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
        options=toml_source(file=tmp_path / "server.toml"),
    ):
        host: str = toml_setting(name="host", default="localhost")

    class WindowFileConfiguration(
        Configuration,
        options=toml_source(file=tmp_path / "window.toml"),
    ):
        width: int = toml_setting(name="width", default=800)

    (tmp_path / "server.toml").write_text('host = "db.example.com"\n', encoding="utf-8")
    (tmp_path / "window.toml").write_text("width = 1024\n", encoding="utf-8")

    ServerFileConfiguration.load_configuration()
    WindowFileConfiguration.load_configuration()
    assert ServerFileConfiguration.host == "db.example.com"
    assert WindowFileConfiguration.width == 1024


def test_the_chain_is_the_classs_own_and_inherits(tmp_path, configured_file):
    own = tmp_path / "own.toml"
    own.write_text('host = "from-own"\n', encoding="utf-8")

    class BoundConfiguration(
        Configuration,
        options=toml_source(file=own),
    ):
        host: str = toml_setting(name="host", default="localhost")

    BoundConfiguration.load_configuration()
    assert BoundConfiguration.host == "from-own"

    # a subclass without its own chain inherits the nearest one above
    class ChildConfiguration(BoundConfiguration):
        pass

    ChildConfiguration.load_configuration()
    assert ChildConfiguration.host == "from-own"

    # a subclass with its own chain switches to it alone: the base class
    # keeps reading its own file
    other = tmp_path / "other.toml"
    other.write_text('host = "from-other"\n', encoding="utf-8")

    class SwitchedConfiguration(
        BoundConfiguration,
        options=toml_source(file=other),
    ):
        pass

    SwitchedConfiguration.load_configuration()
    assert SwitchedConfiguration.host == "from-other"
    BoundConfiguration.load_configuration()
    assert BoundConfiguration.host == "from-own"


def test_invalid_binding_fails_the_builder_call():
    # the link's file is the builder's own parameter: an invalid one fails
    # at the call, before any class statement
    with pytest.raises(TypeError, match="invalid TOML source file: must be a file path"):
        toml_source(file=None)


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
    """The stock serializer, extended to relocate tagged members under one table."""

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


def test_mixed_attribute_classes_read_one_document(configured_file, tagged_attribute):
    # both serializer classes over one file read the same shared document
    # inside the pass brackets, each finding its own keys
    class MixedConfiguration(
        Configuration,
        options=toml_source(file=configured_file),
    ):
        plain: int = toml_setting(name="plain", default=1)
        custom: int = tagged_toml_setting(name="custom", tagged=True, default=2)

    configured_file.write_text(
        "plain = 10\n\n[tagged]\ncustom = 20\n",
        encoding="utf-8",
    )
    MixedConfiguration.load_configuration()
    assert MixedConfiguration.plain == 10
    assert MixedConfiguration.custom == 20


def test_later_pass_re_reads_the_file(configured_file):
    # the shared document lives only inside the pass brackets: an external
    # edit between passes must be seen by the next one
    class RereadConfiguration(
        Configuration,
        options=toml_source(file=configured_file),
    ):
        plain: int = toml_setting(name="plain", default=1)

    configured_file.write_text("plain = 1\n", encoding="utf-8")
    RereadConfiguration.load_configuration()
    assert RereadConfiguration.plain == 1

    configured_file.write_text("plain = 99\n", encoding="utf-8")
    RereadConfiguration.load_configuration()
    assert RereadConfiguration.plain == 99


def test_module_is_self_sufficient(tmp_path):
    """The source's own module carries everything an application needs."""
    script = textwrap.dedent(
        """
        import os
        from pathlib import Path

        import advexp.configuration.plugins.toml_settings as ts
        from advexp.configuration import Configuration

        os.chdir(r"{workdir}")


        class SelfSufficientConfig(
            Configuration, options=ts.toml_source(file="self-sufficient.toml")
        ):
            port: int = ts.toml_setting(default=8080)


        SelfSufficientConfig.load_configuration()
        assert SelfSufficientConfig.port == 8080
        assert not Path("self-sufficient.toml").exists()  # read-only: no file written
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# aliases: several addresses of one member, first found wins
# ---------------------------------------------------------------------------


class AliasAddressConfiguration(
    Configuration,
    options=toml_source(file=CONFIGURED_NAME),
):
    port: int = toml_setting(name="net.port", aliases=["port_main", "PORT"], default=80)


def test_alias_loads_when_primary_address_is_missing(configured_file):
    # an alias is a full address: its dots nest into tables on their own
    configured_file.write_text("port_main = 9000\n", encoding="utf-8")
    AliasAddressConfiguration.load_configuration()
    assert AliasAddressConfiguration.port == 9000


def test_alias_order_primary_then_declaration_order(configured_file):
    configured_file.write_text("PORT = 1\nport_main = 2\n", encoding="utf-8")
    AliasAddressConfiguration.load_configuration()
    assert AliasAddressConfiguration.port == 2  # the first declared alias wins

    configured_file.write_text("[net]\nport = 3\nport_main = 2\n", encoding="utf-8")
    AliasAddressConfiguration.load_configuration()
    assert AliasAddressConfiguration.port == 3  # the primary address outranks every alias
