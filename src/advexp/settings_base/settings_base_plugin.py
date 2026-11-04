# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin base class: the contract plus the conventional implementation.

:class:`SettingsBasePlugin` adds the conventional implementation of the
context binding over the
:class:`~advexp.settings_base.settings_plugin_interface.ISettingsPlugin`
contract, and the declarative attribute-to-serializer binding
(:attr:`binding`, registered by the base :meth:`setup`); deriving
from it is the easiest way to write a plugin, not a requirement.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, ClassVar, Optional, TypeVar

from advexp.settings_base.attribute_serializer_binding import AttributeSerializerBinding
from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.settings_plugin_interface import ISettingsPlugin

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.context import SettingsContext

PluginT = TypeVar("PluginT", bound=ISettingsPlugin)
"""The plugin class a ``get_plugin`` call requests; the call returns its instance."""


class SettingsBasePlugin(ISettingsPlugin):
    """Base class for settings plugins: the contract plus context binding.

    Everything but ``plugin_name`` is ready: the bound context is kept in
    the name-mangled ``__context`` attribute (a subclass's own same-named
    attribute cannot clobber the context binding), and reaching for the
    context before it is bound raises a clear error. A plugin declaring a
    :attr:`binding` needs no ``setup()`` of its own — the base one
    registers it.
    """

    binding: ClassVar[Optional[AttributeSerializerBinding]] = None
    """The declarative attribute-to-serializer binding.

    Registered by the base :meth:`setup` when the plugin is registered. A
    plugin serving several attribute classes, or registering its pieces
    differently, overrides ``setup()`` instead of declaring a binding;
    ``None`` (the default) registers nothing. On a
    dynamic-settings plugin base the binding is mandatory and its attribute
    class is the collection's pin.
    """

    @classmethod
    def setup(cls) -> None:
        """Register the declared attribute-to-serializer pair, if there is one.

        It runs when the plugin is registered (when its module is imported). If
        nothing is declared, there is nothing to register.
        """
        if cls.binding is None:
            return
        if not isinstance(cls.binding, AttributeSerializerBinding):
            raise TypeError(f"{cls.__name__}.binding must be an AttributeSerializerBinding")
        LibraryConfiguration.register_settings_attribute(
            cls.binding.attribute_class, cls.binding.serializer_class
        )

    def __init__(self) -> None:
        self.__context: Optional[SettingsContext] = None

    # -- ISettingsPlugin -------------------------------------------------------

    @property
    def context(self) -> SettingsContext:
        """The settings class context this plugin instance is bound to."""
        if self.__context is None:
            raise RuntimeError(
                f"plugin {type(self).__name__} is not bound to a settings class yet. "
                "Get it via Settings.get_plugin(...)"
            )
        return self.__context

    def bind_context(self, context: SettingsContext) -> None:
        self.__context = context

    @property
    @abc.abstractmethod
    def plugin_name(self) -> str:
        """Human-readable plugin name."""
