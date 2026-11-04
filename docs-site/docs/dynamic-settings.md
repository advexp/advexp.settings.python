# Dynamic settings

Some settings get their names only at runtime. Examples are a window layout
that the user rearranges, dashboards, and options provided by plugins. Such
settings need no declared member. They live in the **dynamic collection** of
the plugin that is bound to the settings class, and the entries are stored in
whatever storage that plugin uses.

Advexp.Settings is responsible for writing: an entry is written back to its
storage through the plugin. The read-only package of the family,
[Advexp.Configuration](configuration.md), can read a written collection back.
It serves the same entries as a read-only snapshot through its own dynamic
plugins, without depending on this package (see
[Reading a written collection](#reading-a-written-collection) below).

By default, the bundled JSON plugin keeps dynamic entries in the same file as
the declared (static) members:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_dynamic_settings as jds


class LocalSettings(
    adv_settings.Settings,
    options=jds.json_source(file="app-settings.json"),
):
    host: str = "localhost"


plugin = LocalSettings.get_plugin(jds.JSONDynamicSettingsPlugin)

# this class's dynamic entries from the same file
plugin.load_settings()

# the type of the default is used for conversion
flag = plugin.get_setting("dark_mode", default=False)
plugin.set_setting("dark_mode", True)
plugin.save_settings()
```

Dynamic entries have their own section of the document, grouped by settings
class. Static keys stay at the root:

```json
{
  "app.LocalSettings.host": "localhost",
  "dynamic": {"app.LocalSettings": {"dark_mode": true}}
}
```

### TOML and YAML plugins

The bundled TOML plugin (`advexp.settings.plugins.toml_dynamic_settings`,
which requires the `toml` extra) uses the same arrangement in a TOML file.
There, the section is a table. Everything below that is said about the JSON
plugin applies to the TOML plugin in the same way, with the `toml_` names
instead of the `json_` ones (`TOMLDynamicSettingsPlugin` and its parameters,
`toml_source(dynamic_file=...)`, `toml_setting`).

In a TOML file, a static key is stored at the address that its name spells
out, and the class part of the section name is nested in the same way. The
name of an entry inside the class table is one literal key, because a name
that is given at runtime may be any text:

```toml
[app.LocalSettings]
host = "localhost"

[dynamic.app.LocalSettings]
dark_mode = true
```

The bundled YAML plugin (`advexp.settings.plugins.yaml_dynamic_settings`,
which requires the `yaml` extra) also works in the same way, with the
`yaml_` names (`YAMLDynamicSettingsPlugin` and its parameters,
`yaml_source(dynamic_file=...)`, `yaml_setting`). Its section is a mapping,
and dates and other native YAML values are stored as they are.

## Where entries go in a JSON document

Where the section is placed is a layout choice of the backend. Two parameters
control it, and they correspond to `name=` and `path=` of `JSONSetting`:

- `JSONDynamicSettingsPlugin.dynamic_settings_section_name` is the key of the
  section. Assign another key to move the section, or assign `None` to use
  the flat layout: at the document root, a key made of the letter `D` and
  the entry's full name, for example `"D.app.LocalSettings.dark_mode"`.
- `dynamic_settings_section_path` (optional) places the section deeper in the
  tree, as a JSON Pointer. For example, `"/config"` puts it inside the
  `config` object.

Both parameters are looked up along the MRO of the settings class, each
independently.

A static setting is rejected if its location overlaps the location of the
section. That means that its own key or `path=` is an ancestor of the
section, is inside it, or is equal to it. This way, static and dynamic
entries cannot collide.

## A separate file for dynamic entries

The shared file is only the default. `JSONDynamicSettingsConfiguration.file_path`
gives the dynamic entries a file of their own:

```python
import advexp.settings.plugins.json_dynamic_settings as jds

jds.JSONDynamicSettingsConfiguration.file_path = "dynamic-settings.json"
```

You can set the file at three levels. The more specific level wins:

1. **Process-wide:** the assignment above.
2. **Per module:** a settings module can declare its own dynamic file. Use
   `for_this_module` on the same parameter. For the classes of that module,
   this wins over the process-wide value, in the same way as on the static
   side.
3. **Per class:** use the `dynamic_file=` parameter of the class's
   `json_source(...)` binding. It wins over the module declaration. This is
   the same builder that also carries the file of the static members.

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.json_dynamic_settings as jds


class LocalSettings(
    adv_settings.Settings,
    options=jds.json_source(dynamic_file="dynamic-settings.json"),
):
    session_ttl: timedelta = timedelta(minutes=30)
```

The `file_path` property of the plugin instance does the same thing at
runtime: both channels write the same entry of the class's own metadata, so
the binding is inherited along the class chain. A subclass without its own
binding uses the nearest one above it.

If no dynamic file is set at any level (the default), the dynamic entries go
into the static file. The static file is the first of these that applies:

- the class's own `json_source(file=...)` binding;
- the module's `for_this_module` declaration;
- the process-wide `JSONSettingsConfiguration.file_path`.

Notes:

- **Switching files does not move entries.** Entries that were already saved
  stay where they were written.
- **In separate-file mode,** the static file has no dynamic section. The
  location of the section is no longer reserved, so a static key named
  `dynamic` is allowed.
- **If `file_path` names the same file as the static side,** the location of
  the section is reserved again, because one document can have only one
  layout.

## Dynamic names: name_pattern

The form of dynamic names is set at the module level, on the dynamic side:
`JSONDynamicSettingsConfiguration.name_pattern`. It determines two names of
an entry:

- the class key in the section;
- in the flat layout, the full name with the `D` prefix at the root.

The default is the full pattern, built from the same slots the static keys
use: `{NamespaceName}`, `{ClassName}` and `{FieldName}` joined by
`{Delimiter}`. The pattern must contain `{FieldName}` and a class part.
Without a class part, the section has nothing to group the entries by, and
only the flat layout works.

This pattern does not control the keys of static members. Their form comes
from the `json_source(name_pattern=...)` of the static family.

Changing the pattern does **not** move entries that are already stored. They
stay under the spelling that they were written with. Therefore, choose the
form before the first save, or move the entries by hand.

```python
import advexp.settings.plugins.json_dynamic_settings as jds

jds.JSONDynamicSettingsConfiguration.name_pattern = (
    "{ClassName}.{FieldName}"
)
# the section now groups the entries under "LocalSettings"
```

## Using the dynamic collection

- The collection lives in memory. Nothing is read from the storage until
  `load_settings()` runs, and nothing is written back until `save_settings()`
  runs.
- Called without `default`, `get_setting` returns the value in its raw
  storage form, without type conversion. It raises `KeyError` if the name is
  missing.
- The plugin behaves like a dictionary: it supports `len(plugin)`,
  `"name" in plugin`, `plugin.to_dict()`, and `plugin.update_from_dict()`.
- The iteration order is declared in the class metadata under the key
  `"dynamic_settings_order"`. The `ITERATION_ORDER_METADATA` constant of the
  plugin holds this name. The listed names come first, followed by the other
  names in the order in which they were added.
- Class-level calls such as `LocalSettings.load_settings()` load only the
  **declared** members. To work with the dynamic collection, use the plugin
  explicitly.

## Reading a written collection

Advexp.Configuration, the read-only package of the family, can read a dynamic
collection that was written by this package. A configuration class declares
the group of the writing class next to its source binding. The read-only
dynamic plugin then serves the entries as a snapshot, which an explicit
`load_configuration()` call refreshes.

The reading side never writes. Every method that would modify the collection
raises `TypeError`, which is the same protection that applies to the declared
members in that package.

```python
from datetime import timedelta

import advexp.configuration as adv_config
import advexp.configuration.plugins.json_dynamic_settings as jds
import advexp.configuration.plugins.json_settings as js

# the writing side: the class "app.LocalSettings" of the advexp.settings
# package keeps its dynamic entries in app-settings.json


class DashboardConfig(
    adv_config.Configuration,
    options=js.json_source(
        file="app-settings.json", dynamic_of="app.LocalSettings"
    ),
):
    # a declared member, read from the same file as usual
    session_ttl: timedelta = js.json_setting(default=timedelta(minutes=30))


dashboard = DashboardConfig.get_plugin(jds.JSONDynamicSettingsPlugin)
dashboard.load_configuration()  # this group's entries from the file
flag = dashboard.get_setting("dark_mode", default=False)
```

`dynamic_of` names the group under which the writer's entries are stored. For
a writer class with the default naming, this is `"app.LocalSettings"`. A
writer with its own dynamic `name_pattern` groups its entries under the class
part of that pattern.

The reading plugin has the same section parameters that this page describes.
If the writer moved the section or switched to the flat layout, set the same
values on the reading side before calling `load_configuration()`. The file
levels mirror those of the writer (`dynamic_file=`, the module declaration,
and the process-wide value). The default is the shared file, which is the
`file=` of the class's `json_source(...)`.

The stored form is a contract between the two packages: a file that is
written by one package can be read by the other. For this reason, the
layouts described above are frozen public formats, not a private choice of
this package. The sample `samples/both_packages/dynamic_exchange.py` walks
through the whole round trip, in both layouts and both formats.
