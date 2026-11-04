# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The declarative attribute-to-serializer binding."""

from __future__ import annotations

from typing import NamedTuple, Type

from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer


class AttributeSerializerBinding(NamedTuple):
    """The declarative binding of a settings plugin.

    ``attribute_class`` is the setting attribute class that the
    ``serializer_class`` of the plugin serves. The :meth:`setup
    <advexp.settings_base.settings_base_plugin.SettingsBasePlugin.setup>` of the
    plugin base registers the binding when the plugin is registered (when its
    module is imported). On a dynamic-settings plugin base, the binding is
    mandatory, and ``attribute_class`` is the pin of the dynamic collection.
    """

    attribute_class: Type[ISettingAttribute]
    serializer_class: Type[ISettingsSerializer]
