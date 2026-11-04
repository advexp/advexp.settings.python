# Configuration API

The application API of the counterpart package, which is read-only and
focused on loading.

::: advexp.configuration.Configuration
    options:
      members:
        - load_configuration

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

The forms that a member's declaration can take. The chain and constant
parameters come from the package root; the file families provide theirs
in their plugin modules — the same modules that the examples import as
`js`, `ts`, `ys`, `env` and `dotenv`.

::: advexp.configuration.chain_setting

::: advexp.configuration.ChainSetting

::: advexp.configuration.constant_setting

::: advexp.configuration.ConstantSetting

::: advexp.configuration.plugins.json_settings.json_setting

::: advexp.configuration.plugins.json_settings.JSONSetting

::: advexp.configuration.plugins.toml_settings.toml_setting

::: advexp.configuration.plugins.toml_settings.TOMLSetting

::: advexp.configuration.plugins.yaml_settings.yaml_setting

::: advexp.configuration.plugins.yaml_settings.YAMLSetting

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

## Path parameters

::: advexp.configuration.env_parameter

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
