# Migrating from pydantic-settings

This page walks a working `pydantic-settings` application through the move
to Advexp.Configuration, step by step, without stopping development. The
[switching page](switching.md) shows what the same class looks like in both
libraries, side by side; here the class keeps working while it moves, and
the application changes one module at a time. Reading the page and repeating
the steps on the example below takes about fifteen minutes.

The move is gradual because the existing model does not have to go anywhere:
the pydantic model source, `pydantic_source`, turns it into one link of the
source chain of the new class. Members then move to their real sources one
by one, and the model shrinks. You can stop after any step and stay there —
the last section shows both legitimate endings.

The source rides pydantic, so install the extra first:
`pip install "advexp-configuration[pydantic]"`.

## The starting point

The example below is small, but it has the parts that make a migration
real: a variable prefix, a `.env` file, a nested model, a constrained
field, and a required field.

```python
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Db(BaseModel):
    host: str = "localhost"
    port: int = 5432


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        env_file=".env",
    )

    debug: bool = False
    port: int = Field(default=8000, ge=1, le=65535)

    # required: the environment or the .env file must provide it;
    # the token is a secret, so the model wraps it
    api_token: SecretStr

    db: Db = Db()
```

Suppose the `.env` file next to the application contains the variables
`APP_API_TOKEN=dev-token` and `APP_DB__PORT=64000`.

The application has one entry module that constructs the settings, and every
other module reads attributes:

```python
settings = AppSettings()

# anywhere in the application
print(repr(settings.port))
```

That single construction point is what makes the migration safe: while it
stands, every change below is invisible to the readers.

## Step 1: the model becomes a layer

The first move translates the whole model into a Configuration class. The
translation is mechanical, field for field — the
[switching page](switching.md#from-pydantic-settings) explains how each
piece maps. The nested model becomes a dataclass, the bounds keep their
parameter names, and the class's only source is the model itself:

```python
from dataclasses import dataclass

import advexp.configuration as adv_config
from advexp.configuration.plugins.pydantic import pydantic_source


@dataclass
class Db:
    host: str = "localhost"
    port: int = 5432


class Settings(
    adv_config.Configuration,
    options=pydantic_source(AppSettings),
):
    debug: bool = False

    # the same bounds, with the same parameter names as Field
    port: int = adv_config.setting(default=8000, ge=1, le=65535)

    # a bare annotation is required here too
    api_token: str

    db: Db = Db()
```

The entry module builds the class instead of the model:

```python
Settings.load_configuration()

# the class carries the values under the name the readers already use
settings = Settings
```

Nothing else in the application changes. The readers keep importing
`settings` and reading `settings.port`, and the values are the ones pydantic
resolves: on every load the source constructs the model, so the model still
reads the environment and the `.env` file, still validates, and still
applies its defaults — the class serves the result. The construction is
lazy and happens at most once per load: members that no source above the
model serves are the only ones that wake it.

Two details of the layer:

- It is keyed by member names, so the class keeps the field names of the
  model as its member names. Renaming a member later is an independent
  change: the environment link accepts `aliases=`, and file links accept
  `name=`.
- Secret fields need no care. The layer unwraps `SecretStr` and
  `SecretBytes` values itself, so a `str` member receives the plain secret,
  and a member of the family's own `SecretStr` wraps it again.

## Step 2: members move to their real sources

In step 1 the class serves whatever pydantic resolved. The next move puts
the real sources into the chain, above the model. The members stay as they
are; only the `options=` changes:

```python
import advexp.configuration.plugins.environment.dotenv as dotenv
import advexp.configuration.plugins.environment.variables as env


class Settings(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(
            name_prefix="APP_",
            name_case=env.NameCase.ANY,
            nested_delimiter="__",
        ),
        dotenv.dotenv_source(file=".env"),
        pydantic_source(AppSettings),
    ),
):
    debug: bool = False

    # the same bounds, with the same parameter names as Field
    port: int = adv_config.setting(default=8000, ge=1, le=65535)

    # a bare annotation is required here too
    api_token: str

    db: Db = Db()
```

The three links, in order:

- The environment first, with the same prefix as the model's `env_prefix`.
  `NameCase.ANY` gives the same case-insensitive lookup that pydantic-settings
  uses by default, and `nested_delimiter` is the same rule as
  `env_nested_delimiter`: `APP_DB__HOST` addresses the `host` field of the
  `db` member.
- The `.env` file next: pydantic-settings reads the environment before the
  `.env` file, and the chain repeats that order.
- The model last, as the safety net for everything the sources above cannot
  see yet: values passed to the model's constructor elsewhere in the code,
  a `secrets_dir=`, custom sources. Until those are spelled out or dropped,
  the layer keeps the class whole. A model that fails to construct is a
  broken source, like a file that cannot be parsed: the load of the member
  that reached it fails with the model's validation error, and the links
  below never hide it.

The naming parameters have one seat per class and are declared on the top
environment link; the `.env` link below reads the same dictionary, which is
why it carries only the file name.

From this moment the environment overrides the model:

```python
import os

# a variable set at launch wins over the model's resolution
os.environ["APP_PORT"] = "9000"
Settings.load_configuration()

print(repr(Settings.port))
```

This prints `9000`: the chain found the variable in the environment and
stopped there, and the model's value never came into play.

Now the members leave the model one by one. A field can go when the chain
covers its values completely: the sources that serve it are declared, and
its default lives in the class. The `db` field is the first to qualify —
its real sources are the environment and the `.env` file, both now in the
chain:

```python
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        env_file=".env",
        # the file keeps variables the model no longer declares
        extra="ignore",
    )

    debug: bool = False
    port: int = Field(default=8000, ge=1, le=65535)
    api_token: SecretStr
```

One line deserves a comment. The variable stays in the `.env` file — the
class reads it now — but pydantic-settings refuses inputs that the model
does not declare, because its `extra` default is `forbid`. `extra="ignore"`
lets the shrinking model live beside the file that the class also reads.
After the field is gone, the layer no longer carries `db`, and the class
does not need it to: the `.env` link serves the member.

The rest of the model moves the same way. Validators move with their
members: `@field_validator` becomes the `validator=` parameter of the
declaration, and rules that involve several fields become the `__validate__`
hook — [Validation](validation.md) covers both. `secrets_dir=` has no
bundled counterpart; a storage with one file per secret is a custom source,
and [Custom backends](extending.md#custom-backends) shows how to build one.

## Step 3: the finish you choose

The model has been shrinking while the chain grew. Where the move ends is a
real choice, and both endings are legitimate.

**The full switch.** When the last field has left the model, the link has
nothing left to carry: delete the model and the `pydantic_source(...)` link.
The declared defaults become the implicit last layer:

```python
class Settings(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(
            name_prefix="APP_",
            name_case=env.NameCase.ANY,
            nested_delimiter="__",
        ),
        dotenv.dotenv_source(file=".env"),
    ),
):
    debug: bool = False

    # the same bounds, with the same parameter names as Field
    port: int = adv_config.setting(default=8000, ge=1, le=65535)

    # a bare annotation is required here too
    api_token: str

    db: Db = Db()
```

The entry module is down to one line, `Settings.load_configuration()`, and
pydantic-settings leaves the project's dependencies. From this point the
application owns its source order, and the gains listed on the
[switching page](switching.md) — aliases for renamed variables, several
storages in one chain — are open to it.

So is an answer that the model could not give about itself: where a value
came from. While a member lives in the model layer, its origin is the
model's internal fold, and neither the class nor the model can name it. A
member of the chain names its sources instead — a load error lists every
address that was checked, and the debug log records each one that came up
empty — so an unexpected value can be traced to the variable or the file
key that provided it.

**The permanent hybrid.** The model stays as the last link of the chain,
and the code of steps 1 and 2, unchanged, is the finished state. This
ending is honest work, not a compromise: the model may serve other code —
a FastAPI schema, a business layer that validates with pydantic — or the
team may be moving slowly by choice. The costs are equally real:
pydantic-settings stays in the dependencies, and every load constructs the
model once.

**The shared base.** The third ending describes the members one time for
both packages: a plain class with the `SettingDeclarations` marker holds the
declarations — the fields of the old model, rewritten as members — and the
settings class and the configuration class inherit it together. This is the
page's class pair on one declaration set; see
[Shared declarations](shared-declarations.md) for the full picture.

```python
from advexp.settings_base import SettingDeclarations, setting


class ModelDeclarations(SettingDeclarations):
    retries: int = setting(default=3)
    timeout: int = setting(default=30, ge=retries)
```

The base holds what each value is; the body of each inheriting class
configures its own sources. A `Field(ge=...)` constraint moves into the
declaration the same way as on this page — the parameters are the same.

## Writing values back with Advexp.Settings

Configuration never writes to its sources, so a migrated class cannot save a
changed value. When the application needs that — the user changes settings
at runtime, a tool writes them back — the family's read-write package takes
over: Advexp.Settings. No pydantic bridge is needed for the file the model
read: a settings class on the same file reads it and writes it. Here is the
class of this page, rewritten for the read-write package:

```python
from dataclasses import dataclass

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as env


@dataclass
class Db:
    host: str = "localhost"
    port: int = 5432


class AppSettings(
    adv_settings.Settings,
    options=env.dotenv_source(
        file=".env",
        name_prefix="APP_",
        name_case=env.NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    debug: bool = False
    port: int = 8000
    api_token: str
    db: Db = Db()


AppSettings.load_settings()

# changing a value in memory is a plain assignment
AppSettings.port = 9000

# save one setting: only its line is written; every other line stays as is
AppSettings.save_setting(lambda s: s.port)

# or save the whole class in one atomic write
# AppSettings.save_settings()
```

The single-line save rewrites only `APP_PORT`; every other line keeps its
spelling and its place. A `save_settings()` call rewrites the whole file
atomically, keeping comments, blank lines, and key order intact. And the
model, if it stayed for the permanent hybrid, reads the same file on its
next construction — one storage, two readers.

### Moving the whole model into a settings class

The steps above end in Advexp.Configuration, with the model still in the
chain. When the destination is Advexp.Settings and the model has nothing
left to feed — the application wants every value saved and the model
deleted — the move is one bulk hand-off. Declare the settings class on a
native storage, mirror the members, and adopt the model's values in one
call. In the code below `AppSettings` is the settings class of this
section, and `model` is the pydantic instance the entry module built:

```python
# the values of the whole model, through the same conversion as a load
AppSettings.update_from_dict(model.model_dump())

# the whole class in one atomic write
AppSettings.save_settings()
```

`update_from_dict` accepts the same dictionary that the pydantic source
serves: member names as keys, nested models as dictionaries that feed the
dataclass members. One difference from the source demands care: a secret
field arrives from `model_dump()` as a live `SecretStr` object. A member
annotated `SecretStr` refuses it, and a plain `str` member accepts its
masked form — the file would then hold `"**********"` in place of the
secret. Unwrap the value before the call:

```python
dump = dict(model.model_dump())
dump["api_token"] = dump["api_token"].get_secret_value()
AppSettings.update_from_dict(dump)

# write the freed secret over the masked form
AppSettings.save_settings()
```

After the save the storage holds every value, and a fresh
`load_settings()` reads them back. From that moment the model has nothing
left to do: delete it, and the settings class owns both the reading and
the writing.

A settings class has no source chain; it has one storage per backend
family. The [switching page's last section][write-back] shows the same
move for the classes of its examples, and [Backends](backends.md) covers
every storage.

[write-back]: switching.md#writing-values-back-with-advexpsettings
