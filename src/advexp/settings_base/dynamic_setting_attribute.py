# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The generic pin of a dynamic-settings plugin."""

from __future__ import annotations

from typing import ClassVar, Dict, Generic, Type

from advexp.settings_base.base_attribute import AttributeT
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.type_display import type_display


# (the pin itself carries the contract abstractly: only its parameterized
# form is concrete — see the class docstring)
# noinspection PyAbstractClass
class DynamicSettingAttribute(ISettingAttribute, Generic[AttributeT]):
    """The namespaced form of a setting attribute: ``DynamicSettingAttribute[X]``.

    Subscripting the class with a setting attribute class produces a distinct
    subclass of that class, once per base class, so the pin is a stable identity
    (``DynamicSettingAttribute[X] is DynamicSettingAttribute[X]``). The pin is
    used as the attribute class of the mandatory binding of a
    :class:`~advexp.settings_base.dynamic_settings_base_plugin.DynamicSettingsBasePlugin`.
    It gives the dynamic entries their own slot in the attribute-to-serializer
    registry: the serializer that the binding names serves only the dynamic
    entries, and the two slots never clash. Bindings of the pin leave the
    registration of the base attribute untouched, and vice versa. An
    unregistered pin resolves like any unregistered attribute class: it raises
    :class:`PluginNotEnabledError`.

    The class itself carries the contract only abstractly. The three fields of
    the interface stay abstract on it, so it cannot be instantiated. Only its
    parameterized form is a concrete setting attribute. It inherits from the
    base class of the subscription, and the constructor conventions of that base
    apply unchanged. Declaring a class member with a pin instance is not
    supported: the pin names the dynamic side of a backend, and it does not
    declare settings.

    ``Generic`` serves the type checkers only: it lets them read
    ``DynamicSettingAttribute[X]`` as a type application. At runtime, the
    subscription is the ``__class_getitem__`` below, which overrides the one that
    ``Generic`` would provide.
    """

    #: The setting attribute class this pin namespaces; set on every
    #: parameterized form.
    pinned_attribute_class: ClassVar[Type[ISettingAttribute]]

    _pins: ClassVar[Dict[type, type]] = {}

    def __class_getitem__(cls, attribute_class: type) -> type:
        if not (
            isinstance(attribute_class, type) and issubclass(attribute_class, ISettingAttribute)
        ):
            raise TypeError(
                "DynamicSettingAttribute[...] expects a setting attribute class "
                f"(an ISettingAttribute implementation), got {type_display(attribute_class)!r}"
            )
        pin = cls._pins.get(attribute_class)
        if pin is None:
            pin = type(
                f"DynamicSettingAttribute[{attribute_class.__name__}]",
                (cls, attribute_class),
                {
                    "__module__": cls.__module__,
                    "__doc__": cls.__doc__,
                    "pinned_attribute_class": attribute_class,
                },
            )
            cls._pins[attribute_class] = pin
        return pin
