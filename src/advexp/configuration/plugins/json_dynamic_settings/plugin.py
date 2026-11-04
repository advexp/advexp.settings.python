# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the dynamic JSON file reader.

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
from advexp.configuration.plugins.json_settings.serializer import JSONSettingsSerializer
from advexp.configuration.plugins.json_settings.setting import JSONSetting
from advexp.settings_base.dynamic_document import JSON_DYNAMIC_GROUP_METADATA


class JSONDynamicSettingsPlugin(ReadOnlyDocumentDynamicSettingsPlugin):
    """Plugin object for reading dynamic settings from the JSON file.

    The namespaced pin names the backend. The collection reads the dynamic
    entries that a writing class of the settings distribution stored in the
    JSON document. The group key of the writer, declared next to the source
    binding of the class (``json_source(dynamic_of=...)``), names the group;
    the file levels and the inherited section parameters place it exactly as
    the writer laid it out. The pin is the own registry slot of the dynamic
    side: the binding ties it to the ``JSONSettingsSerializer`` of this package
    and never touches the registration of ``JSONSetting`` by the static source
    plugin.
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

    WRITER_GROUP_METADATA = JSON_DYNAMIC_GROUP_METADATA

    @property
    def plugin_name(self) -> str:
        return "JSONDynamicSettings"


LibraryConfiguration.register_settings_plugin(JSONDynamicSettingsPlugin)
