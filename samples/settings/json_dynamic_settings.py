"""
Example: dynamic settings with the JSONDynamicSettings plugin.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/json_dynamic_settings.py

Dynamic settings are name-value pairs that have no declared class member:
their names appear at runtime (a window layout that the user rearranges,
dashboards, options that plugins provide). The walkthrough shows the mixed
model:

- declared (static) members and the dynamic collection of one settings class
  living in the same JSON file (the dynamic entries are stored in their own
  section of the document);
- typed reads through the defaults of ``get_setting``;
- the iteration order declared in code;
- snapshots of the open collection;
- the dynamic side moving to a file of its own, either module-wide through
  ``JSONDynamicSettingsConfiguration`` or per class through the
  ``json_source(dynamic_file=...)`` binding of the ``class`` statement.

The settings file is written next to this script and removed at startup, so
every run starts from a clean slate, and the file that the previous run left
is easy to inspect.
"""

import logging
from datetime import datetime
from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.json_dynamic_settings as jds

SAMPLES_DIR = Path(__file__).resolve().parent
APP_SETTINGS_FILE = SAMPLES_DIR / "app-settings.json"
DYNAMIC_SETTINGS_FILE = SAMPLES_DIR / "dynamic-settings.json"


class LocalSettings(adv_settings.Settings):
    """Application settings: one declared member plus a dynamic collection."""

    # declared (static) settings are typed members, as usual; the factory is
    # the analyzer-clean spelling (a JSONSetting instance assigned directly
    # is the same thing at runtime, but the analyzer flags it)
    locale: str = jds.json_setting(name="locale", default="en-US")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # optional: see what the library does under the hood
    adv_settings.LibraryConfiguration.set_log_level(logging.INFO)

    # every run starts from a clean slate
    APP_SETTINGS_FILE.unlink(missing_ok=True)
    DYNAMIC_SETTINGS_FILE.unlink(missing_ok=True)
    jds.JSONSettingsConfiguration.file_path = APP_SETTINGS_FILE

    section("the plugin handle: bound to the settings class, cached")
    plugin = LocalSettings.get_plugin(jds.JSONDynamicSettingsPlugin)
    print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")

    section("runtime names: set values, then save them (storage stays explicit)")
    # names appear at runtime; values are plain assignments until a save
    plugin.set_setting("dark_mode", True)
    plugin.set_setting("window.x", 120)
    plugin.set_setting("window.y", 80)
    plugin.set_setting("last_opened", datetime(2026, 9, 13, 9, 45, 0))
    LocalSettings.locale = "de-DE"
    LocalSettings.save_settings()  # the static member, as usual
    plugin.save_settings()  # the whole dynamic collection
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    print("(dynamic entries live in their own section of the document,")
    print(" grouped by settings class; the static keys stay at the root)")

    section("load back: typed reads through the default")
    plugin.load_settings()  # rebuilds the collection from the file
    print(f"names      = {list(plugin)}")
    print(f"dark_mode  = {plugin.get_setting('dark_mode', default=False)!r}")
    print(f"window.x   = {plugin.get_setting('window.x', default=0)!r}")
    # the default's type drives the conversion, exactly like the annotated
    # conversion of declared settings
    print(f"last_opened = {plugin.get_setting('last_opened', default=datetime(2026, 1, 1))!r}")
    # without a default: the raw storage form (here, the ISO string)
    print(f"last_opened (raw) = {plugin.get_setting('last_opened')!r}")
    print(f"missing    = {plugin.get_setting('refresh', default=30)!r} (fallback)")
    # the class-level passes still load only the declared members
    LocalSettings.load_settings()
    print(f"locale     = {LocalSettings.locale!r} (static side, untouched by the plugin)")

    section("single-setting operations")
    plugin.set_setting("dark_mode", False)
    plugin.save_setting("dark_mode")
    plugin.load_setting("window.x")
    plugin.delete_setting("window.y")
    print(f"names      = {list(plugin)}")
    print(f"dark_mode  = {plugin.get_setting('dark_mode', default=True)!r} (saved value)")

    section("the collection is a dict-like object")
    print(f"len        = {len(plugin)}, 'dark_mode' in plugin = {'dark_mode' in plugin}")
    snapshot = plugin.to_dict()  # deep copy in the effective iteration order
    snapshot["window.x"] = 999
    print(f"window.x   = {plugin.get_setting('window.x', default=0)!r} (the snapshot was a copy)")
    plugin.update_from_dict({"window.x": 240, "refresh": 15})  # 'refresh' is new
    print(
        f"window.x   = {plugin.get_setting('window.x', default=0)!r}, "
        f"refresh = {plugin.get_setting('refresh', default=0)!r}"
    )

    section("iteration order: declared in code, not persisted")
    # the canonical order (a UI screen layout, say) is class metadata: names
    # it lists come first, the rest keep the order they were added
    LocalSettings.set_class_metadata(
        jds.JSONDynamicSettingsPlugin.ITERATION_ORDER_METADATA,
        ["dark_mode", "refresh", "window.x"],
    )
    print(f"ordered    = {list(plugin)}")

    section("metadata of the runtime names")
    # like the member metadata of the settings class, but keyed by the runtime
    # name and held by the plugin's collection: every operation requires a
    # name the collection holds, the deletes take the metadata along, and
    # loads reset it; the storage holds no metadata to bring
    plugin.set_setting_metadata("dark_mode", "ui-label", "Dark mode")
    plugin.set_setting_metadata("refresh", "ui-label", None)  # None is a stored value
    print(f"label      = {plugin.get_setting_metadata('dark_mode', 'ui-label')!r}")
    print(f"all        = {plugin.get_setting_all_metadata('dark_mode')!r}")
    print(
        f"refresh    = {plugin.get_setting_metadata('refresh', 'ui-label', 'fallback')!r}, "
        f"stored? {plugin.contains_setting_metadata('refresh', 'ui-label')}"
    )
    plugin.delete_setting_metadata("refresh", "ui-label")  # metadata alone: the setting stays
    plugin.set_setting_metadata("dark_mode", "hint", "Try the dark look")
    plugin.delete_setting_all_metadata("dark_mode")  # every entry of the name at once
    print(f"label kept? {plugin.contains_setting_metadata('dark_mode', 'ui-label')}")
    plugin.delete_setting("dark_mode")  # the setting went, its metadata with it
    try:  # the name left the collection: metadata cannot reach it anymore
        plugin.set_setting_metadata("dark_mode", "ui-label", "typo")
    except KeyError as error:
        print(f"dark_mode  -> KeyError: {error}")
    # a load resets it too: the loaded name's entry on load_setting, all of
    # it on load_settings; annotate afresh after a load
    plugin.set_setting_metadata("window.x", "ui-label", "Horizontal position")
    plugin.load_setting("window.x")  # the value arrived; the metadata reset
    print(f"window.x   = kept? {plugin.contains_setting_metadata('window.x', 'ui-label')}")

    section("the document section: rename it, relocate it, or drop it")
    # the section is the JSON backend's own layout choice; the parameters live on
    # the plugin, mirroring the name=/path= of JSONSetting. A different name:
    plugin.dynamic_settings_section_name = "runtime"
    plugin.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    # the optional path locates the section deeper in the document tree,
    # as a JSON Pointer like the path= of JSONSetting:
    plugin.dynamic_settings_section_path = "/config/advexp"
    plugin.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    # None switches to the flat layout: D-prefixed full-name keys at the root
    plugin.dynamic_settings_section_name = None
    plugin.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    plugin.dynamic_settings_section_name = jds.JSONDynamicSettingsPlugin.DEFAULT_SECTION
    plugin.dynamic_settings_section_path = None
    plugin.save_settings()  # back to the default section for the rest of the walk
    # switching the bindings does not migrate already stored entries: pick
    # the layout before the first save and keep it

    section("a file of their own: JSONDynamicSettingsConfiguration.file_path")
    # the shared file is the default, not the rule: one assignment moves the
    # dynamic side to its own file, apart from the static one
    jds.JSONDynamicSettingsConfiguration.file_path = DYNAMIC_SETTINGS_FILE
    plugin.save_settings()
    print(DYNAMIC_SETTINGS_FILE.read_text(encoding="utf-8"))
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    print("(the collection went to the dynamic settings file; the shared file")
    print(" keeps what it had; switching does not migrate entries that are already stored)")
    jds.JSONDynamicSettingsConfiguration.file_path = None  # back to sharing

    # one class's dynamic side moves alone through the class's own binding,
    # declared beside the other class options; it wins over the module default
    class PinnedSettings(
        adv_settings.Settings, options=jds.json_source(dynamic_file=DYNAMIC_SETTINGS_FILE)
    ):
        pass

    pinned = PinnedSettings.get_plugin(jds.JSONDynamicSettingsPlugin)
    pinned.set_setting("checkbox", True)
    pinned.save_settings()
    print(f"own file of PinnedSettings = {pinned.file_path!r} (per-class binding)")
    print(DYNAMIC_SETTINGS_FILE.read_text(encoding="utf-8"))

    # the plugin property is the imperative spelling of the same binding;
    # removing it is delete_class_metadata's job, not an assignment
    plugin.file_path = DYNAMIC_SETTINGS_FILE
    plugin.save_settings()
    print(f"own file of LocalSettings = {plugin.file_path!r}")
    LocalSettings.delete_class_metadata(jds.JSON_DYNAMIC_FILE_METADATA)

    section("None is a stored value; deletion stays explicit")
    # saving None keeps the entry, as null in this document storage
    plugin.set_setting("last_opened", None)
    plugin.save_setting("last_opened")
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    # removing entries is the delete operations' job:
    plugin.delete_setting("last_opened")
    plugin.delete_settings()  # dynamic entries only; the static member stays
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))

    section("the names' form: the dynamic configuration's pattern parameter")
    # both visible names of an entry follow the module parameter: the class
    # object's key in the section and the flat full names. The default full
    # pattern names the module too — noise in a file a person edits by hand,
    # where the class name alone tells the whole story. Changing the pattern
    # does not migrate stored entries: pick the form before the first save,
    # or move the entries by hand
    jds.JSONDynamicSettingsConfiguration.name_pattern = "{ClassName}.{FieldName}"
    plugin.set_setting("dark_mode", True)
    plugin.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    print("(the class key in the section is now 'LocalSettings', without the module part;")
    print(" the static keys are handled by the static family options)")
    plugin.delete_settings()  # the demo spelling goes with its entries
    jds.JSONDynamicSettingsConfiguration.name_pattern = jds.DEFAULT_SETTINGS_NAME_PATTERN

    # put the sample data back for inspection after the run
    LocalSettings.locale = "en-US"
    LocalSettings.save_settings()
    plugin.set_setting("dark_mode", True)
    plugin.set_setting("window.x", 120)
    plugin.set_setting("window.y", 80)
    plugin.set_setting("last_opened", datetime(2026, 9, 13, 9, 45, 0))
    plugin.save_settings()
    print(f"\nfiles left for inspection: {APP_SETTINGS_FILE}, {DYNAMIC_SETTINGS_FILE}")


if __name__ == "__main__":
    main()
