"""YAMLSettings source tests (file backend through tmp_path)."""

from __future__ import annotations

import dataclasses
import enum
import logging
import re
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Iterator, List, Optional

import pytest
from ruamel.yaml import YAML

from advexp.configuration import Configuration, LibraryConfiguration, Sources
from advexp.configuration.plugin_api import NO_DEFAULT
from advexp.configuration.plugins.yaml_settings import (
    YAMLSetting,
    YAMLSettingsPlugin,
    YAMLSettingsSerializer,
    yaml_setting,
    yaml_source,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.sources import SOURCE_CHAIN_METADATA


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


CONFIGURED_NAME = "configuration.yaml"
"""The declared link's file: the fixture retargets it to its own tmp path."""


def _retarget(path: Path) -> None:
    for klass in (
        StoreConfiguration,
        EndpointConfiguration,
        ProxyPathConfiguration,
        AliasKeyConfiguration,
    ):
        klass.__settings_context__.set_class_metadata(
            SOURCE_CHAIN_METADATA, Sources(yaml_source(file=path))
        )


class StoreConfiguration(
    Configuration,
    options=yaml_source(file=CONFIGURED_NAME),
):
    host: str = yaml_setting(name="host", default="localhost")
    port: int = yaml_setting(default=9000)
    debug: bool = yaml_setting(name="debug", default=False)
    theme: Color = yaml_setting(name="theme", default=Color.RED)
    started_at: Optional[datetime] = yaml_setting(name="started_at", default=None)
    tags: List[str] = yaml_setting(name="tags", default=[])

    # a None value reads back as the document's null, like any other value
    secret_hint: Optional[str] = yaml_setting(name="secret_hint", default=None)


@dataclasses.dataclass
class Endpoint:
    host: str
    port: int = 80
    since: Optional[datetime] = None


class EndpointConfiguration(
    Configuration,
    options=yaml_source(file=CONFIGURED_NAME),
):
    primary: Optional[Endpoint] = yaml_setting(name="primary", default=None)
    mirrors: List[Endpoint] = yaml_setting(name="mirrors", default=[])


class ProxyPathConfiguration(
    Configuration,
    options=yaml_source(file=CONFIGURED_NAME),
):
    host: str = yaml_setting(name="host", path="/net/proxy", default="proxy.example")
    port: int = yaml_setting(name="port", path="/net/proxy", default=3128)
    retries: int = yaml_setting(name="retries", path="/net", default=3)


@pytest.fixture(autouse=True)
def configured_file(tmp_path) -> Iterator[Path]:
    path = tmp_path / "configuration.yaml"
    _retarget(path)
    yield path


def _write(path: Path, document: Any) -> None:
    stream = StringIO()
    YAML(typ="rt").dump(document, stream)
    path.write_text(stream.getvalue(), encoding="utf-8")


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    assert LibraryConfiguration._get_serializer_factory(YAMLSetting) is not None
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None
    assert YAMLSettingsPlugin in LibraryConfiguration.registered_plugin_classes()


def test_load_missing_file_applies_defaults(configured_file):
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "localhost"
    assert StoreConfiguration.port == 9000


def test_missing_file_names_itself_at_debug(configured_file, caplog):
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        StoreConfiguration.load_configuration()
    messages = [record.getMessage() for record in caplog.records]
    assert f"the YAML file {configured_file} does not exist, treating it as empty" in messages


def test_blank_file_reads_as_an_empty_document(configured_file, caplog):
    # a blank YAML file is valid and holds no keys: the load reads nothing
    # and the declared defaults serve — no parse error, unlike richer formats
    configured_file.write_text("", encoding="utf-8")
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "localhost"
    messages = [record.getMessage() for record in caplog.records]
    assert f"the YAML file {configured_file} contains no keys" in messages
    assert not any("does not exist" in message for message in messages)


def test_load_reads_explicit_and_pattern_names(configured_file):
    module = StoreConfiguration.__module__
    _write(
        configured_file,
        {"host": "preset", f"{module}.StoreConfiguration.port": 8080},
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "preset"
    assert StoreConfiguration.port == 8080
    assert StoreConfiguration.debug is False  # the rest keep their defaults


def test_load_converts_native_yaml_values(configured_file):
    # the parser hands out ready objects: booleans and dates native, null
    # as None, and yes/no as the strings YAML 1.2 makes of them
    configured_file.write_text(
        "debug: true\n"
        "theme: BLUE\n"
        "started_at: 2026-09-06T12:30:00\n"
        "tags:\n"
        "  - a\n"
        "  - b\n"
        "secret_hint: null\n",
        encoding="utf-8",
    )
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.debug is True
    assert StoreConfiguration.theme == Color.BLUE
    assert StoreConfiguration.started_at == datetime(2026, 9, 6, 12, 30, 0)
    assert StoreConfiguration.tags == ["a", "b"]
    assert StoreConfiguration.secret_hint is None  # the stored null, not a missing key


def test_yaml_12_yes_no_read_as_strings(configured_file):
    # yes and no are words, not booleans: a member holding one reads it by
    # its string contract
    configured_file.write_text("debug: no\n", encoding="utf-8")
    StoreConfiguration.load_configuration()
    # "no" converts by the bool contract the way any string does
    assert StoreConfiguration.debug is False


def test_date_members_read_the_native_form(configured_file):
    class CalendarConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        launch_on: date = yaml_setting(name="launch_on", default=date(2026, 1, 1))
        window: timedelta = yaml_setting(name="window", default=timedelta(minutes=30))

    configured_file.write_text("launch_on: 2026-12-01\nwindow: 0:45:00\n", encoding="utf-8")
    CalendarConfiguration.load_configuration()
    assert CalendarConfiguration.launch_on == date(2026, 12, 1)
    assert CalendarConfiguration.window == timedelta(minutes=45)


def test_unconvertible_value_falls_back_to_default(configured_file):
    _write(configured_file, {"port": "not-a-number"})
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.port == 9000


def test_foreign_keys_are_ignored_not_touched(configured_file):
    text = "someone-elses-key: 42  # prose of the file's own\nhost: preset\n"
    configured_file.write_text(text, encoding="utf-8")
    StoreConfiguration.load_configuration()
    assert StoreConfiguration.host == "preset"
    # a read-only source: the file stays exactly as it was, comments too
    assert configured_file.read_text(encoding="utf-8") == text


def test_dataclass_members_parse_from_file(configured_file):
    _write(
        configured_file,
        {
            "primary": {"host": "a.example", "port": 8443, "since": "2026-09-06T12:30:00"},
            "mirrors": [{"host": "b.example"}, {"host": "c.example", "port": 8080}],
        },
    )
    EndpointConfiguration.load_configuration()
    # stored as plain mappings of the fields, no type tags
    assert EndpointConfiguration.primary == Endpoint(
        "a.example", 8443, datetime(2026, 9, 6, 12, 30)
    )
    assert isinstance(EndpointConfiguration.primary, Endpoint)
    assert EndpointConfiguration.mirrors == [
        Endpoint("b.example"),
        Endpoint("c.example", 8080),
    ]


# ---------------------------------------------------------------------------
# document paths (path=, a JSON Pointer)
# ---------------------------------------------------------------------------


def test_path_reads_through_nested_objects(configured_file):
    _write(configured_file, {"net": {"proxy": {"host": "proxy.example", "port": 3128}}})
    ProxyPathConfiguration.load_configuration()
    assert ProxyPathConfiguration.host == "proxy.example"
    assert ProxyPathConfiguration.port == 3128


def test_path_without_leading_slash_raises_at_declaration():
    with pytest.raises(ValueError, match="must start with '/'"):

        class BrokenPathConfiguration(Configuration):
            first: str = yaml_setting(name="first", default="v", path="net/proxy")


def test_dotted_name_is_a_plain_root_key(configured_file):
    class DottedNameConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        first: str = yaml_setting(name="a.b.c", default="v")

    _write(configured_file, {"a.b.c": "w"})
    DottedNameConfiguration.load_configuration()
    assert DottedNameConfiguration.first == "w"


def test_load_path_blocked_by_scalar_applies_default(configured_file):
    _write(configured_file, {"net": 404})
    ProxyPathConfiguration.load_configuration()
    assert ProxyPathConfiguration.host == "proxy.example"


def test_index_path_reads_list_elements(configured_file):
    _write(
        configured_file,
        {"mirrors": [{"host": "a"}, {"host": "b"}]},
    )

    class MirrorConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        host: str = yaml_setting(name="host", path="/mirrors/1", default="x")

    MirrorConfiguration.load_configuration()
    assert MirrorConfiguration.host == "b"


def test_index_path_out_of_range_applies_default(configured_file):
    _write(configured_file, {"mirrors": [{"host": "a"}]})

    class ShortConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        host: str = yaml_setting(name="host", path="/mirrors/2", default="fallback")

    ShortConfiguration.load_configuration()
    assert ShortConfiguration.host == "fallback"


def test_index_path_blocked_by_scalar_element_applies_default(configured_file):
    _write(configured_file, {"mirrors": ["plain-string"]})

    class ScalarConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        host: str = yaml_setting(name="host", path="/mirrors/0", default="fallback")

    ScalarConfiguration.load_configuration()
    assert ScalarConfiguration.host == "fallback"


def test_empty_path_means_the_document_root(configured_file):
    class RootConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        first: str = yaml_setting(name="first", default="v", path="")

    _write(configured_file, {"first": "w"})
    RootConfiguration.load_configuration()
    assert RootConfiguration.first == "w"


# ---------------------------------------------------------------------------
# errors that must reach the caller
# ---------------------------------------------------------------------------


def test_corrupt_file_raises_to_caller(configured_file):
    configured_file.write_text("{not yaml", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match=re.escape(f"cannot parse the YAML configuration file {configured_file}"),
    ):
        StoreConfiguration.load_configuration()


def test_second_document_in_the_file_refused(configured_file):
    # one document per file: the reading side names the condition instead
    # of quietly reading the first of the two
    configured_file.write_text("host: a\n---\nhost: b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a single document"):
        StoreConfiguration.load_configuration()


def test_unknown_tag_refused(configured_file):
    # the configuration file is data, not code: unknown tags construct
    # nothing, and the parse fails
    configured_file.write_text("host: !!weird/value\n", encoding="utf-8")
    with pytest.raises(ValueError, match="could not determine a constructor"):
        StoreConfiguration.load_configuration()


def test_undecodable_file_raises_to_caller(configured_file):
    # a file in another encoding (UTF-16, say) is the read-side sibling
    # of a corrupt one: the load names the library and the file instead
    # of surfacing the bare codec message
    configured_file.write_bytes("host: ok\n".encode("utf-16"))
    with pytest.raises(
        ValueError, match=re.escape(f"cannot read the YAML configuration file {configured_file}")
    ):
        StoreConfiguration.load_configuration()


def test_load_tolerates_a_bom(configured_file):
    # the storing side of the family keeps a file's BOM through its
    # saves, so the reading side tolerates one too
    configured_file.write_bytes(UTF8_BOM.encode("utf-8") + b"host: remote\n")

    class BomConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    BomConfiguration.load_configuration()

    assert BomConfiguration.host == "remote"


def test_non_mapping_root_raises_to_caller(configured_file):
    configured_file.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping at the top level"):
        StoreConfiguration.load_configuration()


def test_broken_storage_path_reaches_caller(tmp_path):
    # a regular file sitting where the configuration directory belongs breaks
    # every read; the error must reach the caller, not end up in the log
    blocker = tmp_path / "blocked"
    blocker.write_text("a file, not a directory", encoding="utf-8")

    class BlockedConfiguration(
        Configuration,
        options=yaml_source(file=blocker / "configuration.yaml"),
    ):
        host: str = yaml_setting(name="host", default="localhost")

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
        options=yaml_source(file=tmp_path / "server.yaml"),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    class WindowFileConfiguration(
        Configuration,
        options=yaml_source(file=tmp_path / "window.yml"),
    ):
        width: int = yaml_setting(name="width", default=800)

    _write(tmp_path / "server.yaml", {"host": "db.example.com"})
    _write(tmp_path / "window.yml", {"width": 1024})

    ServerFileConfiguration.load_configuration()
    WindowFileConfiguration.load_configuration()
    assert ServerFileConfiguration.host == "db.example.com"
    assert WindowFileConfiguration.width == 1024


def test_the_chain_is_the_classs_own_and_inherits(tmp_path, configured_file):
    own = tmp_path / "own.yaml"
    _write(own, {"host": "from-own"})

    class BoundConfiguration(
        Configuration,
        options=yaml_source(file=own),
    ):
        host: str = yaml_setting(name="host", default="localhost")

    BoundConfiguration.load_configuration()
    assert BoundConfiguration.host == "from-own"

    # a subclass without its own chain inherits the nearest one above
    class ChildConfiguration(BoundConfiguration):
        pass

    ChildConfiguration.load_configuration()
    assert ChildConfiguration.host == "from-own"

    # a subclass with its own chain switches to it alone: the base class
    # keeps reading its own file
    other = tmp_path / "other.yaml"
    _write(other, {"host": "from-other"})

    class SwitchedConfiguration(
        BoundConfiguration,
        options=yaml_source(file=other),
    ):
        pass

    SwitchedConfiguration.load_configuration()
    assert SwitchedConfiguration.host == "from-other"
    BoundConfiguration.load_configuration()
    assert BoundConfiguration.host == "from-own"


def test_invalid_binding_fails_the_builder_call():
    with pytest.raises(TypeError, match="invalid YAML source file"):
        yaml_source(file="")


# ---------------------------------------------------------------------------
# one shared document per file (mixed attribute classes)
# ---------------------------------------------------------------------------


class TaggedYAMLSetting(YAMLSetting):
    """A registered ``YAMLSetting`` subclass with a placement parameter of its own."""

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


def tagged_yaml_setting(
    *,
    name: Optional[str] = None,
    default: Any = NO_DEFAULT,
    path: Optional[str] = None,
    tagged: bool = False,
) -> Any:
    return TaggedYAMLSetting(name=name, default=default, path=path, tagged=tagged)


class TaggedYAMLSerializer(YAMLSettingsSerializer):
    """The stock serializer, extended to relocate tagged members under one object."""

    def _setting_segments(self, setting_name: str, attr: Any) -> List[str]:
        setting = self.attribute_of(attr, TaggedYAMLSetting)
        if setting is not None and setting.tagged:
            return ["tagged", setting_name]
        return super()._setting_segments(setting_name, attr)


@pytest.fixture()
def tagged_attribute() -> Iterator[type]:
    # the registry lookup is exact: the pair resolves to its own serializer
    # class, next to the stock YAMLSetting registration
    LibraryConfiguration.register_settings_attribute(TaggedYAMLSetting, TaggedYAMLSerializer)
    yield TaggedYAMLSetting
    LibraryConfiguration._attribute_serializers.pop(TaggedYAMLSetting, None)


def test_mixed_attribute_classes_read_one_document(configured_file, tagged_attribute):
    # both serializer classes over one file read the same shared document
    # inside the pass brackets, each finding its own keys
    class MixedConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        plain: int = yaml_setting(name="plain", default=1)
        custom: int = tagged_yaml_setting(name="custom", tagged=True, default=2)

    _write(configured_file, {"plain": 10, "tagged": {"custom": 20}})
    MixedConfiguration.load_configuration()
    assert MixedConfiguration.plain == 10
    assert MixedConfiguration.custom == 20


def test_later_pass_re_reads_the_file(configured_file):
    # the shared document lives only inside the pass brackets: an external
    # edit between passes must be seen by the next one
    class RereadConfiguration(
        Configuration,
        options=yaml_source(file=configured_file),
    ):
        plain: int = yaml_setting(name="plain", default=1)

    _write(configured_file, {"plain": 1})
    RereadConfiguration.load_configuration()
    assert RereadConfiguration.plain == 1

    _write(configured_file, {"plain": 99})
    RereadConfiguration.load_configuration()
    assert RereadConfiguration.plain == 99


def test_module_is_self_sufficient(tmp_path):
    """The source's own module carries everything an application needs."""
    script = textwrap.dedent(
        """
        import os
        from pathlib import Path

        import advexp.configuration.plugins.yaml_settings as ys
        from advexp.configuration import Configuration

        os.chdir(r"{workdir}")


        class SelfSufficientConfig(
            Configuration, options=ys.yaml_source(file="self-sufficient.yaml")
        ):
            port: int = ys.yaml_setting(default=8080)


        SelfSufficientConfig.load_configuration()
        assert SelfSufficientConfig.port == 8080
        assert not Path("self-sufficient.yaml").exists()  # read-only: no file written
        """
    ).format(workdir=tmp_path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# aliases
# ---------------------------------------------------------------------------


class AliasKeyConfiguration(
    Configuration,
    options=yaml_source(file=CONFIGURED_NAME),
):
    port: int = yaml_setting(name="port", aliases=["port_main", "PORT"], default=80)
    host: str = yaml_setting(
        name="host", path="/net/proxy", aliases=["host_main"], default="localhost"
    )


@pytest.fixture
def alias_file(configured_file: Path) -> Path:
    return configured_file


def test_alias_loads_when_primary_key_is_missing(alias_file: Path):
    _write(alias_file, {"port_main": 9000})
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.port == 9000


def test_alias_order_primary_then_declaration_order(alias_file: Path):
    _write(alias_file, {"PORT": 1, "port_main": 2})
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.port == 2  # the first declared alias wins

    _write(alias_file, {"port": 3, "port_main": 2})
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.port == 3  # the primary key outranks every alias


def test_alias_lands_under_the_same_path(alias_file: Path):
    # every alias key is placed by the member's path=, like the primary one
    _write(alias_file, {"net": {"proxy": {"host_main": "alias.example"}}})
    AliasKeyConfiguration.load_configuration()
    assert AliasKeyConfiguration.host == "alias.example"
