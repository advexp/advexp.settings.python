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

Resetting is a separate operation. `reset_settings()` resets every member to
its declared default and does not touch any storage. `reset_setting(...)`
resets a single member in the same way. Like the other single-setting
operations, it accepts either the member name or a getter lambda.

A member declared `REQUIRED` has no default to go back to, so both reset
forms clear its current value instead. The member then returns to the
never-loaded state, in which reading it raises an error. The delete
operations have the same effect on such a member: after `delete_settings()`
or `delete_setting(...)` removes the member's storage entries, a `REQUIRED`
member becomes unset instead of keeping the deleted value.

Advexp.Configuration has the same snapshots, `to_dict()` and `to_object()`,
but they are read-only there, like everything else in that package:

- The dict form is a frozen mapping. Writing to its items raises
  `TypeError`. To get a mutable copy, wrap it in `dict(...)`.
- The object form does not accept attribute writes either.
- There is no way to apply a snapshot back. New values arrive only when you
  call `load_configuration()` again after the sources change.
