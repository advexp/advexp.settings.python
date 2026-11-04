# Advexp.Configuration: the read-only package

Typed, read-only application configuration for Python.

Advexp.Configuration is the read-only counterpart of
[Advexp.Settings](https://docs.advexp.net/settings/). Declare your
configuration once as a typed class. The library loads it from a chain of
pluggable sources and never writes anything back.

```python
from datetime import timedelta

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as env
import advexp.configuration.plugins.json_settings as js


class AppConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
        js.json_source(file="app-configuration.json"),
    ),
):
    # read from APP_MODE — the prefix plus the member name in upper
    # case — or, with no such variable, from the JSON file's key
    mode: str = "production"

    # read from APP_SESSION_TTL, built the same way
    session_ttl: timedelta = timedelta(minutes=30)

    # read from the "retries" key of the JSON file
    retries: int = js.json_setting(name="retries", default=3)


# suppose the environment contains APP_SESSION_TTL=1:30:00
AppConfig.load_configuration()

# prints datetime.timedelta(seconds=5400):
# the value is parsed into a timedelta, not left as a string
print(repr(AppConfig.session_ttl))
```

> **Status:** This project is a work in progress. The package structure is
> in place, but the public API is still under development and may change
> before the first stable release.

## Installation

```bash
pip install advexp-configuration
```

## Why Advexp.Configuration

- **Plain declarations.** Declare a member with a type annotation. Add a
  value to give it a default, or leave the value out to make it required.
  The sources configured on the class determine where the values come from.
- **Typed values.** Values are converted to the annotated type when they
  are loaded, so a member always holds a value of its declared type.
- **Class-level operations.** You load the configuration on the class
  itself. There are no instances to create or pass around.
- **Read-only by design.** The library never writes to sources, and loaded
  values are read-only: assigning to a declared member raises `TypeError`.
  To pick up new values after the sources change, call
  `load_configuration()` again.
- **A chain of sources.** Sources are read in the order in which they are
  listed, and the first source that has a value wins. If no source has a
  value, the member gets its declared default.
- **Pluggable sources.** Environment variables, dotenv, JSON, TOML, and
  YAML files are supported out of the box, and a mapping source reads
  values from a dictionary. A custom source is a plain plugin class.
- **No third-party dependencies.** Installed without extras, the package
  pulls in nothing beyond its own family: its only dependency is
  `advexp-settings-base`, the family's shared base package, which itself
  depends on nothing. Environment variables and JSON files run on the
  standard library alone, and each parser that is not already in the
  standard library arrives as an extra.
- **Shared type conversion.** Dataclasses, datetimes, decimals, UUIDs,
  secrets, and nested containers are converted from source values using the
  same rules as in Advexp.Settings.
- **Validation.** Value constraints and rules that involve several members
  (cross-member rules) are checked when the class is created and at the end
  of every load.
- **One file per environment.** A file name can contain a placeholder that
  is filled in from an environment variable. For example,
  `settings-{APP_ENV}.json` gives you a separate file for each environment.
- **A read-write counterpart.** The Advexp.Settings package loads **and
  saves** values through its backends. Both packages use the same
  declaration syntax, so you can usually move a class between them by
  changing the base class and the imports.

## Dynamic settings: reading a written collection

Advexp.Settings can store *dynamic settings*: settings whose names are
known only at runtime, such as window layouts, dashboards, or plugin
options. It keeps them in a dynamic collection and writes that collection
to its file.

Advexp.Configuration can read such a collection. To do this, pass the group
key of the writing class to the source declaration, for example
`json_source(dynamic_of="app.LocalSettings")`. The group key is not an
import path. It is the name under which the entries are stored in the file.
If the writing class uses the default name pattern, the group key is
`{module}.{class}`; this is where `"app.LocalSettings"` comes from. If the
writing class has its own dynamic `name_pattern`, its entries are grouped
under the class part of that pattern.

The read-only dynamic plugin provides the entries as a snapshot. The plugin
object has its own `load_configuration()` method, just like a configuration
class. Calling it on the plugin refreshes the snapshot. The class's own
`load_configuration()` loads only the declared members and never touches
the dynamic entries. Any attempt to write raises `TypeError`, just as with
declared members.

```python
from datetime import timedelta

import advexp.configuration as adv_config
import advexp.configuration.plugins.json_dynamic_settings as jds
import advexp.configuration.plugins.json_settings as js


# reads the dynamic group that the advexp.settings class
# "app.LocalSettings" wrote to app-settings.json
class DashboardConfig(
    adv_config.Configuration,
    options=js.json_source(
        file="app-settings.json", dynamic_of="app.LocalSettings"
    ),
):
    # a regular declared member, read from the same file
    session_ttl: timedelta = js.json_setting(default=timedelta(minutes=30))


dashboard = DashboardConfig.get_plugin(jds.JSONDynamicSettingsPlugin)

# reads the group written by app.LocalSettings from the file
dashboard.load_configuration()

flag = dashboard.get_setting("dark_mode", default=False)
```

Three readers are bundled:
`advexp.configuration.plugins.json_dynamic_settings` and the matching TOML
and YAML modules. The page
[Dynamic settings](https://docs.advexp.net/dynamic-settings/#reading-a-written-collection)
describes the reading side in detail: the group key, the file levels, the
section options that must match the writer's, and the storage format. The
storage format is frozen and serves as a public contract between the two
packages.

## Where to go next

- [Project site](https://advexp.net/advexp.configuration/): the
  Advexp.Configuration product page.
- [Getting started](https://docs.advexp.net/configuration/getting-started/):
  installation and your first configuration class.
- [Backends](https://docs.advexp.net/backends/): environment variables,
  dotenv, JSON, TOML, and YAML files. Configuration sources correspond to
  these backends.
- [Value types](https://docs.advexp.net/value-types/): supported types and
  how they are converted from source values.
- [Validation](https://docs.advexp.net/validation/): value constraints and
  cross-member rules.
- [Dynamic settings](https://docs.advexp.net/dynamic-settings/#reading-a-written-collection):
  reading a collection written by Advexp.Settings.
- [Samples](https://docs.advexp.net/samples/): runnable example programs
  for both packages, located in the project's repository.
- [Settings](https://docs.advexp.net/settings/): Advexp.Settings, the
  read-write counterpart.
- [API reference](https://docs.advexp.net/api/): classes, exceptions, and
  plugin interfaces, generated from the docstrings.

## License

Apache License 2.0. The full text is at
<https://www.apache.org/licenses/LICENSE-2.0> and in the LICENSE file.
