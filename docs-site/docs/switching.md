# Switching from other libraries

This page shows the same settings in pydantic-settings, python-decouple, and
dynaconf, and then in Advexp.Settings, so you can learn how to switch by
example.

Your existing storage files can stay as they are wherever the format
matches: a `.env` file keeps its variables and their spelling, and a TOML
file keeps its keys and tables. What changes is the declaration: values,
types, and rules become members of one class.

## From pydantic-settings

In pydantic-settings, you declare a `BaseSettings` subclass with annotated
fields. The sources are configured in `model_config`, and every read creates
an instance:

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    debug: bool = False

    port: int = Field(default=8000, ge=1, le=65535)

    # required: the environment must provide it
    api_token: str


# reads the environment at construction; the instance carries the values
settings = AppSettings()

print(repr(settings.port))
```

Here are the same settings as one Advexp.Settings class. By default,
pydantic-settings looks up variables without regard to case. `NameCase.ANY`
gives the same behavior:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


class AppSettings(
    adv_settings.Settings,
    options=env.env_source(name_prefix="APP_", name_case=env.NameCase.ANY),
):
    debug: bool = False

    # the constraints keep Field's own names
    port: int = adv_settings.setting(default=8000, ge=1, le=65535)

    # a bare annotation is required here too
    api_token: str


# the class itself carries the values; a load reads the environment
AppSettings.load_settings()

print(repr(AppSettings.port))

# write the value back: APP_PORT of the process environment
AppSettings.port = 9000
AppSettings.save_setting(lambda s: s.port)
```

How the pieces map to each other:

- `BaseSettings` and `model_config = SettingsConfigDict(env_prefix="APP_")`
  become the `Settings` base class and
  `options=env_source(name_prefix="APP_")`. `case_sensitive=True` with
  upper-case variables becomes `name_case=env.NameCase.UPPER`. The
  `NameCase.ANY` used above corresponds to the default
  `case_sensitive=False`.
- `Field(default=..., ge=..., le=...)` keeps its parameter names. The same
  bounds are parameters of the declaration, and they are checked wherever a
  value reaches the member: at the `class` statement, on an assignment, in
  an update, on a load, and on a save. See [Validation](validation.md). In
  pydantic-settings, a field without a default is required. A bare
  annotation has the same meaning here.
- `env_file=".env"` becomes the dotenv family. The process environment and a
  `.env` file share one namespace, with one naming declaration per class.
  `env_nested_delimiter="__"` becomes the family's `nested_delimiter="__"`:
  `APP_DB__PORT` addresses the `port` field of the `db` member, and a
  dataclass annotation replaces the nested model.
- `SecretStr` is also exported here. The masked representation,
  `get_secret_value()`, and the plain stored form behave in the same way.
- `@field_validator` becomes the `validator=` parameter of the declaration.
  Rules that involve several fields become member references and the
  `__validate__` hook.
- pydantic-settings reads its sources in a fixed order (the init arguments,
  the environment, `.env`, the secrets directory), and the earlier source
  wins. Reading in layers like this is done by the
  [source chain](configuration/getting-started.md#the-source-chain) of
  Advexp.Configuration. In Advexp.Settings, every member reads from the
  storage that its declaration names.
- Instances become the class. pydantic-settings builds an instance for each
  read. Here, the class itself holds the values, `to_object()` returns a
  detached copy, and `update_from_object` applies a copy back.
- What the switch adds: writing values back (pydantic-settings only reads),
  several backends in one class, aliases for renamed variables, and the
  dynamic collection.

`secrets_dir=` has no bundled counterpart. A storage with one file per secret
needs a backend of its own. [Custom backends](extending.md#custom-backends)
shows how to build one.

## Pydantic models stay

Switching the settings engine does not force you to retire your pydantic
models. Neither package of the family depends on pydantic. Data is exchanged
through a plain dictionary, which both sides already support:

```python
from pydantic import BaseModel


class Deployed(BaseModel):
    api_token: str
    debug: bool = False
    port: int = 8000
    note: str = ""  # a field the settings class never declared


# the class feeds the model: the snapshot is a plain dictionary
deployed = Deployed(**AppSettings.to_dict())

# the model feeds the class: the flag drops the foreign keys
AppSettings.update_from_dict(deployed.model_dump(), ignore_unknown=True)
```

`model_dump()` on the pydantic side corresponds to `to_dict()` on the
Advexp side. A model can also serve as the dictionary storage of a class that
is bound with `mapping_source(...)`: you fill the storage through the
resolver before the load reads it. The full round trip, including the rules
that apply to the values and to the foreign keys, is described in
[Exchanging data with pydantic](settings/getting-started.md#snapshots-and-exchanging-data-with-pydantic).

## From python-decouple

python-decouple reads one value per call. The type is a `cast=` callable, the
fallback is `default=`, and a call without `default=` raises an error if the
variable is absent:

```python
from datetime import timedelta

from decouple import config

DEBUG = config("DEBUG", default=False, cast=bool)

PORT = config("PORT", default=8000, cast=int)

# every further type is a cast of your own
SESSION_TTL = config(
    "SESSION_TTL", cast=lambda v: timedelta(seconds=int(v))
)

API_TOKEN = config("API_TOKEN")
```

Here are the same settings as one class. The file stays as it is. By
default, the backend reads `.env` in the working directory, and every
variable keeps its spelling: `name_case=env.NameCase.UPPER` builds `DEBUG`
from the member `debug`, and so on:

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as env


class AppSettings(
    adv_settings.Settings,
    options=env.dotenv_source(name_case=env.NameCase.UPPER),
):
    debug: bool = False

    port: int = 8000

    # the annotation is the cast; the value arrives parsed
    session_ttl: timedelta = timedelta(minutes=30)

    # a bare annotation is required: the file must provide it
    api_token: str


AppSettings.load_settings()

# datetime.timedelta(seconds=1800): parsed, not a string
print(repr(AppSettings.session_ttl))

# save one setting: its line alone; every other line stays as written
AppSettings.port = 9000
AppSettings.save_setting(lambda s: s.port)
```

How the pieces map to each other:

- One `config(...)` call becomes one member. The variable name is built from
  the member's name, so you do not write the name twice: once as a string in
  the call and once as the Python variable next to it.
- `cast=` becomes the annotation. The conversion is declared once, where the
  type is, and every read after the load returns the converted value.
- `default=` becomes the declared default. A call without `default=` becomes
  a bare annotation, which declares a required member. One load reports all
  missing required members in a single error.
- python-decouple looks the process environment up first: a variable set
  there wins over the `.env` file. Here the environment and the file are
  separate backends, and a member reads the one its declaration names;
  reading one above the other is the
  [source chain](configuration/getting-started.md#the-source-chain) of
  Advexp.Configuration.
- There is no direct equivalent of `Csv`. In a string-based storage, a
  collection is stored as JSON array text, for example `["a", "b"]`. This is
  the form that the library uses for round trips.
- What the switch adds: saving values back into `.env`. A save replaces only
  the lines that it writes, while comments, `export` lines, and variables
  that do not belong to any member stay exactly as they are. It also adds
  value constraints, aliases for renamed variables, and members of one class
  that are served by different backends
  ([Mixing backends in one class](backends.md#mixing-backends-in-one-class)).

python-decouple can also read `settings.ini`. The family has no ini backend,
so an ini file has to be moved to `.env`, JSON, or TOML.

## From dynaconf

dynaconf is built around a single settings object. Files, layers, and
validators are arguments of the `Dynaconf(...)` call, and every read goes
through that object:

```python
from dynaconf import Dynaconf, Validator

settings = Dynaconf(
    settings_files=["settings.toml"],
    validators=[Validator("PORT", gte=1, lte=65535)],
)

port = settings.get("PORT", default=8000)

host = settings.get("HOST", default="localhost")
```

Here are the same settings as one class. A dynaconf file keeps upper-case
names at its root. An explicit `name=` is the full address, so the keys keep
their spelling:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.toml_settings as ts


class ServiceSettings(
    adv_settings.Settings,
    options=ts.toml_source(file="settings.toml"),
):
    # the root key "PORT"; the bounds are part of the declaration
    port: int = ts.toml_setting(name="PORT", default=8000, ge=1, le=65535)

    host: str = ts.toml_setting(name="HOST", default="localhost")


# the same settings.toml; the root keys keep their addresses
ServiceSettings.load_settings()

print(repr(ServiceSettings.port))

# an in-memory change is an assignment
ServiceSettings.port = 9000

# one atomic write; the file's comments and order stay intact
ServiceSettings.save_settings()
```

How the pieces map to each other:

- `Dynaconf(settings_files=[...])` becomes `options=toml_source(file=...)`.
  If you do not give explicit names, the default key pattern is
  `{module}.{class}.{member}`. This keeps the keys of two classes apart when
  they share one file.
- A `Validator` becomes constraint parameters of the declaration itself. The
  bounds are then checked wherever a value reaches the member: at the `class`
  statement, on an assignment, in a bulk update, on a load, and on a save.
  See [Validation](validation.md).
- `settings.get("PORT")` and `settings.PORT` become the member itself. The
  `@int` casts and the `as_int(...)` forms are needed for values that arrive
  as text, for example from environment variables. Here, the annotation
  replaces them.
- `settings.set("PORT", 9000)` becomes an assignment. Writing the value back
  is a separate step: `save_settings()` makes one atomic write, and the
  file's comments, blank lines, and key order survive it.
- A nested table is a name with dots. `name="database.host"` is stored as
  `host` in the `[database]` table, which is the address that TOML itself
  reads. A nested object can also be one member of its own: a dataclass
  annotation, converted field by field.
- `environments=True` is layering: a base value that is overridden for each
  environment. The writable equivalent here is one file per environment,
  using a placeholder in the file name, `settings-{APP_ENV}.toml`
  ([A file per environment](settings/getting-started.md#a-file-per-environment)).
  Reading layers on top of each other, including environment variables above
  files, is the job of the read-only
  [source chain](configuration/getting-started.md#the-source-chain) of
  Advexp.Configuration.
- Keys under dynaconf's `[default]` table are reached in the same way: use a
  dotted explicit name, `name="default.PORT"`, because a dot in a name
  separates table levels here too.
