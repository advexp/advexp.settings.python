# Value types

The following types work out of the box:

- `bool`, `int`, `float`, `complex`, `str`, and `bytes`.
- Enums, which are stored by member name.
- `datetime`, `date`, `time`, and `timedelta`, which are stored in ISO 8601
  format. Two backends are exceptions:
  - The TOML backend stores `datetime`, `date`, and `time` in the native
    form that TOML itself uses.
  - The YAML backend stores `datetime` and `date` in their native form in
    the same way. It stores `time` in ISO format, because YAML has no
    scalar type for time.
- `Decimal`, `Fraction`, `UUID`, `Path`, and `ZoneInfo`.
- The objects of the `ipaddress` module.
- `Optional`, `Union`, and `Literal`.
- `list`, `set`, `frozenset`, `tuple`, and `dict` with typed items, nested
  to any depth (including their `collections.abc` forms).

## Secret values

`SecretStr` and `SecretBytes` (both packages of the family export them) can
also be saved and loaded back unchanged. A loaded value is wrapped, so when
it is printed, written to a log record, or included in an error message, it
appears as `'**********'`. The only way to get the real value is to call
`get_secret_value()`.

Constraints are checked against the real value, but the error messages still
show the mask. In the storage, the value is kept in plain form: saving
unwraps it before it reaches the serializers.

## Defaults are converted too

Declared defaults go through the same conversion when the class is created.
For example, `default="8080"` on an `int` member serves `8080` before any
storage access, and `default={"host": "h"}` on a dataclass member serves an
instance of that dataclass. A mutable default is safe to declare: the
library always hands out a deep copy, so `default=[]` or `default={...}` is
never shared with the class storage or with a backend.

A default that cannot be converted makes the `class` statement fail with a
`TypeError` that lists every offending member. Examples are a malformed
date, an enum member name that does not exist, and `True` on an `int` member
(the conversion does not treat `bool` as `int`).

Annotations that are outside the conversion rules (your own classes, `Any`)
are not converted. Their defaults are checked with `isinstance` instead. The
check also looks inside containers: every element of a declared
`List`/`Set`/`Tuple`, and every key and value of a `Dict`, is checked against
its annotated type. `None` is a valid default for any annotation.

## `None` as a value

`None` is a legitimate value. The JSON backend stores it as `null`. A key
with the value `null` is loaded back as `None`. This is different from a
missing key, which makes the member fall back to its default.

The YAML backend works like the JSON one: it stores `None` as the document's
`null` and reads it back as `None`.

Some storages have no form for null: string-based storages such as
environment variables, and the TOML backend. In these storages, saving
`None` removes the entry, and the next load falls back to the default. To
remove a setting explicitly in any backend, use `delete_setting`.

A `None` inside a container has no TOML form at all. The TOML backend names
the member and skips it, because dropping one position in an array would
change the address of every sibling.

## Your own types: dataclasses

For your own types, use dataclasses. A dataclass value is stored as a plain
object made of its fields:

- a JSON object in the JSON backend;
- a TOML table in the TOML backend;
- a YAML mapping in the YAML backend;
- a JSON string in string-based backends, such as environment variables.

Loading rebuilds the object from the annotation, and each field is converted
according to its own type. Nesting works inside `Optional`, `List`, `Dict`,
`Tuple`, and other dataclasses:

```python
from dataclasses import dataclass
from typing import List, Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


@dataclass
class Proxy:
    host: str
    port: int = 3128


class NetworkSettings(
    adv_settings.Settings,
    options=js.json_source(file="app-settings.json"),
):
    proxy: Optional[Proxy] = js.json_setting(name="proxy", default=None)

    mirrors: List[Proxy] = js.json_setting(name="mirrors", default=[])


NetworkSettings.proxy = Proxy("proxy.example", 8080)
NetworkSettings.mirrors = [
    Proxy("mirror-a.example"),
    Proxy("mirror-b.example", 8080),
]

# "proxy": {"host": "proxy.example", "port": 8080}, ...
NetworkSettings.save_settings()

NetworkSettings.load_settings()

# Proxy(host='proxy.example', port=8080)
NetworkSettings.proxy
```

Fields that are missing in the storage take the defaults of the dataclass.
Stored keys that the dataclass no longer declares are ignored. As a result,
previously stored objects remain loadable when the dataclass changes.

If a value cannot be converted during a load (for example, a required field
is missing or a date is malformed), a member with a default falls back to
it: the problem goes into the load report, and the log carries a warning.
A member without a default fails the load with `AggregateLoadError`.
`update_from_dict` behaves differently: it raises `ValueError` and applies
nothing.
