"""
Example: using Advexp.Settings with the YAML plugin.

Run from the repository root with the package installed
(``pip install "advexp-settings[yaml]"``):

    python samples/settings/yaml_settings.py

The sample walks through the file backend: declaring settings, loading with
type conversion, saving (one atomic file write per pass), user-defined
(dataclass) values, operations on a single setting, and the layout of the
settings file itself. It also shows what YAML does differently from the JSON
file backend:

- dates stay native in the file;
- ``None`` is stored as the null of the document;
- the comments, key order, quoting style, and anchors of the file itself
  survive every save.

The settings files are written next to this script and removed at startup, so
every run starts from a clean slate, and the files that the previous run left
are easy to inspect.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.yaml_settings as ys
from advexp.settings import for_this_module


@dataclass
class Proxy:
    """A user-defined value type: stored as a mapping of its fields."""

    host: str
    port: int = 3128
    since: Optional[datetime] = None


class ServerSettings(adv_settings.Settings):
    """Typed application settings backed by a YAML file."""

    # members are declared through the yaml_setting factory: assigning a
    # YAMLSetting instance is the same thing at runtime, but the analyzer
    # flags it (it cannot see the metaclass swapping the attribute for a
    # value descriptor)
    # explicit storage name: file key is exactly "host"
    host: str = ys.yaml_setting(name="host", default="localhost")
    # no name=: the full pattern name — a flat key of the document root,
    # its dots stay inside the key (no table nesting here)
    port: int = ys.yaml_setting(default=8080)
    debug: bool = ys.yaml_setting(name="debug", default=False)
    started_at: Optional[datetime] = ys.yaml_setting(name="started_at", default=None)
    # stored native: launch_on: 2026-12-01
    launch_on: date = ys.yaml_setting(name="launch_on", default=date(2026, 12, 1))
    tags: List[str] = ys.yaml_setting(name="tags", default=[])
    # dataclasses work directly and inside Optional/List
    proxy: Optional[Proxy] = ys.yaml_setting(name="proxy", default=None)
    mirrors: List[Proxy] = ys.yaml_setting(name="mirrors", default=[])
    # the optional path= locates the key in the document tree, as a JSON
    # Pointer: slash-separated segments (path=None or "" = the document root)
    db_host: str = ys.yaml_setting(name="host", path="/service/database", default="localhost")
    db_port: int = ys.yaml_setting(name="port", path="/service/database", default=5432)
    # a digits-only segment indexes into a sequence when the node it steps
    # into is one: the key lives inside that element (a missing sequence is
    # grown with nulls up to the position the write fills)
    primary_region: str = ys.yaml_setting(name="region", path="/replicas/0", default="eu")


# a real application binds the class to its own configuration location; the
# sample keeps its files next to the code, so they are easy to inspect after
# a run (main() removes them at startup)
SAMPLES_DIR = Path(__file__).resolve().parent
APP_SETTINGS_FILE = SAMPLES_DIR / "app-settings.yaml"
WINDOW_SETTINGS_FILE = SAMPLES_DIR / "window-settings.yaml"

# the module's default file, declared at the module's top level: it holds
# for the classes of this module alone (ServerSettings above), and every
# module of the application can declare its own this way. A location for
# the whole process is the plain assignment instead:
# ys.YAMLSettingsConfiguration.file_path = APP_SETTINGS_FILE
ys.YAMLSettingsConfiguration.file_path = for_this_module(APP_SETTINGS_FILE)


class WindowSettings(
    adv_settings.Settings,
    options=ys.yaml_file(WINDOW_SETTINGS_FILE),
):
    """A settings class with its own file, independent of the module default."""

    width: int = ys.yaml_setting(name="width", default=800)
    height: int = ys.yaml_setting(name="height", default=600)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def populate_server_settings() -> None:
    """Assign the walkthrough values: settings are plain class attributes."""
    ServerSettings.host = "db.example.com"
    ServerSettings.debug = True
    ServerSettings.started_at = datetime(2026, 9, 6, 12, 30, 0)
    ServerSettings.launch_on = date(2027, 1, 15)
    ServerSettings.tags = ["primary", "eu"]
    ServerSettings.proxy = Proxy("proxy.example", 8080, datetime(2026, 9, 6, 12, 0, 0))
    ServerSettings.mirrors = [
        Proxy("mirror-a.example", since=datetime(2026, 1, 2, 3, 4, 0)),
        Proxy("mirror-b.example", 8080, datetime(2026, 2, 3, 4, 5, 0)),
    ]
    ServerSettings.primary_region = "eu-west"


def main() -> None:
    # Optional: see what the library does under the hood
    adv_settings.LibraryConfiguration.set_log_level(logging.INFO)

    # every run starts from a clean slate
    APP_SETTINGS_FILE.unlink(missing_ok=True)
    WINDOW_SETTINGS_FILE.unlink(missing_ok=True)

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
    print("(path= is a JSON Pointer: /service/database nests the key; /replicas/0 binds")
    print(
        " inside the first sequence element; new keys are appended at the end of their container)"
    )

    section("reload: values and types come back from the file")
    ServerSettings.reset_settings()
    ServerSettings.load_settings()
    print(f"host       = {ServerSettings.host!r}")
    print(f"debug      = {ServerSettings.debug!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {ServerSettings.started_at!r}  (native YAML timestamp, no ISO string)")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"launch_on  = {ServerSettings.launch_on!r}  (native YAML date)")
    print(f"tags       = {ServerSettings.tags!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"proxy      = {ServerSettings.proxy!r}  (dataclass rebuilt from its mapping)")
    print(f"mirrors    = {ServerSettings.mirrors!r}")

    section("None is the document's null: it stores and reads back")
    # unlike the string storages and TOML, a None value is stored as null —
    # it comes back as None, apart from a missing key
    ServerSettings.started_at = None
    ServerSettings.save_settings()
    print(f"contains_setting('started_at') = {ServerSettings.contains_setting('started_at')}")
    ServerSettings.load_settings()
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {ServerSettings.started_at!r}  (the stored null, not the default)")

    section("the file's own form survives the save")
    # a YAML file is written to be edited by hand: comments, quoting style,
    # anchors and key order are the file's own, and the pass leaves them
    # standing — it writes values, not prose
    APP_SETTINGS_FILE.write_text(
        "# edited by hand: the deployment's endpoint\n"
        "host: db.example.com  # inline prose stays too\n"
        "'quoted-key': kept\n"
        "anchor: &primary mirror-a.example\n"
        "alias: *primary\n",
        encoding="utf-8",
    )
    ServerSettings.load_settings()
    ServerSettings.debug = True
    ServerSettings.save_settings()
    text = APP_SETTINGS_FILE.read_text(encoding="utf-8")
    print(text)
    print("(the hand-written comment, quotes, anchor and alias were all preserved by the save)")

    section("inspect and delete")
    print(f"contains_setting('host') = {ServerSettings.contains_setting('host')}")
    # the lambda names the setting as code and is never called
    ServerSettings.delete_setting(lambda s: s.host)
    print(
        f"after delete: contains = {ServerSettings.contains_setting('host')}, "
        f"value = {ServerSettings.host!r} (back to the default)"
    )

    section("plugin access")
    plugin = ServerSettings.get_plugin(ys.YAMLSettingsPlugin)
    print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")
    # the class-to-file binding is class metadata; the plugin's file_path
    # property is the imperative spelling over it
    print(f"module default    = {ys.YAMLSettingsConfiguration.file_path}")
    print(
        f"own file of WindowSettings = {WindowSettings.get_plugin(ys.YAMLSettingsPlugin).file_path}"
    )

    section("per-class file binding")
    WindowSettings.width = 1024
    WindowSettings.save_settings()
    print(WINDOW_SETTINGS_FILE.read_text(encoding="utf-8"))
    WindowSettings.load_settings()
    print(f"width = {WindowSettings.width!r}, height = {WindowSettings.height!r}")

    section("delete all settings of a class")
    ServerSettings.delete_settings()
    print(f"after ServerSettings.delete_settings: file contains {APP_SETTINGS_FILE.read_text()!r}")
    WindowSettings.delete_settings()
    print(
        f"after WindowSettings.delete_settings: file contains {WINDOW_SETTINGS_FILE.read_text()!r}"
    )

    # put the sample data back, so the files left next to this script are
    # filled in and can be inspected after the run (removed at next startup)
    populate_server_settings()
    ServerSettings.save_settings()
    WindowSettings.width = 1024
    WindowSettings.height = 600
    WindowSettings.save_settings()
    print(f"\nfiles left for inspection: {APP_SETTINGS_FILE}, {WINDOW_SETTINGS_FILE}")


if __name__ == "__main__":
    main()
