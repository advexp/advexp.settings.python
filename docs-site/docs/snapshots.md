# Snapshots

A settings class holds a single, shared set of values (a singleton). To work
with an independent copy, take a snapshot, and apply it back when you are
done. A snapshot is either a dict or a detached instance of the settings
class:

```python
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class AppSettings(
    adv_settings.Settings, options=js.json_source(file="app-settings.json")
):
    mode: str = "production"


# deep copy of all values, keyed by member name
snapshot = AppSettings.to_dict()

# applies the same type conversion as a load; saving is a separate step
AppSettings.update_from_dict(snapshot)

# a detached AppSettings instance with its own copy
state = AppSettings.to_object()

# changes affect only the snapshot
state.mode = "debug"

# same conversion and copying as the dict form
AppSettings.update_from_object(state)
```

The object form uses the declared member names as attribute names. If you
rename a setting, every leftover `state.old_name` access is reported by your
type checker (and raises `AttributeError` at runtime). With a dict, an
outdated key can go unnoticed.

Deleting a member on the object form removes its own value from the snapshot:
the next read of that member serves its declared default, and the class keeps
its stored value. A second delete of the same member raises `AttributeError`,
because the snapshot holds no own value for it anymore. On a plain instance
the delete is refused with a `TypeError` instead: an instance shares the
class storage, and removing a stored value is the job of `delete_setting(...)`
on the class.

Resetting is a separate operation. `reset_settings()` resets every member to
its declared default and does not touch any storage. `reset_setting(...)`
resets a single member in the same way. Like the other single-setting
operations, it addresses the member by name or by a getter lambda
(`SettingRef`).

A member declared `REQUIRED` has no default to go back to, so both reset
forms clear its current value instead. The member then returns to the
never-loaded state, in which reading it raises an error. The delete
operations have the same effect on such a member: after `delete_settings()`
or `delete_setting(...)` removes the member's storage entries, a `REQUIRED`
member becomes unset instead of keeping the deleted value.

## Required members in a snapshot

`to_dict()` reads every member, and a required member without a value — a
class that was never loaded, a load that failed, or a reset that cleared it
— fails the snapshot with that read error. When you need the snapshot of
such a class anyway, the `missing=` mode says what the member becomes
instead:

```python
from advexp.settings import MISSING_NONE, MISSING_SKIP

# every required member without a value is exported as None
exported = AppSettings.to_dict(missing=MISSING_NONE)

# such members are left out instead
partial = AppSettings.to_dict(missing=MISSING_SKIP)
```

`MISSING_NONE` keeps the dict complete: every member name is present, and a
model with optional fields accepts the result. `MISSING_SKIP` returns only
the members that have a value. The constants are exported by the package
root; an unknown mode raises a `ValueError` that lists the accepted ones.

Applying a dict back (`update_from_dict` and `update_from_object`) stores a
`None` even for a member whose annotation does not include it — the value
is kept, and a warning names the member on the package's logging channel,
so a mistaken key surfaces in the log.

Advexp.Configuration has the same snapshots, `to_dict()` and `to_object()`,
but they are read-only there, like everything else in that package:

- The dict form is a frozen mapping. Writing to its items raises
  `TypeError`. To get a mutable copy, wrap it in `dict(...)`.
- The object form does not accept attribute writes either.
- `to_dict()` takes the same `missing=` modes, with the same constants
  exported by the package root.
- There is no way to apply a snapshot back. New values arrive only when you
  call `load_configuration()` again after the sources change.
