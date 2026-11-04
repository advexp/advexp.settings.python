# Validation

Besides type conversion, a member can declare **value constraints**. They
are keyword parameters of the setting declaration:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class ServerSettings(adv_settings.Settings):
    port: int = js.json_setting(name="port", default=8080, ge=1, le=65535)

    # the pattern is unanchored: you place ^ and $ yourself
    host: str = js.json_setting(
        default="localhost", min_length=1, regex=r"^\w+$"
    )

    mode: str = js.json_setting(
        name="mode", default="primary", ne="backup"
    )
```

- **Ordering bounds** (`gt`, `ge`, `lt`, `le`): greater than, greater than
  or equal to, less than, and less than or equal to. The bound can be any
  value that the member's value can be compared with: numbers, dates, or
  your own comparable types. Each of these parameters also accepts a
  reference to another member. See
  [Rules across members](#rules-across-members).
- **Equality** (`eq`, `ne`): the value must equal the bound (`eq`) or must
  not equal it (`ne`). A member reference works here too.
- **Length** (`min_length`, `max_length`): bounds on `len(value)`. They work
  for strings and collections.
- **`regex`**: an unanchored pattern that a `str` value must match. Add `^`
  and `$` yourself if you need them.
- **`validator`**: a callable that receives the value and returns whether it
  passes. If the callable raises an exception, the exception propagates
  unchanged, because this is a bug in the validator, not a property of the
  value. During a load, the crash first writes an `ERROR` record to the
  package's log, so the bug stays visible even if the application swallows
  the traceback.
- **`when`**: a reference to another member that gates this member. While the
  referenced member is falsy, none of this member's constraints apply.

`None` passes the ordering, length, and `regex` constraints without any
message, because it is the value of an unset `Optional` member. However,
`None` does take part in `eq` and `ne`. If a constraint cannot be applied to
a value, the library reports a violation instead of crashing. Examples are
`gt=0` on a value that cannot be compared, `min_length=` on a value that has
no length, and `regex=` on a value that is not a string.

A member declared without `default=` serves `None` until a value arrives.
This placeholder `None` is checked at class creation, like a declared
default. If the constraints reject it (for example, `eq=` refuses `None`, or
a `validator` returns false for `None`), the `class` statement fails. Such a
member could never hold a valid value without an assignment, so declare it
with `REQUIRED` instead. A `validator` on a member declared without
`default=` must also be able to receive `None`.

## Where constraints are checked

- **Declared defaults** are checked at class creation, after conversion. A
  default that violates a constraint makes the `class` statement fail with a
  `TypeError` that lists every offending member. The `None` that a member
  without a default serves is checked in the same way.
- **An assignment** such as `ServerSettings.port = 70000` raises
  `SettingValidationError` (a subclass of `ValueError`, importable from
  `advexp.settings`). The value is not stored in the class. This also holds
  for assignments on instances and on `to_object()` snapshots.
  Advexp.Configuration has no assignment at all, because its values are
  read-only. It reports violations through the same load error mechanisms
  that both packages share. See
  [Configuration](configuration/getting-started.md#validation).
- **`update_from_dict` and `update_from_object`** raise an error before
  anything is applied. A rejected update leaves every value untouched.
- **A load** is lenient for optional members. A stored value that
  violates a constraint is treated like a value that cannot be converted: a
  warning is logged, the default is used, and the fallback is added to the
  report that `load_settings` returns. For a `REQUIRED` member, the
  violation becomes an entry in the abort error instead.
- **A save** checks the whole class first. If there is a violation, it
  raises `SettingValidationError` and writes nothing. `save_setting`, which
  saves a single setting, is the narrow path. It runs no cross-member
  checks, so a member whose rule involves another member is written like any
  other member. The member is skipped, and the failure is logged, only if
  its own storage fails.

The declaration itself is also validated:

- A `regex` that does not compile fails with `ValueError`.
- A `validator` that is not callable fails with `TypeError`.
- Combining ordering bounds with `min_length`, `max_length`, or `regex` also
  fails with `TypeError`.

## Rules across members

A comparison bound can refer to **another member of the same class** instead
of a fixed value. To do this, pass the attribute that was declared earlier
in the class body. Whenever the whole class is checked at once, the
comparison uses the current value of that member.

The `when=` parameter gates all constraints of a member. While the
referenced member is falsy, none of this member's constraints apply.

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class NetSettings(adv_settings.Settings):
    min_port: int = js.json_setting(default=1024)

    # compared with min_port
    max_port: int = js.json_setting(default=65535, ge=min_port)

    ssl: bool = js.json_setting(default=False)

    # eq=443 applies only when ssl is true
    port: int = js.json_setting(default=80, eq=443, when=ssl)
```

Some rules cannot be written as comparisons. Examples are conditional
requirements, "at least one of", and invariants over several members. Put
such rules in the class hook `__validate__`:

- The hook runs wherever the cross-member checks run, with one exception: it
  does not run at the `class` statement. At class creation, only the
  declared defaults are checked, and only against the comparison rules.
- The hook always runs on a fully built settings object.
- It returns a dictionary that maps a member name to a description of the
  problem. An empty dictionary means that the class is valid.
- The hook only reads and reports. It must not try to fix values, because
  fixing is the job of the load pass. When the hook reports a problem, the
  load pass resets the member that the problem names. If that member is
  already at its default, the reset changes nothing, and the load aborts.
  A load never finishes in a state that the hook rejects.

An exception raised in the hook propagates unchanged. This is the same rule
as for a custom `validator`: it is a bug in your code, not a property of the
values.

There is one exception to this rule. If the hook reads a required member
that has no value, this is treated as a finding, not as a crash. The member
is reported at every checkpoint where the hook runs: it becomes an entry in
the load abort, next to the member's own "missing value" error, or a problem
line in `SettingValidationError` at the strict checkpoints. As a result, the
hook can read the whole object without guarding against a member that its
source never provided.

```python
from typing import Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class NetSettings(adv_settings.Settings):
    mode: str = js.json_setting(default="dev")

    ssl: Optional[str] = js.json_setting(default=None)

    def __validate__(self) -> dict:
        if self.mode == "prod" and self.ssl is None:
            return {"ssl": "ssl is required when mode is 'prod'"}
        return {}
```

The checks run at five checkpoints:

1. **Class creation.** Declared defaults must satisfy the comparison rules.
   A violation makes the `class` statement fail with a `TypeError` that
   lists every finding. This is what makes the load fallback safe: the state
   in which every member has its default is consistent by construction. The
   hook does **not** run here, because it needs a fully built object.
2. **A load.** The check is lenient, like a check of a single member's
   constraints. The members that take part in a violated rule fall back to
   their defaults, and a warning is logged. These are the member itself, the
   members it references, and the `when=` member. If no reset can fix a
   violation, the load aborts. Examples are a hook finding that names a
   member that is already at its default, and a rule that involves a
   required member holding its loaded value. As a result, a completed load
   is always consistent: either the state is valid, or the load did not
   complete.
3. **`update_from_dict` and `update_from_object`.** The check is strict.
   The new values are checked next to the current values of the other
   members, so a rule can involve members the update does not touch. A
   violation raises `SettingValidationError`, and the whole update is
   rejected.
4. **A save.** The check is strict. A violation raises an error, and nothing
   is written.
5. **`validate_settings()`.** This is the manual strict check. It collects
   every finding for every member (field constraints, member rules, and the
   hook) into one `SettingValidationError`. The `problems` attribute of the
   error is a dictionary that maps each member name to a list of problems.
   The check does not change anything.

A single assignment **never** runs the cross-member checks. When you change
a pair of related members one by one, the class passes through an
intermediate state that may violate a rule. Therefore, running the check is
your responsibility: call `validate_settings()` after the series of
assignments, or let the next update or save do it.

Messages about member rules name both members and keep secret values masked.
Each finding is attributed to the member that carries the rule.

A member that has no value yet (nothing stored and no default) is skipped by
the field checks at the runtime checkpoints. At class creation, the library
has already checked the placeholder `None` against the member's own
constraints. A rule that refers to such a member is not checked until the
member has a value.

Advexp.Configuration applies the same rules at its own two points: class
creation and the end of a load. Violations are reported through the same
load error mechanisms as the other load errors: as an entry in the abort
error for a required member, and as an entry in the returned report for an
optional member. See
[Configuration](configuration/getting-started.md#validation).
