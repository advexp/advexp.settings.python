# Samples

The project's repository contains runnable examples in the
[samples/](https://github.com/advexp/advexp.settings.python/tree/main/samples)
directory. Each sample is a standalone program. It creates its demo files
next to itself and prints what happens at every step. To run a sample:

1. Clone the repository.
2. Install the packages that are named in the sample's docstring. They are
   available on PyPI: `pip install advexp-settings` and
   `pip install advexp-configuration`.
3. Run the file from the repository root.

## Advexp.Settings

These are the samples of the read-write package, located in
[samples/settings/](https://github.com/advexp/advexp.settings.python/tree/main/samples/settings):

- [settings_api.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/settings_api.py)
  — a live tour of the application API: one class with members that use
  several bundled backends, run from start to finish.
- [custom_backend.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/custom_backend.py)
  — a complete custom backend built on the plugin contracts of
  `plugin_api`. It includes a custom attribute parameter, behavior that is
  controlled by metadata, and dynamic settings on the same storage.
- [plain_declarations.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/plain_declarations.py)
  — the plain declaration style in full: plain declarations, the
  full-featured `setting(...)` form, source builders, the cases in which the
  `class` statement fails with an error, and a file per environment.
- [environment_variables.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/environment_variables.py)
  — the environment backend: declaring, loading, and saving settings,
  operations on a single setting, and metadata.
- [dotenv_file.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/dotenv_file.py)
  — the dotenv backend: reading a `.env` file and editing it line by line.
- [json_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_settings.py)
  — the JSON backend: the file layout, dataclass values, and operations on a
  single setting.
- [json_path_index.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_path_index.py)
  — array indices in the `path=` of the JSON backend.
- [toml_dotted_keys.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/toml_dotted_keys.py)
  — dotted keys, quoted segments, and array slots in the TOML backend.
- [toml_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/toml_settings.py)
  — the TOML backend, including the values that it stores in native TOML
  form.
- [yaml_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/yaml_settings.py)
  — the YAML backend, including what a round-trip save preserves.
- [json_dynamic_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_dynamic_settings.py),
  [toml_dynamic_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/toml_dynamic_settings.py),
  and
  [yaml_dynamic_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/yaml_dynamic_settings.py)
  — dynamic collections, with one tour for each file format.
- [validation.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/validation.py)
  — the full validation tour: every constraint, the rules across members,
  and every point at which the checks run.
- [json_custom_metadata.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_custom_metadata.py)
  and
  [json_dynamic_metadata.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_dynamic_metadata.py)
  — metadata in use: a serializer that reacts to the runtime metadata of its
  class, and a dynamic collection that is controlled by its own metadata
  parameters.

## Advexp.Configuration

These are the samples of the read-only package, located in
[samples/configuration/](https://github.com/advexp/advexp.settings.python/tree/main/samples/configuration):

- [configuration_api.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/configuration_api.py)
  — a live tour of the application API: one chain of bundled sources, read
  in order from first to last.
- [custom_source.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/custom_source.py)
  — a complete custom source built on the contracts of
  `advexp.configuration.plugin_api`.
- [plain_declarations.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/plain_declarations.py)
  — the plain declaration style from start to finish: plain declarations,
  `chain_setting(...)`, constant members, and the source chain together with
  the cases in which it fails with an error.
- [environment_variables.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/environment_variables.py)
  and
  [dotenv_file.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/dotenv_file.py)
  — the read-only workflow of the environment family.
- [json_configuration.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/json_configuration.py),
  [toml_configuration.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/toml_configuration.py),
  and
  [yaml_configuration.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/yaml_configuration.py)
  — the file sources, with one tour for each format.
- [validation.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/validation.py)
  — the validation tour: the same capabilities as in Advexp.Settings, with
  violations reported through the load errors of the read-only package.

## Both packages together

These samples use both packages and are located in
[samples/both_packages/](https://github.com/advexp/advexp.settings.python/tree/main/samples/both_packages):

- [one_app.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/both_packages/one_app.py)
  — both packages in one application. Every storage address belongs to a
  class, not to a package (the naming prefixes are per class, and file
  bindings name their own files), so the two packages coexist without
  collisions.
- [dynamic_exchange.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/both_packages/dynamic_exchange.py)
  — a dynamic collection that one package writes and the other reads back.
  The two sides share nothing except the file.
