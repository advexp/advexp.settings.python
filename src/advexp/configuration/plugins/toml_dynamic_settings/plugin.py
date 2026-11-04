# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the dynamic TOML file reader.

Importing the package (which imports this module) enables the reader, so no
explicit registration call is needed. See the package docstring for a
usage example.
"""

from __future__ import annotations

from advexp.configuration.plugin_api import (
    AttributeSerializerBinding,
    DynamicSettingAttribute,
    LibraryConfiguration,
    ReadOnlyDocumentDynamicSettingsPlugin,
)
from advexp.configuration.plugins.toml_settings.serializer import TOMLSettingsSerializer
from advexp.configuration.plugins.toml_settings.setting import TOMLSetting
from advexp.settings_base.dynamic_document import TOML_DYNAMIC_GROUP_METADATA


class TOMLDynamicSettingsPlugin(ReadOnlyDocumentDynamicSettingsPlugin):
    """Plugin object for reading dynamic settings from the TOML file.

    The namespaced pin names the backend. The collection reads the dynamic
    entries that a writing class of the settings distribution stored in the
    TOML document. The group key of the writer, declared next to the source
    binding of the class (``toml_source(dynamic_of=...)``), names the group;
    the file levels and the inherited section parameters place it exactly as
    the writer laid it out. The pin is the own registry slot of the dynamic
    side: the binding ties it to the ``TOMLSettingsSerializer`` of this package
    and never touches the registration of ``TOMLSetting`` by the static source
    plugin.
    """

    # the pin's own slot: the binding registered by the base setup() makes this
    # package self-sufficient — importing it alone is enough — and leaves the
    # static plugin's registration of TOMLSetting untouched
    binding = AttributeSerializerBinding(
        # the runtime subscription builds a concrete subclass of TOMLSetting;
        # the static type application cannot express that, so the checker
        # sees an abstract class here
        DynamicSettingAttribute[TOMLSetting],  # type: ignore[type-abstract]
        TOMLSettingsSerializer,
    )

    WRITER_GROUP_METADATA = TOML_DYNAMIC_GROUP_METADATA

    @property
    def plugin_name(self) -> str:
        return "TOMLDynamicSettings"


LibraryConfiguration.register_settings_plugin(TOMLDynamicSettingsPlugin)
