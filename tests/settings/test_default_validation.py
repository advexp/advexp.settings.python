"""Startup validation of declared defaults: the conversion and isinstance tiers.

Creating a settings class converts every declared ``default=`` through the
member annotation (failing the class statement when it does not convert)
and checks defaults of pass-through annotations with ``isinstance``.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Literal,
    NewType,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
    Union,
)

import pytest

from advexp.settings import Settings

# noinspection PyProtectedMember
from advexp.settings._internal.non_storage_setting import (
    NonStorageSetting,
    non_storage_setting,
)
from advexp.settings.plugin_api import NO_DEFAULT, SettingsAttribute
from advexp.settings.plugins.environment.variables import (
    environment_variable_setting,
)

# noinspection PyProtectedMember
from advexp.settings_base import default_validation
from advexp.settings_base.required import REQUIRED


class Shade(enum.Enum):
    red = "red"
    green = "green"


class Endpoint:
    """A custom type outside the conversion contract (not a dataclass)."""

    def __init__(self, url: str) -> None:
        self.url = url


@dataclasses.dataclass
class Proxy:
    host: str
    port: int = 3128


T = TypeVar("T")


class Box(Generic[T]):
    pass


class Runnable(Protocol):
    def run(self) -> int: ...


UserId = NewType("UserId", int)

# ---------------------------------------------------------------------------
# conversion tier: defaults are served in their converted form


def test_loosely_typed_default_serves_converted():
    class PortSettings(Settings):
        port: int = non_storage_setting(default="8080")

    assert PortSettings.port == 8080
    assert isinstance(PortSettings.port, int)


def test_well_typed_default_is_served_unchanged():
    moment = datetime.datetime(2026, 9, 21, 12, 0)

    class Fine(Settings):
        when: datetime.datetime = non_storage_setting(default=moment)

    assert Fine.when == moment


def test_storage_form_default_becomes_the_annotated_shape():
    class Shapes(Settings):
        mirrors: tuple = non_storage_setting(default=["a", "b"])
        tags: set = non_storage_setting(default=["a"])
        proxy: Optional[Proxy] = non_storage_setting(default={"host": "h"})

    assert Shapes.mirrors == ("a", "b")
    assert Shapes.tags == {"a"}
    assert Shapes.proxy == Proxy("h")


def test_declared_default_stays_as_written():
    class PortSettings(Settings):
        port: int = non_storage_setting(default="8080")

    attribute = PortSettings.__settings_members__["port"].attribute
    assert attribute.default == "8080"  # the declaration is not rewritten
    assert PortSettings.__settings_members__["port"].descriptor.resolved_default() == 8080


def test_served_defaults_are_isolated_copies():
    class Tags(Settings):
        tags: List[str] = non_storage_setting(default=["a"])

    first = Tags.tags
    first.append("mutated")
    assert Tags.tags == ["a"]  # every read is its own copy

    Tags.tags = ["stored"]
    Tags.reset_settings()
    assert Tags.tags == ["a"]


def test_to_dict_reports_converted_defaults():
    class PortSettings(Settings):
        port: int = non_storage_setting(default="8080")

    assert PortSettings.to_dict() == {"port": 8080}


def test_no_default_and_none_defaults():
    class Bare(Settings):
        nothing = NonStorageSetting()
        empty: Optional[int] = non_storage_setting(default=None)

    assert Bare.nothing is None
    assert Bare.empty is None


def test_unannotated_default_serves_as_declared():
    class Plain(Settings):
        raw = NonStorageSetting(default=42)

    assert Plain.raw == 42


def test_subclass_serves_the_converted_default_and_does_not_reconvert(monkeypatch):
    real = default_validation.correct_type
    calls = []

    def spy(value, annotation):
        calls.append(value)
        return real(value, annotation)

    monkeypatch.setattr(default_validation, "correct_type", spy)

    class Base(Settings):
        port: int = non_storage_setting(default="8080")

    assert calls == ["8080"]

    class Sub(Base):
        extra: str = non_storage_setting(default="x")

    # the inherited member shares the base's descriptor: converted once
    assert calls == ["8080", "x"]
    assert Sub.port == 8080
    assert (
        Sub.__settings_members__["port"].descriptor is Base.__settings_members__["port"].descriptor
    )


# ---------------------------------------------------------------------------
# conversion tier: unconvertible defaults fail the class statement


def test_unconvertible_default_fails_class_creation():
    with pytest.raises(TypeError, match="invalid defaults in BadSettings") as info:

        class BadSettings(Settings):
            when: datetime.datetime = non_storage_setting(default="not-a-timestamp")

    assert "when" in str(info.value)
    assert "cannot convert 'not-a-timestamp' to datetime" in str(info.value)


def test_bool_default_for_int_member_is_rejected():
    # the conversion keeps bools and ints apart on purpose; the isinstance
    # tier would have accepted it (True is an int to isinstance)
    with pytest.raises(TypeError, match="cannot convert True to int"):

        class Flagged(Settings):
            flag: int = non_storage_setting(default=True)


def test_wrong_enum_member_name_is_rejected():
    with pytest.raises(TypeError) as info:

        class Bad(Settings):
            shade: Shade = non_storage_setting(default="mauve")

    assert "cannot convert 'mauve' to enum Shade" in str(info.value)


def test_literal_default_outside_values_is_rejected():
    with pytest.raises(TypeError, match="mauve"):

        class Bad(Settings):
            shade: Literal["red", "green"] = non_storage_setting(default="mauve")


def test_all_violations_are_listed_at_once():
    with pytest.raises(TypeError) as info:

        class Mixed(Settings):
            when: datetime.datetime = non_storage_setting(default="nope")
            endpoint: Endpoint = non_storage_setting(default=42)

    text = str(info.value)
    assert "Mixed" in text
    assert "when" in text and "cannot convert" in text
    assert "endpoint" in text and "is not an instance" in text


# ---------------------------------------------------------------------------
# isinstance tier: pass-through annotations


def test_custom_type_default_not_an_instance_fails():
    with pytest.raises(TypeError) as info:

        class Bad(Settings):
            endpoint: Endpoint = non_storage_setting(default="https://x.example")

    assert "endpoint" in str(info.value)
    assert "default 'https://x.example' is not an instance of the annotated type Endpoint" in str(
        info.value
    )


def test_custom_type_default_instance_passes():
    declared = Endpoint("https://x.example")

    class Good(Settings):
        endpoint: Endpoint = non_storage_setting(default=declared)

    assert Good.endpoint is not declared  # served as a deep copy
    assert Good.endpoint.url == "https://x.example"


def test_none_default_passes_for_a_custom_type():
    class Nullable(Settings):
        endpoint: Endpoint = non_storage_setting(default=None)

    assert Nullable.endpoint is None


def test_optional_custom_type_accepts_an_instance():
    class Opt(Settings):
        endpoint: Optional[Endpoint] = non_storage_setting(default=Endpoint("https://x.example"))

    assert Opt.endpoint.url == "https://x.example"


def test_bare_generic_class_is_checked_subscripted_is_skipped():
    # bare Box is a plain class: the isinstance question applies
    with pytest.raises(TypeError, match="is not an instance"):

        class BadBare(Settings):
            box: Box = non_storage_setting(default=42)

    # a subscripted generic cannot be asked; it is skipped, not crashed on
    class Parametrized(Settings):
        box: "Box[int]" = non_storage_setting(default=42)

    assert Parametrized.box == 42


def test_any_protocol_and_newtype_annotations_are_not_asked():
    class Open(Settings):
        blob: Any = non_storage_setting(default=object())
        runnable: Runnable = non_storage_setting(default=42)  # not @runtime_checkable
        uid: UserId = non_storage_setting(default="not-even-an-int")

    assert isinstance(Open.blob, object)
    assert Open.runnable == 42
    assert Open.uid == "not-even-an-int"


# ---------------------------------------------------------------------------
# isinstance tier inside containers


def test_container_element_not_an_instance_fails():
    with pytest.raises(TypeError) as info:

        class Bad(Settings):
            points: List[Endpoint] = non_storage_setting(default=[Endpoint("https://a"), 42])

    assert "points[1]: value 42 is not an instance of the annotated type Endpoint" in str(
        info.value
    )


def test_nested_containers_are_walked_to_the_bottom():
    with pytest.raises(TypeError) as info:

        class Bad(Settings):
            grid: List[List[Endpoint]] = non_storage_setting(default=[[42]])

    assert "grid[0][0]: value 42 is not an instance of the annotated type Endpoint" in str(
        info.value
    )


def test_mapping_keys_and_values_are_checked():
    with pytest.raises(TypeError, match=r"routes\[key 42\]"):

        class BadKeys(Settings):
            routes: Dict[Endpoint, str] = non_storage_setting(default={42: "x"})

    with pytest.raises(TypeError, match=r"routes\['x'\]"):

        class BadValues(Settings):
            routes: Dict[str, Endpoint] = non_storage_setting(default={"x": 42})


def test_tuple_positions_are_checked():
    with pytest.raises(TypeError, match=r"pair\[1\]"):

        class BadPair(Settings):
            pair: Tuple[str, Endpoint] = non_storage_setting(default=("a", 42))

    with pytest.raises(TypeError, match=r"many\[1\]"):

        class BadMany(Settings):
            many: Tuple[Endpoint, ...] = non_storage_setting(default=[Endpoint("https://a"), 42])


def test_set_elements_are_checked():
    with pytest.raises(TypeError, match=r"unique\[0\]"):

        class BadSet(Settings):
            unique: Set[Endpoint] = non_storage_setting(default=[42])


def test_valid_container_defaults_pass():
    first = Endpoint("https://a")
    second = Endpoint("https://b")

    class Good(Settings):
        points: List[Endpoint] = non_storage_setting(default=[first, second])
        routes: Dict[str, Endpoint] = non_storage_setting(default={"a": first})
        sparse: List[Optional[Endpoint]] = non_storage_setting(default=[None, second])

    assert [point.url for point in Good.points] == ["https://a", "https://b"]
    assert Good.routes["a"].url == "https://a"
    assert Good.sparse[0] is None and Good.sparse[1].url == "https://b"


def test_none_elements_pass_everywhere():
    class WithNone(Settings):
        points: List[Endpoint] = non_storage_setting(default=[None])

    assert WithNone.points == [None]


def test_storage_form_container_default_is_checked_after_conversion():
    # a JSON-shaped default converts to dicts — which are not Endpoint
    # instances, and the annotation promised they would be
    with pytest.raises(TypeError) as info:

        class Bad(Settings):
            points: List[Endpoint] = non_storage_setting(default='[{"url": "https://a"}]')

    assert "points[0]: value {'url': 'https://a'} is not an instance" in str(info.value)


def test_contract_elements_are_validated_by_the_conversion_itself():
    with pytest.raises(TypeError, match="cannot convert True to int"):

        class BadBool(Settings):
            nums: List[int] = non_storage_setting(default=[True])


def test_dataclass_elements_convert_instead():
    class Good(Settings):
        proxies: List[Proxy] = non_storage_setting(default=[{"host": "h"}])

    assert Good.proxies == [Proxy("h")]


def test_union_element_positions_are_not_checked():
    # a union with a custom-class arm accepts anything, like on load
    class Open(Settings):
        items: List[Union[Endpoint, int]] = non_storage_setting(default=[42])

    assert Open.items == [42]


def test_bare_containers_check_nothing_inside():
    class Bare(Settings):
        items: list = non_storage_setting(default=[42])

    assert Bare.items == [42]


def test_unresolvable_annotation_keeps_the_default_as_declared():
    # a function-local class cannot be resolved by get_type_hints, so the
    # annotation stays a raw string: no conversion, no isinstance question
    def build():
        class Inner:
            pass

        class Unresolved(Settings):
            inner: Inner = non_storage_setting(default=42)

        return Unresolved

    settings_class = build()
    assert settings_class.inner == 42


# ---------------------------------------------------------------------------
# NO_DEFAULT members: the served None must pass the member's constraints


def test_no_default_member_rejected_by_eq_fails_class_creation():
    with pytest.raises(TypeError, match="invalid defaults in BadStandIn") as info:

        class BadStandIn(Settings):
            token: Optional[str] = environment_variable_setting(
                name="DV_NO_DEFAULT_TOKEN", default=NO_DEFAULT, eq="fixed"
            )

    assert "token" in str(info.value)
    assert "value None must be equal to 'fixed'" in str(info.value)


def test_no_default_member_rejected_by_validator_fails_class_creation():
    with pytest.raises(TypeError) as info:

        class BadValidator(Settings):
            retries: Optional[int] = environment_variable_setting(
                name="DV_NO_DEFAULT_RETRIES",
                default=NO_DEFAULT,
                validator=lambda value: value is not None,
            )

    assert "retries" in str(info.value)
    assert "value None failed the validator" in str(info.value)


def test_no_default_member_rejected_by_member_reference_fails_class_creation():
    with pytest.raises(TypeError) as info:

        class BadReference(Settings):
            anchor: str = non_storage_setting(default="a")
            tied: Optional[str] = environment_variable_setting(
                name="DV_NO_DEFAULT_TIED", default=NO_DEFAULT, eq=anchor
            )

    assert "tied" in str(info.value)
    assert "value None must be equal to the value of 'anchor' ('a')" in str(info.value)


def test_no_default_member_passes_constraints_none_satisfies():
    # the constraints an unset Optional member is designed for accept None
    class Quiet(Settings):
        port: Optional[int] = environment_variable_setting(
            name="DV_QUIET_PORT", default=NO_DEFAULT, gt=0, le=65535
        )
        host: Optional[str] = environment_variable_setting(
            name="DV_QUIET_HOST", default=NO_DEFAULT, min_length=1, regex=r"^\w+$"
        )
        mode: Optional[str] = environment_variable_setting(
            name="DV_QUIET_MODE", default=NO_DEFAULT, ne="backup"
        )

    assert Quiet.port is None
    assert Quiet.host is None
    assert Quiet.mode is None


def test_no_default_member_with_falsy_when_passes():
    # while the condition member is falsy in the all-default state, the
    # constraints do not apply to the stand-in either
    class Gated(Settings):
        tls: bool = non_storage_setting(default=False)
        port: Optional[int] = environment_variable_setting(
            name="DV_GATED_PORT",
            default=NO_DEFAULT,
            eq=443,
            validator=lambda value: value is not None,
            when=tls,
        )

    assert Gated.port is None


def test_required_member_rejecting_none_passes_class_creation():
    # REQUIRED serves no stand-in at all: there is nothing to check
    class Demanding(Settings):
        retries: Optional[int] = environment_variable_setting(
            name="DV_DEMANDING_RETRIES",
            default=REQUIRED,
            validator=lambda value: value is not None,
        )

    assert "retries" in Demanding.__settings_members__


# ---------------------------------------------------------------------------
# attribute construction itself is not the validation point


def test_attribute_accepts_any_default_before_class_binding():
    attribute = SettingsAttribute(default=object())
    assert attribute.default is not NO_DEFAULT
