# Getting started with Advexp.Configuration

## Installation

```bash
pip install advexp-configuration
```

## Your first configuration class

To declare a configuration, subclass `Configuration` and declare each setting
as a class member. Pass the sources that the values come from through the
`options=` keyword. Call `load_configuration()` to load the values. Once
loaded, the values are read-only:

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

If the class has **one source**, pass its builder directly to `options=`. If
it has **several sources**, wrap them in `Sources(...)`. Sources are read in
the order in which they are listed, and the first source that has a value
wins. If no source has a value, the member gets its declared default.

Members are declared like this:

- A bare annotation (`token: str`) declares a required member.
- An annotation with a value (`mode: str = "production"`) declares a member
  with that value as its default.

## Read-only by design

The library never writes to sources. Loaded values are read-only: assigning
to a declared member, either on the class or on an instance, raises
`TypeError`. To pick up new values after the sources change, call
`load_configuration()` again.

For secrets, annotate the member as `SecretStr` or `SecretBytes` (the package
exports both). The loaded value is wrapped, so it appears as `'**********'`
when printed or written to a log. To get the real value, call
`get_secret_value()`.

## Sources

The bundled sources correspond to the storage backends of Advexp.Settings,
the counterpart package (see
[The read-write counterpart](#the-read-write-counterpart)).

To use a source, import its module. Each module contains everything that the
source needs, including its builder function. For example,
`advexp.configuration.plugins.environment.variables` provides the source for
process environment variables, and
`advexp.configuration.plugins.environment.dotenv` provides the source for
`.env` files.

### Environment variables

The first example on this page uses this source.

### `.env` files

The dotenv source reads a `.env` file using
[python-dotenv](https://github.com/theskumar/python-dotenv). It requires the
`dotenv` extra: `pip install "advexp-configuration[dotenv]"`.

Pass the file name to the source. Its naming parameters control how variable
names are built from member names (see
[Naming options of the environment sources](#naming-options-of-the-environment-sources)).
A missing file is treated as an empty file:

```python
import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.dotenv as env


class ServiceConfig(
    adv_config.Configuration,
    options=env.dotenv_source(
        file="app.env", name_prefix="APP_", name_case=env.NameCase.UPPER
    ),
):
    port: int = env.dotenv_setting(default=8080)


ServiceConfig.load_configuration()
```

### JSON files

Pass the file name to the JSON source. Optionally, you can also:

- read keys from a subtree of the document instead of its root (`path=`, a
  JSON Pointer);
- change how keys are built from member names (`name_pattern=`).

A single member can also set its own JSON Pointer `path=` and its own key
`name=`:

```python
import advexp.configuration as adv_config
import advexp.configuration.plugins.json_settings as js


class ServiceConfig(
    adv_config.Configuration,
    options=js.json_source(file="app-configuration.json"),
):
    port: int = js.json_setting(name="port", default=8080)


ServiceConfig.load_configuration()
```

### TOML files

The TOML source works like the JSON source, with a few differences:

- Values are converted to the member's annotated type as usual, but
  `datetime`, `date`, and `time` values arrive as native TOML types, so they
  are not parsed from strings.
- Dots in a key name separate table levels, and the last part is the key
  itself. This applies both to an explicit `name=` and to names built by
  `name_pattern=`. For example, the name `app.ServiceConfig.port` refers to
  `port = 8080` in the `[app.ServiceConfig]` table, which is how TOML itself
  interprets it.
- On Python 3.11 and later, files are read with the standard library's
  `tomllib`. On older versions, the package uses `tomli`, which you can
  install with the `toml` extra: `pip install "advexp-configuration[toml]"`.

```python
import advexp.configuration as adv_config
import advexp.configuration.plugins.toml_settings as ts


class ServiceConfig(
    adv_config.Configuration,
    options=ts.toml_source(file="app-configuration.toml"),
):
    port: int = ts.toml_setting(name="port", default=8080)


ServiceConfig.load_configuration()
```

### YAML files

The YAML source works like the JSON source, with a few differences:

- Values are converted to the member's annotated type as usual, but dates
  and timestamps arrive as `date` and `datetime` objects, and `null` arrives
  as `None`. `true`/`false` are booleans, while `yes`/`no` remain strings,
  because the source follows YAML 1.2.
- Keys are flat: a dot in a name stays part of the key. The optional `path=`
  parameter of a member places the key within the document tree. Both work
  the same way as in the JSON source.
- A file must contain only one document. A `---` separator followed by a
  second document makes parsing fail, and so does a tag that the YAML core
  schema does not recognize. A blank file is read as an empty document.
- The source reads files with
  [ruamel.yaml](https://sourceforge.net/p/ruamel-yaml/), the same library
  that the settings package uses for saving. This way, both packages
  interpret the same files in the same way. Install it with the `yaml`
  extra: `pip install "advexp-configuration[yaml]"`. The source ignores the
  file extension and uses whatever path you declare, so an existing `.yml`
  file needs no renaming.

```python
from datetime import date

import advexp.configuration as adv_config
import advexp.configuration.plugins.yaml_settings as ys


class ServiceConfig(
    adv_config.Configuration,
    options=ys.yaml_source(file="app-configuration.yaml"),
):
    port: int = ys.yaml_setting(name="port", default=8080)

    # read natively: launch_on: 2026-12-01 arrives as a date
    launch_on: date = ys.yaml_setting(
        name="launch_on", default=date(2026, 12, 1)
    )


ServiceConfig.load_configuration()
```

## Required and optional members

A member without a default is **required**: its value must come from a
source.

In Advexp.Configuration, the `default` parameter of member factories is
`REQUIRED` unless you set it. Omitting `default=` is the same as writing
`default=REQUIRED`. You can import `REQUIRED` from `advexp.configuration` if
you prefer to write it out.

Advexp.Settings behaves differently here: a factory called without
`default=` declares an optional member, which is `None` until a value is
loaded. A bare annotation declares a required member in both packages.

A member with an explicit `default=` (any value, including `None`) is
**optional**. Whether a member is required or optional determines how its
load errors are reported (see below). Both packages follow the same rules
here.

Using `default=None` requires some care. The member is `None` until a value
is loaded. Like any declared default, `None` is checked against the member's
constraints when the class is created. If the constraints reject `None` (for
example, `eq=`, or a `validator` that returns false for `None`), the `class`
statement fails, because without a value from a source such a member could
never be valid. In effect, it is a required member, so declare it with
`REQUIRED`.

### Load errors

If a required member gets no usable value, the load fails. The error message
names the member, its address in the source, and the class. There are four
error classes:

- `MissingValueError`: no source provided a value.
- `ConversionError`: the value could not be converted to the member's type.
  The message shows the value and the type.
- `ConstraintViolationError`: the value violates the member's constraints.
  The message lists all the violations.
- `SourceLoadError`: the source itself raised an error while loading. The
  original exception is attached.

All four are subclasses of `MemberLoadError`, which is a subclass of
`ValueError`. Reading a required member that has never been loaded also
raises `MemberLoadError`, because the library has no placeholder value that
it could return. An optional member that is read before its first load
returns its declared default.

!!! note "All failures in one error"

    A load does not stop at the first failing member. It loads every member
    and then raises a single error that reports all failures of required
    members at once. This error is always one `AggregateLoadError` (also a
    subclass of `MemberLoadError`), whether one member failed or five. Its
    message lists every failed member, and its `errors` tuple holds each
    member's individual error; you can distinguish their types with
    `isinstance`. So you do not have to fix failures one at a time and rerun
    after each fix.

!!! note "How a load works"

    A load builds the new state of the class from scratch and applies it in
    a single step.

    A successful load fully determines the state. Every member gets either a
    value from its sources or its declared default. A value from a previous
    load never survives if the current sources no longer provide it. You can
    load the same class many times, and each load is independent of the
    previous ones.

    A failed load changes nothing. If a load is aborted or a source error is
    raised, the class stays exactly as it was before the call: no values are
    partly applied, and no defaults are applied either. This matters when a
    running application reloads its configuration. If a reload hits a
    corrupt file, the process keeps the last working configuration, which is
    safer than falling back to defaults.

!!! note "Optional members fall back to their defaults"

    An optional member never makes a load fail. If it has a problem, it
    keeps its default value, and the library reports the problem in two
    ways:

    - **The return value.** `load_configuration()` returns a report: a tuple
      of errors of the same classes as above. This lets the caller see which
      members fell back without parsing logs. If every member loaded
      cleanly, the report is an empty tuple.
    - **The log.** Each fallback writes one log record with a fixed
      structure: the member's location, the cause, and the closing phrase
      `using the default value`. The level is `WARNING` if the member could
      not accept the value, and `ERROR` if a source failed.

    A plain miss is not a problem: if no source has a value for an optional
    member, using the default is the expected outcome, and nothing is
    reported.

    If the load fails because of a required member, the fallbacks from the
    same load are attached to the raised error. They are kept separately, in
    its `fallbacks` tuple, so you can tell the two kinds of problems apart.

## The source chain

`Sources(...)` lists the class's sources in lookup order: the first source
listed is read first. The bundled builders are:

- `env_source(name_prefix=, name_case=, nested_delimiter=)`: process
  environment variables
- `dotenv_source(file=, ...)`: a `.env` file
- `json_source(file=, path=, name_pattern=)`: a JSON file
- `toml_source(file=, path=, name_pattern=)`: a TOML file
- `mapping_source(dictionary)`: a dictionary provided by the application.
  Called without a dictionary, it creates a *live* layer that the
  application fills at runtime through `mapping_source_for(cls)` (see
  below).

```python
from datetime import timedelta

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as env
import advexp.configuration.plugins.json_settings as js
from advexp.configuration.plugins.mapping_source import mapping_source

BASE_DEFAULTS = {
    "token": "dev-token",
    # matches no member of the class: the mapping source drops it
    "port": 8080,
}


class AppConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
        js.json_source(file="app.json"),
        mapping_source(BASE_DEFAULTS),
    ),
):
    token: str
    ttl: timedelta = timedelta(minutes=30)
```

A lookup works like this:

- **A miss moves down the chain.** If a source has no value for a member,
  the next source is asked. The declared default acts as the implicit last
  layer.
- **Only the first value found counts.** It is converted once. If the
  conversion fails, that is the member's error, and sources further down the
  chain are not tried.
- **A broken source stops the search.** If a file exists but cannot be read
  or parsed, the search stops there. Sources further down the chain never
  hide a broken source above them.

### The mapping source

The mapping source uses member names as keys, and only member names: an
explicit `name=` and declared `aliases=` do not apply to it. All
dictionary-based APIs in the library use keys in the same way. Keys that do
not match any member are dropped, and a debug log record is written. The
dictionary is copied when the class is declared, and every value it returns
is a fresh copy, so later changes on either side never affect the other.

Called without a dictionary, `mapping_source()` declares a **live layer**: an
empty layer that the application fills at runtime.
`mapping_source_for(AppConfig)`, imported from the same module as
`mapping_source`, returns the live mapping source of the class's chain. Its
`set(mapping)` method replaces the layer's dictionary:

```python
from advexp.configuration.plugins.mapping_source import (
    mapping_source,
    mapping_source_for,
)


class AppConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
        mapping_source(),
    ),
):
    token: str


# fill the dictionary before the load that reads it
mapping_source_for(AppConfig).set({"token": "dev-token"})
AppConfig.load_configuration()
```

How the live layer behaves:

- Until it is filled, the layer is empty, and the lookup silently moves on
  to the next source.
- `set()` replaces the whole dictionary; it does not merge with the old one.
  The dictionary passed in is deep-copied, and every value returned is a
  fresh copy, with the same isolation as in the static form.
- `mapping_source_for()` uses the nearest chain. A subclass without its own
  chain therefore shares the live mapping source of its base class: one
  dictionary, filled by one `set()` call.
- `mapping_source_for()` raises a `TypeError` that names the class if the
  class is not a configuration class, if its chain has no live mapping
  source, or if the chain has more than one of them.
- A mapping source created with a dictionary cannot be refilled: its content
  is always the dictionary passed in the declaration.

### Source path

A source's `path=` makes it read keys from a subtree of its storage. This
path is prepended to every member's own `path=`, and a member cannot opt out
of it. If a member needs a key outside that subtree, add another source for
the same storage without this path.

### Overrides

`load_configuration(overrides={...})` adds a layer above the whole chain.
This layer is not a declared source. Its keys are member names, and its
values go through the same conversion and constraint checks as values from
sources. Overrides can set any member, and a source's `path=` does not limit
them.

Keys that do not match any member are dropped, and so are keys that match
constant members. Each dropped key writes a debug record. This means you can
pass a dictionary from elsewhere, such as the `model_dump()` of another model
with keys that this class never declared, and the load does not fail because
of them:

```python
AppConfig.load_configuration(overrides={"ttl": "2:00:00"})
```

### Chains and inheritance

**The chain belongs to the class that declares it.** A subclass without its
own chain inherits the nearest chain from its base classes. A subclass with
its own chain uses it for itself and its own subclasses, while the base
class keeps reading its own sources.

Do not put source builders directly into a sequence passed to `options=`
(for example, `options=[env_source(...), json_source(...)]`), because this
makes the `class` statement fail. The whole chain is treated as a **single**
entry, so wrap the builders in `Sources(...)`.

## A file per environment

A file source can take a file name template with named placeholders (slots).
Each slot is filled from one environment variable. This gives you one file
per environment, similar to the `appsettings.{env}.json` convention in .NET,
without any extra machinery:

```python
from advexp.configuration import env_parameter

app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))


class AppConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        js.json_source(file="app.json"),
        js.json_source(file="settings-{APP_ENV}.json", parameters=app_env),
    ),
):
    token: str
```

By default, the slot name is the variable name (`{APP_ENV}` above). To use a
different name in the template, set it with `env_parameter(..., slot="env")`
and write `{env}` in the template. All template checks refer to slot
names: an error names the slot, not the variable. Every file source
(`json_source`, `toml_source`, `dotenv_source`) accepts
`parameters=` in the same way, and one parameter can be used by several
sources of the same class.

**`choices` is required.** It validates the value of the variable, not the
file. The check runs before the library touches the file system, so a typo
such as `APP_ENV=prodd` fails the load with a clear error. Without this
check, the typo would quietly turn into a missing file, the chain would skip
it, and a production process would silently run on development settings.

What happens in each case:

- **The value is valid and the file exists.** The file is read.
- **The value is valid, but the file does not exist.** This is a normal
  miss, and the search continues down the chain.
- **The variable is not set, but the parameter has a default.** The
  parameter's declared `default=` is used. There is no implicit default
  environment.
- **The variable is not set, and the parameter has no default.** The source
  cannot be resolved, so the load fails with an error that names the
  variable and the file. Sources further down the chain do not hide the
  problem.

Variables are resolved on every load: each load reads them again, and
nothing is cached between loads. Within one load, each variable is resolved
once, and a debug record shows the variable, its value, and the resulting
file name.

The builder checks the template and the parameters against each other when
it is called:

- a slot without a matching parameter is an error, including a template
  with slots but no `parameters=` at all;
- a parameter that no slot uses is also an error.

The error message names the slot. A source without `parameters=` and without
slots is an ordinary file path. Braces that do not contain an identifier
(`{}`, `{1}`) stay in the file name as literal text.

## Declaration styles and member factories

Plain declarations are the main way to declare members:

- A bare annotation declares a required member.
- An annotation with a value declares a default. Write the default as a
  typed value (`timedelta(minutes=30)`, not a string).
- A `ClassVar` annotation is not a member at all; it stays an ordinary class
  attribute.

`chain_setting(...)` is the full-featured way to declare a *neutral* member,
which is a member that is not tied to any source family. It accepts `name=`,
`aliases=`, `default=`, `metadata=`, and all value constraints (from `gt` to
`validator`, plus `when=`). Its `name=` and `aliases=` are used as complete,
literal addresses in every source that looks up values by name. If no name is
given, each source builds one using the rules of its own family.

Family factories restrict a member to the sources of one family, which are
still read in chain order: `json_setting(...)`, `toml_setting(...)`,
`yaml_setting(...)`, `environment_variable_setting(...)`, and
`dotenv_setting(...)`. They accept `name=`, `aliases=`, and `default=`. Only
the factories of the file families (`json_setting`, `toml_setting`, and
`yaml_setting`) also accept `path=`, because a document has a tree that a
path can point into, while a variable name does not. If the class has no
source of the member's family, the `class` statement fails with an error
that names the member and the family.

One class can mix the styles:

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
    # a bare annotation: a required member, the whole chain is searched
    token: str

    # a typed default; the whole chain is searched here too
    timeout: timedelta = timedelta(seconds=5)

    # the same chain member with a constraint
    retries: int = adv_config.chain_setting(default=3, ge=1)

    # environment variables only: APP_DB_URL
    db_url: str = env.environment_variable_setting()

    # the JSON file only: the "level" key inside the "logging" subtree
    log_level: str = js.json_setting(
        path="/logging", name="level", default="INFO"
    )
```

A neutral member (a plain declaration or `chain_setting`) reads the whole
chain. If the class has no chain at all, the `class` statement fails, just
as it does when a family factory has no source of its family.
`constant_setting(default=...)` does not use the chain at all.

## Members that do not use the source chain

`constant_setting(default=...)` declares a member whose value is always the
declared one. No source is asked for it, load overrides skip it, and a
reload returns the same value. Use it for values that the application fixes
for itself, such as a schema version:

```python
import advexp.configuration as adv_config


class Endpoints(adv_config.Configuration):
    schema_version: int = adv_config.constant_setting(default=2)
    url: str = adv_config.constant_setting(default="https://api.example")
    port: int = adv_config.constant_setting(default=8080, le=65535)
```

`default=` is required: no source will ever provide a value, so the
declaration must state it. A constant accepts the same constraint parameters
as every other member factory, and its declared value is checked against
them. Sources cannot change a constant, but its own constraints still
apply.

An annotation wrapped in `typing.ClassVar` declares no member at all: the
class does not treat it as a member, and `to_dict()` does not include it.

The read-write counterpart has its own version of this concept:
`advexp.settings` provides `non_storage_setting(default=...)`. It declares a
member without any storage whose value still takes part in bulk updates and
snapshots (see
[Settings: Members without storage](../settings/getting-started.md#members-without-storage)).

## Naming options of the environment sources

Environment sources build each variable name as
`name_prefix + name_case(member name)`. The naming rules are set once per
class, on one environment source in the chain:

```python
from datetime import timedelta

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as env


class AppConfig(
    adv_config.Configuration,
    options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER
    ),
):
    # APP_SESSION_TTL, required
    session_ttl: timedelta = env.environment_variable_setting()

    # APP_PORT
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
  case-insensitive: a variable matches in any spelling. An exact match
  takes priority. If two variables differ only in case and neither matches
  exactly, the load fails.
- An explicit `name=` is the full address: neither the prefix nor the case
  is applied to it.

These rules are implemented in `advexp.settings-base`, which both packages
share. As a result, a variable that is read by both a settings class and a
configuration class is resolved in the same way in both.

**Nested objects are addressed field by field.** A member annotated with a
dataclass holds a nested object. The `nested_delimiter` option lets you set
each of its fields with a separate variable. For example, with the delimiter
`"__"`, the variable `APP_DB__PORT` sets the `port` field of the `db`
member. This works at any depth. The object is updated partially: the
declared default instance is the starting point, and every field that no
variable sets keeps its declared value. The source resolves these addresses
exactly as the settings backend does, so the same variable gives the same
value in both packages.

## Aliases

A member can declare additional full addresses with `aliases=`. This is
useful when you rename something: after a variable gets a new name, the old
name keeps working. A load checks the primary address first, then the
aliases in the order they are declared. The first address that has a value
wins.

```python
class AppConfig(
    adv_config.Configuration,
    options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER
    ),
):
    # the primary address is APP_SESSION_TTL;
    # the old name APP_TTL still works
    session_ttl: timedelta = env.environment_variable_setting(
        default=timedelta(minutes=30), aliases=["APP_TTL"]
    )
```

- Every alias is a full address, like an explicit `name=`: `name_prefix` and
  `name_case` never apply to it. In the file backends, alias keys are placed
  under the member's `path=`, like the primary key.
- When no value is found, the error lists every address that was checked,
  for example
  `environment variable 'APP_SESSION_TTL' (aliases: 'APP_TTL')`.
- The rules for writing (saving to the primary address, deleting from every
  address) belong to `advexp.settings`; this package only reads.
- An invalid alias list (wrong type, empty string, or duplicate address)
  makes the `class` statement fail before any source is read.

The alias rules are shared with the settings package. See the full
description on the
[Backends](../backends.md#aliases-one-member-several-addresses) page.

## Validation

Members support the same value constraints as in Advexp.Settings (`gt`,
`max_length`, `regex`, `validator`, and others), which are written and
checked in the same way. See the [Validation](../validation.md) page for the
full list.

Cross-member rules (rules that involve several members) also work here.
Violations are reported with this package's own error classes. The rules
are:

- A comparison bound can refer to a member declared earlier in the same
  class body, for example `ge=min_port`.
- `when=` enables a member's constraints only while a referenced member is
  truthy.
- The `__validate__` class hook handles anything that a comparison cannot
  express.

A read-only class checks these rules at two points:

1. **Class creation.** The declared defaults must satisfy the comparison
   rules, and for a `default=None` member, `None` must pass the member's
   constraints. Otherwise, the `class` statement fails.
2. **The end of a load**, after every member has its value. The
   `__validate__` hook runs only here, because it needs a fully built
   object.

A violated rule counts as one more error for its member:

- **Required member:** a `ConstraintViolationError` that names the member
  whose rule failed. It is included in the single `AggregateLoadError`
  together with the other required failures.
- **Optional member:** the error appears in the returned report. The member
  falls back to its default, and the other members involved in the same rule
  are reset to their defaults too.

Some violations cannot be fixed by resetting to defaults. For example, the
`__validate__` hook may report a member that is already at its default, or a
rule may involve a required member that holds its loaded value. Such
violations abort the load, so a successful load is always consistent.

There is no manual check such as `validate_settings()`, because values change
only through a load, and every load checks them.

## Exchanging data with pydantic

Neither package depends on pydantic. Data is exchanged through a plain
dictionary, which both sides already support.

There are two ways to pass a pydantic model into a configuration class. The
difference between them is priority, not syntax:

- **As a layer of the chain.** Declare an empty `mapping_source()` at the
  position you need in the chain (for example, below the environment and
  above a defaults file). Once the model exists, fill the layer with
  `mapping_source_for(AppConfig).set(deployed.model_dump())`. The model then
  becomes one of the layers of the configuration.
- **As overrides.** `load_configuration(overrides=deployed.model_dump())`
  applies the model above the whole chain for that one call. Overrides take
  priority over every source, which suits tests, command-line values, and
  one-off substitutions.

To go the other way, from a configuration class to pydantic, use
`Model(**cls.to_dict())`:

```python
from pydantic import BaseModel

from advexp.configuration.plugins.mapping_source import (
    mapping_source,
    mapping_source_for,
)


class Deployed(BaseModel):
    token: str
    port: int


# the model as one layer of the chain: below env, above the defaults file
class AppConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
        mapping_source(),
        js.json_source(file="defaults.json"),
    ),
):
    token: str
    port: int = 8080


# the model exists at runtime: fill the layer before the load reads it
deployed = Deployed(token="svc-token", port=9090)
mapping_source_for(AppConfig).set(deployed.model_dump())
AppConfig.load_configuration()

# this one call applies the model above the whole chain
AppConfig.load_configuration(overrides=deployed.model_dump())

# the other way: build the model from a snapshot
restored = Deployed(**AppConfig.to_dict())
```

Both ways of passing a model in follow the same rules. Values go through the
library's type conversion and constraints, so no adapter code is needed.
Keys that do not match any member of the class (for example, computed or
extra fields in a model dump) are dropped with a debug record and never make
the call fail.

`to_dict()` requires a successful load: it raises an error if a required
member has no value. This is intentional, so that a partly loaded class is
never mistaken for a complete model.

Advexp.Settings supports the same round trip. A model dump can be used as the
dictionary storage of a settings class that is bound with its
`mapping_source()`. In that case, the dictionary is the class's storage,
which saves also write into, not a layer of a chain. Fill it with
`mapping_source_for(Settings).set(deployed.model_dump())`. If the dump
contains fields that the class does not declare, pass it to
`update_from_dict` with `ignore_unknown=True` instead. To go the other way,
use `Model(**Settings.to_dict())`.

## Value types

The conversion rules are the same as in Advexp.Settings; see
[Value types](../value-types.md).

## The read-write counterpart

Advexp.Settings is the other package of the family. It uses the corresponding
backends, but it can also write: you assign a value on the class, and saving
writes it to the member's storage.

Members are declared the same way, with the same value constraints and the
same type conversion, so you can usually move a class between the packages
by changing the base class and the imports. There are two exceptions:

1. **An omitted `default=` means different things.** In
   Advexp.Configuration, a factory call without `default=` declares a
   required member. In Advexp.Settings, the same call declares an optional
   member, which is `None` until a value is loaded. When moving a class
   between the packages, write the default explicitly in every factory call.
2. **Settings classes have no source chain.** A settings class has one
   storage per backend family. There is no `Sources(...)`, no chain layers,
   and no load-time `overrides={...}`. The settings package has its own
   `mapping_source()`, but it binds the class's
   [dictionary storage](../backends.md#the-dictionary-storage), which saves
   also write into, rather than a layer of a chain. A class that uses a
   source chain cannot be moved just by changing its base class.

The [Settings getting started](../settings/getting-started.md) page walks
through the same topics from the Settings side.

## Samples

Runnable examples of this package are in the repository, in
[samples/configuration/](https://github.com/advexp/advexp.settings.python/tree/main/samples/configuration):

- [configuration_api.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/configuration_api.py)
  — a live tour of the application API using a chain of bundled sources;
- [custom_source.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/custom_source.py)
  — a complete custom source built on the plugin contracts;
- [plain_declarations.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/plain_declarations.py)
  — the plain declaration style from start to finish;
- one walkthrough per source:
  [environment_variables.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/environment_variables.py),
  [dotenv_file.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/dotenv_file.py),
  [json_configuration.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/json_configuration.py),
  [toml_configuration.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/toml_configuration.py),
  and
  [yaml_configuration.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/yaml_configuration.py);
- [validation.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/configuration/validation.py)
  — the validation tour over this package's load channels.

The [Samples](../samples.md) page of the Guide lists all of them, together
with the Advexp.Settings examples and the examples that use both packages in
one application.

## What's next

- [Backends](../backends.md) covers the bundled backends in detail; the
  configuration sources correspond to them.
- [Value types](../value-types.md) lists all the types that source values
  can be converted to.
- [Validation](../validation.md) covers value constraints and cross-member
  rules.
- [Samples](../samples.md): runnable example programs for both packages,
  located in the project's repository.
- [Advexp.Settings](../settings/getting-started.md) walks through the same
  topics for the read-write package of the family.
