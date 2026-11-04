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
        - set_class_metadata
        - get_class_metadata
        - get_class_all_metadata
        - contains_class_metadata
        - delete_class_metadata
        - delete_class_all_metadata

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
the non-storage parameter come from the package root; the file families
provide theirs in their plugin modules — the same modules that the
examples import as `js`, `ts`, `ys`, `env` and `dotenv`.

::: advexp.settings.setting

::: advexp.settings.Setting

::: advexp.settings.non_storage_setting

::: advexp.settings.plugins.json_settings.json_setting

::: advexp.settings.plugins.json_settings.JSONSetting

::: advexp.settings.plugins.toml_settings.toml_setting

::: advexp.settings.plugins.toml_settings.TOMLSetting

::: advexp.settings.plugins.yaml_settings.yaml_setting

::: advexp.settings.plugins.yaml_settings.YAMLSetting

::: advexp.settings.plugins.environment.variables.environment_variable_setting

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

## Path parameters

::: advexp.settings.env_parameter

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
