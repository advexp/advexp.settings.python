# Switching from other libraries

This page shows the same settings written first in pydantic-settings,
python-decouple, and dynaconf, and then in Advexp.Configuration, so you can
learn how to switch by example.

Your existing storage files can usually stay as they are, as long as the
format matches: a `.env` file keeps its variables and their spelling, and a
TOML file keeps its keys and tables. What changes is the declaration:
values, types, and rules become members of one class.

All three libraries read their values in layers: pydantic-settings checks
the environment before `.env`, python-decouple checks the environment
before the file it reads, and dynaconf stacks files and environments on top
of each other. Advexp.Configuration handles layering with one mechanism, the
[source chain](configuration/getting-started.md#the-source-chain): the
sources of a class are listed in lookup order, and the first source that
has a value wins. The other package of the family, Advexp.Settings, adds
saving; [the last section](#writing-values-back-with-advexpsettings) explains
when to choose it.

## From pydantic-settings

In pydantic-settings, you declare a `BaseSettings` subclass with annotated
fields. The sources are configured in `model_config`, and every read creates
a new instance:

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

Here are the same settings as one Advexp.Configuration class. By default,
pydantic-settings looks up variables case-insensitively, and `NameCase.ANY`
gives the same behavior:

```python
import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.dotenv as dotenv
import advexp.configuration.plugins.environment.variables as env


class AppSettings(
    adv_config.Configuration,
    options=adv_config.Sources(
        # the environment takes priority over the .env file, as in pydantic
        env.env_source(name_prefix="APP_", name_case=env.NameCase.ANY),
        dotenv.dotenv_source(file=".env"),
    ),
):
    debug: bool = False

    # the bounds use the same parameter names as Field above
    port: int = adv_config.chain_setting(default=8000, ge=1, le=65535)

    # a bare annotation is required here too
    api_token: str


# one load walks the chain: the environment first, then the .env file
AppSettings.load_configuration()

print(repr(AppSettings.port))

# a layer above the whole chain for this call only, like init arguments
AppSettings.load_configuration(overrides={"port": 9000})
```

How the pieces map to each other:

- `BaseSettings` and `model_config = SettingsConfigDict(env_prefix="APP_")`
  become the `Configuration` base class and the `Sources(...)` list of the
  class. `case_sensitive=True` with upper-case variables becomes
  `name_case=env.NameCase.UPPER`. The `NameCase.ANY` used above corresponds
  to the default `case_sensitive=False`.
- `env_file=".env"` becomes the dotenv link of the chain. The naming rules
  are declared once per class and apply to both environment links, because
  the process environment and the `.env` file form one namespace.
  `env_nested_delimiter="__"` becomes the `nested_delimiter="__"` parameter
  of the family: `APP_DB__PORT` addresses the `port` field of the `db`
  member, and a dataclass annotation replaces the nested model.
- pydantic-settings reads its sources in a fixed order (the init arguments,
  the environment, `.env`, the secrets directory), and the earlier source
  wins. Here you set the order yourself by listing the sources in
  `Sources(...)`. The init arguments become the `overrides={...}` argument
  of the load: a layer above the whole chain for a single call, which is
  also convenient in tests.
- The bounds of `Field(default=..., ge=..., le=...)` become parameters of
  the declaration with the same names. A read-only class checks them at two
  points: at the `class` statement, against the declared defaults, and at
  the end of every load. See [Validation](validation.md). In
  pydantic-settings, a field without a default is required. A bare
  annotation has the same meaning here, and so does a factory call without
  `default=`.
- `SecretStr` is also exported here and behaves the same way: it has the
  masked representation and `get_secret_value()`, and the value is stored in
  plain form.
- `@field_validator` becomes the `validator=` parameter of the declaration.
  Rules that involve several fields use member references and the
  `__validate__` hook.
- Instances are replaced by the class. pydantic-settings builds an instance
  for each read. Here, the class itself holds the values, and `to_object()`
  returns a detached copy for code that needs an object.
- What you gain by switching: your own order of sources instead of the fixed
  one, aliases for renamed variables, and several storages in one chain.
  Writing values back is handled by the family's read-write package,
  Advexp.Settings; see
  [the last section](#writing-values-back-with-advexpsettings).

`secrets_dir=` has no bundled counterpart. A storage with one file per
secret needs a custom source.
[Custom backends](extending.md#custom-backends) shows how to build one.

## Pydantic models can stay

Switching the configuration library does not mean you have to drop your
pydantic models. Neither package of the family depends on pydantic, so data
is exchanged through a plain dictionary, which both sides already support:

```python
from pydantic import BaseModel


class Deployed(BaseModel):
    api_token: str
    debug: bool = False
    port: int = 8000
    note: str = ""  # a field the settings class never declared


# the class feeds the model: its values come out as a plain dictionary
deployed = Deployed(**AppSettings.to_dict())

# the model feeds the class: a layer above the whole chain for one call
AppSettings.load_configuration(overrides=deployed.model_dump())
```

`model_dump()` on the pydantic side corresponds to `to_dict()` on the
Advexp side. Keys that the class does not declare, such as the extra `note`
field above, are dropped, so a model with extra fields never breaks the
call. A model can also become a separate layer of the chain: put an empty
`mapping_source()` at the position you need, and fill it with
`mapping_source_for(AppSettings).set(deployed.model_dump())` before the
load reads it. The full round trip, including the options of the read-write
package, is described in
[Exchanging data with pydantic](configuration/getting-started.md#exchanging-data-with-pydantic).

## From python-decouple

python-decouple reads one value per call. The type is given by a `cast=`
callable, the fallback by `default=`, and a call without `default=` raises
an error when the variable is absent:

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

Here are the same settings as one class. The file stays as it is, and the
environment keeps its priority: the process environment link comes before
the dotenv link. `name_case=env.NameCase.UPPER` builds the variable name
`DEBUG` from the member `debug`, and so on:

```python
from datetime import timedelta

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.dotenv as dotenv
import advexp.configuration.plugins.environment.variables as env


class AppSettings(
    adv_config.Configuration,
    options=adv_config.Sources(
        # the environment takes priority over the file, as in python-decouple
        env.env_source(name_case=env.NameCase.UPPER),
        dotenv.dotenv_source(file=".env"),
    ),
):
    debug: bool = False

    port: int = 8000

    # the annotation is the cast; the value arrives parsed
    session_ttl: timedelta = timedelta(minutes=30)

    # a bare annotation is required: a source must provide it
    api_token: str


AppSettings.load_configuration()

# datetime.timedelta(seconds=1800): parsed, not a string
print(repr(AppSettings.session_ttl))
```

How the pieces map to each other:

- One `config(...)` call becomes one member. The variable name is built from
  the member's name, so you no longer write the name twice: once as a string
  in the call and once as the Python variable it is assigned to.
- `cast=` becomes the annotation. The conversion is declared once, together
  with the type, and every read after the load returns the converted value.
- `default=` becomes the declared default. A call without `default=`
  becomes a bare annotation, which declares a required member. One load
  reports all missing required members in a single error.
- python-decouple checks the process environment first: a variable set
  there wins over the `.env` file. The chain keeps this order: the
  environment link comes before the dotenv link, and a single list states
  the whole priority.
- There is no direct equivalent of `Csv`. In a string-based storage, a
  collection is stored as JSON array text, for example `["a", "b"]`. This
  is the form that the library uses for round trips.
- What you gain by switching: value constraints on every member, aliases for
  renamed variables, and files in the same chain as the environment.
  Writing values back into `.env` is done by Advexp.Settings; see
  [the last section](#writing-values-back-with-advexpsettings).

python-decouple can also read `settings.ini`. The family has no ini source,
so an ini file must be converted to `.env`, JSON, or TOML.

## From dynaconf

dynaconf is built around a single settings object. Files, layers, and
validators are arguments of the `Dynaconf(...)` call, and every read goes
through that object:

```python
from dynaconf import Dynaconf, Validator

settings = Dynaconf(
    settings_files=["settings.toml"],
    environments=True,
    validators=[Validator("PORT", gte=1, lte=65535)],
)

port = settings.get("PORT", default=8000)

host = settings.get("HOST", default="localhost")
```

Here are the same settings as one class. dynaconf keeps the environments as
tables of one file and picks one through the `ENV_FOR_DYNACONF` variable.
Here every environment gets its own file, and the file of the current
environment takes priority over the base file:

```python
import advexp.configuration as adv_config
import advexp.configuration.plugins.toml_settings as ts
from advexp.configuration import env_parameter

# APP_ENV names the environment; a typo makes the load fail early
app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))


class ServiceSettings(
    adv_config.Configuration,
    options=adv_config.Sources(
        # the file of the current environment (settings-dev.toml
        # when APP_ENV=dev) takes priority over the base file
        ts.toml_source(file="settings-{APP_ENV}.toml", parameters=app_env),
        ts.toml_source(file="settings.toml"),
    ),
):
    # the root key "PORT"; the bounds are part of the declaration
    port: int = ts.toml_setting(name="PORT", default=8000, ge=1, le=65535)

    host: str = ts.toml_setting(name="HOST", default="localhost")


ServiceSettings.load_configuration()

print(repr(ServiceSettings.port))
```

How the pieces map to each other:

- `Dynaconf(settings_files=[...])` becomes the `Sources(...)` list: every
  file is one link, read in lookup order. If you do not give explicit
  names, the default key pattern is `{module}.{class}.{member}`. This keeps
  the keys of two classes distinct when they share one file.
- `environments=True` becomes a file per environment. The base values of
  dynaconf's `[default]` table become the base file, `settings.toml`, and
  the overrides of each environment become `settings-{APP_ENV}.toml`, one
  layer above it. `APP_ENV` names the environment, and the `choices` of the
  parameter catch a typo before the library accesses the file system. See
  [A file per environment](configuration/getting-started.md#a-file-per-environment)
  for details about these slots and how they are checked.
- A `Validator` becomes constraint parameters in the declaration itself.
  These bounds are checked at the `class` statement and at the end of every
  load. See [Validation](validation.md).
- `settings.get("PORT")` and `settings.PORT` become the member itself.
  dynaconf's `@int` casts and `as_int(...)` forms are needed for values that
  arrive as text, for example from environment variables. Here, the
  annotation replaces them.
- `settings.set("PORT", 9000)` has no counterpart: this package is
  read-only, and an assignment raises `TypeError`. New values are picked up
  by calling `load_configuration()` again. Writing values into the file is
  done by Advexp.Settings; see
  [the last section](#writing-values-back-with-advexpsettings).
- A nested table is addressed with a dotted name. `name="database.host"`
  refers to the key `host` in the `[database]` table, which is the same
  address that TOML itself uses. A nested object can also be a single
  member: use a dataclass annotation, and it is converted field by field.

## Writing values back with Advexp.Settings

Advexp.Configuration is read-only: it loads values and never writes them
back. When the application also needs to save — for example, when a user
changes a setting or a tool stores its state — use the other package of the
family, Advexp.Settings. It reads and writes the same storages and declares
members in the same way, so a class can usually move between the packages
just by changing the base class and the imports.

Here is the class from the python-decouple section, rewritten for the
read-write package. The `.env` file is the storage, and saving writes the
values back into it:

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as env


class AppSettings(
    adv_settings.Settings,
    options=env.dotenv_source(file=".env", name_case=env.NameCase.UPPER),
):
    debug: bool = False

    port: int = 8000

    # the annotation is the cast; the value arrives parsed
    session_ttl: timedelta = timedelta(minutes=30)

    # a bare annotation is required here too
    api_token: str


AppSettings.load_settings()

# changing a value in memory is a plain assignment
AppSettings.port = 9000

# save one setting: only its line is written; every other line stays as is
AppSettings.save_setting(lambda s: s.port)

# or save the whole class in one atomic write
# AppSettings.save_settings()
```

What to keep in mind when a class moves between the packages:

- A settings class has no source chain. There is no `Sources(...)`, and a
  member reads the storage that its declaration names. Layering sources
  above files is the job of Advexp.Configuration.
- A factory call without `default=` has different meanings: in
  Advexp.Settings it declares an optional member (`None` until a value is
  loaded), and in Advexp.Configuration it declares a required member. A bare
  annotation is required in both. In a class that moves between the
  packages, write the default explicitly in every factory call.
- Saving preserves the rest of the file. `save_setting` rewrites only the
  line that it saves: comments, `export` lines, and unknown variables stay
  as they are. `save_settings` rewrites the whole file atomically, keeping
  comments, blank lines, and key order intact.

The two packages are often used together in one application:
Advexp.Configuration reads the process configuration, and one small
Advexp.Settings class keeps the values that the user or the tool changes. A
settings class can also mix backends
([Mixing backends in one class](settings/getting-started.md#mixing-backends-in-one-class))
and use a writable file per environment
([A file per environment](settings/getting-started.md#a-file-per-environment)).
