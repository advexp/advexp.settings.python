# Settings API

The application-facing API of the settings package.

::: advexp.settings.Settings
    options:
      members:
        - load_settings
        - save_settings
        - delete_settings
        - reset_settings
        - validate_settings
        - load_setting
        - save_setting
        - delete_setting
        - reset_setting
        - contains_setting
        - to_dict
        - update_from_dict
        - to_object
        - update_from_object
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

::: advexp.settings.LibraryConfiguration
    options:
      members:
        - register_settings_plugin
        - registered_plugin_classes
        - register_settings_attribute
        - register_class_metadata_validator
        - set_log_level
        - logger

## Attribute parameters

The forms that a member's declaration can take. The plain parameter and
the sourceless parameter come from the package root; the file families
provide theirs in their plugin modules — the same modules that the
examples import as `js`, `ts`, `ys`, `env` and `dotenv`.

::: advexp.settings.setting

::: advexp.settings.sourceless_setting

::: advexp.settings.SourcelessSetting

The member factories of the source families are family-wide: they live in
`advexp.settings_base`, and the package of each family re-exports its
factory — importing that package is what enables the family, so the
factory and the backend always arrive together. They work in a class body
and in a [declaration base](../shared-declarations.md) alike.

::: advexp.settings.plugins.json_settings.json_setting
::: advexp.settings.plugins.toml_settings.toml_setting
::: advexp.settings.plugins.yaml_settings.yaml_setting
::: advexp.settings.plugins.environment.dotenv.dotenv_setting
::: advexp.settings.plugins.environment.variables.environment_variable_setting

## Shared declarations

::: advexp.settings.SettingDeclarations







::: advexp.settings.plugins.environment.dotenv.dotenv_setting

## Source builders

The only way to bind a class to its storage. A builder is passed as the
`options=` argument of the `class` statement. Use one builder per family; a
class can use as many families as it has storages.

::: advexp.settings.plugins.json_settings.json_source

::: advexp.settings.plugins.toml_settings.toml_source

::: advexp.settings.plugins.yaml_settings.yaml_source

::: advexp.settings.plugins.environment.variables.env_source

::: advexp.settings.plugins.environment.variables.NameCase

::: advexp.settings.plugins.environment.dotenv.dotenv_source

::: advexp.settings.plugins.mapping_source.mapping_source

::: advexp.settings.plugins.mapping_source.mapping_source_for

::: advexp.settings.plugins.mapping_source.MappingStorageLink

## File binders

::: advexp.settings.plugins.json_settings.json_file

::: advexp.settings.plugins.toml_settings.toml_file

::: advexp.settings.plugins.yaml_settings.yaml_file

::: advexp.settings.plugins.environment.dotenv.dotenv_file

## Dynamic file binders

::: advexp.settings.plugins.json_settings.json_dynamic_file

::: advexp.settings.plugins.toml_settings.toml_dynamic_file

::: advexp.settings.plugins.yaml_settings.yaml_dynamic_file

## Settings profiles

::: advexp.settings.settings_profile

## Module file defaults

::: advexp.settings.for_this_module

::: advexp.settings.declared_module_defaults

::: advexp.settings.plugins.json_settings.JSONSettingsConfiguration

::: advexp.settings.plugins.toml_settings.TOMLSettingsConfiguration

::: advexp.settings.plugins.yaml_settings.YAMLSettingsConfiguration

::: advexp.settings.plugins.environment.dotenv.DotenvConfiguration

## Dynamic settings

The plugins that store entries whose names are defined at runtime. The
plugin object holds the section parameters and the runtime `file_path`;
the configuration holder holds the module-level file and the name pattern.

::: advexp.settings.plugins.json_dynamic_settings.JSONDynamicSettingsPlugin

::: advexp.settings.plugins.json_dynamic_settings.JSONDynamicSettingsConfiguration

::: advexp.settings.plugins.toml_dynamic_settings.TOMLDynamicSettingsPlugin

::: advexp.settings.plugins.toml_dynamic_settings.TOMLDynamicSettingsConfiguration

::: advexp.settings.plugins.yaml_dynamic_settings.YAMLDynamicSettingsPlugin

::: advexp.settings.plugins.yaml_dynamic_settings.YAMLDynamicSettingsConfiguration

## The member address

The `setting_name` parameter of the per-member and the metadata methods:
a member name or a getter lambda for it.

::: advexp.settings.SettingRef

## Errors and sentinels

::: advexp.settings.SettingValidationError

::: advexp.settings.AggregateLoadError

::: advexp.settings.MemberLoadError

::: advexp.settings.MissingValueError

::: advexp.settings.ConversionError

::: advexp.settings.ConstraintViolationError

::: advexp.settings.SourceLoadError

::: advexp.settings.PluginNotEnabledError

::: advexp.settings.REQUIRED

## Secret wrappers

::: advexp.settings.SecretStr

::: advexp.settings.SecretBytes
