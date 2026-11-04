"""
Example: the runtime metadata of dynamic settings. The JSON collection reacts
to its own metadata parameters.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/json_dynamic_metadata.py

The recipe in one step: the dynamic collection of one settings class is
served by a subclass of the stock JSON serializer, and the application
drives it through two metadata channels without touching a single
declaration.

- Entry metadata (``set_setting_metadata`` on the dynamic plugin) marks one
  runtime name.
- Class metadata (:meth:`~adv_settings.Settings.set_class_metadata`)
  switches the whole collection.

There is only one reaction: a marked entry stores its value base64-encoded
under a ``$b64:`` tag. This is plain unreadable text at rest, not
encryption.

The serializer reads the metadata through
:meth:`~adv_settings.SettingsContext.get_dynamic_setting_name`. Storage
calls carry the full dynamic name (the ``D`` prefix plus the class part of
the pattern), while the metadata of the collection is keyed by the plain
name that the application knows. The context converts one into the other.

The storage form carries its own flag on purpose. Entry metadata is the
runtime state of the collection (loads reset it, and deletes take it away
with the entry), so a load cannot rely on the mark. The tag decides on
read, and the marks decide only on write.

The custom serializer needs a registry slot of its own, and the slot of the
dynamic side is the pin of the plugin. The stock plugin pins
``api.DynamicSettingAttribute[JSONSetting]``, and that slot belongs to the
stock serializer (a second claim under it is a conflict, not an override).
The plugin of this sample therefore subclasses ``JSONDynamicSettingsPlugin``
and pins its binding again, under
``api.DynamicSettingAttribute[MyJSONSetting]``, where ``MyJSONSetting`` is a
bare subclass of ``JSONSetting`` that serves as the slot marker. The
application then reaches its collection through its own plugin class:
``get_plugin(JSONDynamicSettingsPlugin)`` would return the stock plugin,
which is a different instance with a different, empty collection.

The static counterpart of this layer (member and class metadata of declared
members) is shown in ``samples/settings/json_custom_metadata.py``. The CRUD
surface of the metadata of the collection is shown in
``samples/settings/json_dynamic_settings.py``.

The settings class declares nothing: the dynamic side needs no declared
member. The class anchors the collection. With no static side to share a
file with, the collection writes to a file of its own
(``JSONDynamicSettingsConfiguration.file_path``; the module default of the
static side would serve as the fallback). The class-level passes
(``load_settings`` and similar calls) have no member to touch on an empty
class, so the methods of the plugin drive the storage alone.

Every demonstration writes its own file next to this script, so each state
stays available for inspection after the run, instead of being overwritten
by the next save. (A real application points the configuration at one
location once, at startup, and keeps it there. A pass resolves its file when
it runs, which is what makes the re-pointing work.) The files are removed at
startup, so every run starts from a clean slate. The reload demonstration
reads the file of the demonstration before it.
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import advexp.settings as adv_settings
import advexp.settings.plugin_api as api
import advexp.settings.plugins.json_dynamic_settings as jds
import advexp.settings.plugins.json_settings as js


class MyJSONSetting(js.JSONSetting):
    """The registry slot of the custom serializer of the dynamic side, and nothing
    else.

    The pin ``api.DynamicSettingAttribute[MyJSONSetting]`` namespaces this bare
    subclass into a registry identity of its own. The binding of the plugin of
    this sample therefore never touches the stock registrations (neither the one
    of ``JSONSetting`` nor the pin of the stock plugin). The subclass declares no
    parameters: its construction and behavior are those of a plain
    ``JSONSetting``.
    """


class MyDynamicJSONSerializer(js.JSONSettingsSerializer):
    """The stock JSON serializer, extended to react to the metadata of the dynamic
    collection.

    Dynamic entries reach a serializer as calls with ``attr=None``. Everything
    else keeps the stock behavior through the ``super()`` calls.

    Two channels switch the single reaction on, and both are read through the
    context that the pass hands over:

    - the ``obfuscate`` entry metadata (kept by the collection of the plugin and
      keyed by the plain name);
    - the ``obfuscate_all`` class metadata (kept by the context, and it covers
      the whole collection at once).
    """

    _TAG = "$b64:"

    def _obfuscates(self, setting_name: str) -> bool:
        # entry metadata lives on the plugin's collection, keyed by the
        # plain name; the context strips it out of the full storage name
        # (this serializer passes itself, so its delimiter wish applies)
        context = self.context
        plain_name = context.get_dynamic_setting_name(setting_name, self)
        if plain_name is not None:
            plugin = context.get_plugin(MyJSONDynamicSettingsPlugin)
            try:
                if plugin.get_setting_metadata(plain_name, "obfuscate", False):
                    return True
            except KeyError:
                # a name the collection does not hold carries no mark
                pass
        # class metadata is context state: it survives loads and applies
        # for every entry of the collection at once
        return bool(context.get_class_metadata("obfuscate_all", False))

    def save(
        self,
        setting_name: str,
        attr: Optional[api.ISettingAttribute],
        value: Any,
    ) -> None:
        # the value reaction: a marked entry stores base64(json(value))
        # under a tag. The JSON storage form is rendered first, so any
        # round-trip type wraps the same way
        if attr is None and self._obfuscates(setting_name):
            encoded = json.dumps(self.to_json_value(value))
            value = self._TAG + base64.b64encode(encoded.encode("utf-8")).decode("ascii")
        super().save(setting_name, attr, value)

    def load(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> Any:
        # the tag, not the mark, decides on read: a load has just reset the
        # entry metadata, so the storage form carries the flag itself
        value = super().load(setting_name, attr)
        if attr is None and isinstance(value, str) and value.startswith(self._TAG):
            value = json.loads(base64.b64decode(value[len(self._TAG) :]))
        return value


class MyJSONDynamicSettingsPlugin(jds.JSONDynamicSettingsPlugin):
    """The JSON dynamic plugin whose collection ``MyDynamicJSONSerializer`` serves.

    The new pin of the binding is the whole difference from the stock plugin.
    The pin over the slot marker is a fresh registry slot, so registering it
    claims nothing that the stock plugins have already claimed. The collection
    itself (values, entry metadata, and the storage passes) is that of the base
    class, untouched.
    """

    binding = api.AttributeSerializerBinding(
        # (as in the stock plugin: the runtime subscription builds a concrete
        # subclass of the attribute, the static type application cannot
        # express that, so the checker sees an abstract class here)
        api.DynamicSettingAttribute[MyJSONSetting],  # type: ignore[type-abstract]
        MyDynamicJSONSerializer,
    )


adv_settings.LibraryConfiguration.register_settings_plugin(MyJSONDynamicSettingsPlugin)


class SessionState(adv_settings.Settings):
    """A settings class with nothing declared: the collection is all of it."""


# a real application binds the class to its own configuration location; the
# sample keeps its files next to the code, so they are easy to inspect after
# a run (main() removes them at startup)
SAMPLES_DIR = Path(__file__).resolve().parent


def demo_file(name: str) -> Path:
    """Point the collection at the file of this demonstration.

    With no static side to share a file with, the natural parameter is the own
    module default of the collection (the module default of the static side would
    serve as the fallback). A real application points it at one location once,
    at startup, and keeps it there. This sample points it at a new file for each
    demonstration (a pass resolves its file when it runs), so every save lands
    in a file of its own and overwrites nothing.
    """
    path = SAMPLES_DIR / name
    jds.JSONDynamicSettingsConfiguration.file_path = path
    return path


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # every run starts from a clean slate
    for stale in SAMPLES_DIR.glob("dynamic-metadata-*.json"):
        stale.unlink()

    section("the collection handle: the custom plugin class")
    plugin = SessionState.get_plugin(MyJSONDynamicSettingsPlugin)
    print(f"plugin = {type(plugin).__name__}, bound to {plugin.context.settings_class.__name__}")
    # the stock plugin class stays registered and is its own instance: a
    # different collection of the same settings class; hold your own
    # plugin class, or the marks land where no serializer reads them
    stock = SessionState.get_plugin(jds.JSONDynamicSettingsPlugin)
    print(
        f"the stock plugin is a separate instance: {stock is plugin}, its collection: {list(stock)}"
    )

    section("runtime names, stock layout (nothing marked: values as-is)")
    stock_file = demo_file("dynamic-metadata-1-stock.json")
    plugin.set_setting("dark_mode", True)
    plugin.set_setting("window.x", 120)
    plugin.set_setting("session_token", "tok-7f31")
    plugin.set_setting("last_opened", datetime(2026, 9, 13, 9, 45, 0))
    plugin.save_settings()  # the whole dynamic collection
    print(stock_file.read_text(encoding="utf-8"))

    section("entry metadata: one runtime name obfuscates at rest")
    entry_mark_file = demo_file("dynamic-metadata-2-entry-mark.json")
    plugin.set_setting_metadata("session_token", "obfuscate", True)
    # a mark requires a name the collection holds: anything else could
    # only hide a typo (the CRUD walkthrough lives in json_dynamic_settings.py)
    try:
        plugin.set_setting_metadata("session_tokn", "obfuscate", True)
    except KeyError as error:
        print(f"session_tokn -> KeyError: {error}")
    plugin.save_settings()
    print(entry_mark_file.read_text(encoding="utf-8"))
    print("(only the marked entry is tagged; the rest stay unchanged)")

    section("class metadata: the whole collection obfuscates")
    all_obfuscated_file = demo_file("dynamic-metadata-3-all-obfuscated.json")
    SessionState.set_class_metadata("obfuscate_all", True)
    plugin.save_settings()
    print(all_obfuscated_file.read_text(encoding="utf-8"))
    print("(one switch applies to every entry at once; with nothing else declared,")
    print(" the section is the whole document)")

    section("reload: every value, the tagged ones included, comes back")
    # the collection rebuilds from the all-obfuscated file above, the one
    # the module default still points at
    plugin.load_settings()
    print(f"dark_mode     = {plugin.get_setting('dark_mode', default=False)!r}")
    print(f"session_token = {plugin.get_setting('session_token', default='')!r}")
    # the default's type drives the conversion, exactly like the annotated
    # conversion of declared settings
    print(f"last_opened   = {plugin.get_setting('last_opened', default=datetime(2026, 1, 1))!r}")
    # the load reset the entry metadata; the class metadata survived it:
    # context state, not collection state
    print(f"entry mark kept?  {plugin.contains_setting_metadata('session_token', 'obfuscate')}")
    print(f"class switch kept? {SessionState.contains_class_metadata('obfuscate_all')}")

    section("lifecycle: the marks are runtime state, the tag is the storage truth")
    # a save right after the load would re-tag everything: the class switch
    # is still on. The application retunes instead: it turns the switch off
    # and re-marks the token, and only the token stores obfuscated again
    retuned_file = demo_file("dynamic-metadata-4-retuned.json")
    SessionState.delete_class_metadata("obfuscate_all")
    plugin.set_setting_metadata("session_token", "obfuscate", True)
    plugin.save_settings()
    print(retuned_file.read_text(encoding="utf-8"))
    print("files left for inspection, one per demonstration:")
    for path in sorted(SAMPLES_DIR.glob("dynamic-metadata-*.json")):
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
