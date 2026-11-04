"""
Example: dynamic settings with the YAMLDynamicSettings plugin.

Run from the repository root with the package installed
(``pip install "advexp-settings[yaml]"``):

    python samples/settings/yaml_dynamic_settings.py

Dynamic settings are name-value pairs that have no declared class member:
their names appear at runtime (a window layout that the user rearranges,
dashboards, options that plugins provide). The walkthrough shows the mixed
model:

- declared (static) members and the dynamic collection of one settings class
  living in the same YAML file (the dynamic entries are stored in their own
  section of the document);
- typed reads through the defaults of ``get_setting``;
- the iteration order declared in code;
- snapshots of the open collection;
- the dynamic side moving to a file of its own, either module-wide through
  ``YAMLDynamicSettingsConfiguration`` or per class through the
  ``yaml_source(dynamic_file=...)`` binding of the ``class`` statement.

The settings files are written next to this script and removed at startup, so
every run starts from a clean slate, and the files that the previous run left
are easy to inspect.
"""

import logging
from datetime import date
from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.yaml_dynamic_settings as yds

SAMPLES_DIR = Path(__file__).resolve().parent
APP_SETTINGS_FILE = SAMPLES_DIR / "app-settings.yaml"
DYNAMIC_SETTINGS_FILE = SAMPLES_DIR / "dynamic-settings.yaml"


class LocalSettings(adv_settings.Settings):
    """Application settings: one declared member plus a dynamic collection."""

    # declared (static) settings are typed members, as usual; the factory is
    # the analyzer-clean spelling (a YAMLSetting instance assigned directly
    # is the same thing at runtime, but the analyzer flags it)
    locale: str = yds.yaml_setting(name="locale", default="en-US")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # optional: see what the library does under the hood
    adv_settings.LibraryConfiguration.set_log_level(logging.INFO)

    # every run starts from a clean slate
    APP_SETTINGS_FILE.unlink(missing_ok=True)
    DYNAMIC_SETTINGS_FILE.unlink(missing_ok=True)
    yds.YAMLSettingsConfiguration.file_path = APP_SETTINGS_FILE

    section("the plugin handle: bound to the settings class, cached")
    plugin = LocalSettings.get_plugin(yds.YAMLDynamicSettingsPlugin)
    again = LocalSettings.get_plugin(yds.YAMLDynamicSettingsPlugin)
    print(f"plugin = {plugin.plugin_name!r}, cached per class: {plugin is again}")

    section("runtime names: set values, then save them (storage stays explicit)")
    plugin.set_setting("dark_mode", True)
    plugin.set_setting("window_width", 1024)
    plugin.set_setting("pinned_until", date(2026, 12, 24))  # stored native
    plugin.set_setting("note", None)  # the document's null, a value like any other
    plugin.save_settings()

    # the declared member sits under its own full name; the dynamic entries
    # live in their own section, grouped per settings class
    LocalSettings.locale = "de-DE"
    LocalSettings.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))

    section("load back: typed reads through the default")
    plugin.load_settings()
    print(f"dark_mode    = {plugin.get_setting('dark_mode', default=False)!r}")
    print(f"window_width = {plugin.get_setting('window_width', default=800)!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"pinned_until = {plugin.get_setting('pinned_until', default=None)!r}  (native date)")
    print(f"note         = {plugin.get_setting('note', default='missing')!r}  (the stored null)")

    section("single-setting operations")
    plugin.set_setting("dark_mode", False)
    plugin.save_setting("dark_mode")  # one value, one write
    print(f"dark_mode = {plugin.get_setting('dark_mode', default=True)!r}")
    plugin.load_setting("window_width")  # refresh one value from the file
    print(f"window_width = {plugin.get_setting('window_width', default=0)!r}")

    section("the collection is a dict-like object")
    print(f"len(plugin) = {len(plugin)}, 'note' in plugin = {'note' in plugin}")
    print(f"sorted(plugin) = {sorted(plugin)}")
    snapshot = plugin.to_dict()  # a deep copy, the collection stays safe
    print(f"to_dict()['dark_mode'] = {snapshot['dark_mode']!r}")

    section("iteration order: declared in code, not persisted")
    LocalSettings.set_class_metadata(
        yds.YAMLDynamicSettingsPlugin.ITERATION_ORDER_METADATA,
        ["window_width", "dark_mode"],
    )
    print(f"list(plugin) = {list(plugin)}  (the two declared settings come first)")

    section("a file of their own: YAMLDynamicSettingsConfiguration.file_path")
    # the shared file is the default, not the rule: one assignment moves the
    # dynamic side to its own file, apart from the static one
    yds.YAMLDynamicSettingsConfiguration.file_path = DYNAMIC_SETTINGS_FILE
    plugin.save_settings()
    print(DYNAMIC_SETTINGS_FILE.read_text(encoding="utf-8"))
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    print("(the collection went to the dynamic settings file; the shared file")
    print(" keeps what it had; switching does not migrate entries that are already stored)")
    yds.YAMLDynamicSettingsConfiguration.file_path = None  # back to sharing

    section("per class: the yaml_source(dynamic_file=...) binding")

    # one class's dynamic side moves alone through the class's own binding,
    # declared beside the other class options; it wins over the module default
    class PinnedSettings(
        adv_settings.Settings,
        options=yds.yaml_source(dynamic_file=DYNAMIC_SETTINGS_FILE),
    ):
        pass

    pinned = PinnedSettings.get_plugin(yds.YAMLDynamicSettingsPlugin)
    pinned.set_setting("checkbox", True)
    pinned.save_settings()
    print(f"own file of PinnedSettings = {pinned.file_path!r} (per-class binding)")
    print(DYNAMIC_SETTINGS_FILE.read_text(encoding="utf-8"))

    section("deletion: one name, or the whole collection")
    # null is a value, so removal stays explicit — the delete operations are
    # the only spelling of it
    plugin.delete_setting("note")
    plugin.save_settings()
    print(f"'note' in plugin = {'note' in plugin}")
    plugin.delete_settings()  # dynamic entries only; the static member stays
    plugin.save_settings()
    print(f"after delete_settings: file contains {APP_SETTINGS_FILE.read_text()!r}")

    section("the document section: rename it, relocate it, or drop it")
    # the section key names the section; dynamic_settings_section_path
    # (a JSON Pointer) would place it deeper in the tree, and None instead
    # of a key switches to the flat layout (D-prefixed full-name keys at
    # the document root). Changing the parameter does not migrate what earlier
    # saves stored: pick the form before the first save, or move the
    # entries by hand
    plugin.set_setting("dark_mode", True)  # give the section something to hold
    plugin.dynamic_settings_section_name = "runtime"
    plugin.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    plugin.dynamic_settings_section_name = "dynamic"  # back to the stock key

    # put the sample data back for inspection after the run
    LocalSettings.locale = "en-US"
    LocalSettings.save_settings()
    plugin.set_setting("dark_mode", True)
    plugin.set_setting("window_width", 1024)
    plugin.set_setting("pinned_until", date(2026, 12, 24))
    plugin.save_settings()
    print(f"\nfiles left for inspection: {APP_SETTINGS_FILE}, {DYNAMIC_SETTINGS_FILE}")


if __name__ == "__main__":
    main()
