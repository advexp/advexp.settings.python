# Getting started with Advexp.Settings

## Installation

```bash
pip install advexp-settings
```

## Your first settings class

To declare settings, subclass `Settings` and declare each setting as a class
member:

- A bare annotation (`token: str`) declares a required member: its value
  must come from the storage.
- An annotation with a value (`mode: str = "production"`) declares a member
  with that value as its default.

Pass the storage configuration through the `options=` keyword in the `class`
statement. All operations, such as loading, saving, and deleting, work on the
class itself, not on instances. In this documentation, each such operation is
called a *pass*.

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

    # read from APP_SESSION_TTL, built the same way
    session_ttl: timedelta = timedelta(minutes=30)

    # read from the "retries" key of the JSON file
    retries: int = js.json_setting(name="retries", default=3)


# suppose the environment contains APP_SESSION_TTL=1:30:00
AppSettings.load_settings()

# prints datetime.timedelta(seconds=5400):
# the value is parsed into a timedelta, not left as a string
print(repr(AppSettings.session_ttl))

# assign directly on the class: values are stored per class, not
# per instance
AppSettings.retries = 10

# save one setting: writes the "retries" key of the JSON file
AppSettings.save_setting(lambda s: s.retries)

# AppSettings.save_settings() would save every setting of the class
```

In this example, the environment is the class's only source.
`json_file(...)` is a **file declaration**: it tells the JSON backend which
file to use, but it does not count as a second source. Because there is only
one source, plain members (`mode`, `session_ttl`) are read from the
environment. `retries` is declared with the JSON family factory
`json_setting(...)`, so it is read from and written to the JSON file
instead. The result is one class with two backends. See
[Mixing backends in one class](#mixing-backends-in-one-class) for other
combinations.

Passes that work on a single setting take a getter lambda instead of a name
string, for example `save_setting(lambda s: s.retries)` above. The library
only inspects the lambda to find the member; it never calls it.

### The `setting(...)` factory

`advexp.settings.setting(...)` is the full-featured way to declare a plain
member. Use it when a plain assignment is not enough, for example when you
need value constraints, an explicit storage address, or aliases:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class ServerSettings(
    adv_settings.Settings, options=js.json_source(file="app-settings.json")
):
    port: int = adv_settings.setting(
        name="port", ge=1, le=65535, default=8080
    )
```

A `typing.ClassVar` annotation does not declare a member. It stays an
ordinary class attribute, and no pass touches its value.

### Family factories

A family factory binds a member to the backend of one family:
`json_setting(...)` (used above), `environment_variable_setting(...)`,
`dotenv_setting(...)`, `toml_setting(...)`, and `yaml_setting(...)`.
You can use a family factory in a class with a single source. In a
class with several sources, family factories are the only option,
because a plain member does not say which source to read from.

Members are declared by calling factory functions. You can also assign an
attribute instance directly, for example
`mode: str = EnvironmentVariableSetting(...)`, and it works the same way at
runtime. However, type checkers do not know that the metaclass replaces the
attribute with a value descriptor, so they report a type error. Factories
return `Any`, so type checkers accept them.

!!! tip

    A backend plugin is enabled by importing its module; no registration
    calls are needed. If you use an attribute whose backend module has not
    been imported, the library raises `PluginNotEnabledError`. The error
    message names the attribute class that has no plugin.

## Using a local file instead

The JSON backend stores settings as a single flat JSON object. Each key is
the full setting name: either the explicit `name=` or a name built from the
pattern `{module}.{class}.{member}`. Values are stored as native JSON
values:

```python
from datetime import timedelta
from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class LocalSettings(
    adv_settings.Settings,
    options=js.json_source(file=Path("app-settings.json")),
):
    session_ttl: timedelta = timedelta(minutes=30)

    # key: local_settings.LocalSettings.port
    port: int = 8080


# if the file is missing, the members keep their defaults
LocalSettings.load_settings()

# writes all settings to the file in one atomic operation
LocalSettings.save_settings()
```

## Dotenv, TOML, and YAML files

### `.env` files

The dotenv backend reads and edits a `.env` file using
[python-dotenv](https://github.com/theskumar/python-dotenv). It requires the
`dotenv` extra: `pip install "advexp-settings[dotenv]"`.

Pass the file name to the builder. The naming parameters are the same as for
environment variables (see
[Naming options of the environment sources](#naming-options-of-the-environment-sources)).
A missing file is treated as an empty file:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as env


class ServiceSettings(
    adv_settings.Settings,
    options=env.dotenv_source(
        file="app.env", name_prefix="APP_", name_case=env.NameCase.UPPER
    ),
):
    port: int = env.dotenv_setting(default=8080)


ServiceSettings.load_settings()
```

Saving changes only the lines of the variables being saved. Comments,
`export` lines, and variables that do not belong to any member stay exactly
as they are.

### TOML files

The TOML backend stores settings in a single TOML document, using native
TOML values. For example, `datetime`, `date`, and `time` values are stored
as TOML dates and times, not as ISO strings.

Dots in a key name separate table levels, and the last part is the key
itself. This applies both to an explicit `name=` and to names built from the
pattern. For example, the name `app.ServiceConfig.port` refers to
`port = 8080` in the `[app.ServiceConfig]` table, which is how TOML itself
interprets it.

The backend uses [tomlkit](https://github.com/python-poetry/tomlkit), which
preserves the file's formatting when editing it. It requires the `toml`
extra: `pip install "advexp-settings[toml]"`.

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.toml_settings as ts


class ServiceSettings(
    adv_settings.Settings,
    options=ts.toml_source(file="app-settings.toml"),
):
    port: int = ts.toml_setting(default=8080)


# if the file is missing, the members keep their defaults
ServiceSettings.load_settings()

# one atomic write; comments and key order in the file are preserved
ServiceSettings.save_settings()
```

### YAML files

The YAML backend stores settings in a single YAML document, using native
YAML values. Dates and timestamps are kept as `date` and `datetime` (not as
ISO strings), `null` maps to `None`, and `true`/`false` are booleans, while
`yes`/`no` remain strings, because the backend follows YAML 1.2.

Keys are flat: a dot in a name stays part of the key. The optional `path=`
parameter of a setting places the key within the document tree. Both work
the same way as in the JSON backend.

The backend uses [ruamel.yaml](https://sourceforge.net/p/ruamel-yaml/) in
its round-trip mode, so the comments, key order, quoting style, and anchors
that the file already contains survive a save. It requires the `yaml` extra:
`pip install "advexp-settings[yaml]"`. The backend does not look at the
file extension: it uses any path you declare, so an existing `.yml`
file needs no renaming.

```python
from datetime import date

import advexp.settings as adv_settings
import advexp.settings.plugins.yaml_settings as ys


class ServiceSettings(
    adv_settings.Settings,
    options=ys.yaml_source(file="app-settings.yaml"),
):
    port: int = ys.yaml_setting(default=8080)

    # stored native: launch_on: 2026-12-01
    launch_on: date = ys.yaml_setting(
        name="launch_on", default=date(2026, 12, 1)
    )


# a missing or blank file leaves the defaults
ServiceSettings.load_settings()

# one atomic write; comments and key order in the file are preserved
ServiceSettings.save_settings()
```

### Common options of the file backends

The JSON, TOML, and YAML backends let you:

- place keys inside a subtree of the document with `path=` (a JSON Pointer);
- change how keys are built from member names with `name_pattern=`;
- share one file among many classes, either at the module level or for the
  whole process.

The [Backends](../backends.md) page covers all of this in detail.

## Members without storage

`non_storage_setting(...)` comes from the core package, so it does not need
any backend module. It declares a member that is never stored:

- `default=` is required.
- The value is either the declared default or the last value assigned.
- A load resets the member to its declared default.
- Saving and deleting skip the member.
- Bulk updates, snapshots, constraints, and validation treat it like any
  other member.

```python
import advexp.settings as adv_settings


class Limits(adv_settings.Settings):
    retries: int = adv_settings.non_storage_setting(default=3, ge=0)
```

An annotation wrapped in `typing.ClassVar` declares no member at all: the
class does not treat it as a member, no storage ever sees it, and
`to_dict()` does not include it. Use `ClassVar` for plain values that simply
live on the class, and `non_storage_setting(...)` for values that should
behave as members.

The read-only counterpart has its own version of this concept:
`advexp.configuration` provides `constant_setting(default=...)`. It declares
a member whose value cannot be changed by sources or by load overrides, so
after every load its value is always the declared one. See
[Configuration: Members that do not use the source chain](../configuration/getting-started.md#members-that-do-not-use-the-source-chain).

## Mixing backends in one class

Members of one class can use different backends. Each member is handled by
the backend that its declaration selects, and `options=` provides the
configuration for every backend family that needs it:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env
import advexp.settings.plugins.json_settings as js


class MixedSettings(
    adv_settings.Settings, options=js.json_source(file="app-settings.json")
):
    host: str = js.json_setting(name="host", default="localhost")

    # read from MIXED: an explicit name is used as is
    mode: str = env.environment_variable_setting(
        name="MIXED", default="production"
    )


# mode comes from the environment, host from the file
MixedSettings.load_settings()

# each member is written by its own backend
MixedSettings.save_settings()
```

The environment member does not need an `env_source(...)` entry next to the
JSON builder. The environment family has no file to name. Its builder only
carries naming rules, and an explicit `name=` (a full address) never uses
them. Environment members work in any class, even if the class has no
configuration for the environment family.

Class-level passes still cover the whole class, and members are processed in
declaration order. A storage error that must not be hidden from the user,
such as a corrupt file, aborts the pass. The class then stays exactly as it
was before the call, and none of the values loaded by the aborted pass are
applied.

## Required and optional members

A bare annotation declares a **required** member. `default=REQUIRED`
(importable from `advexp.settings`) does the same thing explicitly. A member
with an explicit `default=` (any value, including `None`) is **optional**.

In Advexp.Settings, a factory called without `default=` declares an optional
member, which is `None` until a value is loaded. Advexp.Configuration
behaves differently: there, omitting `default=` is the same as writing
`default=REQUIRED`. A bare annotation declares a required member in both
packages.

### Load errors

Whether a member is required or optional determines how its load errors are
reported. Both packages follow the same rules here. If a required member
gets no usable value, the load fails. There are four error classes:

- `MissingValueError`: the storage provided no value.
- `ConversionError`: the value could not be converted to the member's type.
  The message shows the value and the type.
- `ConstraintViolationError`: the value violates the member's constraints.
  The message lists all the violations.
- `SourceLoadError`: the storage itself raised an error while loading. The
  original exception is attached.

All four are subclasses of `MemberLoadError`, which is a subclass of
`ValueError`. A load does not stop at the first failing member. It loads
every member and then raises a single `AggregateLoadError` that reports all
failures of required members at once. Its `errors` tuple holds each member's
individual error.

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


class DeploySettings(adv_settings.Settings):
    # required: the value must come from the environment, there is
    # no fallback
    token: str = env.environment_variable_setting(
        name="DEPLOY_TOKEN", default=adv_settings.REQUIRED
    )


try:
    DeploySettings.load_settings()
except adv_settings.AggregateLoadError as error:
    # one entry per failed required member
    for entry in error.errors:
        print(entry)
```

### Fallbacks of optional members

An optional member never makes a load fail. If it has a problem, it keeps
its default value, and `load_settings()` returns a report: a tuple of errors
of the same classes as above. This lets the caller see which members fell
back without parsing logs. If every member loaded cleanly, the report is an
empty tuple:

```python
report = MixedSettings.load_settings()

# the members that fell back, and why
for entry in report:
    print(entry)
```

A plain miss is not a problem: if the storage has no value for an optional
member, using the default is the expected outcome, and nothing is reported.

If the load fails because of a required member, the fallbacks from the same
load are attached to the raised error. They are kept separately, in its
`fallbacks` tuple, so you can tell the two kinds of problems apart.

!!! note "How a load works"

    A load builds the new state of the class from scratch and applies it in
    a single step.

    A successful load fully determines the state. Every member gets either a
    value from its storage or its declared default. A value from a previous
    load never survives.

    A failed load changes nothing: the class stays exactly as it was before
    the call, and no values are partly applied. When a running application
    reloads its settings, keeping the last working configuration is safer
    than falling back to defaults.

## Naming options of the environment sources

Environment backends build each variable name as
`name_prefix + name_case(member name)`. The naming rules are set once per
class, in the `options=` keyword:

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


class WorkerSettings(
    adv_settings.Settings,
    options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER
    ),
):
    # read from APP_SESSION_TTL, required
    session_ttl: timedelta = env.environment_variable_setting(
        default=adv_settings.REQUIRED
    )

    # read from APP_PORT
    port: int = env.environment_variable_setting(default=8080)

    # read from legacy_flag as is: an explicit name is the full address
    legacy: str = env.environment_variable_setting(
        name="legacy_flag", default="off"
    )
```

- The prefix is added exactly as written.
- `NameCase.UPPER` and `NameCase.LOWER` change the case of the member name
  only, not the prefix. `None` (the default) leaves the name unchanged.
- `NameCase.ANY` keeps the name as built, but makes the lookup
  case-insensitive: a variable matches in any spelling. An exact match takes
  priority. If two variables differ only in case and neither matches
  exactly, the load fails.
- An explicit `name=` is the full address: neither the prefix nor the case
  is applied to it.

These rules are implemented in `advexp.settings-base`, which both packages
share. The process environment and a `.env` file share one namespace of
variable names. Therefore, a class has a single set of naming rules, which
you set on either the `env_source` or the `dotenv_source` builder. Setting
the rules a second time in the same class makes the `class` statement fail.
A variable that is read by both a settings class and a configuration class
is resolved in the same way in both packages.

**Nested objects are addressed field by field.** A member annotated with a
dataclass holds a nested object. The `nested_delimiter` option lets you set
each of its fields with a separate variable. For example, with the delimiter
`"__"`, the variable `APP_DB__PORT` sets the `port` field of the `db`
member. This works at any depth.

- **Loading** updates the object partially: the declared default instance is
  the starting point, and every field that no variable sets keeps its
  declared value.
- **Saving** uses the same addressing: each field is written to its own
  variable, so a saved object loads back exactly as it was saved.

```python
from dataclasses import dataclass

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


@dataclass
class DbConfig:
    host: str = "localhost"

    port: int = 5432


class AppSettings(
    adv_settings.Settings,
    options=env.env_source(
        name_prefix="APP_",
        name_case=env.NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    db: DbConfig = DbConfig(host="db.local")
```

If only `APP_DB__PORT=6543` is set, `db` loads as
`DbConfig(host="db.local", port=6543)`.

## Aliases

A member can declare additional full addresses with `aliases=`. This is
useful when you rename something: after a variable or a document key gets a
new name, the old name keeps working, so existing deployments that still use
it load as before. A load checks the primary address first, then the aliases
in the order they are declared. The first address that has a value wins.

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


class WorkerSettings(
    adv_settings.Settings,
    options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER
    ),
):
    # the primary address is APP_SESSION_TTL;
    # the old name APP_TTL still works
    session_ttl: timedelta = env.environment_variable_setting(
        aliases=["APP_TTL"], default=timedelta(minutes=30)
    )
```

- Every alias is a full address, like an explicit `name=`: `name_prefix` and
  `name_case` never apply to it. In the file backends, alias keys are placed
  under the member's `path=`, like the primary key.
- **Saving** writes only to the primary address, so the rename is complete
  after the next save.
- **Deleting** removes the value from every address of the member, so a
  deleted value cannot come back through an old name.
- When no value is found, the error lists every address that was checked,
  for example
  `environment variable 'APP_SESSION_TTL' (aliases: 'APP_TTL')`.
- An invalid alias list (wrong type, empty string, or duplicate address)
  makes the `class` statement fail before any storage is accessed.

The read-only sources of Advexp.Configuration support `aliases=` in the same
way. See the full description on the
[Backends](../backends.md#aliases-one-member-several-addresses) page.

## Validation

Value constraints are keyword parameters of the member declaration: `gt`,
`ge`, `lt`, `le`, `eq`, `ne`, `min_length`, `max_length`, `regex`,
`validator`, and `when`. The `regex` pattern is not anchored: it can match
anywhere in the value. Advexp.Configuration uses the same parameters. See
the [Validation](../validation.md) page for the full list.

Cross-member rules:

- A comparison bound can refer to a member declared earlier in the same
  class body, for example `ge=min_port`.
- `when=` enables a member's constraints only while a referenced member is
  truthy.
- The `__validate__` class hook handles anything that a comparison cannot
  express. It runs on a fully built object and returns a dictionary that
  maps member names to problems.

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class NetSettings(adv_settings.Settings):
    min_port: int = js.json_setting(default=1024)

    # must be greater than or equal to min_port
    max_port: int = js.json_setting(default=65535, ge=min_port)

    ssl: bool = js.json_setting(default=False)

    # eq=443 applies only when ssl is true
    port: int = js.json_setting(default=80, eq=443, when=ssl)
```

This example does not bind a file, and it does not need one, because no
storage pass runs. A pass that touches storage would take the file from a
module-level or process-level binding (see [Backends](../backends.md)).

Constraints are checked whenever a member receives a value:

- **Class creation.** Declared defaults are checked after they are converted
  to the member's type.
- **Assignment.** An assignment that violates a member's constraints raises
  `SettingValidationError`, and the class keeps its previous value.
- **Bulk updates.** `update_from_dict` and `update_from_object` check the
  whole update first. If any value is invalid, nothing is applied.
- **Loading.** A load is lenient for optional members: a stored
  value that violates a constraint is replaced with the default and appears
  in the load report.
- **Saving.** A save checks the whole class first and writes nothing if any
  rule is violated.

`validate_settings()` runs a strict check on demand: it collects all
problems into one `SettingValidationError`. A single assignment does not run
cross-member checks. If you change related members one at a time, call
`validate_settings()` yourself afterwards.

## Secret values

`SecretStr` and `SecretBytes` (the package exports both) are saved and
loaded like any other type. The loaded value is wrapped, so it appears as
`'**********'` when printed, in log records, and in error messages. To get
the real value, call `get_secret_value()`.

In the storage, the value is kept in plain form: saving unwraps it before
serialization. Constraints are checked against the real value, but their
error messages still show the mask.

## Snapshots and exchanging data with pydantic

A settings class holds a single, shared set of values. To work with an
independent copy, take a snapshot and apply it back later:

- `to_dict()` returns a deep copy of all values, keyed by member name.
- `to_object()` returns a detached instance of the class.
- `update_from_dict` and `update_from_object` apply either form back, using
  the same type conversion as a load.

`reset_settings()` resets every member to its declared default without
touching any storage.

### Pydantic

Neither package depends on pydantic. Data is exchanged through a plain
dictionary, which both sides already support. There are two ways to pass a
pydantic model into a settings class:

- **Through a load.** Use `mapping_source()` as the class's storage. Once the
  model exists, fill the storage with its dump through
  `mapping_source_for(...).set(...)`, then load.
- **In memory, without a load.** Call `update_from_dict` with
  `ignore_unknown=True`.

A `mapping_source()` dictionary is a full storage: `save_settings()` writes
the class's current values back into it.

A model dump often contains keys that the settings class does not declare,
such as computed fields or fields that are not meant to be stored. In both
cases, these keys are dropped, and a debug log record is written:

```python
from pydantic import BaseModel

import advexp.settings as adv_settings
from advexp.settings.plugins.mapping_source import (
    mapping_source,
    mapping_source_for,
)


class Deployed(BaseModel):
    token: str
    port: int
    note: str = ""  # a field the settings class does not declare


class ServiceSettings(
    adv_settings.Settings,
    options=mapping_source(),
):
    token: str

    port: int = 8080


# fill the dictionary storage with the model's dump, then load
deployed = Deployed(token="svc-token", port=9090, note="extra")
mapping_source_for(ServiceSettings).set(deployed.model_dump())
ServiceSettings.load_settings()

# or update in memory, without a load: unknown keys are dropped
ServiceSettings.update_from_dict(
    deployed.model_dump(), ignore_unknown=True
)

# the other way: build the model from a snapshot
restored = Deployed(**ServiceSettings.to_dict())
```

Advexp.Configuration has the same `to_dict()` and `to_object()` snapshots,
but values cannot be applied back from them: the only way to get new values
there is to load again.

## A file per environment

A file source can take a file name template with a placeholder that is
filled in from an environment variable. This gives you one file per
environment, similar to the `appsettings.{env}.json` convention in .NET:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js
from advexp.settings import env_parameter

app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))


class EnvSettings(
    adv_settings.Settings,
    options=js.json_source(
        file="settings-{APP_ENV}.json", parameters=app_env
    ),
):
    token: str
```

- **`choices` is required.** The value is checked before the library touches
  the file system, so a typo such as `APP_ENV=prodd` fails the load with a
  clear error instead of silently turning into a missing file.
- **The variable is not set, but the parameter has a default.** The
  parameter's declared `default=` is used. There is no implicit default
  environment.
- **The variable is not set, and the parameter has no default.** The source
  cannot be resolved, so the load fails with an error that names the
  variable and the file.
- **Saving** always writes to the file that the values were loaded from,
  which is the file of the environment used by the last load. Even if the
  variable has changed since that load, the save still writes to the same
  file. The new environment's file is picked up only by the next load.

## The read-only counterpart

Advexp.Configuration is the other package of the family. It supports the
same kinds of backends as sources but never saves. Its loaded values are
read-only: assigning to a declared member raises `TypeError`. To get new
values, call `load_configuration()` again.

Members are declared the same way, with the same value constraints and the
same type conversion, so you can usually move a class between the packages
by changing the base class and the imports. There are two exceptions:

1. **An omitted `default=` means different things.** In Advexp.Settings, a
   factory call without `default=` declares an optional member, which is
   `None` until a value is loaded. In Advexp.Configuration, the same call
   declares a required member. When moving a class between the packages,
   write the default explicitly in every factory call.
2. **Settings classes have no source chain.** Advexp.Configuration reads its
   sources as a chain: `Sources(...)` lists them, the first source that has
   a value wins, a dictionary can be one of the layers, and
   `overrides={...}` adds a one-time layer on top of all the others. A
   settings class has no chain, because a save needs exactly one storage to
   write to. A class that uses a source chain cannot be moved just by
   changing its base class.

The [Configuration getting started](../configuration/getting-started.md)
page walks through the same topics from the Configuration side.

## Samples

Runnable examples of this package are in the repository, in
[samples/settings/](https://github.com/advexp/advexp.settings.python/tree/main/samples/settings):

- [settings_api.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/settings_api.py)
  — a live tour of the application API using the bundled backends;
- [custom_backend.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/custom_backend.py)
  — a complete custom backend built on the plugin contracts;
- [plain_declarations.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/plain_declarations.py)
  — the plain declaration style in full;
- one walkthrough per backend:
  [environment_variables.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/environment_variables.py),
  [dotenv_file.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/dotenv_file.py),
  [json_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_settings.py),
  [toml_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/toml_settings.py),
  and
  [yaml_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/yaml_settings.py);
- dynamic collections, one tour per format:
  [json_dynamic_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_dynamic_settings.py),
  [toml_dynamic_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/toml_dynamic_settings.py),
  and
  [yaml_dynamic_settings.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/yaml_dynamic_settings.py);
- [validation.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/validation.py)
  — the full validation tour;
- [json_path_index.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_path_index.py)
  — array indices in the `path=` of the JSON backend;
- [toml_dotted_keys.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/toml_dotted_keys.py)
  — dotted keys, quoted segments, and array slots in the TOML backend;
- [json_custom_metadata.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_custom_metadata.py)
  and
  [json_dynamic_metadata.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/json_dynamic_metadata.py)
  — metadata in use.

The [Samples](../samples.md) page of the Guide lists all of them, together
with the Advexp.Configuration examples and the examples that use both
packages in one application.

## What's next

- [Backends](../backends.md) covers all bundled backends in detail: JSON
  Pointers, per-class files, family options, and mixing backends in one
  class.
- [Value types](../value-types.md) lists all supported types and how they
  are stored.
- [Validation](../validation.md) covers value constraints and cross-member
  rules.
- [Samples](../samples.md): runnable example programs for both packages,
  located in the project's repository.
- [Configuration](../configuration/getting-started.md) walks through the
  same topics for Advexp.Configuration, the read-only package of the family.
