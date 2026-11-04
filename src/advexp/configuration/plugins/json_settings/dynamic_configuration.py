# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The dynamic side of the configuration of the JSON source.

The holder carries the reading defaults of the dynamic side, which reads
the dynamic entries that a settings class of the writing distribution
stored. It lives next to the serializer of the source in the package of the
JSON family, as the reading counterpart of the holder of the writing
distribution. The dynamic plugin package re-exports it for the classes that
enable the dynamic side.
"""

from __future__ import annotations

import os
from typing import Optional

from advexp.settings_base.json_file import check_json_file
from advexp.settings_base.module_default import register_module_default
from advexp.settings_base.module_default_meta import ModuleDefaultMeta


class JSONDynamicSettingsConfiguration(metaclass=ModuleDefaultMeta):
    """Dynamic JSON configuration reading (class-level state)."""

    file_path: Optional[os.PathLike] = None
    """Own file for the dynamic entries this package reads (``str`` or
    ``os.PathLike``).

    When set, every dynamic collection without a binding of its own reads
    this file, apart from the file of the declared members; the document
    inside is shaped by the section parameters of the reading plugin, placed
    exactly as the writing side laid it out.

    A module can declare the dynamic entries' own file for itself alone —
    at the module's top level, with ``for_this_module`` from the package
    root::

        JSONDynamicSettingsConfiguration.file_path = for_this_module(
            Path("dynamic-settings.json")
        )

    The declaration holds for the classes of the module it is written in
    and wins over this attribute; modules without one keep reading the
    attribute. When both are unset (the default), the dynamic entries are
    read from the class's source file — the link's own ``file=``: the
    one-document default the writing side writes by default too.
    """


register_module_default(
    JSONDynamicSettingsConfiguration,
    lambda configuration: configuration.file_path,
    check_json_file,
)
