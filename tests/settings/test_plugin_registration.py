"""Plugin registration semantics (``register_settings_plugin``,
``register_settings_attribute``)."""

from __future__ import annotations

import abc
from typing import Any, ClassVar, Optional, Sequence, Tuple

import pytest

from advexp.settings import Settings
from advexp.settings.plugin_api import (
    NO_DEFAULT,
    NOT_FOUND,
    AttributeSerializerBinding,
    DynamicSettingAttribute,
    ISettingAttribute,
    ISettingsPlugin,
    LibraryConfiguration,
    SettingsAttribute,
    SettingsBasePlugin,
    SettingsBaseSerializer,
)


class NullSerializer(SettingsBaseSerializer):
    """A concrete registry token: the four storage operations are no-ops."""

    def load(self, setting_name: str, attr: Any) -> Any:
        return NOT_FOUND

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        return None

    def delete(self, setting_name: str, attr: Any) -> None:
        return None

    def contains(self, setting_name: str, attr: Any) -> bool:
        return False


class CountingPlugin(SettingsBasePlugin):
    setup_calls = 0

    @property
    def plugin_name(self) -> str:
        return "counting"

    @classmethod
    def setup(cls) -> None:
        cls.setup_calls += 1


def test_reregistration_does_not_rerun_setup():
    CountingPlugin.setup_calls = 0
    LibraryConfiguration.register_settings_plugin(CountingPlugin)
    assert CountingPlugin.setup_calls == 1

    LibraryConfiguration.register_settings_plugin(CountingPlugin)
    assert CountingPlugin.setup_calls == 1  # setup skipped on the second pass
    assert LibraryConfiguration.registered_plugin_classes().count(CountingPlugin) == 1


def test_base_plugin_implements_the_plugin_contract():
    assert issubclass(SettingsBasePlugin, ISettingsPlugin)


class DeclaredAttribute(SettingsAttribute):
    """Attribute of the declarative-binding test pair."""


class DeclaredSerializer(NullSerializer):
    """Serializer class of the declarative-binding test pair."""


def test_base_plugin_setup_registers_the_declared_binding():
    class DeclaredPlugin(SettingsBasePlugin):
        binding = AttributeSerializerBinding(DeclaredAttribute, DeclaredSerializer)

        @property
        def plugin_name(self) -> str:
            return "declared"

    LibraryConfiguration.register_settings_plugin(DeclaredPlugin)
    try:
        assert LibraryConfiguration._get_serializer_factory(DeclaredAttribute) is DeclaredSerializer
    finally:
        LibraryConfiguration._attribute_serializers.pop(DeclaredAttribute, None)


def test_base_plugin_setup_registers_nothing_without_the_pair():
    class PlainPlugin(SettingsBasePlugin):
        @property
        def plugin_name(self) -> str:
            return "plain"

    before = set(LibraryConfiguration._attribute_serializers)
    LibraryConfiguration.register_settings_plugin(PlainPlugin)
    assert set(LibraryConfiguration._attribute_serializers) == before


def test_base_plugin_setup_rejects_a_malformed_binding():
    class HalfDeclaredPlugin(SettingsBasePlugin):
        # a plain value is not a declarative binding: the named
        # AttributeSerializerBinding constructor is the API
        # noinspection PyClassVar
        binding: ClassVar[Optional[AttributeSerializerBinding]] = "not-a-binding"  # type: ignore[assignment]

        @property
        def plugin_name(self) -> str:
            return "half-declared"

    with pytest.raises(TypeError, match="AttributeSerializerBinding"):
        LibraryConfiguration.register_settings_plugin(HalfDeclaredPlugin)


class InterfaceOnlyPlugin(ISettingsPlugin):
    """A plugin implementing the contract alone, without the base class.

    The context lives wherever the plugin wants: here a plain attribute
    written by the contract's bind_context hook.
    """

    def __init__(self) -> None:
        self._bound_context = None

    # -- ISettingsPlugin -------------------------------------------------------

    @property
    def plugin_name(self) -> str:
        return "interface-only"

    @property
    def context(self):
        return self._bound_context

    def bind_context(self, context) -> None:
        self._bound_context = context


LibraryConfiguration.register_settings_plugin(InterfaceOnlyPlugin)


class InterfaceHostSettings(Settings):
    pass


def test_plugin_implementing_only_the_interface_works():
    plugin = InterfaceHostSettings.get_plugin(InterfaceOnlyPlugin)
    assert plugin.plugin_name == "interface-only"
    assert plugin.context is InterfaceHostSettings.__settings_context__
    # the handle is the requested class, not a base type
    assert isinstance(plugin, InterfaceOnlyPlugin)


class SharedAttribute(SettingsAttribute):
    """Attribute registered by two plugins sharing one serializer pair."""


class SerializerA(NullSerializer):
    """Distinct serializer factory; never instantiated by the registry."""


class SerializerB(NullSerializer):
    """Another distinct factory for the same attribute."""


def test_attribute_reregistration_with_same_factory_is_noop():
    LibraryConfiguration.register_settings_attribute(SharedAttribute, SerializerA)
    # a second plugin registering the same pair must not raise
    LibraryConfiguration.register_settings_attribute(SharedAttribute, SerializerA)


def test_attribute_reregistration_with_different_factory_raises():
    LibraryConfiguration.register_settings_attribute(SharedAttribute, SerializerA)
    with pytest.raises(ValueError, match="already registered"):
        LibraryConfiguration.register_settings_attribute(SharedAttribute, SerializerB)


# -- the namespaced pin (DynamicSettingAttribute) ---------------------------------


class PinnedAttribute(SettingsAttribute):
    """Attribute whose pin slot is tested independently of its own."""


class PinSerializerA(NullSerializer):
    """Factory bound to the attribute's own slot."""


class PinSerializerB(NullSerializer):
    """Factory bound to the pin's slot."""


def test_pin_is_a_stable_namespaced_subclass():
    assert DynamicSettingAttribute[PinnedAttribute] is DynamicSettingAttribute[PinnedAttribute]
    pin = DynamicSettingAttribute[PinnedAttribute]
    assert issubclass(pin, PinnedAttribute)  # the attribute's namespaced form
    assert pin.pinned_attribute_class is PinnedAttribute
    with pytest.raises(TypeError, match="setting attribute class"):
        # the invalid subscript itself is the case under test
        # noinspection PyTypeHints
        _ = DynamicSettingAttribute[int]  # type: ignore[type-var]


def test_pin_slot_is_independent_of_the_attribute_slot():
    pin = DynamicSettingAttribute[PinnedAttribute]
    LibraryConfiguration.register_settings_attribute(PinnedAttribute, PinSerializerA)
    LibraryConfiguration.register_settings_attribute(pin, PinSerializerB)
    try:
        # different factories under the two slots are not a conflict
        assert LibraryConfiguration._get_serializer_factory(pin) is PinSerializerB
        assert LibraryConfiguration._get_serializer_factory(PinnedAttribute) is PinSerializerA
    finally:
        LibraryConfiguration._attribute_serializers.pop(PinnedAttribute, None)
        LibraryConfiguration._attribute_serializers.pop(pin, None)


def test_pin_reregistration_with_different_factory_raises():
    pin = DynamicSettingAttribute[PinnedAttribute]
    LibraryConfiguration.register_settings_attribute(pin, PinSerializerA)
    try:
        with pytest.raises(ValueError, match="already registered"):
            LibraryConfiguration.register_settings_attribute(pin, PinSerializerB)
    finally:
        LibraryConfiguration._attribute_serializers.pop(pin, None)


class InterfaceSetting(ISettingAttribute):
    """A setting attribute that implements the contract alone.

    It has no base class and inherits nothing but ``object``. The fields of the
    contract are properties over private instance storage, which is declared and
    initialized in ``__init__``. This is the same shape that
    :class:`SettingsAttribute` gives to its subclasses, written out here by
    hand.
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = NO_DEFAULT,
        aliases: Optional[Sequence[str]] = None,
    ) -> None:
        self._name: Optional[str] = name
        self._default: Any = default
        self._aliases: Tuple[str, ...] = tuple(aliases) if aliases else ()
        self._bound_name: Optional[str] = None
        self._declaring_class: Optional[type] = None

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def default(self) -> Any:
        return self._default

    @property
    def aliases(self) -> Tuple[str, ...]:
        return self._aliases

    @property
    def bound_name(self) -> Optional[str]:
        return self._bound_name

    @bound_name.setter
    def bound_name(self, value: Optional[str]) -> None:
        # (the metaclass's write on binding, not an initializer re-run)
        # noinspection PyAttributeOutsideInit
        self._bound_name = value

    @property
    def declaring_class(self) -> Optional[type]:
        return self._declaring_class

    @declaring_class.setter
    def declaring_class(self, value: Optional[type]) -> None:
        # noinspection PyAttributeOutsideInit
        self._declaring_class = value


def interface_setting(*, name: Optional[str] = None, default: Any = NO_DEFAULT) -> Any:
    return InterfaceSetting(name=name, default=default)


class InterfaceAttrSettings(Settings):
    mode: str = interface_setting(name="app.mode", default="production")


def test_attribute_implementing_only_the_interface_is_detected():
    members = InterfaceAttrSettings.__settings_members__
    assert "mode" in members
    attribute = members["mode"].attribute
    assert isinstance(attribute, InterfaceSetting)
    assert attribute.bound_name == "mode"  # set by the metaclass on binding
    assert InterfaceAttrSettings.mode == "production"  # the declared default
    InterfaceAttrSettings.mode = "staging"
    assert InterfaceAttrSettings.mode == "staging"  # routed through the descriptor


def test_interface_requires_the_contract_fields():
    # the abstract fields are enforced at instantiation: an attribute class
    # missing any of the contract fields fails instead of misbehaving at
    # the first storage pass
    # (the missing contract fields are the point of the class)
    # noinspection PyAbstractClass
    class IncompleteSetting(ISettingAttribute):
        name = None  # default and bound_name missing

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompleteSetting"):
        # (the failed instantiation is the test)
        # noinspection PyAbstractClass
        IncompleteSetting()


def test_unregistered_pin_has_no_registration():
    # no fallback: a pin without its own registration resolves like any
    # unregistered attribute class (PluginNotEnabledError downstream)
    pin = DynamicSettingAttribute[PinnedAttribute]
    LibraryConfiguration.register_settings_attribute(PinnedAttribute, PinSerializerA)
    try:
        assert LibraryConfiguration._get_serializer_factory(pin) is None
    finally:
        LibraryConfiguration._attribute_serializers.pop(PinnedAttribute, None)


def test_setting_attribute_interface_is_an_abc():
    # the contract's fields are abstract members, so the interface is an
    # ABC — ABCMeta lands in every attribute's MRO (the known cost: PyCharm
    # may weak-flag constructor kwargs; see the interface docstring)
    assert issubclass(ISettingAttribute, abc.ABC)


def test_interface_attribute_serves_the_dynamic_plugin_pin():
    from advexp.settings.plugin_api import DynamicSettingsBasePlugin

    class InterfaceSerializer(NullSerializer):
        """No-op concrete serializer for the interface-only attribute."""

    class InterfaceDynamicPlugin(DynamicSettingsBasePlugin):
        binding = AttributeSerializerBinding(InterfaceSetting, InterfaceSerializer)

        @property
        def plugin_name(self) -> str:
            return "interface-dynamic"

    assert InterfaceDynamicPlugin.binding.attribute_class is InterfaceSetting
