# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The extension plugin base class: the contract plus the conventional
implementation.

:class:`ExtensionBasePlugin` adds the conventional implementation of the
context binding over the
:class:`~advexp.settings_base.extension_plugin_interface.IExtensionPlugin`
contract; deriving from it is the easiest way to write an extension, not a
requirement.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional

from advexp.settings_base.extension_plugin_interface import IExtensionPlugin

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.context import SettingsContext


class ExtensionBasePlugin(IExtensionPlugin):
    """Base class for extension plugins: the contract plus context binding.

    Everything but ``plugin_name`` is ready: the bound context is kept in
    the name-mangled ``__context`` attribute (a subclass's own same-named
    attribute cannot clobber the context binding), and reaching for the
    context before it is bound raises a clear error. An extension declares
    no storage: a ``binding`` declaration fails the ``class`` statement —
    a storage backend derives from
    :class:`~advexp.settings_base.settings_base_plugin.SettingsBasePlugin`
    instead.
    """

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        for ancestor in cls.__mro__:
            if ancestor is ExtensionBasePlugin:
                break
            if "binding" in vars(ancestor):
                raise TypeError(
                    f"{cls.__name__} is an extension plugin: it declares no "
                    "attribute-to-serializer binding. Derive from "
                    "SettingsBasePlugin for a storage backend."
                )

    def __init__(self) -> None:
        self.__context: Optional[SettingsContext] = None

    # -- IPlugin --------------------------------------------------------------

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
