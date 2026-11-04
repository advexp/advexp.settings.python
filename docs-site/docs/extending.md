# Extending

There are two ways to extend the library, and together they cover most
needs: custom attribute parameters that the bundled storages react to, and
fully custom backends built on the plugin API contracts.

## Custom attribute parameters

You can add your own parameters to the bundled plugins, and the storage can
react to them. To do this, declare the parameters on a subclass of the
attribute — a bundled one, such as the `JSONSetting` below, or the base
`SettingsAttribute` from `plugin_api`, which the `custom_backend.py` sample
builds on. The custom parameters follow the standard `path=` spelling:
keyword-only arguments of `__init__`, with the subclass passing the standard
arguments on to the base class. Then subclass the serializer so that it
reacts to the new parameters, and register the attribute and the serializer
as a pair:

```python
from typing import Any

import advexp.settings as adv_settings
import advexp.settings.plugin_api as api
import advexp.settings.plugins.json_settings as js


class SectionedJSONSetting(js.JSONSetting):
    def __init__(
        self,
        *,
        name=None,
        default=api.NO_DEFAULT,
        path=None,
        section=None,
        metadata=None,
    ):
        super().__init__(
            name=name, default=default, path=path, metadata=metadata
        )
        self.section = section


def sectioned_json_setting(
    *,
    name=None,
    default=api.NO_DEFAULT,
    path=None,
    section=None,
    metadata=None,
) -> Any:
    return SectionedJSONSetting(
        name=name,
        default=default,
        path=path,
        section=section,
        metadata=metadata,
    )


class SectionedJSONSerializer(js.JSONSettingsSerializer):
    def _setting_segments(self, setting_name, attr):
        setting = self.attribute_of(attr, SectionedJSONSetting)
        if setting is not None and setting.section is not None:
            # one level deeper
            return [setting.section, setting_name]

        # otherwise, the standard placement: path= and dynamic entries
        return super()._setting_segments(setting_name, attr)


adv_settings.LibraryConfiguration.register_settings_attribute(
    SectionedJSONSetting, SectionedJSONSerializer
)
```

The companion factory function lets declarations such as `host: str = ...`
pass type checking. Assigning an attribute instance to an annotated member
is valid Python, and the settings metaclass replaces it with a value
descriptor. However, type checkers cannot see this replacement, so they
report a type error for the assignment. A factory that returns `Any` is
accepted by all type checkers.

!!! warning "Name-mangled internals"

    Only the methods of the serializer are extension points. The internal
    machinery behind them uses name mangling, so a subclass cannot access
    it.

    Placement (where a key is stored) is controlled by the protected hook
    `_setting_segments(setting_name, attr)`. Subclasses are meant to
    override it, and outside code must not call it. Call `super()` to get
    the standard placement, which handles the `path=` segments and the
    dynamic entries in their section. The base class refuses to place a key
    inside the dynamic settings section. If an override does not call
    `super()`, it is responsible for making sure that it never uses that
    section.

## Custom backends

You can write a backend of your own, for example for a database, a remote
service, or another file format. A backend is a plugin that consists of
three parts, built on the contracts from `advexp.settings.plugin_api`:

- a setting attribute: the class whose instances are assigned to members;
- a serializer: it writes values to the storage and reads them back;
- a plugin object: the handle that user code obtains through
  `Settings.get_plugin`.

The [custom_backend.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/custom_backend.py)
sample in the repository is a complete working backend in a single file,
built on these contracts. It shows how to:

- split the storage using an attribute parameter;
- react to metadata through the `context` of the serializer;
- support dynamic settings on the same storage.

Use it as a starting template.

The [settings_api.py](https://github.com/advexp/advexp.settings.python/blob/main/samples/settings/settings_api.py)
sample is a live tour of the application-facing API, running on a minimal
hand-made backend.
