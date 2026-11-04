# Advexp.Settings

Typed application settings and configuration with pluggable backends. The
project consists of two packages:

- **Advexp.Settings** loads and saves typed settings using pluggable
  backends.
- **Advexp.Configuration** is its read-only counterpart. It loads values for
  the same kind of declarations from its sources, but never writes anything
  back.

Both packages share the declaration syntax, the type conversion rules, the
validation, and the plugin API.

!!! note "Status"

    This project is a work in progress. The package structure is in place,
    but the public API is still under development and may change before the
    first stable release.

## Advexp.Settings

Settings are typed, and you load, save, and delete them through the settings
class itself. Storage backends are provided as plugins.

- **Typed values.** Values are converted to the annotated type when they are
  loaded, so a setting always holds a value of its declared type.
- **Pluggable backends.** Environment variables, dotenv, JSON, TOML, and YAML
  files are supported out of the box. A custom backend is a plain plugin
  class.
- **Lossless round trips.** Dataclasses, datetimes, decimals, UUIDs, secrets,
  and nested containers are restored unchanged after being saved and loaded.
- **Safe saving.** Saving updates only the settings being saved. Comments,
  formatting, and keys that the library does not recognize are left exactly
  as they were.
- **Validation.** Value constraints and rules that involve several members
  (cross-member rules) are checked when the class is created, on every load,
  and on every save.
- **Dynamic settings.** You can create settings at runtime, even when their
  names are not known in advance.

For a full introduction, see the [Settings](settings.md) page.

## Advexp.Configuration

The same declarations, loaded from a chain of pluggable sources and never
written back.

- **Typed values.** Values are converted to the annotated type when they are
  loaded, using the same conversion rules as Advexp.Settings.
- **The source chain.** Sources are read in order, from first to last, and
  the first source that has a value wins. The declared default acts as an
  implicit last layer.
- **Pluggable sources.** Environment variables, dotenv, JSON, TOML, and YAML
  files are supported out of the box. Sources use the same plugin interfaces
  as Advexp.Settings backends, so if you have written a backend for one
  package, you already know how to write one for the other.
- **Read-only by design.** The library never writes to sources. Assigning to
  a declared member, either on the class or on an instance, raises
  `TypeError`. To pick up new values after the sources change, call
  `load_configuration()` again.
- **Validation.** Value constraints and cross-member rules are checked when
  the class is created and at the end of every load.
- **Dynamic settings.** A configuration class can read the dynamic
  collections that a settings class has written to its file. The entries are
  loaded as a snapshot, which is refreshed only when you explicitly load
  again.

For a full introduction, see the [Configuration](configuration.md) page.

## Quick example

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env
import advexp.settings.plugins.json_settings as js


class AppSettings(
    adv_settings.Settings,
    options=(
        env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
        js.json_file("app-settings.json"),
    ),
):
    # read from APP_MODE: the prefix plus the member name in upper case
    mode: str = "production"

    # the same APP_SESSION_TTL address as mode, in the rich setting
    # form, which carries the default
    session_ttl: timedelta = adv_settings.setting(
        default=timedelta(minutes=30)
    )

    # read from the "retries" key of the JSON file
    retries: int = js.json_setting(name="retries", default=3)


# suppose the environment contains APP_SESSION_TTL=1:30:00
AppSettings.load_settings()

# prints datetime.timedelta(seconds=5400):
# the value is parsed into a timedelta, not left as a string
print(repr(AppSettings.session_ttl))
```

In this example, plain members such as `mode` are read only from the
environment. The `js.json_file(...)` entry does not make JSON a source for
every member. It only specifies the file used by JSON members such as
`retries`. The rule is explained on the [Settings](settings.md) page.

## Where to go next

- [Settings](settings.md): Advexp.Settings, the read-write package.
- [Configuration](configuration.md): Advexp.Configuration, the read-only
  counterpart.
- [Backends](backends.md): environment variables, dotenv, JSON, TOML, and
  YAML files.
- [Value types](value-types.md): supported types and how they are stored.
- [Validation](validation.md): value constraints and cross-member rules.
- [Snapshots](snapshots.md): independent copies of the settings state, as a
  dictionary or as an object.
- [Dynamic settings](dynamic-settings.md): settings whose names are known
  only at runtime.
- [Setting metadata](metadata.md): labels and flags attached to settings,
  for use by UIs and code generators.
- [Extending](extending.md): custom attribute parameters and custom
  backends.
- [Samples](samples.md): runnable example programs for both packages, located
  in the project's repository.
- [API reference](api/index.md): classes, exceptions, and plugin interfaces,
  generated from the docstrings.