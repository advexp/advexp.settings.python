# Setting metadata

You can attach extra information to settings and classes: labels for a UI, a
secret flag, a config version, and so on. Declare it where the setting or
the class is defined:

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

## Changing metadata at runtime

`set_setting_metadata` and `set_class_metadata` let you override, add, or
remove entries at runtime.

- A declared entry is only the **initial state**. If you delete it at
  runtime, it does not come back.
- The declared mapping is copied once, when the class is created. Changing
  it after the `class` statement has no effect. Make live changes through
  the runtime functions.
- Values can be arbitrary objects. The library stores deep copies of them
  and returns deep copies when you read them, so a change made to one copy
  never affects another.

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
