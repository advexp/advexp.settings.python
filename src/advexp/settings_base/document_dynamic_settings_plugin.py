# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Dynamic-settings plugins over document backends.

A document backend stores everything in one tree-shaped document. The JSON,
TOML, and YAML file backends of the family are such backends. Its dynamic
side lays out the entries in a section of that document: one nested object
per settings class, with the own name of the entry as the key inside it.

This intermediate base carries the two parameters that place the section, so
every document backend of the family spells them in the same way. The root
base stays unchanged for backends without sections (a key-value store, for
example), which keep deriving from it directly.
"""

from __future__ import annotations

from typing import Any, Optional

from advexp.settings_base.dynamic_settings_base_plugin import DynamicSettingsBasePlugin
from advexp.settings_base.pointer import pointer_steps

_UNSET_SECTION = object()
"""Marks "no explicit binding": a section parameter falls back to its default."""


# (plugin_name stays abstract: a document backend names itself in its
# concrete plugin)
# noinspection PyAbstractClass
class DocumentDynamicSettingsPlugin(DynamicSettingsBasePlugin):
    """Base class for dynamic-settings plugins over document backends.

    The document holds the dynamic entries in their own section, with one nested
    object per settings class. The section is placed by two parameters that
    mirror the ``name=``/``path=`` of the setting attribute of a document
    family:

    - :attr:`dynamic_settings_section_name` is the key of the section. Assign
      another key to relocate the section, or ``None`` for the flat layout
      (``D``-prefixed full-name keys at the document root).
    - The optional :attr:`dynamic_settings_section_path` locates the section
      deeper in the document tree, as a JSON Pointer.

    The layout that is built from these parameters is the shared storage form of
    the family: a file that is written by one distribution of the family can be
    read back through another. The parameters and the layout that they spell are
    therefore a frozen contract, not a private choice of a backend.

    Both parameters follow the MRO of the settings class, each independently.
    The most derived class that has an explicit binding of a parameter wins, and
    a class without one uses the default of the parameter, which puts the
    section at the document root. A backend without sections derives from the
    root base instead: the parameters here belong to document backends only.
    """

    DEFAULT_SECTION = "dynamic"
    """Document key holding the dynamic entries (absent in the flat layout)."""

    def __init__(self) -> None:
        super().__init__()
        # name-mangled: the section binding state behind the properties,
        # kept out of a subclass's reach
        self.__dynamic_settings_section_name: Any = _UNSET_SECTION
        self.__dynamic_settings_section_path: Any = _UNSET_SECTION

    # -- section parameters ----------------------------------------------------

    @property
    def dynamic_settings_section_name(self) -> Optional[str]:
        """The document key that holds the dynamic entries of this class.

        A non-empty string names the section object in which the entries are stored
        (grouped per settings class). ``None`` switches to the flat layout:
        ``D``-prefixed full-name keys at the document root, next to the static keys.
        The path parameter does not apply to the flat layout.
        """
        if self.__dynamic_settings_section_name is _UNSET_SECTION:
            return self.DEFAULT_SECTION
        return self.__dynamic_settings_section_name

    @dynamic_settings_section_name.setter
    def dynamic_settings_section_name(self, value: Optional[str]) -> None:
        if value is None or (isinstance(value, str) and value):
            self.__dynamic_settings_section_name = value
        else:
            raise ValueError(
                "dynamic_settings_section_name must be a non-empty string (the document "
                "section for the dynamic entries) or None (flat full-name keys)"
            )

    @property
    def dynamic_settings_section_path(self) -> Optional[str]:
        """The location of the section in the document tree, as a JSON Pointer.

        ``"/config"`` places the section inside the ``config`` object of the
        document, in the same way that the ``path=`` of a setting of a document
        family locates a static key. ``None`` (the default) keeps the section at the
        document root. The path must start with ``/``; ``~1`` and ``~0`` escape
        ``/`` and ``~``.
        """
        if self.__dynamic_settings_section_path is _UNSET_SECTION:
            return None
        return self.__dynamic_settings_section_path

    @dynamic_settings_section_path.setter
    def dynamic_settings_section_path(self, value: Optional[str]) -> None:
        if value is not None:
            # fail at the binding site, not at the first storage pass
            pointer_steps(value)
        self.__dynamic_settings_section_path = value

    # -- raw section bindings ---------------------------------------------------

    def _raw_dynamic_section_name(self) -> Any:
        """The name binding as it was set: the sentinel if it was never assigned.

        This is the raw form that the section resolution of the document side
        reads, because the effective property cannot tell an explicit binding from
        the default. The single underscore is deliberate: this is a contract between
        modules, not an interface for subclasses.
        """
        return self.__dynamic_settings_section_name

    def _raw_dynamic_section_path(self) -> Any:
        """The path binding as it was set: the sentinel if it was never assigned.

        This is the raw form that the section resolution of the document side
        reads, because the effective property cannot tell an explicit binding from
        the default. The single underscore is deliberate: this is a contract between
        modules, not an interface for subclasses.
        """
        return self.__dynamic_settings_section_path
