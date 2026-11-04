# Backends

Backends are provided as plugins. **Importing a backend's module enables
it.** No registration calls are needed. Each module contains everything its
backend needs, including its source builder. The bundled backends are:

- the environment family: the process environment
  (`advexp.settings.plugins.environment.variables`) and a `.env` file
  (`advexp.settings.plugins.environment.dotenv`);
- the JSON, TOML, and YAML file backends;
- the dictionary storage (`advexp.settings.plugins.mapping_source`).

A save changes only the settings that it writes. In a file backend, the rest
of the file stays as the user left it: comments, layout, and keys that the
library does not recognize survive a save. The section for each backend
lists exactly what it keeps and what it rewrites.

## Aliases: one member, several addresses

A member has one primary address: the explicit `name=` or the name built
from the pattern. The member can also declare more full addresses with
`aliases=`. Aliases are useful when you rename something. If a variable or a
document key gets a new spelling, the old spelling keeps working, so a
deployment that still uses it loads as before.

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
    # the primary address is APP_SESSION_TTL (prefix + the member
    # name in upper case); the old name APP_TTL keeps serving the
    # member
    session_ttl: timedelta = env.environment_variable_setting(
        aliases=["APP_TTL"], default=timedelta(minutes=30)
    )
```

The rules:

- Every alias is a full address and has the same status as an explicit
  `name=`. `name_prefix`, `name_case`, and the JSON/TOML name patterns never
  change it, whatever spelling the primary address uses.
- A load looks up the primary address first, then the aliases in the order
  in which they were declared. The first address that has a value wins.
- `contains_setting` recognizes any of the addresses.
- Saving writes only to the primary address, so the rename is complete after
  the next save. Deleting removes the value from every address of the
  member, so a deleted value cannot come back through an old name.
- In JSON and YAML, an alias is placed under the member's `path=`, like the
  primary key. In TOML, an alias is placed under the member's `path=` too,
  nested by its own dots.
- Diagnostics list every address that was checked. This applies to the debug
  record of a fallback and to the abort entry of a required member, for
  example: `environment variable 'APP_SESSION_TTL' (aliases: 'APP_TTL')`.
- The field-by-field addressing of the environment family is resolved from
  the primary name only. Aliases take no part in it.

An invalid alias list makes the `class` statement fail before any storage
pass. Examples of invalid lists are a wrong type, an empty string, and an
alias that repeats the `name=` address or another alias. The read-only
sources of `advexp.configuration` support `aliases=` in the same way
([Configuration: Aliases](configuration/getting-started.md#aliases)). A
backend of your own can support aliases through the attribute contract
(`attr.aliases`) and the `setting_name_candidates` helper from `plugin_api`.

## Members without storage

`non_storage_setting(...)` is provided by the core package, directly in
`advexp.settings`. It declares a member that no storage ever serves:

- `default=` is required.
- The value is either the declared default or the last assigned value.
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
class does not treat the name as a member, no storage ever sees it, and
`to_dict()` does not include it. `ClassVar` is the standard Python way to
mark a value that simply lives on the class. Use `non_storage_setting(...)`
for values that should behave as members.

The read-only counterpart has its own version of this concept:
`advexp.configuration` provides `constant_setting(default=...)`. It declares
a member that neither the sources nor the load overrides can change, so its
value is always the declared one, on every load. See
[Configuration: Members that do not use the source chain](configuration/getting-started.md#members-that-do-not-use-the-source-chain).

## Environment variables

Each member maps to one variable, and `name=` is the full address:

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


class AppSettings(adv_settings.Settings):
    session_ttl: timedelta = env.environment_variable_setting(
        name="APP_SESSION_TTL", default="0:30:00"
    )

    debug: bool = env.environment_variable_setting(
        name="APP_DEBUG", default=False
    )
```

All environment backends share the same naming options: the prefix, the
name case, and the nested delimiter for dataclass members. They are
arguments of the family's source builder, which you pass through the
`options=` keyword of the `class` statement:

```python
from datetime import timedelta

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


class AppSettings(
    adv_settings.Settings,
    options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER
    ),
):
    # APP_SESSION_TTL
    session_ttl: timedelta = timedelta(minutes=30)

    # untouched: an explicit name is the full address
    legacy: str = env.environment_variable_setting(
        name="legacy_flag", default="off"
    )
```

The variable name is `name_prefix + name_case(member name)`:

- The prefix is added exactly as written.
- `NameCase.UPPER` and `NameCase.LOWER` change the case of the member name
  only. There is no conversion between camelCase and snake_case. `None`,
  the default, changes nothing.
- An explicit `name=` is the full address in the storage. The prefix and
  the case never change it.

A member can also declare more full addresses next to the primary one. See
[Aliases](#aliases-one-member-several-addresses).

`NameCase.ANY` changes the lookup, not the name. The name is built as
declared, and the lookup accepts any spelling of it:

- An exact match wins silently.
- If two spellings differ only in case and neither matches exactly, the load
  fails with an error that names the source and both spellings.
- An explicit `name=` is also looked up without regard to case.
- When saving with `ANY`, the library updates the spelling that already
  exists in the environment. If no spelling exists, it writes the variable
  under its built name.

### Nested objects

Nested objects are addressed field by field. A member annotated with a
dataclass holds one nested object. The `nested_delimiter` option of the
family opens its fields to the environment. With the delimiter `"__"`,
`APP_DB__PORT` is the `port` field of the `db` member, and
`APP_DB__DEEP__V4` is the `v4` field of `db.deep`. A nested address consists
of the member's own variable name, then the delimiter, then the field name
with its case applied. This works at any depth, and `name_case` applies to
every part:

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

The whole-object form still works: the member's own variable can hold the
object as JSON, and so can the own variable of any nested object
(`APP_DB__DEEP` holds the whole `deep` object). A per-field variable takes
precedence over a whole-object variable that overlaps with it.

If `APP_DB__PORT=6543` is set and nothing else, `db` loads as
`DbConfig(host="db.local", port=6543)`:

- **Loading** updates the object partially. The declared default instance is
  the base, and every field that no variable addresses keeps its declared
  value. If there is no declared default, the dataclass's own field defaults
  are used.
- **A whole-object variable that is not a JSON object** is handled in the
  same way as a failed flat member: a warning is reported, and the member
  falls back to its effective default.
- **Saving** mirrors the addressing. Each field is written to its own
  variable, and the whole-object variables are removed, so a saved object
  loads back exactly as it was saved.
- **The delimiter is off by default** (`nested_delimiter=None`). Without it,
  every member stays one flat variable, and `APP_DB__PORT` addresses
  nothing.

Saving writes the variables back through `os.environ`. A `None` value has no
string form, so saving it removes the entry, and the next load falls back to
the default.

## JSON files

The JSON backend stores settings as one flat JSON object. The keys are full
setting names (the explicit `name=` or the `{module}.{class}.{member}`
pattern), and the values are stored as native JSON. The optional `path=` of
`JSONSetting` places the key inside the document. It is a JSON Pointer
(RFC 6901):

- `path="/net/proxy"` stores the key under `net`, then `proxy`.
- `path="/mirrors/1"` stores it inside the second element of the `mirrors`
  array.
- `path="/endpoints/api.internal"` stores it under an object key that
  contains a dot.
- In a pointer, `~1` escapes `/` and `~0` escapes `~`.

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class LocalSettings(adv_settings.Settings):
    host: str = js.json_setting(name="host", default="localhost")

    port: int = js.json_setting(default=8080)

    # net -> timeout
    timeout: int = js.json_setting(name="timeout", path="/net", default=30)

    region: str = js.json_setting(
        name="region", path="/replicas/0", default="eu"
    )

    # a path segment may contain a dot: it names the object key
    # api.internal
    api: str = js.json_setting(path="/endpoints/api.internal", default="")
```

A path segment made only of digits indexes an array if the node it steps
into is an array. Otherwise, it names an object key. If an array is missing
or too short, saving pads it with JSON `null` values up to the indexed
position.

Each pass reads the file once and writes it back atomically at the end: a
temporary file replaces the old one. Because the replacement creates a new
file, the write copies the permission mode from the old file. A mode that
was set by hand (for example, `600` on a secrets file) therefore survives a
save. A file in another encoding is rejected with a read error that names
the file, instead of a bare codec message.

Keys that the library does not know are kept, and so is the file's layout.
Existing keys stay where they are, and new keys are added at the end of
their container. The file keeps the formatting it already uses:

- its indentation (four spaces, tabs, or a one-line compact form);
- raw non-ASCII text where the file already has it (an ASCII-only file keeps
  its `\u` escapes);
- a UTF-8 BOM, if the file starts with one;
- its line endings, so a CRLF file stays CRLF.

A new file gets two-space indentation, members in declaration order, plain
UTF-8 for non-ASCII values, and LF line endings.

??? note "Deleting a setting"

    Deleting a setting also removes the path objects that it left empty. An
    emptied array element becomes a `null`, so its siblings keep their
    positions. An array in which every element is a `null` is removed.

The file itself is configured outside the class, on several levels, from the
widest to the most specific. The more specific level wins. The process-wide
level sets one value for every settings class in the application. You assign
`js.JSONSettingsConfiguration.file_path` once at startup. Alternatively, a
module can keep its file to itself. Declare the file once, at the top level
of the module. The declaration then applies only to the classes of that
module:

```python
from pathlib import Path

from advexp.settings import for_this_module
import advexp.settings.plugins.json_settings as js

js.JSONSettingsConfiguration.file_path = for_this_module(
    Path("app-settings.json")
)
```

Every module can declare its own file this way, and the declarations
coexist. A module's declaration wins over the process-wide value for the
classes of that module, while classes in other modules keep the
process-wide value. The line is an ordinary module-level statement that takes
effect when the module is imported. Therefore, a tool that imports the
settings modules without running the application can collect every
declaration with `declared_module_defaults()`. If no file is configured at
any level, the first storage access raises an error that names the
available options.

A class can be bound to its own file through the `options=` keyword of the
`class` statement. A subclass inherits the binding unless it declares its
own:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class WindowSettings(
    adv_settings.Settings,
    options=js.json_source(file="window-settings.json"),
):
    width: int = js.json_setting(default=800)
```

At runtime, the `file_path` property of the plugin handle reads and changes
the file while the program is running. The class's own binding wins over
both the module level and the process-wide level.

By default, JSON keys follow the full pattern `{module}.{class}.{member}`.
This keeps the keys of two classes apart when they share one document. You
can change the pattern with `name_pattern=` on the same builder. For
example, plain member names suit a file that a person edits by hand:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class EditorSettings(
    adv_settings.Settings,
    options=js.json_source(
        file="editor-settings.json", name_pattern="{FieldName}"
    ),
):
    tab_width: int = js.json_setting(default=4)  # "tab_width" in the file

    # an explicit name= is the full address, as always
    ui_font: str = js.json_setting(name="font", default="monospace")
```

The pattern can use the slots `{NamespaceName}` (the module), `{ClassName}`,
`{FieldName}`, and `{Delimiter}`. It must contain `{FieldName}`, because
otherwise every member of the class would collapse onto one key. The pattern
applies to the whole class that reads through the builder. A subclass's own
binding replaces the pattern for that subclass and its subclasses. An
explicit `name=` stays the full address in the document, and a member's
`path=` still places its key in the tree. Declared `aliases=` extend the
lookup in the same way for the whole family
([Aliases](#aliases-one-member-several-addresses)). A class with no binding
can still change the pattern at runtime through the family entry of the raw
metadata (`JSON_METADATA_OPTIONS`).

A short pattern trades safety for readability. If two classes use the same
short form in one file, their keys collide, and the later write overwrites
the earlier key. The overwrite is not completely silent: a debug-level
record names the key. To avoid the collision, give one of the classes a
different pattern, its own file (`json_source(file=...)`), or explicit
names.

The file declaration `json_file(...)` names the class's file when the
binding is held by the builder of another family. A plain member requires
the class to have a single source, and the file declaration does not count
as a second source. The factory members of the JSON family read the named
file:

```python
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
    mode: str = "production"

    retries: int = js.json_setting(name="retries", default=3)
```

The file declaration belongs to the class that declares it, like the
binding. A subclass without its own declaration reads the nearest one above
it. A subclass with its own declaration switches to it for itself and its
subclasses. A file declaration next to a source builder of the same family
makes the `class` statement fail, because the pair would name one storage
twice, and the file of a bound family belongs on the source builder. The
`file_path` of the plugin handle reads and writes the declaration at
runtime. The TOML and dotenv families spell their file declarations in the
same way (`toml_file(...)`, `dotenv_file(...)`). The variable name of a
dotenv member is still built by the naming rules shared with the
environment family.

Like the family's binding, a file declaration governs the members that its
class declared. It is stored per declaring class and can be changed at
runtime through the same channel as the
[options of the environment family](#environment-variables).

## TOML files

The TOML backend stores settings in one TOML document, using native TOML
values. `datetime`, `date`, and `time` values keep the form that TOML itself
uses, not ISO strings. The backend uses
[tomlkit](https://github.com/python-poetry/tomlkit), an editor that
preserves formatting. Install it with the `toml` extra
(`pip install "advexp-settings[toml]"`).

A setting is stored at the address that its key names. Every dot in the key
(the explicit `name=` or the pattern-built one) separates table levels, and
the last part is the key itself. This is the same address that TOML itself
reads: `[app.LocalSettings] port = 8080`, never a quoted flat key such as
`"app.LocalSettings.port"`. A name without a dot is a plain key. A `path=`
segment never splits at a dot, so `path="/a.b"` steps into the table whose
key is `a.b`. The optional `path=` of `TOMLSetting` places the key in the
tree as a JSON Pointer (RFC 6901), in the same way as in the JSON backend:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.toml_settings as ts


class LocalSettings(adv_settings.Settings):
    host: str = ts.toml_setting(name="host", default="localhost")

    # [app.LocalSettings] port: the dots of the pattern are levels
    port: int = ts.toml_setting(default=8080)

    # [net] -> timeout
    timeout: int = ts.toml_setting(name="timeout", path="/net", default=30)

    region: str = ts.toml_setting(
        name="region", path="/replicas/0", default="eu"
    )

    # a path segment may contain a dot: it names the table key api.internal
    api: str = ts.toml_setting(path="/endpoints/api.internal", default="")
```

A path segment made only of digits indexes an array if the node it steps
into is an array. Otherwise, it names a table key. Arrays follow these
rules:

- An array on a path can grow only by one element at its end. Writing to a
  position further out would leave a gap, so the save refuses it.
- A new array of tables is written as `[[name]]` rows, which is how TOML
  itself represents a list of tables.
- An inline array that the file already contains keeps its inline form when
  it grows.
- A slot that is itself an array stays inline, because only that form can
  hold it.

Each pass reads the file once and writes it back atomically at the end. A
temporary file replaces the old file, and the write copies the permission
mode, so a mode that was set by hand survives a save. The write preserves
the file's format:

- Comments, blank lines, key order, and line endings survive.
- A new key goes to the end of its table.
- A value that the pass leaves unchanged keeps the file's own spelling.
- Keys that the library does not know are kept.

A file in another encoding is rejected with a read error that names the
file. A file that starts with a UTF-8 BOM is also rejected, with a read
error that names the BOM as the cause, because TOML requires plain UTF-8.

??? note "TOML has no null"

    TOML has no null. Saving `None` removes the entry, and the next load
    falls back to the default. A `None` nested inside a container (for
    example, in a `List[Optional[int]]`) has no TOML form either. In that
    case, the save names the member and skips it, because dropping one
    position in an array would change the address of every sibling.

??? note "Deleting a setting"

    Deleting a setting also removes the path tables that it left empty. An
    emptied array element stays as the empty table that it becomes, so its
    siblings keep their positions. An array in which every element is
    emptied is removed as well.

The per-class binding and the key pattern (`ts.toml_source(file=...,
name_pattern=...)`) work exactly as in the JSON family. See the
[JSON section above](#json-files). The same is true for the file declaration
(`ts.toml_file(...)`) and the module declaration
(`TOMLSettingsConfiguration.file_path = for_this_module(...)`).

## YAML files

The YAML backend stores settings in one YAML document, using native YAML
values:

- Dates and timestamps are `date` and `datetime` objects.
- `null` is `None`.
- Integers may contain underscores (`1_000`).
- `true`/`false` are booleans, while `yes`/`no` remain strings, because the
  backend follows YAML 1.2.

The backend uses [ruamel.yaml](https://sourceforge.net/p/ruamel-yaml/) in its
round-trip mode, so the comments, key order, quoting style, and anchors that
a file already contains survive a save. Install it with the `yaml` extra
(`pip install "advexp-settings[yaml]"`). The backend ignores the file
extension and uses whatever path you declare, so an existing `.yml` file
needs no renaming.

A setting's key (the explicit `name=` or the pattern-built one) is a flat
mapping key at the root of the document. A dot in it stays part of the key,
exactly as in the JSON backend. The optional `path=` of `YAMLSetting` places
the key in the tree as a JSON Pointer (RFC 6901), also in the same way as in
the JSON backend:

```python
from datetime import date

import advexp.settings as adv_settings
import advexp.settings.plugins.yaml_settings as ys


class LocalSettings(adv_settings.Settings):
    host: str = ys.yaml_setting(name="host", default="localhost")

    # a flat pattern key: app.LocalSettings.port, dots and all
    port: int = ys.yaml_setting(default=8080)

    # net: -> timeout
    timeout: int = ys.yaml_setting(name="timeout", path="/net", default=30)

    # a sequence position: mirrors -> 0 -> region
    region: str = ys.yaml_setting(
        name="region", path="/mirrors/0", default="eu"
    )

    # stored native: launch_on: 2026-12-01
    launch_on: date = ys.yaml_setting(
        name="launch_on", default=date(2026, 12, 1)
    )
```

A path segment made only of digits indexes a sequence if the node it steps
into is a sequence. Otherwise, it names a mapping key. A missing sequence is
padded with nulls up to the position that the write fills.

Each pass reads the file once and writes it back atomically at the end. A
temporary file replaces the old file, and the write copies the permission
mode, so a mode that was set by hand survives a save. The write preserves
the file's own form: comments, key order, quoting style, anchors, and line
endings (a CRLF file stays CRLF) survive, and so does a UTF-8 BOM at the
start of the file. A new key goes to the end of its container, and keys that
the library does not know are kept. A file created by a save uses the
library's layout: two spaces per mapping level, and sequence dashes indented
by two spaces.

??? note "One document per file, and no unknown tags"

    A `---` separator followed by a second document makes parsing fail,
    because a save must not drop what comes after the separator. A tag that
    the YAML core schema does not recognize also makes parsing fail, so no
    tag can construct arbitrary objects: the settings file is data, not
    code.

??? note "A blank file is an empty document"

    A file that is empty or contains only whitespace is parsed as a document
    with no keys: a load reads nothing from it, and a save starts the file
    over. In some other formats, an empty file is a parse error. Here it is
    not.

??? note "Null is a value"

    `None` is stored as the document's `null` and is read back as `None`,
    which is different from a missing key. This follows the JSON rule, not
    the TOML one. Removing a value is the job of the delete operations.

??? note "Deleting a setting"

    Deleting a setting also removes the path containers that it left empty.
    An emptied sequence element becomes a null, so its siblings keep their
    positions. A sequence in which every element is a null is removed as
    well.

The per-class binding and the key pattern (`ys.yaml_source(file=...,
name_pattern=...)`) work exactly as in the JSON family. See the
[JSON section above](#json-files). The same is true for the file declaration
(`ys.yaml_file(...)`) and the module declaration
(`YAMLSettingsConfiguration.file_path = for_this_module(...)`).

## The dictionary storage

`mapping_source(...)` binds the class to its own dictionary. Plain members
read from this storage, and the class's saves write to it. Import it from
`advexp.settings.plugins.mapping_source`:

```python
import advexp.settings as adv_settings
from advexp.settings.plugins.mapping_source import mapping_source

BASE_DEFAULTS = {"token": "dev-token", "port": 8080}


class AppSettings(
    adv_settings.Settings,
    options=mapping_source(BASE_DEFAULTS),
):
    token: str
```

The dictionary uses member names as keys, and only member names. All
dictionary-based APIs in the library use keys in the same way. An explicit
`name=` and declared `aliases=` have no effect on it. Keys that match no
member are dropped, and a debug record is written. The dictionary is copied
when the class is declared, and every value that is served or stored is a
fresh copy, so changes on either side never reach the other. A save writes
only the member keys and leaves the rest of the dictionary as it is. A
delete removes the key of its member in the same way. This is the same rule
that a shared JSON file follows.

Called without a dictionary, the builder binds an empty storage. The
resolver `mapping_source_for(AppSettings)`, which is imported next to the
builder, returns the storage. Its `set(mapping)` method replaces the whole
dictionary, and `get()` returns a deep copy of the current contents:

```python
from advexp.settings.plugins.mapping_source import mapping_source_for

mapping_source_for(AppSettings).set({"token": "runtime-token"})
AppSettings.load_settings()

snapshot = mapping_source_for(AppSettings).get()
```

A storage that nothing has filled is a silent miss: the load moves on to the
declared defaults. A subclass without its own `mapping_source` shares the
storage of its base class: one dictionary, one `set`, one `get`.

The storage is the class's **only** source binding. If a class declares it
together with another source builder (`json_source(...)`, `env_source(...)`,
and so on), the `class` statement fails, because there is no defined order
between the bindings that a plain member could follow. A family's file
declaration (for example, `json_file(...)`) and the family factory members
can be used next to it without restrictions.

## Mixing backends in one class

Members of one class can come from different backends. Each member is served
by the backend that its attribute selects. The `options=` keyword carries
the binding of every family that needs one: a single binding, or a sequence
when several families need bindings:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js
import advexp.settings.plugins.environment.variables as env


class MixedSettings(
    adv_settings.Settings, options=js.json_file("app-settings.json")
):
    host: str = js.json_setting(name="host", default="localhost")

    # MIXED: the explicit name is the full address, untouched
    mode: str = env.environment_variable_setting(
        name="MIXED", default="production"
    )


# mode comes from the environment, host from the file
MixedSettings.load_settings()

# each member is written by its own backend
MixedSettings.save_settings()
```

Class-level passes still cover the whole class, and members are visited in
declaration order. A storage error that the user must see, such as a corrupt
file or an inaccessible directory, aborts the pass. The class then stays
exactly as it was before the call, and nothing that the pass loaded is
applied.

A load reports each member's problem according to the member's declaration.
This is the same logic that `advexp.configuration` uses:

- **A required member** (declared with `REQUIRED`) has no default to fall
  back to. If its storage provides nothing usable, the pass records an error
  that names the cause, the member, its storage name, and the class. At the
  end, one `AggregateLoadError` carries every failure in its `errors` tuple.
- **Every other member** never makes a load fail by itself. It keeps its
  default, and the same error goes into the report that `load_settings`
  returns.
- **A plain miss is not an error.** For a member with a default, a miss is
  the normal way in which the default gets used.
- **The report** is an empty tuple if every member loaded cleanly.
- **If a required member failed and an optional member fell back in the same
  run,** the abort error also carries the fallbacks, kept separately in its
  `fallbacks` tuple.

The single-setting form reports in the same way. `load_setting(...)` returns
this member's row of the report:

- `None`, if the member loaded cleanly or took its default through a plain
  miss;
- the same entry that a class pass would collect, if the member fell back to
  its default because of a problem.

A `REQUIRED` member raises an error instead. A single member has no
aggregate, so you see the member's own error, for example a source failure
or a read of a member that was never loaded.

A load builds the new state of the class from scratch and applies it in one
step. A finished pass fully determines the state: every member gets either
the value that its storages produced or its declared default. A value from
an earlier pass never survives if the current storages hold nothing for that
member. A failed pass changes nothing: if a pass ends in an abort or a
storage error is raised, the class stays exactly as it was before the call.
No values are partly applied, and no defaults are applied from the failed
run. See [Validation](validation.md) for the full description.

## Writing your own

A custom backend is built on the contracts of the plugin API: an attribute,
a serializer, and a plugin class. See [Extending](extending.md) and the
`samples/settings/custom_backend.py` sample, which contains a complete
backend built on the public contracts.
