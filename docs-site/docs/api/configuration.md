# Configuration API

The application API of the counterpart package, which is read-only and
focused on loading.

::: advexp.configuration.Configuration
    options:
      members:
        - load_configuration
        - contains_member
        - to_dict
        - to_object
        - get_plugin
        - set_setting_metadata
        - get_setting_metadata
        - get_setting_all_metadata
        - contains_setting_metadata
        - delete_setting_metadata
        - delete_setting_all_metadata
        - set_class_metadata
        - get_class_metadata
        - get_class_all_metadata
        - contains_class_metadata
        - delete_class_metadata
        - delete_class_all_metadata
        - reset_setting_all_metadata
        - reset_all_settings_metadata
        - reset_class_all_metadata

## Library configuration

::: advexp.configuration.LibraryConfiguration
    options:
      members:
        - register_settings_plugin
        - registered_plugin_classes
        - register_settings_attribute
        - register_class_metadata_validator
        - set_log_level
        - logger

## The source chain

::: advexp.configuration.Sources

## Attribute parameters

The forms that a member's declaration can take. The plain and sourceless
parameters come from the package root; the file families provide theirs
in their plugin modules — the same modules that the examples import as
`js`, `ts`, `ys`, `env` and `dotenv`.

::: advexp.configuration.setting

::: advexp.configuration.sourceless_setting

::: advexp.configuration.SourcelessSetting

The member factories of the source families are family-wide: they live in
`advexp.settings_base`, and the package of each family re-exports its
factory — importing that package is what enables the family, so the
factory and the backend always arrive together. They work in a
class body and in a [declaration base](../shared-declarations.md) alike.
`setting` is the configuration-side name of the same `setting`.

::: advexp.configuration.plugins.json_settings.json_setting
::: advexp.configuration.plugins.toml_settings.toml_setting
::: advexp.configuration.plugins.yaml_settings.yaml_setting
::: advexp.configuration.plugins.environment.dotenv.dotenv_setting
::: advexp.configuration.plugins.environment.variables.environment_variable_setting

## Shared declarations

::: advexp.configuration.SettingDeclarations






::: advexp.configuration.plugins.environment.variables.environment_variable_setting

::: advexp.configuration.plugins.environment.dotenv.dotenv_setting

## Source builders

The links that a source chain is built from. They are passed as the
`options=` argument of the `class` statement, with one builder per family,
either inside `Sources(...)` or on its own.

::: advexp.configuration.plugins.json_settings.json_source

::: advexp.configuration.plugins.toml_settings.toml_source

::: advexp.configuration.plugins.yaml_settings.yaml_source

::: advexp.configuration.plugins.environment.variables.env_source

::: advexp.configuration.plugins.environment.variables.NameCase

::: advexp.configuration.plugins.environment.dotenv.dotenv_source

::: advexp.configuration.plugins.mapping_source.mapping_source

::: advexp.configuration.plugins.mapping_source.mapping_source_for

::: advexp.configuration.plugins.mapping_source.MappingSourceLink

::: advexp.configuration.plugins.pydantic.pydantic_source

## Settings profiles

::: advexp.configuration.settings_profile

## Module file declarations

The reading defaults of the dynamic side can have a file of their own, just
as the backends of the settings package can. A module declares its own file
with `for_this_module`, and the process-wide attribute provides the file
for all other modules.

::: advexp.configuration.for_this_module

::: advexp.configuration.declared_module_defaults

::: advexp.configuration.plugins.json_dynamic_settings.JSONDynamicSettingsConfiguration

::: advexp.configuration.plugins.toml_dynamic_settings.TOMLDynamicSettingsConfiguration

::: advexp.configuration.plugins.yaml_dynamic_settings.YAMLDynamicSettingsConfiguration

## Dynamic readers

The read-only dynamic plugins, which read a collection previously written
by Advexp.Settings, are located in their plugin modules. They are described,
together with the rest of the dynamic settings, on the
[Dynamic settings](../dynamic-settings.md#reading-a-written-collection)
page.

::: advexp.configuration.plugins.json_dynamic_settings.JSONDynamicSettingsPlugin

::: advexp.configuration.plugins.toml_dynamic_settings.TOMLDynamicSettingsPlugin

::: advexp.configuration.plugins.yaml_dynamic_settings.YAMLDynamicSettingsPlugin

## The member address

The `setting_name` parameter of the metadata methods: a member name or a
getter lambda for it.

::: advexp.configuration.SettingRef

## Errors

::: advexp.configuration.AggregateLoadError

::: advexp.configuration.MemberLoadError

::: advexp.configuration.MissingValueError

::: advexp.configuration.ConversionError

::: advexp.configuration.ConstraintViolationError

::: advexp.configuration.SourceLoadError

::: advexp.configuration.PluginNotEnabledError

## Sentinels

::: advexp.configuration.REQUIRED

## Secret wrappers

::: advexp.configuration.SecretStr

::: advexp.configuration.SecretBytes
