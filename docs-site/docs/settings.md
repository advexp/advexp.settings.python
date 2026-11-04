---
# This page is the landing page of its nav section: the header breadcrumb
# shows the section name for it (docs-site/overrides/partials/header.html).
section_landing: true
---

# Advexp.Settings: the read-write package

Typed application settings with pluggable storage backends.

Declare your settings once as a typed class. The library loads and saves them
through pluggable backends: environment variables or local files (JSON, TOML,
YAML, or dotenv).

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

In this example, the environment is the class's only source, and plain
members such as `mode` are read from it. The `json_file(...)` entry is a file
declaration, not a second source: it only names the file used by JSON members
such as `retries`.

!!! note "Status"

    This project is a work in progress. The package structure is in place,
    but the public API is still under development and may change before the
    first stable release.

## Why Advexp.Settings

- **Plain declarations.** Declare a member with a type annotation. Add a
  value to give it a default, or leave the value out to make it required.
  Where values are stored is determined by the backends configured on the
  class, so in most cases you do not need any special factory functions.
- **Typed values.** Values are converted to the annotated type when they are
  loaded, so a setting always holds a value of its declared type.
- **Class-level operations.** You load, save, and delete settings on the
  class itself. There are no instances to create or pass around.
- **Pluggable backends.** Environment variables, dotenv, JSON, TOML, and YAML
  files are supported out of the box. A custom backend is a plain plugin
  class.
- **No third-party dependencies.** Installed without extras, the package
  pulls in nothing beyond its own family: its only dependency is
  `advexp-settings-base`, the family's shared base package, which itself
  depends on nothing. Environment variables and JSON files run on the
  standard library alone, and each parser that is not already in the
  standard library arrives as an extra.
- **Lossless round trips.** Dataclasses, datetimes, decimals, UUIDs,
  secrets, and nested containers are restored unchanged after being saved
  and loaded.
- **Validation.** Value constraints and rules that involve several members
  (cross-member rules) are checked when the class is created, on every load,
  and on every save.
- **One file per environment.** A file name can contain a placeholder that
  is filled in from an environment variable. For example,
  `settings-{APP_ENV}.json` gives you a separate file for each environment.
- **Safe saving.** Saving updates only the settings being saved. Comments,
  formatting, and keys that the library does not recognize are left exactly
  as they were.
- **A read-only counterpart.** The Advexp.Configuration package uses the same
  declarations to load values from its sources, but never writes anything
  back.

## Where to go next

- [Getting started](settings/getting-started.md): installation and your
  first settings class.
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
- [Samples](samples.md): runnable example programs for both packages,
  located in the project's repository.
- [Configuration](configuration.md): Advexp.Configuration, the read-only
  counterpart.
- [API reference](api/index.md): classes, exceptions, and plugin interfaces,
  generated from the docstrings.