# Setting metadata

You can attach extra information to members and classes in both packages:
labels for a UI, a secret flag, a config version, and so on. Declare it where
the member or the class is defined:

- `metadata=` is a keyword-only parameter of the base attribute. Every
  factory (`json_setting` and the others) accepts it, and a custom attribute
  accepts it when its subclass passes the parameter on to the base.
- `class_metadata` is a reserved class-level name that holds the metadata of
  the class itself.

```python
from typing import Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class AppSettings(adv_settings.Settings):
    class_metadata = {"config-version": 2}

    # metadata is the general channel: for example, labels that a UI reads
    mode: str = js.json_setting(
        default="production", metadata={"ui-label": "Mode"}
    )

    api_token: Optional[str] = js.json_setting(
        default=None, metadata={"secret": True}
    )
```

Both kinds of metadata (for members and for the class) can be read through
the metadata API as soon as the class exists. No `set_*` call is needed. A UI
builder or a schema generator can read this static view at any time, without
running any application code first:

```python
# "Mode"
AppSettings.get_setting_metadata("mode", "ui-label")

# {"config-version": 2}
AppSettings.get_class_all_metadata()
```

The member is addressed by its name in the class body (`mode` above) or by
a getter lambda for it — the two spellings of `SettingRef`, which the root
of each package exports. The storage spellings — the attribute's `name=`,
its aliases, and `path=` — belong to the backends alone, and a metadata
operation does not recognize them: a name that the class does not declare
raises `KeyError`.

A missing entry follows the dictionary rule, on both the member and the
class level: without `default=` the read raises `KeyError` that lists the
metadata the member or the class carries; with `default=`, the fallback is
served. A stored `None` is a value like any other — `contains_*` is what
tells it from a missing entry.

## Both packages carry the same API

A configuration class has the same twelve metadata methods. The declarations
open the channel there as well, and the methods read and write it the same
way:

```python
import advexp.configuration as adv_config


class AppConfig(adv_config.Configuration):
    class_metadata = {"config-version": 2}

    mode: str = adv_config.sourceless_setting(
        default="production", metadata={"ui-label": "Mode"}
    )


# "Mode"
AppConfig.get_setting_metadata("mode", "ui-label")
```

The read-only contract of a configuration class covers the values and the
sources. Metadata is a separate channel, and no pass over the values ever
touches it — see [Metadata and the value passes](#metadata-and-the-value-passes)
below.

## Changing metadata at runtime

`set_setting_metadata` and `set_class_metadata` store entries at runtime:
writing an existing key overrides it, writing a new key adds it. Removing
entries is the job of the `delete_*` methods.

- A declared entry is only the **initial state**. If you delete it at
  runtime, it does not come back.
- The declared mapping is copied once, when the class is created. Changing
  it after the `class` statement has no effect. Make live changes through
  the runtime functions.
- Values can be arbitrary objects. The library stores deep copies of them
  and returns deep copies when you read them, so a change made to one copy
  never affects another.
- Two whole-bucket forms complete the runtime layer:
  `delete_setting_all_metadata` removes every own entry of one member at
  once, and `delete_class_all_metadata` clears the own class-level storage
  of the class. Both touch only the class's own entries; the entries of the
  base classes stay visible.
- The class-level snapshot (`get_class_all_metadata`) lists the open channel
  alone. The machinery keeps its own service records — the keys of the
  reserved `__ADVEXP_SETTINGS_BASE_` prefix and the per-class entries of
  registered families, the file bindings and the source chain among them —
  in the same storage: the snapshot hides them, while their exact names
  still address them for reads, writes, and deletes.
- Three reset forms restore the declared state:
  `reset_setting_all_metadata` returns the metadata of one member to its
  `metadata=` declaration, `reset_all_settings_metadata` does the same for
  every member of the class, and `reset_class_all_metadata` returns the
  class-level storage to the state of the end of the `class` statement.
  Entries added at runtime are dropped; declared entries that were deleted
  or overridden at runtime come back. The restored state is the snapshot
  taken when the class was created, so changing the declared mappings after
  the `class` statement never reaches a reset. The service records are part
  of the declared state, and they return with the rest. These resets touch
  the metadata channel alone — they are distinct from the value passes
  described in the next section.

## Dynamic collections

A dynamic collection keeps the metadata of its entries on the plugin, not on
the class. The six methods are the same as the member channel of the class,
spelled on the plugin handle, and both packages carry them: the writing
collection of `advexp.settings` and the reading snapshot of
`advexp.configuration` (see [Dynamic settings](dynamic-settings.md)).

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_dynamic_settings as jds


class LocalSettings(
    adv_settings.Settings,
    options=jds.json_source(file="app-settings.json"),
):
    host: str = "localhost"


plugin = LocalSettings.get_plugin(jds.JSONDynamicSettingsPlugin)

# a dynamic entry exists while it has a value
plugin.set_setting("dark_mode", True)

# the entries of the collection carry their own runtime annotations
plugin.set_setting_metadata("dark_mode", "ui-hint", "switch")
# "switch"
plugin.get_setting_metadata("dark_mode", "ui-hint")
```

- A name must be one that the collection holds: a dynamic entry exists
  exactly while it has a value, and metadata for anything else could only
  hide a typo. A miss raises `KeyError` that names the collection.
- The dictionary rule of this page applies here as well: without `default=`
  the read raises `KeyError` that lists the available metadata, and
  `contains_setting_metadata` tells a missing entry from a stored `None`.
- The metadata is the runtime state of the collection alone. It never goes
  to the storage, and the load of the collection — `load_settings` on the
  writing plugin, `load_configuration` on the reading one — clears it with
  the rebuild.
- On the reading side the annotations are the reader's own: the writer's
  metadata is the state of the writing process, and it never crosses the
  file.

## Metadata and the value passes

Metadata lives only in the memory of the class. The passes over the values —
load, save, delete, and reset — never reach it, in either package.

- `load_settings()` and `load_configuration()` rebuild the values of the
  members alone. The metadata storages are not recreated: declared entries
  remain, entries added at runtime remain, an entry that you deleted stays
  deleted, and an entry that you overrode at runtime stays overridden.
- `save_settings()` writes the values into the storages, nothing else: a
  saved file carries no metadata.
- `delete_settings()` removes the stored values and puts the members back to
  their defaults. The metadata of the members and the class metadata stay
  exactly as they were.
- `reset_settings()` leaves the metadata channel alone in the same way.
- Removing metadata is the job of the channel's own methods:
  `delete_setting_metadata`, `delete_setting_all_metadata`, and their
  class-level twins.

Of these passes, a configuration class has only the load — the read-only
contract has no save, delete, or reset. The independence itself is the
behavior of the shared base, so one rule covers both packages.

The dynamic collection's own load is the one pass that does reach metadata:
it rebuilds the entries and clears their runtime annotations, as the
[Dynamic collections](#dynamic-collections) section above says.

## Inheritance of metadata

Member metadata and class metadata are looked up in the same way as
attributes: through a `ChainMap` built along the inheritance chain.

- Each class holds its own entries. These are the entries declared in its
  body, plus anything written into it at runtime.
- Each key resolves to the entry of the most derived class that declares it.
- A runtime write into a base class is visible in its subclasses, whether
  they were created before or after the write. A write into a subclass
  never affects its base classes.
- Deleting (`delete_class_metadata`, `delete_setting_metadata`) removes only
  the class's own entries. It returns whether such an entry existed. If a
  base class has an entry with the same key, that entry becomes visible
  again, just as deleting an attribute from a subclass makes the lookup fall
  back to the attribute of the base class.
- A member's chain stops at the class that declares the member. If a
  subclass declares the member again, the member's metadata comes only from
  the new declaration. It is not merged key by key with the old one. A
  runtime write, by contrast, adds keys on top of the inherited ones without
  removing them.
- If a declaration is not a mapping, the `class` statement fails.

## Metadata versus backend parameters

`metadata=` is the **general** channel of the core. Backend parameters such
as `path=` are different: each one is declared and read by the
attribute/serializer pair of a single backend (see
[Extending](extending.md)). Metadata, in contrast, can be read by any
consumer through the class API, or through the context that a serializer
receives. Examples of such consumers are a serializer that reacts at
runtime (`redact-on-save`), a UI, and a schema generator.
