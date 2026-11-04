# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The single import site through which the two public facades read the
internals.

Both ``advexp/configuration/__init__.py`` and
``advexp.configuration.plugin_api`` re-export names from the private
modules. Importing all of them here reduces each facade to a single import
from this package, and it lists the whole public surface explicitly in one
place.
"""

from advexp.configuration._internal.chain_setting import ChainSetting, chain_setting
from advexp.configuration._internal.configuration import Configuration
from advexp.configuration._internal.configuration_attribute import ConfigurationAttribute
from advexp.configuration._internal.constant_setting import ConstantSetting, constant_setting
from advexp.configuration._internal.package_name import PACKAGE_NAME
from advexp.configuration._internal.read_only_dynamic_settings_plugin import (
    ReadOnlyDocumentDynamicSettingsPlugin,
)
from advexp.configuration._internal.version import __version__
from advexp.settings_base.aggregate_load_error import AggregateLoadError
from advexp.settings_base.attribute_serializer_binding import (
    AttributeSerializerBinding,
)
from advexp.settings_base.constraint_violation_error import (
    ConstraintViolationError,
)
from advexp.settings_base.context import SETTINGS_CONTEXT_ATTR, SettingsContext
from advexp.settings_base.conversion_error import ConversionError
from advexp.settings_base.document_dynamic_settings_plugin import (
    DocumentDynamicSettingsPlugin,
)
from advexp.settings_base.dynamic_setting_attribute import DynamicSettingAttribute
from advexp.settings_base.dynamic_settings_base_plugin import (
    DynamicSettingsBasePlugin,
)
from advexp.settings_base.dynamic_settings_info_interface import IDynamicSettingsInfo
from advexp.settings_base.env_parameter import (
    EnvParameter,
    env_parameter,
    resolve_templated_path,
)
from advexp.settings_base.library_configuration import LibraryConfiguration, family_entry_key
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.missing_value_error import MissingValueError
from advexp.settings_base.module_default import declared_module_defaults, for_this_module
from advexp.settings_base.names import setting_name_candidates, spelled_with_aliases
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.not_found import NOT_FOUND
from advexp.settings_base.plugin_not_enabled_error import PluginNotEnabledError
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.secret_bytes import SecretBytes
from advexp.settings_base.secret_str import SecretStr
from advexp.settings_base.serializer_notification_sink_interface import (
    ISerializerNotificationSink,
)
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.setting_name_describer_interface import (
    ISettingNameDescriber,
)
from advexp.settings_base.settings_base_plugin import SettingsBasePlugin
from advexp.settings_base.settings_base_serializer import SettingsBaseSerializer
from advexp.settings_base.settings_plugin_interface import ISettingsPlugin
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.settings_serializer_wishes_interface import (
    ISettingsSerializerWishes,
)
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.source_describer_interface import ISourceDescriber
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.source_link_sink_interface import ISourceLinkSink
from advexp.settings_base.source_load_error import SourceLoadError
from advexp.settings_base.sources import (
    LINK_PARAMETERS_PARAM,
    SOURCE_CHAIN_METADATA,
    Sources,
)
from advexp.settings_base.user_facing_error import UserFacingError

__all__ = [
    "AggregateLoadError",
    "AttributeSerializerBinding",
    "ChainSetting",
    "Configuration",
    "ConfigurationAttribute",
    "ConstantSetting",
    "ConstraintViolationError",
    "ConversionError",
    "DocumentDynamicSettingsPlugin",
    "DynamicSettingAttribute",
    "DynamicSettingsBasePlugin",
    "EnvParameter",
    "IDynamicSettingsInfo",
    "ISettingAttribute",
    "ISettingNameDescriber",
    "ISourceDescriber",
    "ISourceLinkSink",
    "ISerializerNotificationSink",
    "ISettingsPlugin",
    "ISettingsSerializer",
    "ISettingsSerializerWishes",
    "LINK_PARAMETERS_PARAM",
    "MissingValueError",
    "NO_DEFAULT",
    "NOT_FOUND",
    "PACKAGE_NAME",
    "PluginNotEnabledError",
    "REQUIRED",
    "ReadOnlyDocumentDynamicSettingsPlugin",
    "MemberLoadError",
    "SecretBytes",
    "SecretStr",
    "SettingsBasePlugin",
    "SettingsBaseSerializer",
    "LibraryConfiguration",
    "SettingsContext",
    "SETTINGS_CONTEXT_ATTR",
    "SourceBinding",
    "SourceLink",
    "SourceLoadError",
    "Sources",
    "SOURCE_CHAIN_METADATA",
    "UserFacingError",
    "__version__",
    "chain_setting",
    "constant_setting",
    "declared_module_defaults",
    "env_parameter",
    "family_entry_key",
    "for_this_module",
    "resolve_templated_path",
    "setting_name_candidates",
    "spelled_with_aliases",
]
