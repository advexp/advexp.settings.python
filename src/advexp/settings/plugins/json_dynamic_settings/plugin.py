# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the dynamic JSON file backend.

Importing the package (which imports this module) enables the backend — no
explicit registration call is needed; see the package docstring for a usage
example.
"""

from __future__ import annotations

import os
from typing import Optional, Union

from advexp.settings.plugin_api import (
    AttributeSerializerBinding,
    DocumentDynamicSettingsPlugin,
    DynamicSettingAttribute,
    LibraryConfiguration,
)
from advexp.settings.plugins.json_settings.dynamic_configuration import (
    JSONDynamicSettingsConfiguration,
)
from advexp.settings.plugins.json_settings.serializer import JSONSettingsSerializer
from advexp.settings.plugins.json_settings.setting import JSONSetting
from advexp.settings_base.json_file import JSON_DYNAMIC_FILE_METADATA


class JSONDynamicSettingsPlugin(DocumentDynamicSettingsPlugin):
    """Plugin object for dynamic settings in the JSON settings file.

    The namespaced pin names the backend. Dynamic entries use the same
    serializer and the same file as the ``JSONSetting`` members of the class,
    so one document holds the static and the runtime settings of the class side
    by side: the static entries under their full names, and the dynamic ones in
    the dedicated section of the document (see
    :attr:`DocumentDynamicSettingsPlugin.dynamic_settings_section_name` and
    :attr:`DocumentDynamicSettingsPlugin.dynamic_settings_section_path`,
    inherited here).

    The shared file is the default, not a rule. The ``dynamic_file=`` parameter
    of the ``json_source(...)`` binding of the class (class metadata; the
    nearest entry along the class chain wins) or the module-wide
    ``JSONDynamicSettingsConfiguration.file_path`` moves the dynamic entries to
    a file of their own, separate from the static one.

    The pin is the own registry slot of the dynamic side: the binding ties it to
    ``JSONSettingsSerializer`` here and never touches the registration of
    ``JSONSetting`` by the static plugin.
    """

    # the pin's own slot: the binding registered by the base setup() makes this
    # package self-sufficient — importing it alone is enough — and leaves the
    # static plugin's registration of JSONSetting untouched
    binding = AttributeSerializerBinding(
        # the runtime subscription builds a concrete subclass of JSONSetting;
        # the static type application cannot express that, so the checker
        # sees an abstract class here
        DynamicSettingAttribute[JSONSetting],  # type: ignore[type-abstract]
        JSONSettingsSerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "JSONDynamicSettings"

    @property
    def file_path(self) -> Optional[Union[str, os.PathLike]]:
        """The own file for the dynamic entries of this class; ``None`` when the static
        file governs.

        Reading resolves along the class chain: the own binding of the class, or
        otherwise the binding of the nearest ancestor. Assigning re-binds the class
        itself: the value is validated and stored as an own metadata entry of the
        class. The declarative ``json_source(dynamic_file=...)`` binding and an
        assignment here are therefore the same channel. The binding moves the
        dynamic entries of this class to the named file, separate from the static
        side, and it wins over ``JSONDynamicSettingsConfiguration.file_path``.

        ``None`` means that there is no binding anywhere. In that case, the module
        default applies. If the module default is also unset, the dynamic entries go
        into the static file. ``delete_class_metadata`` removes the binding again.
        """
        return self.context.get_class_metadata(JSON_DYNAMIC_FILE_METADATA)

    @file_path.setter
    def file_path(self, value: Union[str, os.PathLike]) -> None:
        self.context.set_class_metadata(JSON_DYNAMIC_FILE_METADATA, value)

    def _dynamic_name_pattern(self) -> str:
        """The name pattern of the dynamic entries: a parameter of the configuration.

        The storage names of the base class are built from it: the class part of
        the section layout, the flat full names, and the parsing of the enumerated
        names in a pass. The serializer over the entries reads the same parameter,
        so the two sides agree by construction. See
        :attr:`JSONDynamicSettingsConfiguration.name_pattern` for the rules of the
        form and the migration note.
        """
        return JSONDynamicSettingsConfiguration.name_pattern


LibraryConfiguration.register_settings_plugin(JSONDynamicSettingsPlugin)
