# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The per-pass serializer cache of the serialization pipeline."""

from __future__ import annotations

from typing import Any, Dict, Type

from advexp.settings_base.context import SettingsContext
from advexp.settings_base.library_configuration import LibraryConfiguration, SerializerFactory
from advexp.settings_base.plugin_not_enabled_error import PluginNotEnabledError
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.settings_serializer_wishes_interface import (
    ISettingsSerializerWishes,
)


class SerializerCache:
    """Per-pass serializer cache."""

    def __init__(self, context: SettingsContext) -> None:
        self._context = context
        self._serializers: Dict[Any, ISettingsSerializer] = {}

    def get_for_attribute(self, attribute: ISettingAttribute) -> ISettingsSerializer:
        return self.get_for_attribute_class(type(attribute))

    def get_for_attribute_class(
        self, attribute_class: Type[ISettingAttribute]
    ) -> ISettingsSerializer:
        # the serializer registered for the attribute class
        factory = LibraryConfiguration._get_serializer_factory(attribute_class)
        if factory is None:
            raise PluginNotEnabledError(
                f"Cannot find a serializer for the '{attribute_class.__name__}' attribute. "
                "Import the corresponding plugin module to enable it."
            )
        return self._get(factory)

    def _get(self, factory: SerializerFactory) -> ISettingsSerializer:
        serializer = self._serializers.get(factory)
        if serializer is None:
            serializer = factory()
            if isinstance(serializer, ISettingsSerializerWishes):
                serializer.set_serializer_params(self._context)
            self._serializers[factory] = serializer
        return serializer
