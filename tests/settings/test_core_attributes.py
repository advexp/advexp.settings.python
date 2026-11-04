"""Core contract tests: attributes, descriptor storage, metaclass, context."""

from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import enum
import ipaddress
import json
import logging
import os
import uuid
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path
from typing import (
    AbstractSet,
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from zoneinfo import ZoneInfo

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import tomlkit
from ruamel.yaml import YAML as _RuamelYAML

from advexp.settings import (
    LibraryConfiguration,
    PluginNotEnabledError,
    SecretBytes,
    SecretStr,
    Settings,
    SettingValidationError,
)

# noinspection PyProtectedMember
from advexp.settings._internal.non_storage_setting import NonStorageSetting, non_storage_setting
from advexp.settings.plugin_api import (
    NO_DEFAULT,
    NOT_FOUND,
    AttributeSerializerBinding,
    ISerializerNotificationSink,
    ISettingsSerializer,
    ISettingsSerializerWishes,
    SettingsAttribute,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings.plugins.environment.variables import (
    EnvironmentVariablesPlugin,
    environment_variable_setting,
)

# noinspection PyProtectedMember
from advexp.settings_base.conversion import (
    correct_type,
    to_json_value,
    to_storage_string,
    to_toml_value,
    to_yaml_value,
)

# noinspection PyProtectedMember
from advexp.settings_base.names import get_full_setting_name

# noinspection PyProtectedMember
from advexp.settings_base.setting_descriptor import SettingDescriptor

# ---------------------------------------------------------------------------
# attributes & descriptor behavior
# ---------------------------------------------------------------------------


class SimpleSettings(Settings):
    flag: bool = non_storage_setting(default=False)
    text: str = non_storage_setting(default="fallback")
    nothing: Optional[str] = non_storage_setting(default=None)


def test_defaults_resolution():
    assert SimpleSettings.flag is False
    assert SimpleSettings.text == "fallback"
    assert SimpleSettings.nothing is None  # explicit None default


def test_attribute_instance_is_replaced_by_descriptor():
    assert isinstance(vars(SimpleSettings)["flag"], SettingDescriptor)
    member = SimpleSettings.__settings_members__["flag"]
    assert member.attribute.default is False
    assert member.attribute.bound_name == "flag"


def test_no_default_uses_sentinel():
    # the sentinel state is the base attribute machinery: family factories
    # declare optional members with it, so the base class carries it alone
    class NoDefault(Settings):
        count: Optional[int] = SettingsAttribute(default=NO_DEFAULT)

    member = NoDefault.__settings_members__["count"]
    assert member.descriptor.resolved_default() is None
    assert member.attribute.default is NO_DEFAULT
    attribute = member.attribute
    assert isinstance(attribute, SettingsAttribute)
    assert attribute.default_in_use is False


def test_own_contract_field_names_in_a_subclass_do_not_clobber_the_storage():
    class CachedDefaultAttribute(SettingsAttribute):
        # the subclass's own _name/_default/_bound_name with the plain
        # names: the base's contract storage is name-mangled, so the two
        # never collide
        def __init__(self, *, name=None, default=NO_DEFAULT, cache=""):
            super().__init__(name=name, default=default)
            self._default = cache
            self._name = f"own:{name}"
            self._bound_name = "own bookkeeping"

    attr = CachedDefaultAttribute(name="n", default=1, cache="my cache")
    assert attr.name == "n"
    assert attr.default == 1
    assert attr.default_in_use is True
    assert attr.bound_name is None
    # the subclass's own same-named storage kept its values
    assert attr._default == "my cache"
    assert attr._name == "own:n"
    assert attr._bound_name == "own bookkeeping"


def test_base_attribute_construction_and_argument_validation():
    attr = SettingsAttribute(name="n", default=1)
    assert attr.name == "n"
    assert attr.default == 1
    assert attr.bound_name is None

    # keyword-only parameters: the errors are Python's own
    with pytest.raises(TypeError, match="positional argument"):
        SettingsAttribute("n")
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        # the misspelled keyword is the point: a bogus name must hit this error path
        SettingsAttribute(nmae="n")


def test_aliases_declaration_and_validation():
    attr = SettingsAttribute(name="n", default=1, aliases=["a", "b"])
    assert attr.aliases == ("a", "b")  # stored as a tuple, in the declared order

    plain = SettingsAttribute(name="n", default=1)
    assert plain.aliases == ()  # no aliases= declared: the empty tuple
    assert SettingsAttribute(name="n", default=1, aliases=[]).aliases == ()

    # a bare string is a sequence of characters, not a sequence of names
    with pytest.raises(
        TypeError, match=r"aliases must be a sequence of non-empty strings, got str"
    ):
        SettingsAttribute(name="n", default=1, aliases="APP_TTL")

    # a set has no order, and the alias order is the lookup order
    with pytest.raises(
        TypeError, match=r"aliases must be a sequence of non-empty strings, got set"
    ):
        SettingsAttribute(name="n", default=1, aliases={"APP_TTL"})

    with pytest.raises(TypeError, match=r"aliases must be a sequence of non-empty strings, got ''"):
        SettingsAttribute(name="n", default=1, aliases=["APP_TTL", ""])

    with pytest.raises(
        ValueError, match=r"aliases must not repeat the address given by name=: 'n'"
    ):
        SettingsAttribute(name="n", default=1, aliases=["n"])

    with pytest.raises(ValueError, match=r"aliases must not contain the same address twice: 'a'"):
        SettingsAttribute(name="n", default=1, aliases=["a", "a"])


def test_attribute_instances_do_not_share_contract_fields():
    first = SettingsAttribute(name="one", default=1)
    second = SettingsAttribute(name="two")

    assert first.name == "one"
    assert second.name == "two"
    assert first.default == 1
    assert second.default is NO_DEFAULT

    # the binding write on one attribute must not leak into another
    first.bound_name = "first"
    assert second.bound_name is None


def test_mutable_default_survives_in_place_mutation():
    class TagsSettings(Settings):
        tags: List[str] = non_storage_setting(default=[])

    TagsSettings.reset_settings()
    TagsSettings.tags.append("mutated")  # in-place change of the stored copy

    TagsSettings.reset_settings()  # defaults come from the attribute again
    assert TagsSettings.tags == []  # the declared default was not corrupted


def test_unset_mutable_default_read_returns_fresh_copy():
    class FreshTagsSettings(Settings):
        tags: List[str] = non_storage_setting(default=[])

    FreshTagsSettings.tags.append("mutated")  # append to an unset member's copy

    assert FreshTagsSettings.tags == []  # the read handed out a copy, not the default


def test_mutable_default_not_shared_between_classes_sharing_the_attribute():
    class TagsBase(Settings):
        tags: List[str] = non_storage_setting(default=[])

    class TagsDerived(TagsBase):
        pass  # the member (and its attribute object) is inherited, not cloned

    TagsBase.reset_settings()
    TagsBase.tags.append("mutated")

    TagsDerived.reset_settings()
    assert TagsDerived.tags == []  # sibling class sees the pristine default


def test_class_level_assignment_goes_to_storage():
    SimpleSettings.flag = True
    assert SimpleSettings.flag is True
    # descriptor stays intact, storage holds the value
    assert isinstance(vars(SimpleSettings)["flag"], SettingDescriptor)
    assert SimpleSettings.__settings_values__["flag"] is True


def test_instance_access_shares_class_storage():
    SimpleSettings.text = "via-class"
    instance = SimpleSettings()
    assert instance.text == "via-class"
    instance.text = "via-instance"
    assert SimpleSettings.text == "via-instance"


def test_delete_setting_member_is_rejected():
    with pytest.raises(TypeError, match="delete_setting"):
        del SimpleSettings.flag


def test_non_setting_attribute_behaves_normally():
    setattr(SimpleSettings, "extra", 42)
    assert getattr(SimpleSettings, "extra") == 42
    delattr(SimpleSettings, "extra")
    assert not hasattr(SimpleSettings, "extra")


def test_inheritance_composes_members_with_separate_storage():
    class Base(Settings):
        flag: bool = non_storage_setting(default=False)

    class Derived(Base):
        extra: int = non_storage_setting(default=5)

    assert set(Derived.__settings_members__) == {"flag", "extra"}
    Derived.flag = True
    assert Base.flag is False  # base storage untouched
    assert Derived.flag is True


def test_reset_settings_resets_values():
    SimpleSettings.flag = True
    SimpleSettings.reset_settings()
    assert SimpleSettings.flag is False


def test_annotations_are_resolved():
    members = SimpleSettings.__settings_members__
    assert members["flag"].annotation is bool
    assert members["nothing"].annotation is Optional[str]


# ---------------------------------------------------------------------------
# metadata & plugins
# ---------------------------------------------------------------------------


class MetadataSettings(Settings):
    flag: bool = non_storage_setting(default=False)


def test_setting_metadata_roundtrip():
    MetadataSettings.set_setting_metadata("flag", "my-key", "my-value")
    assert MetadataSettings.get_setting_metadata("flag", "my-key") == "my-value"
    assert MetadataSettings.get_setting_metadata("flag", "missing", "fallback") == "fallback"

    # None is a stored value, not a removal: it wins over the default
    MetadataSettings.set_setting_metadata("flag", "my-key", None)
    assert MetadataSettings.get_setting_metadata("flag", "my-key", "gone") is None

    MetadataSettings.delete_setting_metadata("flag", "my-key")
    assert MetadataSettings.get_setting_metadata("flag", "my-key", "gone") == "gone"


def test_setting_metadata_all_snapshot():
    MetadataSettings.set_setting_metadata("flag", "all-a", {"nested": 1})
    MetadataSettings.set_setting_metadata("flag", "all-b", 2)
    snapshot = MetadataSettings.get_setting_all_metadata("flag")
    assert snapshot == {"all-a": {"nested": 1}, "all-b": 2}

    snapshot["all-a"]["nested"] = 99  # the snapshot is a copy
    snapshot["all-c"] = 3
    again = MetadataSettings.get_setting_all_metadata(lambda s: s.flag)  # getter form
    assert again == {"all-a": {"nested": 1}, "all-b": 2}

    MetadataSettings.delete_setting_metadata("flag", "all-a")
    MetadataSettings.delete_setting_metadata("flag", "all-b")
    assert MetadataSettings.get_setting_all_metadata("flag") == {}  # nothing stored left
    with pytest.raises(KeyError):  # the declared-member check applies here too
        MetadataSettings.get_setting_all_metadata("nope")


def test_class_metadata_roundtrip():
    MetadataSettings.set_class_metadata("key", 123)
    assert MetadataSettings.get_class_metadata("key") == 123

    MetadataSettings.set_class_metadata("key", None)
    assert MetadataSettings.get_class_metadata("key", "gone") is None

    MetadataSettings.delete_class_metadata("key")
    assert MetadataSettings.get_class_metadata("key", "gone") == "gone"


def test_setting_metadata_contains():
    # contains tells a stored None from a missing entry: get answers its
    # default for both
    assert not MetadataSettings.contains_setting_metadata("flag", "c-key")
    MetadataSettings.set_setting_metadata("flag", "c-key", "value")
    assert MetadataSettings.contains_setting_metadata("flag", "c-key")

    MetadataSettings.set_setting_metadata("flag", "c-key", None)
    assert MetadataSettings.get_setting_metadata("flag", "c-key", "gone") is None
    assert MetadataSettings.contains_setting_metadata("flag", "c-key")

    MetadataSettings.delete_setting_metadata("flag", "c-key")
    assert not MetadataSettings.contains_setting_metadata("flag", "c-key")
    # a member with no metadata at all
    assert not MetadataSettings.contains_setting_metadata("flag", "never-set")


def test_class_metadata_contains():
    assert not MetadataSettings.contains_class_metadata("c-key")
    MetadataSettings.set_class_metadata("c-key", None)
    assert MetadataSettings.get_class_metadata("c-key", "gone") is None
    assert MetadataSettings.contains_class_metadata("c-key")

    MetadataSettings.delete_class_metadata("c-key")
    assert not MetadataSettings.contains_class_metadata("c-key")


def test_class_all_metadata_snapshot_and_clear():
    MetadataSettings.set_class_metadata("all-a", {"nested": 1})
    MetadataSettings.set_class_metadata("all-b", 2)

    snapshot = MetadataSettings.get_class_all_metadata()
    assert snapshot["all-a"] == {"nested": 1}
    assert snapshot["all-b"] == 2
    snapshot["all-a"]["nested"] = 99  # the snapshot is a copy
    snapshot["all-c"] = 3
    assert MetadataSettings.get_class_metadata("all-a") == {"nested": 1}

    MetadataSettings.delete_class_all_metadata()
    assert MetadataSettings.get_class_all_metadata() == {}  # the whole storage went
    assert not MetadataSettings.contains_class_metadata("all-a")
    MetadataSettings.delete_class_all_metadata()  # nothing stored: not an error


def test_context_logger_rides_the_distribution_channel():
    # the channel is declared by the distribution's root settings class and
    # inherited by every subclass: the base routes the machinery's records
    # (load/save/delete/sync errors and warnings) through the context
    class InheritedChannelSettings(Settings):
        pass

    assert InheritedChannelSettings.__settings_context__.logger.name == "advexp.settings"


def test_context_logger_honors_a_channel_redeclared_on_a_subclass():
    # a sibling distribution (advexp.configuration) will declare its own root
    # the same way; the machinery then logs on that channel for its classes
    class ReroutedChannelSettings(Settings):
        __logger_name__ = "probe.channel"

    assert ReroutedChannelSettings.__settings_context__.logger.name == "probe.channel"


def test_context_contains_metadata():
    # the context form is what backend authors reach through self.context
    context = MetadataSettings.get_plugin(EnvironmentVariablesPlugin).context
    assert not context.contains_setting_metadata("flag", "ctx")
    assert not context.contains_class_metadata("ctx")

    context.set_setting_metadata("flag", "ctx", None)
    context.set_class_metadata("ctx", None)
    assert context.contains_setting_metadata("flag", "ctx")
    assert context.contains_class_metadata("ctx")

    context.delete_setting_metadata("flag", "ctx")
    context.delete_class_metadata("ctx")
    assert not context.contains_setting_metadata("flag", "ctx")
    assert not context.contains_class_metadata("ctx")


def test_context_metadata_accepts_getter():
    # the context takes the same reference forms as the facade: written via
    # a getter lambda, read back through the member-name string and back
    context = MetadataSettings.get_plugin(EnvironmentVariablesPlugin).context
    context.set_setting_metadata(lambda s: s.flag, "g-key", "value")
    assert context.get_setting_metadata("flag", "g-key") == "value"
    assert context.get_setting_metadata(lambda s: s.flag, "g-key") == "value"
    assert context.contains_setting_metadata(lambda s: s.flag, "g-key")
    context.delete_setting_metadata(lambda s: s.flag, "g-key")
    assert not context.contains_setting_metadata("flag", "g-key")


def test_setting_metadata_rejects_undeclared_member():
    # a name the class does not declare could never be read back — no
    # backend iterates anything but declared members — so it is a typo, and
    # every metadata operation says so instead of playing along
    with pytest.raises(KeyError, match="'nope' is not a setting of MetadataSettings"):
        MetadataSettings.set_setting_metadata("nope", "k", "v")
    with pytest.raises(KeyError, match="'nope' is not a setting of MetadataSettings"):
        MetadataSettings.set_setting_metadata(lambda s: s.nope, "k", "v")
    with pytest.raises(KeyError):
        MetadataSettings.get_setting_metadata("nope", "k")
    with pytest.raises(KeyError):
        MetadataSettings.contains_setting_metadata("nope", "k")
    with pytest.raises(KeyError):
        MetadataSettings.delete_setting_metadata("nope", "k")
    # the check lives in the context: backend code through self.context too
    context = MetadataSettings.get_plugin(EnvironmentVariablesPlugin).context
    with pytest.raises(KeyError):
        context.set_setting_metadata("nope", "k", "v")


def test_setting_metadata_accepts_inherited_member():
    class SubMetadataSettings(MetadataSettings):
        extra: int = non_storage_setting(default=1)

    # an inherited member is declared on the subclass as well
    SubMetadataSettings.set_setting_metadata("flag", "k", "value")
    assert SubMetadataSettings.get_setting_metadata("flag", "k") == "value"


def test_metadata_is_isolated_from_caller():
    # set stores a deep copy: mutating the caller's object afterward does
    # not rewrite the stored metadata
    layout = {"window": {"x": 1}}
    MetadataSettings.set_class_metadata("layout", layout)
    layout["window"]["x"] = 99
    assert MetadataSettings.get_class_metadata("layout") == {"window": {"x": 1}}

    # get returns a deep copy: mutating the returned object is local
    got = MetadataSettings.get_class_metadata("layout")
    got["window"]["x"] = 77
    assert MetadataSettings.get_class_metadata("layout") == {"window": {"x": 1}}

    MetadataSettings.set_setting_metadata("flag", "ui", {"label": "on"})
    stored = MetadataSettings.get_setting_metadata("flag", "ui")
    stored["label"] = "off"
    assert MetadataSettings.get_setting_metadata("flag", "ui") == {"label": "on"}

    # a missing entry returns the caller's own default object untouched
    fallback = {"n": 1}
    assert MetadataSettings.get_class_metadata("no-such", fallback) is fallback
    assert MetadataSettings.get_setting_metadata("flag", "no-such", fallback) is fallback


def test_get_plugin_returns_cached_bound_instance():
    plugin = MetadataSettings.get_plugin(EnvironmentVariablesPlugin)
    assert isinstance(plugin, EnvironmentVariablesPlugin)
    assert plugin.context.settings_class is MetadataSettings
    assert MetadataSettings.get_plugin(EnvironmentVariablesPlugin) is plugin


def test_get_plugin_unknown_class_raises():
    class NeverRegisteredPlugin:  # not a registered plugin at all
        pass

    with pytest.raises(KeyError, match="not registered"):
        # (a class outside the plugin contract is the error case under test)
        # noinspection PyTypeChecker
        MetadataSettings.get_plugin(NeverRegisteredPlugin)


# ---------------------------------------------------------------------------
# serializer resolution errors
# ---------------------------------------------------------------------------


class UnregisteredAttribute(SettingsAttribute):
    pass


def unregistered_attribute(
    *,
    name: Optional[str] = None,
    default: Any = NO_DEFAULT,
) -> Any:
    return UnregisteredAttribute(name=name, default=default)


def test_unregistered_attribute_raises_plugin_not_enabled():
    class BrokenSettings(Settings):
        mystery: str = unregistered_attribute(default="?")

    with pytest.raises(PluginNotEnabledError, match="UnregisteredAttribute"):
        BrokenSettings.load_settings()


def test_unknown_setting_name_raises_key_error():
    with pytest.raises(KeyError, match="not a setting"):
        MetadataSettings.load_setting("no-such-setting")


# ---------------------------------------------------------------------------
# name formatting
# ---------------------------------------------------------------------------


def test_full_setting_name_default_pattern():
    attr = NonStorageSetting()
    full = get_full_setting_name("flag", attr, MetadataSettings)
    module = MetadataSettings.__module__
    assert full == f"{module}.MetadataSettings.flag"


def test_full_setting_name_explicit_name_replaces_pattern():
    attr = NonStorageSetting(name="my-name")
    full = get_full_setting_name("flag", attr, MetadataSettings)
    assert full == "my-name"


# ---------------------------------------------------------------------------
# conversion
# ---------------------------------------------------------------------------


class Color(enum.Enum):
    RED = 1
    GREEN = 2


@dataclasses.dataclass
class Point:
    x: int
    y: int = 0


@dataclasses.dataclass(frozen=True)
class Booking:
    when: dt.datetime
    color: Color = Color.RED
    tags: List[str] = dataclasses.field(default_factory=list)
    origin: Optional[Point] = None


@dataclasses.dataclass
class Node:
    # self-reference through a string annotation (this module uses
    # ``from __future__ import annotations``)
    value: int
    children: List[Node] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Trip:
    bookings: List[Booking]
    by_code: Dict[str, Point] = dataclasses.field(default_factory=dict)
    anchor: Optional[Booking] = None


@dataclasses.dataclass
class TaggedPoint(Point):
    tags: List[Color] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class FrozenPoint:
    x: int
    y: int = 0


def test_correct_type_bool_strings():
    assert correct_type("True", bool) is True
    assert correct_type("false", bool) is False
    assert correct_type("1", bool) is True
    assert correct_type("off", bool) is False
    with pytest.raises(ValueError):
        correct_type("maybe", bool)


def test_correct_type_numbers_and_strings():
    assert correct_type("42", int) == 42
    assert correct_type("2.5", float) == 2.5
    assert correct_type(7, int) == 7
    assert correct_type(5, str) == "5"


def test_correct_type_optional_unwraps():
    assert correct_type("7", Optional[int]) == 7
    assert correct_type(None, Optional[int]) is None


def test_correct_type_enum():
    assert correct_type("RED", Color) is Color.RED
    assert correct_type("1", Color) is Color.RED
    assert correct_type(2, Color) is Color.GREEN
    with pytest.raises(ValueError):
        correct_type("BLUE", Color)


def test_correct_type_unknown_annotation_passes_through():
    value = object()
    assert correct_type(value, "SomeForwardRef") is value


def test_correct_type_all_supported_common_types():
    uuid_value = uuid.uuid4()
    value = {
        "flag": "true",
        "count": "7",
        "ratio": "3.5",
        "note": 123,
        "when": "2026-09-08T12:30:00",
        "day": "2026-09-08",
        "clock": "12:30:00",
        "delta": "86400",
        "payload": ["a", "b"],
        "tags": ["x", "y", "x"],
        "mapping": {"first": "1", "second": "2"},
        "blob": "hello",
        "decimal": "3.14159",
        "path": "/tmp/demo",
        "guid": str(uuid_value),
        "maybe": "42",
    }

    assert correct_type(value["flag"], bool) is True
    assert correct_type(value["count"], int) == 7
    assert correct_type(value["ratio"], float) == 3.5
    assert correct_type(value["note"], str) == "123"
    assert correct_type(value["when"], dt.datetime) == dt.datetime(2026, 9, 8, 12, 30)
    assert correct_type(value["day"], dt.date) == dt.date(2026, 9, 8)
    assert correct_type(value["clock"], dt.time) == dt.time(12, 30)
    assert correct_type(value["delta"], dt.timedelta) == dt.timedelta(seconds=86400)
    assert correct_type(value["payload"], List[str]) == ["a", "b"]
    assert correct_type(value["tags"], Set[str]) == {"x", "y"}
    assert correct_type(value["mapping"], Dict[str, int]) == {"first": 1, "second": 2}
    assert correct_type(value["blob"], bytes) == b"hello"
    assert correct_type(value["decimal"], decimal.Decimal) == decimal.Decimal("3.14159")
    assert correct_type(value["path"], Path) == Path("/tmp/demo")
    assert correct_type(value["guid"], uuid.UUID) == uuid_value
    assert correct_type(value["maybe"], Optional[int]) == 42

    assert to_storage_string(True) == "True"
    assert to_storage_string(dt.datetime(2026, 9, 8, 12, 30)) == "2026-09-08T12:30:00"
    assert to_storage_string(dt.date(2026, 9, 8)) == "2026-09-08"
    assert to_storage_string(dt.time(12, 30)) == "12:30:00"
    assert to_storage_string({"a": 1, "b": [2, 3]}) == '{"a":1,"b":[2,3]}'
    assert to_storage_string([1, 2, 3]) == "[1,2,3]"
    assert to_storage_string(bytes("hello", "utf-8")) == "hello"
    assert to_storage_string(decimal.Decimal("3.14")) == "3.14"
    assert to_storage_string(Path("/tmp/demo")) == "/tmp/demo"
    assert to_storage_string(uuid_value) == str(uuid_value)
    assert to_json_value({"k": {"v": 1}}) == {"k": {"v": 1}}
    assert to_json_value(("a", "b")) == ["a", "b"]
    assert set(to_json_value({"arr": {1, 2}})["arr"]) == {1, 2}


def test_to_storage_string_roundtrip():
    assert to_storage_string(True) == "True"
    assert to_storage_string(Color.RED) == "RED"
    assert correct_type(to_storage_string(Color.RED), Color) is Color.RED
    assert correct_type(to_storage_string(True), bool) is True
    with pytest.raises(TypeError):
        to_storage_string(object())


def test_base_serializer_value_form_helpers():
    """The public path to the value forms: methods on the serializer base."""
    from advexp.settings.plugin_api import SettingsBaseSerializer

    class HelperSerializer(SettingsBaseSerializer):
        def load(self, setting_name, attr):
            return NOT_FOUND

        def save(self, setting_name, attr, value):
            pass

        def delete(self, setting_name, attr):
            pass

        def contains(self, setting_name, attr):
            return False

    serializer = HelperSerializer()
    assert serializer.to_storage_string(True) == "True"
    assert serializer.to_json_value(("a", "b")) == ["a", "b"]


# ---------------------------------------------------------------------------
# conversion: broader type coverage and round-trips
# ---------------------------------------------------------------------------

_POPULAR_ROUND_TRIP_VALUES = [
    (bool, True),
    (bool, False),
    (int, 42),
    (float, 2.5),
    (complex, 3 + 4j),
    (str, "plain"),
    (bytes, b"\xff\x00binary"),
    (bytearray, bytearray(b"\xfedata")),
    (SecretStr, SecretStr("s3cret-text")),
    (SecretBytes, SecretBytes(b"\xff\x00key")),
    (Color, Color.GREEN),
    (dt.date, dt.date(2026, 9, 8)),
    (
        dt.datetime,
        dt.datetime(2026, 9, 8, 12, 30, tzinfo=dt.timezone(dt.timedelta(hours=3))),
    ),
    (dt.time, dt.time(23, 59, 58)),
    (dt.timedelta, dt.timedelta(days=1, seconds=90, microseconds=7)),
    (dt.timedelta, dt.timedelta(seconds=-90)),
    (decimal.Decimal, decimal.Decimal("3.14159")),
    (Fraction, Fraction(3, 4)),
    (uuid.UUID, uuid.UUID("12345678-1234-5678-1234-567812345678")),
    (Path, Path("/tmp/advexp")),
    (ZoneInfo, ZoneInfo("UTC")),
    (ipaddress.IPv4Address, ipaddress.IPv4Address("192.168.0.1")),
    (ipaddress.IPv6Address, ipaddress.IPv6Address("2001:db8::1")),
    (ipaddress.IPv4Network, ipaddress.IPv4Network("10.0.0.0/8")),
    (ipaddress.IPv6Network, ipaddress.IPv6Network("2001:db8::/32")),
    (ipaddress.IPv4Interface, ipaddress.IPv4Interface("10.0.0.5/24")),
    (ipaddress.IPv6Interface, ipaddress.IPv6Interface("2001:db8::1/64")),
    (List[int], [1, 2, 3]),
    (Set[str], {"alpha", "beta"}),
    (Dict[str, int], {"alpha": 1, "beta": 2}),
    (Tuple[int, str], (7, "seven")),
    (Tuple[int, ...], (2, 4, 8)),
    # items that are not native JSON must be converted inside an existing list
    (List[Color], [Color.RED, Color.GREEN]),
    (List[dt.datetime], [dt.datetime(2026, 9, 8, 12, 30)]),
    (Point, Point(1, 2)),
    (
        Booking,
        Booking(
            dt.datetime(2026, 9, 8, 12, 30, tzinfo=dt.timezone.utc),
            Color.GREEN,
            ["a", "b"],
            Point(3),
        ),
    ),
    (List[Point], [Point(1), Point(2, 5)]),
    (Dict[str, Point], {"a": Point(1)}),
    (Optional[Point], Point(4)),
    # nesting to any depth: items are converted at every level
    (List[List[List[Color]]], [[[Color.RED, Color.GREEN], []], [[Color.GREEN]], []]),
    (Dict[str, List[Color]], {"a": [Color.RED], "b": []}),
    (List[Dict[str, Color]], [{"k": Color.GREEN}, {}]),
    (List[Optional[Color]], [Color.RED, None, Color.GREEN]),
    (Set[Tuple[int, Color]], {(1, Color.RED), (2, Color.GREEN)}),
    (Tuple[List[Color], Dict[str, Color]], ([Color.RED], {"z": Color.GREEN})),
    (List[List[Point]], [[Point(1), Point(2, 3)], []]),
    # user-defined types nested in each other
    (Node, Node(1, [Node(2, [Node(3), Node(4)]), Node(5)])),
    (List[Node], [Node(1, [Node(2)]), Node(0)]),
    (
        Trip,
        Trip(
            [Booking(dt.datetime(2026, 9, 8, 12, 30), Color.GREEN, ["a"], Point(3))],
            {"p": Point(1, 2)},
            Booking(dt.datetime(2026, 1, 1)),
        ),
    ),
    (Dict[str, List[Trip]], {"t": [Trip([], {"p": Point(1)})]}),
    (TaggedPoint, TaggedPoint(1, 2, [Color.RED])),
    (Set[FrozenPoint], {FrozenPoint(1, 2), FrozenPoint(3)}),
    (Union[Point, Booking], Booking(dt.datetime(2026, 1, 1), Color.RED)),
    (Union[Point, Booking], Point(5)),
]


@pytest.mark.parametrize("annotation,value", _POPULAR_ROUND_TRIP_VALUES)
def test_round_trip_through_storage_string(annotation, value):
    assert correct_type(to_storage_string(value), annotation) == value


@pytest.mark.parametrize("annotation,value", _POPULAR_ROUND_TRIP_VALUES)
def test_round_trip_through_json_text(annotation, value):
    stored = json.loads(json.dumps(to_json_value(value)))
    assert correct_type(stored, annotation) == value


def _has_no_toml_form(value: Any) -> bool:
    """Return whether the value holds something that the TOML form refuses: a
    ``None`` nested inside it (a ``None`` at the level of the entry is the drop
    rule of the TOML backend, not a round-trip value), or bytes that are not
    UTF-8 text (every TOML string is UTF-8).
    """
    if value is None:
        return True
    if isinstance(value, SecretBytes):
        value = value.get_secret_value()
    if isinstance(value, (bytes, bytearray)):
        try:
            bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            return True
        return False
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_has_no_toml_form(item) for item in value)
    if isinstance(value, dict):
        return any(_has_no_toml_form(item) for item in value.values())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return any(
            _has_no_toml_form(getattr(value, field.name)) for field in dataclasses.fields(value)
        )
    return False


_TOML_ROUND_TRIP_VALUES = [
    (annotation, value)
    for annotation, value in _POPULAR_ROUND_TRIP_VALUES
    if not _has_no_toml_form(value)
]


@pytest.mark.parametrize("annotation,value", _TOML_ROUND_TRIP_VALUES)
def test_round_trip_through_toml_document(annotation, value):
    # the document's top level is always a table: the value rides inside
    # one key, the way the backend nests every setting value
    document = tomllib.loads(tomlkit.dumps({"value": to_toml_value(value)}))
    assert correct_type(document["value"], annotation) == value


@pytest.mark.parametrize(
    "annotation,value",
    [(bytes, b"\xff\x00binary"), (List[Optional[int]], [1, None])],
    ids=["non-utf8-bytes", "nested-none"],
)
def test_toml_form_refuses_values_it_cannot_hold(annotation, value):
    with pytest.raises(TypeError):
        to_toml_value(value)


def _has_no_yaml_form(value: Any) -> bool:
    """Return whether the value holds text that a YAML string cannot hold: bytes
    that are not UTF-8 (every YAML string is UTF-8). ``None`` is fine, because
    the document has a null, and so are date and time objects, which YAML
    carries natively.
    """
    if isinstance(value, SecretBytes):
        value = value.get_secret_value()
    if isinstance(value, (bytes, bytearray)):
        try:
            bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            return True
        return False
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_has_no_yaml_form(item) for item in value)
    if isinstance(value, dict):
        return any(_has_no_yaml_form(item) for item in value.values())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return any(
            _has_no_yaml_form(getattr(value, field.name)) for field in dataclasses.fields(value)
        )
    return False


_YAML_ROUND_TRIP_VALUES = [
    (annotation, value)
    for annotation, value in _POPULAR_ROUND_TRIP_VALUES
    if not _has_no_yaml_form(value)
]


@pytest.mark.parametrize("annotation,value", _YAML_ROUND_TRIP_VALUES)
def test_round_trip_through_yaml_document(annotation, value):
    # the document's top level is always a mapping: the value rides inside
    # one key, the way the backend nests every setting value
    from io import StringIO

    stream = StringIO()
    _RuamelYAML(typ="rt").dump({"value": to_yaml_value(value)}, stream)
    document = _RuamelYAML(typ="safe").load(stream.getvalue())
    assert correct_type(document["value"], annotation) == value


@pytest.mark.parametrize(
    "annotation,value",
    [(bytes, b"\xff\x00binary"), (List[str], ["ok", "bad\udcff"])],
    ids=["non-utf8-bytes", "nested-non-utf8-bytes"],
)
def test_yaml_form_refuses_values_it_cannot_hold(annotation, value):
    with pytest.raises(TypeError):
        to_yaml_value(value)


def test_correct_type_literal():
    assert correct_type("debug", Literal["debug", "info"]) == "debug"
    assert correct_type("1", Literal[1, 2]) == 1
    with pytest.raises(ValueError):
        correct_type("trace", Literal["debug", "info"])


def test_correct_type_union_tries_alternatives_in_order():
    assert correct_type("42", Union[int, str]) == 42
    assert correct_type("abc", Union[int, str]) == "abc"
    with pytest.raises(ValueError):
        correct_type("abc", Union[int, float])


def test_correct_type_bare_collection_annotations():
    assert correct_type("[1, 2]", list) == [1, 2]
    assert correct_type('{"a": 1}', dict) == {"a": 1}
    assert correct_type("[1, 1, 2]", set) == {1, 2}
    assert correct_type("[1, 2]", tuple) == (1, 2)


def test_correct_type_abc_collection_origins():
    assert correct_type('["a", "b"]', Sequence[str]) == ["a", "b"]
    assert correct_type('{"a": "1"}', Mapping[str, int]) == {"a": 1}
    assert correct_type("[1, 2]", AbstractSet[int]) == {1, 2}

    ordered = correct_type('{"a": 1, "b": 2}', OrderedDict[str, int])
    assert isinstance(ordered, OrderedDict)
    assert list(ordered) == ["a", "b"]


def test_correct_type_bool_from_int():
    assert correct_type(1, bool) is True
    assert correct_type(0, bool) is False


def test_correct_type_ipaddress_fraction_zoneinfo():
    assert correct_type("127.0.0.1", ipaddress.IPv4Address) == ipaddress.IPv4Address("127.0.0.1")
    assert correct_type("2001:db8::1", ipaddress.IPv6Address) == ipaddress.IPv6Address(
        "2001:db8::1"
    )
    assert correct_type("10.0.0.0/8", ipaddress.IPv4Network) == ipaddress.IPv4Network("10.0.0.0/8")
    assert correct_type("10.0.0.5/24", ipaddress.IPv4Interface) == ipaddress.IPv4Interface(
        "10.0.0.5/24"
    )
    assert correct_type("3/4", Fraction) == Fraction(3, 4)
    assert correct_type("0.75", Fraction) == Fraction(3, 4)
    assert correct_type(0.75, Fraction) == Fraction(3, 4)
    assert correct_type("Europe/Berlin", ZoneInfo) is ZoneInfo("Europe/Berlin")
    with pytest.raises(ValueError):
        correct_type("10.0.0.999", ipaddress.IPv4Address)
    with pytest.raises(ValueError):
        correct_type("No/Such_Zone", ZoneInfo)


def test_correct_type_timedelta_string_forms():
    assert correct_type("0:00:03", dt.timedelta) == dt.timedelta(seconds=3)
    assert correct_type("1 day, 0:00:00", dt.timedelta) == dt.timedelta(days=1)
    assert correct_type("2 days, 3:04:05.000006", dt.timedelta) == dt.timedelta(
        days=2, hours=3, minutes=4, seconds=5, microseconds=6
    )
    assert correct_type("-1 day, 23:58:30", dt.timedelta) == dt.timedelta(seconds=-90)
    assert correct_type("90", dt.timedelta) == dt.timedelta(
        seconds=90
    )  # plain seconds stay supported


def test_correct_type_date_truncates_datetime_strings():
    assert correct_type("2026-09-08T12:30:00", dt.date) == dt.date(2026, 9, 8)
    assert correct_type("2026-09-08 12:30:00+03:00", dt.date) == dt.date(2026, 9, 8)


def test_culture_dependent_formats_are_rejected():
    # the decimal separator is always "."; thousands separators are never accepted
    for annotation in (int, float, decimal.Decimal, Fraction):
        with pytest.raises(ValueError):
            correct_type("3,14", annotation)
    with pytest.raises(ValueError):
        correct_type("1.234,5", float)
    with pytest.raises(ValueError):
        correct_type("1,234", int)

    # dates are always ISO 8601 (YYYY-MM-DD); DD/MM and MM/DD are ambiguous
    for annotation in (dt.date, dt.datetime):
        with pytest.raises(ValueError):
            correct_type("09/08/2026", annotation)
    with pytest.raises(ValueError):
        correct_type("08.09.2026", dt.date)


def test_correct_type_converts_items_of_an_existing_container():
    # a JSON document already yields a list; its items still need converting
    assert correct_type(["RED"], List[Color]) == [Color.RED]
    assert correct_type(["2026-09-08T12:30:00"], List[dt.datetime]) == [
        dt.datetime(2026, 9, 8, 12, 30)
    ]
    assert correct_type(("1", "2"), Tuple[int, ...]) == (1, 2)
    assert correct_type(["1", "x"], Tuple[int, str]) == (1, "x")
    # untyped containers of the right type pass through as is
    items = [1, 2]
    assert correct_type(items, list) is items


def test_correct_type_dataclass_fields_converted_by_their_annotations():
    stored = {
        "when": "2026-09-08T12:30:00+00:00",
        "color": "GREEN",
        "tags": ["a"],
        "origin": {"x": "3"},
    }
    booking = correct_type(stored, Booking)
    assert booking == Booking(
        dt.datetime(2026, 9, 8, 12, 30, tzinfo=dt.timezone.utc), Color.GREEN, ["a"], Point(3)
    )
    assert isinstance(booking.origin, Point)


def test_correct_type_dataclass_instance_and_text_forms():
    point = Point(1, 2)
    assert correct_type(point, Point) is point
    assert to_storage_string(point) == '{"x":1,"y":2}'
    assert correct_type('{"x": 1, "y": 2}', Point) == point
    assert to_json_value(point) == {"x": 1, "y": 2}
    assert correct_type(None, Optional[Point]) is None


def test_correct_type_dataclass_ignores_dropped_fields_and_requires_the_rest():
    # a stored object survives a field being removed from the class...
    assert correct_type({"x": 1, "legacy": True}, Point) == Point(1)
    # ...but a required field cannot be invented
    with pytest.raises(ValueError):
        correct_type({"y": 2}, Point)
    with pytest.raises(ValueError):
        correct_type("not an object", Point)
    with pytest.raises(ValueError):
        correct_type(42, Point)


def test_correct_type_dataclass_evolution_rules_apply_at_any_depth():
    trip = Trip([Booking(dt.datetime(2026, 1, 1), origin=Point(1))])
    stored = json.loads(json.dumps(to_json_value(trip)))
    stored["bookings"][0]["origin"]["legacy"] = True  # dropped field, three levels down
    del stored["bookings"][0]["origin"]["y"]  # field with a default, three levels down
    assert correct_type(stored, Trip) == trip

    del stored["bookings"][0]["origin"]["x"]  # required field, three levels down
    with pytest.raises(ValueError):  # the whole value is rejected, not just the leaf
        correct_type(stored, Trip)


def test_dataclass_unresolvable_field_annotation_is_reported_once_and_passed_through(caplog):
    def make():
        @dataclasses.dataclass
        class Inner:
            v: int

        @dataclasses.dataclass
        class Outer:
            # string annotations here (module-wide ``from __future__ import
            # annotations``); "Inner" only exists inside make(), not in the module
            count: int
            inner: Inner

        return Outer

    outer_class = make()
    with caplog.at_level(logging.WARNING, logger="advexp.settings_base"):
        loaded = correct_type({"count": "5", "inner": {"v": 1}}, outer_class)
        correct_type({"count": "6", "inner": {"v": 2}}, outer_class)

    assert loaded.count == 5  # resolvable fields are still converted
    assert loaded.inner == {"v": 1}  # the unresolvable one is passed through as loaded
    reports = [r for r in caplog.records if "cannot resolve the annotations" in r.getMessage()]
    assert len(reports) == 1  # reported once per class, not per value
    assert "['inner']" in reports[0].getMessage()
    assert "Outer" in reports[0].getMessage()


def test_correct_type_dataclass_init_false_fields_are_recomputed():
    @dataclasses.dataclass
    class WithDerived:
        width: int
        area: int = dataclasses.field(init=False)

        def __post_init__(self):
            self.area = self.width * self.width

    stored = json.loads(json.dumps(to_json_value(WithDerived(3))))
    assert stored == {"width": 3, "area": 9}
    # a stale derived value in storage does not override the class's own computation
    stored["area"] = 1
    assert correct_type(stored, WithDerived).area == 9


def test_dataclass_class_object_is_not_a_storable_value():
    with pytest.raises(TypeError):
        to_json_value(Point)
    with pytest.raises(TypeError):
        to_storage_string(Point)


def test_correct_type_non_dataclass_class_annotation_still_passes_through():
    class Plain:
        pass

    value = object()
    assert correct_type(value, Plain) is value
    assert correct_type({"x": 1}, Plain) == {"x": 1}


# ---------------------------------------------------------------------------
# value constraints: boundaries, declaration checks, custom validators
# ---------------------------------------------------------------------------

_CONSTRAINT_CASES = [
    # (constraints, valid values, invalid values) — exercised through the
    # update and assignment boundaries; the member annotation is Any, the
    # interplay with conversion has its own tests below
    ({"gt": 0}, [1, 0.5], [0, -1]),
    ({"ge": 1}, [1, 2], [0]),
    ({"lt": 100}, [99], [100]),
    ({"le": 100}, [100], [101]),
    ({"eq": "prod"}, ["prod"], ["dev"]),
    ({"ne": 0}, [1, -1], [0]),
    ({"min_length": 2}, ["ab", [1, 2], {"a": 1, "b": 2}], ["a", [1], {}]),
    ({"max_length": 3}, ["abc", "", [1]], ["abcd", [1, 2, 3, 4]]),
    ({"regex": r"^[a-z]+$"}, ["abc"], ["ABC", "abc1"]),
    ({"gt": 0, "le": 65535}, [1, 8080, 65535], [0, -1, 65536]),
    ({"min_length": 1, "regex": r"\w+"}, ["a1"], ["", "-"]),
]


def _constrained(default=None, **constraints):
    class Constrained(Settings):
        value: Any = non_storage_setting(default=default, **constraints)

    return Constrained


@pytest.mark.parametrize("constraints,valid_values,invalid_values", _CONSTRAINT_CASES)
def test_constraints_accept_valid_values_on_update(constraints, valid_values, invalid_values):
    constrained = _constrained(default=valid_values[0], **constraints)
    for value in valid_values:
        constrained.update_from_dict({"value": value})
        assert constrained.value == value


@pytest.mark.parametrize("constraints,valid_values,invalid_values", _CONSTRAINT_CASES)
def test_constraints_reject_invalid_values_on_update(constraints, valid_values, invalid_values):
    constrained = _constrained(default=valid_values[0], **constraints)
    constrained.update_from_dict({"value": valid_values[0]})
    for value in invalid_values:
        with pytest.raises(SettingValidationError):
            constrained.update_from_dict({"value": value})
        # a rejected update applies nothing
        assert constrained.value == valid_values[0]


@pytest.mark.parametrize("constraints,valid_values,invalid_values", _CONSTRAINT_CASES)
def test_constraints_reject_invalid_values_on_assignment(constraints, valid_values, invalid_values):
    constrained = _constrained(default=valid_values[0], **constraints)
    instance = constrained()  # an ordinary instance shares the class storage
    snapshot = constrained.to_object()
    for value in invalid_values:
        with pytest.raises(SettingValidationError):
            constrained.value = value
        with pytest.raises(SettingValidationError):
            instance.value = value
        with pytest.raises(SettingValidationError):
            snapshot.value = value


def test_setting_validation_error_is_a_value_error():
    # the plain ``except ValueError`` spelling keeps working
    assert issubclass(SettingValidationError, ValueError)


def test_constraint_violation_message_names_member_class_and_bound():
    class Port(Settings):
        port: int = non_storage_setting(default=8080, le=65535)

    with pytest.raises(
        SettingValidationError,
        match=(
            r"invalid value for setting 'port' of Port: "
            r"value 99999 must be less than or equal to 65535"
        ),
    ):
        Port.port = 99999


def test_constraints_apply_after_conversion():
    class Port(Settings):
        port: int = non_storage_setting(default=1, le=65535)

    # "70000" converts to int first, then meets the bound
    with pytest.raises(SettingValidationError, match="70000"):
        Port.update_from_dict({"port": "70000"})


def test_invalid_default_fails_the_class_statement():
    with pytest.raises(TypeError, match="invalid defaults in Constrained"):

        class Constrained(Settings):
            port: int = non_storage_setting(default=70000, le=65535)


def test_converted_default_is_checked_in_converted_form():
    with pytest.raises(TypeError, match="port: value 70000"):

        class Constrained(Settings):
            port: int = non_storage_setting(default="70000", le=65535)


def test_subclasses_validate_inherited_constraints():
    class Base(Settings):
        port: int = non_storage_setting(default=8080, le=65535)

    class Derived(Base):
        pass

    with pytest.raises(SettingValidationError):
        Derived.port = 70000


def test_load_falls_back_to_default_on_violating_stored_value(caplog, monkeypatch):
    class PortSettings(Settings):
        port: int = environment_variable_setting(
            name="ADVEXP_TEST_CONSTRAINT_PORT", default=8080, ge=1, le=65535
        )

    monkeypatch.setenv("ADVEXP_TEST_CONSTRAINT_PORT", "70000")
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        PortSettings.load_settings()

    assert PortSettings.port == 8080  # the fallback, like a value that does not convert
    reports = [r for r in caplog.records if "violates its constraints" in r.getMessage()]
    assert len(reports) == 1
    assert "'port'" in reports[0].getMessage()


def test_save_raises_on_a_violating_value_and_writes_nothing(caplog, monkeypatch):
    class PortSettings(Settings):
        port: int = environment_variable_setting(
            name="ADVEXP_TEST_CONSTRAINT_SAVE", default=8080, ge=1, le=65535
        )

    monkeypatch.setenv("ADVEXP_TEST_CONSTRAINT_SAVE", "9090")
    PortSettings.load_settings()
    # the only way an invalid value reaches memory: written past the guarded
    # boundaries, straight into the class storage
    PortSettings.__settings_values__["port"] = 70000
    with pytest.raises(SettingValidationError) as info:
        PortSettings.save_settings()

    assert PortSettings.port == 70000  # memory keeps it; the store does not
    assert os.environ["ADVEXP_TEST_CONSTRAINT_SAVE"] == "9090"
    assert info.value.problems == {"port": ["value 70000 must be less than or equal to 65535"]}


# -- single-setting passes on a failing source -------------------------------


class _FailingSaveAttribute(SettingsAttribute):
    """A test source attribute: every write or probe operation fails."""


class _FailingSaveSerializer(SettingsBaseSerializer):
    """A test source serializer that raises on demand, chosen per class attribute.

    ``kind_save`` and its siblings choose what each operation raises: ``"plain"``
    raises a runtime error, ``"facing"`` raises a user-facing wrapper, and
    ``None`` succeeds.
    """

    kind_save: ClassVar[Optional[str]] = None
    kind_delete: ClassVar[Optional[str]] = None
    kind_contains: ClassVar[Optional[str]] = None

    @staticmethod
    def _raise(kind: Optional[str], operation: str) -> None:
        if kind == "plain":
            raise RuntimeError(f"{operation} boom")
        if kind == "facing":
            raise UserFacingError(ValueError(f"{operation} inner"))

    def load(self, setting_name: str, attr: Any) -> Any:
        return NOT_FOUND

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        self._raise(self.kind_save, "save")

    def delete(self, setting_name: str, attr: Any) -> None:
        self._raise(self.kind_delete, "delete")

    def contains(self, setting_name: str, attr: Any) -> bool:
        self._raise(self.kind_contains, "contains")
        return False


class _FailingSavePlugin(SettingsBasePlugin):
    binding = AttributeSerializerBinding(_FailingSaveAttribute, _FailingSaveSerializer)

    @property
    def plugin_name(self) -> str:
        return "FailingWrites"


LibraryConfiguration.register_settings_plugin(_FailingSavePlugin)


def _failing_write_setting(**kwargs: Any) -> Any:
    """The declaration spelling of the failing-write source: the factory form
    that type-checker-friendly member declarations use.
    """
    return _FailingSaveAttribute(**kwargs)


def _failing_write_class(**states: Any) -> type:
    """A settings class of one member behind the failing-write source,
    with the serializer's raises picked per operation."""
    _FailingSaveSerializer.kind_save = states.get("save")
    _FailingSaveSerializer.kind_delete = states.get("delete")
    _FailingSaveSerializer.kind_contains = states.get("contains")

    class FailingWrites(Settings):
        member: str = _failing_write_setting(default="stored-value")

    return FailingWrites


def test_single_setting_save_source_failure_is_logged_and_skipped(caplog):
    # the single-setting write follows the class pass's policy: a plain
    # storage error is an ERROR record, the write is skipped and the
    # caller sees no exception
    klass = _failing_write_class(save="plain")
    klass.member = "new-value"

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        klass.save_setting("member")

    assert [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ] == ["save exception for setting 'member': save boom"]


def test_single_setting_save_user_facing_error_arrives_unwrapped():
    # the family unwraps a user-facing condition into the inner exception
    klass = _failing_write_class(save="facing")

    with pytest.raises(ValueError, match="save inner") as info:
        klass.save_setting("member")

    assert isinstance(info.value.__cause__, UserFacingError)


def test_single_setting_save_of_a_violating_value_raises():
    # no whole-class gate runs on the narrow path: the member's own
    # check is the guard, and a violation raises like the assignment
    # and the class gate do — not a logged skip
    class ConditionalPort(Settings):
        ssl: bool = non_storage_setting(default=False)
        port: int = environment_variable_setting(
            name="TEST_SINGLE_SAVE_PORT", default=80, eq=443, when=ssl
        )

    ConditionalPort.port = 8080  # valid while the condition is off
    ConditionalPort.ssl = True  # the condition turns the constraint on
    with pytest.raises(SettingValidationError):
        ConditionalPort.save_setting("port")


def test_single_setting_delete_source_failure_is_logged_and_skipped(caplog):
    klass = _failing_write_class(delete="plain")

    with caplog.at_level(logging.ERROR, logger="advexp.settings"):
        klass.delete_setting("member")

    assert [
        record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
    ] == ["delete exception for setting 'member': delete boom"]
    # the skipped delete leaves the member's value alone
    assert klass.member == "stored-value"


def test_single_setting_delete_user_facing_error_arrives_unwrapped():
    klass = _failing_write_class(delete="facing")

    with pytest.raises(ValueError, match="delete inner") as info:
        klass.delete_setting("member")

    assert isinstance(info.value.__cause__, UserFacingError)


def test_contains_setting_source_errors_arrive_plain_and_unwrapped():
    # the probe has no soft answer: a plain error leaves as is, a
    # user-facing one unwrapped into the inner exception
    klass = _failing_write_class(contains="plain")
    with pytest.raises(RuntimeError, match="contains boom"):
        klass.contains_setting("member")

    klass = _failing_write_class(contains="facing")
    with pytest.raises(ValueError, match="contains inner") as info:
        klass.contains_setting("member")
    assert isinstance(info.value.__cause__, UserFacingError)


def test_none_passes_ordered_and_shape_constraints():
    class OptionalSettings(Settings):
        count: Optional[int] = non_storage_setting(default=None, gt=0)
        name: Optional[str] = non_storage_setting(default=None, min_length=1)

    assert OptionalSettings.count is None  # unset reads as the None default
    assert OptionalSettings.name is None


def test_none_takes_part_in_equality_constraints():
    class OnlyProd(Settings):
        mode: Optional[str] = non_storage_setting(default="prod", eq="prod")

    OnlyProd.mode = "prod"
    with pytest.raises(SettingValidationError):
        OnlyProd.mode = None


def test_constraint_bounds_compare_any_comparable_type():
    class Schedule(Settings):
        since: dt.date = non_storage_setting(default=dt.date(2026, 6, 1), gt=dt.date(2026, 1, 1))

    Schedule.since = dt.date(2026, 6, 1)
    with pytest.raises(SettingValidationError):
        Schedule.since = dt.date(2025, 12, 31)


def test_incomparable_value_is_a_violation_not_a_crash():
    constrained = _constrained(gt=0)
    with pytest.raises(SettingValidationError, match="not comparable"):
        constrained.value = object()


def test_length_constraint_on_value_without_len():
    constrained = _constrained(min_length=1)
    with pytest.raises(SettingValidationError, match="has no length"):
        constrained.value = 42


def test_regex_requires_a_string_value():
    constrained = _constrained(regex=r"\d+")
    with pytest.raises(SettingValidationError, match="not a string"):
        constrained.value = 123


def test_validator_receives_the_value_and_gates_it():
    # a member without a declared default serves None, so its validator
    # meets the stand-in too — here, and at class creation
    constrained = _constrained(validator=lambda value: value is None or value % 2 == 1)
    constrained.update_from_dict({"value": 3})
    assert constrained.value == 3
    with pytest.raises(SettingValidationError, match="failed the validator"):
        constrained.update_from_dict({"value": 4})


def test_validator_exception_propagates_as_is():
    # a raising validator is a bug in the validator, not a property of the
    # value; it stays silent on the None stand-in so the class can exist
    def broken(value):
        if value is None:
            return True
        raise RuntimeError("bug in the validator")

    constrained = _constrained(validator=broken)
    with pytest.raises(RuntimeError, match="bug in the validator"):
        constrained.value = 1


def test_bad_regex_fails_at_declaration():
    with pytest.raises(ValueError, match="Invalid regex"):
        non_storage_setting(default="x", regex="([unclosed")


def test_non_callable_validator_fails_at_declaration():
    with pytest.raises(TypeError, match="validator must be callable"):
        non_storage_setting(default=1, validator=42)


def test_ordering_and_shape_constraints_do_not_mix():
    with pytest.raises(TypeError, match="conflicting constraints"):
        non_storage_setting(default=1, gt=0, min_length=1)
    non_storage_setting(default=1, gt=0)  # alone is fine
    non_storage_setting(default="x", min_length=1, regex="x")  # both shape the string — fine too


def test_valueless_declaration_is_refused():
    # a member no storage ever serves must state its value: the factory
    # refuses the declaration instead of leaving a member nothing loads
    with pytest.raises(TypeError, match="pass default="):
        non_storage_setting()


# ---------------------------------------------------------------------------
# registry behavior
# ---------------------------------------------------------------------------


def test_register_and_unregister_settings_attribute():
    # (a registry-only token: the class never serves a storage call)
    class DummySerializer:
        pass

    class DummyAttribute(SettingsAttribute):
        pass

    try:
        # (a registry token: never serving a storage call is the point)
        # noinspection PyTypeChecker
        LibraryConfiguration.register_settings_attribute(DummyAttribute, DummySerializer)
        assert LibraryConfiguration._get_serializer_factory(DummyAttribute) is DummySerializer
    finally:
        LibraryConfiguration._attribute_serializers.pop(DummyAttribute, None)


# ---------------------------------------------------------------------------
# pipeline contract: hooks, synchronize, user errors
# ---------------------------------------------------------------------------


def _make_dummy_backend(events, fail_load=False, user_error=False, sync_user_error=False):
    from advexp.settings.plugin_api import (
        NOT_FOUND,
        SettingsBaseSerializer,
        UserFacingError,
    )

    class DummyHookAttribute(SettingsAttribute):
        pass

    class DummyHookSerializer(SettingsBaseSerializer):
        # -- ISettingsSerializerWishes -------------------------------------

        def set_serializer_params(self, context):
            events.append(("params", context.settings_class.__name__))

        # -- ISettingsSerializer -------------------------------------------

        def load(self, setting_name, attr):
            events.append(("load", setting_name))
            if user_error:
                raise UserFacingError(ValueError("backend is misconfigured"))
            if fail_load:
                raise RuntimeError("storage exploded")
            return NOT_FOUND

        def save(self, setting_name, attr, value):
            events.append(("save", setting_name, value))

        def delete(self, setting_name, attr):
            events.append(("delete", setting_name))

        def contains(self, setting_name, attr):
            return False

        def synchronize(self):
            events.append(("synchronize",))
            if sync_user_error:
                raise UserFacingError(ValueError("flush failed"))

        # -- ISerializerNotificationSink -----------------------------------

        def on_start_serializer_action(self):
            events.append(("start-action",))

        def on_end_serializer_action(self):
            events.append(("end-action",))

        def on_start_load_settings(self):
            events.append(("start-load",))

        def on_end_load_settings(self):
            events.append(("end-load",))

        def on_start_save_settings(self):
            events.append(("start-save",))

        def on_end_save_settings(self):
            events.append(("end-save",))

        def on_start_delete_settings(self):
            events.append(("start-delete",))

        def on_end_delete_settings(self):
            events.append(("end-delete",))

        def on_start_contains_settings(self):
            events.append(("start-contains",))

        def on_end_contains_settings(self):
            events.append(("end-contains",))

    return DummyHookAttribute, DummyHookSerializer


def _with_dummy_backend(events, **kwargs):
    attribute_class, serializer_class = _make_dummy_backend(events, **kwargs)
    LibraryConfiguration.register_settings_attribute(attribute_class, serializer_class)

    class HookSettings(Settings):
        value: int = attribute_class(default=5)

    return HookSettings, attribute_class


def test_serializer_notification_sink_call_count_and_order():
    events = []
    settings_class, attribute_class = _with_dummy_backend(events)
    full_name = f"{settings_class.__module__}.HookSettings.value"

    try:
        # class-level passes: one notification bracket per serializer per pass
        settings_class.load_settings()
        assert events == [
            ("params", "HookSettings"),
            ("start-action",),
            ("start-load",),
            ("load", full_name),
            ("end-load",),
            ("end-action",),
        ]

        events.clear()
        settings_class.value = 7
        settings_class.save_settings()
        assert events == [
            ("params", "HookSettings"),
            ("start-action",),
            ("start-save",),
            ("save", full_name, 7),
            ("synchronize",),
            ("end-save",),
            ("end-action",),
        ]

        events.clear()
        settings_class.delete_settings()
        assert events == [
            ("params", "HookSettings"),
            ("start-action",),
            ("start-delete",),
            ("delete", full_name),
            ("synchronize",),
            ("end-delete",),
            ("end-action",),
        ]

        # single-setting passes fire the same bracket for their serializer
        events.clear()
        settings_class.load_setting("value")
        assert events == [
            ("params", "HookSettings"),
            ("start-action",),
            ("start-load",),
            ("load", full_name),
            ("end-load",),
            ("end-action",),
        ]

        events.clear()
        settings_class.save_setting("value")
        assert events == [
            ("params", "HookSettings"),
            ("start-action",),
            ("start-save",),
            ("save", full_name, 5),
            ("synchronize",),
            ("end-save",),
            ("end-action",),
        ]

        events.clear()
        settings_class.delete_setting("value")
        assert events == [
            ("params", "HookSettings"),
            ("start-action",),
            ("start-delete",),
            ("delete", full_name),
            ("synchronize",),
            ("end-delete",),
            ("end-action",),
        ]

        # contains fires its own notification bracket, but no synchronize
        events.clear()
        assert settings_class.contains_setting("value") is False
        assert events == [
            ("params", "HookSettings"),
            ("start-action",),
            ("start-contains",),
            ("end-contains",),
            ("end-action",),
        ]

        # the bracket is per serializer per pass, not per member
        class TwoHookSettings(Settings):
            first: int = attribute_class(default=1)
            second: int = attribute_class(default=2)

        events.clear()
        TwoHookSettings.load_settings()
        assert events == [
            ("params", "TwoHookSettings"),
            ("start-action",),
            ("start-load",),
            ("load", f"{TwoHookSettings.__module__}.TwoHookSettings.first"),
            ("load", f"{TwoHookSettings.__module__}.TwoHookSettings.second"),
            ("end-load",),
            ("end-action",),
        ]
    finally:
        LibraryConfiguration._attribute_serializers.pop(attribute_class, None)


def test_pipeline_survives_backend_exception_and_keeps_default():
    events = []
    settings_class, attribute_class = _with_dummy_backend(events, fail_load=True)

    try:
        settings_class.load_settings()
        assert settings_class.value == 5  # default kept
        assert ("end-load",) in events  # hooks still balanced
    finally:
        LibraryConfiguration._attribute_serializers.pop(attribute_class, None)


def test_user_facing_error_is_propagated():
    events = []
    settings_class, attribute_class = _with_dummy_backend(events, user_error=True)

    try:
        with pytest.raises(ValueError, match="misconfigured"):
            settings_class.load_settings()
    finally:
        LibraryConfiguration._attribute_serializers.pop(attribute_class, None)


def test_user_facing_error_from_synchronize_is_propagated():
    events = []
    settings_class, attribute_class = _with_dummy_backend(events, sync_user_error=True)

    try:
        with pytest.raises(ValueError, match="flush"):
            settings_class.save_settings()
    finally:
        LibraryConfiguration._attribute_serializers.pop(attribute_class, None)


# ---------------------------------------------------------------------------
# third-party serializers: optional interfaces are probed, not required
# ---------------------------------------------------------------------------


def test_minimal_serializer_without_optional_interfaces():
    storage = {}
    syncs = []

    class MinimalAttribute(SettingsAttribute):
        pass

    class MinimalSerializer(ISettingsSerializer):
        """A third-party backend implementing only the mandatory interface."""

        def load(self, setting_name, attr):
            return storage.get(setting_name, NOT_FOUND)

        def save(self, setting_name, attr, value):
            storage[setting_name] = value

        def delete(self, setting_name, attr):
            storage.pop(setting_name, None)

        def contains(self, setting_name, attr):
            return setting_name in storage

        def synchronize(self):
            syncs.append(True)

    LibraryConfiguration.register_settings_attribute(MinimalAttribute, MinimalSerializer)

    class MinimalSettings(Settings):
        value: int = MinimalAttribute(default=5)

    try:
        MinimalSettings.value = 9
        MinimalSettings.save_settings()
        full_name = f"{MinimalSettings.__module__}.MinimalSettings.value"
        assert storage == {full_name: 9}
        assert len(syncs) == 1  # synchronize is mandatory: once per save pass

        MinimalSettings.reset_settings()
        MinimalSettings.load_settings()
        assert MinimalSettings.value == 9
        assert MinimalSettings.contains_setting("value") is True
        assert len(syncs) == 1  # load passes do not synchronize

        MinimalSettings.delete_settings()
        assert storage == {}
        assert len(syncs) == 2
    finally:
        LibraryConfiguration._attribute_serializers.pop(MinimalAttribute, None)


def test_serializer_with_wishes_but_no_notification_sink():
    storage = {}
    events = []

    class WishAttribute(SettingsAttribute):
        pass

    class WishSerializer(ISettingsSerializer, ISettingsSerializerWishes):
        # -- ISettingsSerializer -------------------------------------------

        def load(self, setting_name, attr):
            return storage.get(setting_name, NOT_FOUND)

        def save(self, setting_name, attr, value):
            storage[setting_name] = value

        def delete(self, setting_name, attr):
            storage.pop(setting_name, None)

        def contains(self, setting_name, attr):
            return setting_name in storage

        def synchronize(self):
            events.append(("synchronize",))

        # -- ISettingsSerializerWishes -------------------------------------

        def delimiter(self):
            return "_"

        def remove_inappropriate_symbols(self, text):
            return text.replace("-", "")

        def set_serializer_params(self, context):
            events.append(("params", context.settings_class.__name__))

    LibraryConfiguration.register_settings_attribute(WishAttribute, WishSerializer)

    class WishSettings(Settings):
        patterned: int = WishAttribute(default=1)
        explicit: int = WishAttribute(name="some-thing", default=2)

    try:
        WishSettings.patterned = 7
        WishSettings.explicit = 8
        WishSettings.save_settings()

        # the delimiter wish joins the pattern parts and the sanitizer cleans
        # fragments (the '-' dropped from the hyphenated name)
        module = WishSettings.__module__
        assert storage == {
            f"{module}_WishSettings_patterned": 7,
            "something": 8,
        }
        # params were injected and synchronize ran; there are no notification
        # methods on this backend and none may be called
        assert events == [
            ("params", "WishSettings"),
            ("synchronize",),
        ]
    finally:
        LibraryConfiguration._attribute_serializers.pop(WishAttribute, None)


def test_serializer_delimiter_wish_outside_whitelist_falls_back_with_warning(caplog):
    storage = {}

    class DashAttribute(SettingsAttribute):
        pass

    class DashSerializer(ISettingsSerializer, ISettingsSerializerWishes):
        # -- ISettingsSerializer -------------------------------------------

        def load(self, setting_name, attr):
            return storage.get(setting_name, NOT_FOUND)

        def save(self, setting_name, attr, value):
            storage[setting_name] = value

        def delete(self, setting_name, attr):
            storage.pop(setting_name, None)

        def contains(self, setting_name, attr):
            return setting_name in storage

        def synchronize(self):
            pass

        # -- ISettingsSerializerWishes -------------------------------------

        def delimiter(self):
            return "-"

        def remove_inappropriate_symbols(self, text):
            return text

        def set_serializer_params(self, context):
            pass

    LibraryConfiguration.register_settings_attribute(DashAttribute, DashSerializer)

    class DashSettings(Settings):
        first: int = DashAttribute(default=1)
        second: int = DashAttribute(default=2)

    try:
        DashSettings.first = 10
        DashSettings.second = 20

        with caplog.at_level(logging.WARNING, logger="advexp.settings"):
            DashSettings.save_settings()

        # the wish outside '.'/'_' falls back to '.' and warns once per
        # serializer class, though the wish is asked for every name
        module = DashSettings.__module__
        assert storage == {
            f"{module}.DashSettings.first": 10,
            f"{module}.DashSettings.second": 20,
        }
        warning_records = [record for record in caplog.records if record.levelno >= logging.WARNING]
        assert len(warning_records) == 1
        message = warning_records[0].getMessage()
        assert "DashSerializer" in message
        assert "'-'" in message
    finally:
        LibraryConfiguration._attribute_serializers.pop(DashAttribute, None)


def test_serializer_with_notification_sink_but_no_wishes():
    storage = {}
    events = []

    class SinkAttribute(SettingsAttribute):
        pass

    class SinkSerializer(ISettingsSerializer, ISerializerNotificationSink):
        # -- ISettingsSerializer -------------------------------------------

        def load(self, setting_name, attr):
            events.append(("load", setting_name))
            return storage.get(setting_name, NOT_FOUND)

        def save(self, setting_name, attr, value):
            storage[setting_name] = value

        def delete(self, setting_name, attr):
            storage.pop(setting_name, None)

        def contains(self, setting_name, attr):
            return setting_name in storage

        def synchronize(self):
            events.append(("synchronize",))

        # -- ISerializerNotificationSink -----------------------------------

        def on_start_serializer_action(self):
            events.append(("start-action",))

        def on_end_serializer_action(self):
            events.append(("end-action",))

        def on_start_load_settings(self):
            events.append(("start-load",))

        def on_end_load_settings(self):
            events.append(("end-load",))

        def on_start_save_settings(self):
            events.append(("start-save",))

        def on_end_save_settings(self):
            events.append(("end-save",))

        def on_start_delete_settings(self):
            events.append(("start-delete",))

        def on_end_delete_settings(self):
            events.append(("end-delete",))

        def on_start_contains_settings(self):
            events.append(("start-contains",))

        def on_end_contains_settings(self):
            events.append(("end-contains",))

    LibraryConfiguration.register_settings_attribute(SinkAttribute, SinkSerializer)

    class SinkSettings(Settings):
        value: int = SinkAttribute(default=5)

    try:
        SinkSettings.value = 6
        SinkSettings.save_settings()
        full_name = f"{SinkSettings.__module__}.SinkSettings.value"
        # default naming (no wishes), notifications delivered, no params call
        assert storage == {full_name: 6}
        assert events == [
            ("start-action",),
            ("start-save",),
            ("synchronize",),
            ("end-save",),
            ("end-action",),
        ]

        # the contains probe gets the same bracket, without synchronize
        events.clear()
        assert SinkSettings.contains_setting("value") is True
        assert events == [
            ("start-action",),
            ("start-contains",),
            ("end-contains",),
            ("end-action",),
        ]
    finally:
        LibraryConfiguration._attribute_serializers.pop(SinkAttribute, None)
