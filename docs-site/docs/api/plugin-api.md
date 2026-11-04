# Plugin API

The contracts for backend and source authors: the vocabulary shared by the
extension points of both packages. It covers the contracts themselves, the
base classes that fill them with defaults, the bindings that declare a
plugin, and the registration that opens a family's seats for plugins.

## The serializer side

::: advexp.settings.plugin_api.ISettingsSerializer

::: advexp.settings.plugin_api.ISettingsSerializerWishes

::: advexp.settings.plugin_api.ISerializerNotificationSink

::: advexp.settings.plugin_api.ISettingNameDescriber

::: advexp.settings.plugin_api.ISourceDescriber

::: advexp.settings.plugin_api.SettingsBaseSerializer

## The plugin side

::: advexp.settings.plugin_api.ISettingsPlugin

::: advexp.settings.plugin_api.SettingsBasePlugin

## The settings context

::: advexp.settings.plugin_api.SettingsContext

## The attribute side

::: advexp.settings.plugin_api.ISettingAttribute

::: advexp.settings.plugin_api.SettingsAttribute

::: advexp.settings.plugin_api.AttributeSerializerBinding

::: advexp.configuration.plugin_api.ConfigurationAttribute

## The dynamic side

::: advexp.settings.plugin_api.IDynamicSettingsInfo

::: advexp.settings.plugin_api.DynamicSettingsBasePlugin

::: advexp.settings.plugin_api.DocumentDynamicSettingsPlugin

::: advexp.settings.plugin_api.DynamicSettingAttribute

::: advexp.settings.plugin_api.get_dynamic_settings_class_prefix

The configuration package's read-only facade built on the same base classes:

::: advexp.configuration.plugin_api.ReadOnlyDocumentDynamicSettingsPlugin

## The layered side

The additional contracts that the configuration package defines for its
source chains.

::: advexp.configuration.plugin_api.ISourceLinkSink

::: advexp.configuration.plugin_api.SourceBinding

::: advexp.configuration.plugin_api.SourceLink

::: advexp.configuration.plugin_api.SOURCE_CHAIN_METADATA

::: advexp.configuration.plugin_api.LINK_PARAMETERS_PARAM

::: advexp.configuration.plugin_api.resolve_templated_path

## Registration and module defaults

::: advexp.settings.plugin_api.register_source_link_key

::: advexp.settings.plugin_api.register_file_seat

::: advexp.settings.plugin_api.register_module_default

::: advexp.settings.plugin_api.module_default_for

::: advexp.settings.plugin_api.family_entry_key

::: advexp.settings.plugin_api.ModuleDefaultMeta

## The supporting names

::: advexp.settings.plugin_api.UserFacingError

::: advexp.settings.plugin_api.NOT_FOUND

::: advexp.settings.plugin_api.NO_DEFAULT

::: advexp.settings.plugin_api.REQUIRED

::: advexp.settings.plugin_api.PACKAGE_NAME

::: advexp.settings.plugin_api.SETTINGS_CONTEXT_ATTR

::: advexp.settings.plugin_api.SettingRef

::: advexp.settings.plugin_api.EnvParameter

::: advexp.settings.plugin_api.env_parameter

::: advexp.settings.plugin_api.setting_name_candidates

::: advexp.settings.plugin_api.spelled_with_aliases
