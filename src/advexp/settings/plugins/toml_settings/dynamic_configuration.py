# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The dynamic side of the configuration of the TOML backend.

The holder lives next to the serializer of the backend in the package of
the TOML family. The serializer resolves the file and the names of the
dynamic entries through it, and the dynamic plugin package re-exports it for
the classes that enable the dynamic side. The two holders together (this one
and ``TOMLSettingsConfiguration``) configure the one backend from its two
sides.
"""

from __future__ import annotations

import os
from typing import Optional

from advexp.settings_base.module_default import register_module_default
from advexp.settings_base.module_default_meta import ModuleDefaultMeta
from advexp.settings_base.names import DEFAULT_SETTINGS_NAME_PATTERN
from advexp.settings_base.toml_file import check_toml_file


class TOMLDynamicSettingsConfiguration(metaclass=ModuleDefaultMeta):
    """Dynamic TOML settings configuration (class-level state)."""

    file_path: Optional[os.PathLike] = None
    """Own file for the dynamic entries (``str`` or ``os.PathLike``).

    When set, every dynamic collection without a binding of its own goes to
    this file, apart from the file of the declared (static) settings; the
    document inside is shaped by the section parameters of
    :class:`TOMLDynamicSettingsPlugin` as usual.

    A settings module can declare the dynamic entries' own file for
    itself alone — at the module's top level, with ``for_this_module``
    from the package root:

    ```python
    TOMLDynamicSettingsConfiguration.file_path = for_this_module(
        Path("dynamic-settings.toml")
    )
    ```

    The declaration holds for the classes of the module it is written
    in and wins over this attribute; modules without one keep reading
    the attribute. When both are unset (the default), the dynamic
    entries share the static file: the class's own binding, the static
    module declaration, or ``TOMLSettingsConfiguration.file_path``.
    """

    name_pattern: str = DEFAULT_SETTINGS_NAME_PATTERN
    """The name pattern of the dynamic entries; the default is the full
    pattern ``{module}.{class}.{name}``.

    The pattern shapes both visible names of an entry: the class object's
    key in the document's dynamic section (the part in front of the
    entry's own name) and, in the flat layout, the ``D``-prefixed full
    name at the document root. The plain names the collection works with
    never change — the pattern spells them into the document. It may hold
    the ``{NamespaceName}`` (module), ``{ClassName}``, ``{FieldName}`` and
    ``{Delimiter}`` slots, and it must hold ``{FieldName}`` and a class
    part: without ``{FieldName}`` the entries would collide, and without a
    class part the section layout has nothing to group (and parse back)
    the entries by — both are refused at the first pass that needs a name.
    The static members' keys are not governed here: they take their form
    from the static side's own naming options (the ``toml_options``
    family entry), and a backend without them keeps the default full
    pattern.

    Changing the pattern is a migration of every file already written: the
    class object's key in the section and the flat full names change with
    it, and the entries stored under the old spelling are no longer found.
    That is the declaring side's own choice — set the pattern once, before
    the first stored file, or move the entries by hand when it changes.
    """


register_module_default(
    TOMLDynamicSettingsConfiguration,
    lambda configuration: configuration.file_path,
    check_toml_file,
)
