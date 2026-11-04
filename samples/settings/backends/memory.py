"""
A minimal local backend that is shared by the samples. It is the smallest
thing that can serve the passes of the library: an attribute, a serializer,
and a plugin object, registered on the public contracts of
``advexp.settings.plugin_api``.

The full pattern (backend parameters, behavior driven by metadata, and
dynamic settings) is built in ``samples/settings/custom_backend.py``.
Importing this module is what enables the backend, in the same way as
importing the module of a bundled plugin enables it: there are no
registration calls at the place of use.
"""

from copy import deepcopy
from typing import Any, Callable, Mapping, Optional

import advexp.settings as adv_settings
import advexp.settings.plugin_api as api


class MemorySetting(api.SettingsAttribute):
    """Setting attribute: the value lives in this process's dictionary."""


def memory_setting(
    *,
    name: Optional[str] = None,
    default: Any = api.NO_DEFAULT,
    metadata: Optional[Mapping[str, Any]] = None,
    gt: Any = None,
    ge: Any = None,
    lt: Any = None,
    le: Any = None,
    eq: Any = None,
    ne: Any = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    regex: Optional[str] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    when: Any = None,
) -> Any:
    """Declare a setting on this backend. This is the type-checker-friendly
    spelling of ``MemorySetting``.

    It is the same attribute with the same keyword parameters. Only the spelling
    differs: type checkers cannot see that the settings metaclass replaces an
    assigned attribute instance with a value descriptor, so they report a type
    mismatch. They accept a plain function that returns ``Any``.
    """
    return MemorySetting(
        name=name,
        default=default,
        metadata=metadata,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        eq=eq,
        ne=ne,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        validator=validator,
        when=when,
    )


class MemoryStorage:
    """The storage of the backend, which is external to the serializer.

    Like a settings file or ``os.environ`` in real backends, the storage
    outlives the serializer instances that the pipeline creates for each pass.
    This is why it is a class-level dict: one storage that is shared by every
    pass of the backend.
    """

    data: dict = {}


class MemorySerializer(api.SettingsBaseSerializer):
    """In-memory backend: values are keyed by the full setting name and
    deep-copied at both boundaries (the class storage and the storage of the
    backend must not share objects).
    """

    # -- ISettingsSerializer ---------------------------------------------------

    def load(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> Any:
        value = MemoryStorage.data.get(setting_name, api.NOT_FOUND)
        return value if value is api.NOT_FOUND else deepcopy(value)

    def save(
        self,
        setting_name: str,
        attr: Optional[api.ISettingAttribute],
        value: Any,
    ) -> None:
        # per the save contract, None is a legitimate value and stays stored;
        # a backend with no null form (env vars, say) would drop the entry
        MemoryStorage.data[setting_name] = deepcopy(value)

    def delete(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> None:
        MemoryStorage.data.pop(setting_name, None)

    def contains(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> bool:
        return setting_name in MemoryStorage.data


class MemoryPlugin(api.SettingsBasePlugin):
    """Plugin object; the base's declarative binding registers the pair."""

    binding = api.AttributeSerializerBinding(MemorySetting, MemorySerializer)

    @property
    def plugin_name(self) -> str:
        return "InMemory"


# importing the module enables the backend, the bundled plugins' way
adv_settings.LibraryConfiguration.register_settings_plugin(MemoryPlugin)
