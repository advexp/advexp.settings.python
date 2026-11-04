"""
Example: using Advexp.Settings with the JSON plugin.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/json_settings.py

The sample walks through the file backend: declaring settings, loading with
type conversion, saving (one atomic file write per pass), user-defined
(dataclass) values, operations on a single setting, and the layout of the
settings file itself.

The settings files are written next to this script and removed at startup, so
every run starts from a clean slate, and the files that the previous run left
are easy to inspect.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js
from advexp.settings import for_this_module


@dataclass
class Proxy:
    """A user-defined value type: stored as a JSON object of its fields."""

    host: str
    port: int = 3128
    since: Optional[datetime] = None


class ServerSettings(adv_settings.Settings):
    """Typed application settings backed by a JSON file."""

    # members are declared through the json_setting factory: assigning a
    # JSONSetting instance is the same thing at runtime, but the analyzer
    # flags it (it cannot see the metaclass swapping the attribute for a
    # value descriptor)
    # explicit storage name: file key is exactly "host"
    host: str = js.json_setting(name="host", default="localhost")
    port: int = js.json_setting(default=8080)  # file key is the full pattern name
    debug: bool = js.json_setting(name="debug", default=False)
    started_at: Optional[datetime] = js.json_setting(name="started_at", default=None)
    tags: List[str] = js.json_setting(name="tags", default=[])
    # dataclasses work directly and inside Optional/List/Dict
    proxy: Optional[Proxy] = js.json_setting(name="proxy", default=None)
    mirrors: List[Proxy] = js.json_setting(name="mirrors", default=[])
    # the optional path= locates the key in the document tree, as a JSON
    # Pointer: slash-separated segments (path=None or "" = the document root)
    db_host: str = js.json_setting(name="host", path="/service/database", default="localhost")
    db_port: int = js.json_setting(name="port", path="/service/database", default=5432)
    # a digits-only segment indexes into an array when the node it steps into
    # is one: the key lives inside that element, and a missing or too short
    # array is grown with nulls on save
    primary_region: str = js.json_setting(name="region", path="/replicas/0", default="eu")
    secondary_region: str = js.json_setting(name="region", path="/replicas/1", default="us")


# a real application binds the class to its own configuration location; the
# sample keeps its files next to the code, so they are easy to inspect after
# a run (main() removes them at startup)
SAMPLES_DIR = Path(__file__).resolve().parent
APP_SETTINGS_FILE = SAMPLES_DIR / "app-settings.json"
WINDOW_SETTINGS_FILE = SAMPLES_DIR / "window-settings.json"
EDITOR_SETTINGS_FILE = SAMPLES_DIR / "editor-settings.json"

# the module's default file, declared at the module's top level: it holds
# for the classes of this module alone (ServerSettings below), and every
# module of the application can declare its own this way. A location for
# the whole process is the plain assignment instead:
# js.JSONSettingsConfiguration.file_path = APP_SETTINGS_FILE
js.JSONSettingsConfiguration.file_path = for_this_module(APP_SETTINGS_FILE)


class WindowSettings(
    adv_settings.Settings,
    options=js.json_file(WINDOW_SETTINGS_FILE),
):
    """A settings class with its own file, independent of the module default."""

    width: int = js.json_setting(name="width", default=800)
    height: int = js.json_setting(name="height", default=600)


class EditorSettings(
    adv_settings.Settings,
    options=js.json_source(file=EDITOR_SETTINGS_FILE, name_pattern="{FieldName}"),
):
    """A hand-edited file with plain member names: the naming options of the family.

    The pattern replaces the default full spelling (``{module}.{class}.{member}``)
    for the pattern-built keys of this class. An explicit ``name=`` stays the
    full address. A form this short belongs in a file of its own: in a shared
    document, two classes with short forms would collide.
    """

    tab_width: int = js.json_setting(default=4)  # editor-settings.json: "tab_width"

    word_wrap: bool = js.json_setting(default=False)  # "word_wrap"

    # the escape hatch: an explicit name= is the full address, as always
    ui_font: str = js.json_setting(name="font", default="monospace")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def populate_server_settings() -> None:
    """Assign the walkthrough values: settings are plain class attributes."""
    ServerSettings.host = "db.example.com"
    ServerSettings.debug = True
    ServerSettings.started_at = datetime(2026, 9, 6, 12, 30, 0)
    ServerSettings.tags = ["primary", "eu"]
    ServerSettings.proxy = Proxy("proxy.example", 8080, datetime(2026, 9, 6, 12, 0, 0))
    ServerSettings.mirrors = [Proxy("mirror-a.example"), Proxy("mirror-b.example", 8080)]
    ServerSettings.primary_region = "eu-west"
    ServerSettings.secondary_region = "us-east"


def main() -> None:
    # Optional: see what the library does under the hood
    adv_settings.LibraryConfiguration.set_log_level(logging.INFO)

    # every run starts from a clean slate
    APP_SETTINGS_FILE.unlink(missing_ok=True)
    WINDOW_SETTINGS_FILE.unlink(missing_ok=True)
    EDITOR_SETTINGS_FILE.unlink(missing_ok=True)

    section("declare once, load anywhere (missing file -> defaults)")
    ServerSettings.load_settings()
    print(f"host       = {ServerSettings.host!r}")
    print(f"port       = {ServerSettings.port!r}")
    # (Optional members print None at times; None does define __repr__, the
    # checker's stub view says otherwise)
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {ServerSettings.started_at!r}")

    section("assign and save (one atomic file write per pass)")
    populate_server_settings()
    ServerSettings.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    print("(path= is a JSON Pointer: /service/database nests the key; /replicas/0 and")
    print(" /replicas/1 bind to the array elements)")

    section("reload: values and types come back from the file")
    ServerSettings.reset_settings()
    ServerSettings.load_settings()
    print(f"host       = {ServerSettings.host!r}")
    print(f"debug      = {ServerSettings.debug!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {ServerSettings.started_at!r}  (parsed ISO datetime)")
    print(f"tags       = {ServerSettings.tags!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"proxy      = {ServerSettings.proxy!r}  (dataclass rebuilt, with its datetime parsed)")
    print(f"mirrors    = {ServerSettings.mirrors!r}")
    print(f"regions    = {ServerSettings.primary_region!r}, {ServerSettings.secondary_region!r}")

    section("the user-defined type evolves: stored objects keep loading")
    # a file written by another app version: no "port" field yet, an extra key
    document = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    document["proxy"] = {"host": "legacy.example", "region": "eu"}
    APP_SETTINGS_FILE.write_text(json.dumps(document), encoding="utf-8")
    ServerSettings.load_settings()
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"proxy      = {ServerSettings.proxy!r}")
    print("             (missing field -> dataclass default, unknown key ignored)")

    section("inspect and delete")
    print(f"contains_setting('host') = {ServerSettings.contains_setting('host')}")
    # the lambda names the setting as code and is never called
    ServerSettings.delete_setting(lambda s: s.host)
    print(
        f"after delete: contains = {ServerSettings.contains_setting('host')}, "
        f"value = {ServerSettings.host!r} (back to the default)"
    )

    section("plugin access")
    plugin = ServerSettings.get_plugin(js.JSONSettingsPlugin)
    print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")
    # the class-to-file binding is class metadata; the plugin's file_path
    # property is the imperative spelling over it
    print(f"module default    = {js.JSONSettingsConfiguration.file_path}")
    print(
        f"own file of WindowSettings = {WindowSettings.get_plugin(js.JSONSettingsPlugin).file_path}"
    )

    section("per-class file binding")
    WindowSettings.width = 1024
    WindowSettings.save_settings()
    print(WINDOW_SETTINGS_FILE.read_text(encoding="utf-8"))
    WindowSettings.load_settings()
    print(f"width = {WindowSettings.width!r}, height = {WindowSettings.height!r}")

    section("the keys' form: the JSON naming options")
    # the family's naming options build this class's keys from the pattern:
    # bare member names here, a file a person edits by hand
    EditorSettings.tab_width = 2
    EditorSettings.save_settings()
    print(EDITOR_SETTINGS_FILE.read_text(encoding="utf-8"))
    EditorSettings.reset_settings()
    EditorSettings.load_settings()
    print(f"tab_width = {EditorSettings.tab_width!r}, word_wrap = {EditorSettings.word_wrap!r}")
    print(f"ui_font   = {EditorSettings.ui_font!r} (an explicit name= keeps its address)")

    section("delete all settings of a class")
    ServerSettings.delete_settings()
    print(f"after ServerSettings.delete_settings: file contains {APP_SETTINGS_FILE.read_text()!r}")
    WindowSettings.delete_settings()
    print(
        f"after WindowSettings.delete_settings: file contains {WINDOW_SETTINGS_FILE.read_text()!r}"
    )
    EditorSettings.delete_settings()
    print(
        f"after EditorSettings.delete_settings: file contains {EDITOR_SETTINGS_FILE.read_text()!r}"
    )

    # put the sample data back, so the files left next to this script are
    # filled in and can be inspected after the run (removed at next startup)
    populate_server_settings()
    ServerSettings.save_settings()
    WindowSettings.width = 1024
    WindowSettings.height = 600
    WindowSettings.save_settings()
    EditorSettings.tab_width = 2
    EditorSettings.save_settings()
    print(f"\nfiles left for inspection: {APP_SETTINGS_FILE}, {WINDOW_SETTINGS_FILE}")
    print(f"and {EDITOR_SETTINGS_FILE}")


if __name__ == "__main__":
    main()
