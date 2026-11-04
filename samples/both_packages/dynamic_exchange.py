"""
Example: a dynamic collection that is written by Advexp.Settings and read
back by Advexp.Configuration.

One library of an application owns its user-tunable state (window layouts,
dashboards, plugin options). The names of this state arrive at runtime, so
the owning side keeps it in a dynamic collection of ``advexp.settings``.

Another library needs to read that state without depending on the writer. It
declares the group of the writer next to its JSON source binding, and it
reads the entries through the read-only dynamic plugin of the configuration
package. Nothing moves between the two sides except the file.

Run from the repository root with the packages installed
(``pip install advexp-settings advexp-configuration``):

    python samples/both_packages/dynamic_exchange.py

The sample walks through four cases, and in each of them one side reads
exactly what the other side wrote:

- the round trip through a shared file (the default layout);
- the flat layout that a writer may switch to;
- a dynamic file of its own;
- the TOML counterpart.
"""

import json
from pathlib import Path

import advexp.configuration as adv_config
import advexp.configuration.plugins.json_dynamic_settings as cjson_dynamic
import advexp.configuration.plugins.json_settings as cjson
import advexp.configuration.plugins.toml_dynamic_settings as ctoml_dynamic
import advexp.configuration.plugins.toml_settings as ctoml
import advexp.settings as adv_settings
import advexp.settings.plugins.json_dynamic_settings as sjson_dynamic
import advexp.settings.plugins.json_settings as sjson
import advexp.settings.plugins.toml_dynamic_settings as stoml_dynamic
import advexp.settings.plugins.toml_settings as stoml

SAMPLES_DIR = Path(__file__).resolve().parent
SHARED_JSON = SAMPLES_DIR / "exchange-state.json"
OWN_DYNAMIC_JSON = SAMPLES_DIR / "exchange-dynamic.json"
SHARED_TOML = SAMPLES_DIR / "exchange-state.toml"


def section(title: str) -> None:
    print()
    print(f"— {title} " + "-" * (66 - len(title)))


class LocalSettings(
    adv_settings.Settings,
    options=sjson.json_file(SHARED_JSON),
):
    """The writing side: a settings class with a dynamic collection."""

    # a declared member shares the file with the dynamic entries
    session_ttl: int = sjson.json_setting(default=30)


class DashboardConfig(
    adv_config.Configuration,
    options=cjson.json_source(file=SHARED_JSON, dynamic_of=f"{__name__}.LocalSettings"),
):
    """The reading side: the writer's group, read-only."""

    # a declared member reads the same file as always
    session_ttl: int = cjson.json_setting(default=30)


class TomlWriter(
    adv_settings.Settings,
    options=stoml.toml_file(SHARED_TOML),
):
    """The writing side of the TOML round trip."""


class TomlConfig(
    adv_config.Configuration,
    options=ctoml.toml_source(file=SHARED_TOML, dynamic_of=f"{__name__}.TomlWriter"),
):
    """The reading side of the TOML round trip."""


def shared_file_round_trip() -> None:
    section("the shared file: one document, both sides")
    writer = LocalSettings.get_plugin(sjson_dynamic.JSONDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.set_setting("retries", 5)
    writer.save_settings()
    print("the file stored by the writer:")
    print(json.dumps(json.loads(SHARED_JSON.read_text(encoding="utf-8")), indent=2))

    reader = DashboardConfig.get_plugin(cjson_dynamic.JSONDynamicSettingsPlugin)
    reader.load_configuration()
    print("the reader's snapshot:", reader.to_dict())
    print("converted to the type of the default:", repr(reader.get_setting("retries", default=0)))


def the_read_only_contract() -> None:
    section("the collection is read-only")
    reader = DashboardConfig.get_plugin(cjson_dynamic.JSONDynamicSettingsPlugin)
    try:
        reader.set_setting("dark_mode", False)
    except TypeError as error:
        print("a write is refused:", error)


def the_flat_layout() -> None:
    section("the flat layout: the reader mirrors the writer's parameter")
    # a fresh file: switching the layout leaves the old entries where they
    # were stored, and this section shows the flat form alone
    SHARED_JSON.unlink(missing_ok=True)
    LocalSettings.get_plugin(
        sjson_dynamic.JSONDynamicSettingsPlugin
    ).dynamic_settings_section_name = None
    writer = LocalSettings.get_plugin(sjson_dynamic.JSONDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    print("the flat full-name keys:", sorted(json.loads(SHARED_JSON.read_text(encoding="utf-8"))))

    DashboardConfig.get_plugin(
        cjson_dynamic.JSONDynamicSettingsPlugin
    ).dynamic_settings_section_name = None
    reader = DashboardConfig.get_plugin(cjson_dynamic.JSONDynamicSettingsPlugin)
    reader.load_configuration()
    print("the reader's snapshot:", reader.to_dict())


def the_own_dynamic_file() -> None:
    section("a dynamic file of its own: dynamic_file= on both sides")
    SHARED_JSON.unlink(missing_ok=True)

    class SeparateWriter(
        adv_settings.Settings,
        options=sjson.json_source(file=SHARED_JSON, dynamic_file=OWN_DYNAMIC_JSON),
    ):
        """The writer moves its dynamic entries into a file of their own."""

    SeparateWriter.get_plugin(
        sjson_dynamic.JSONDynamicSettingsPlugin
    ).dynamic_settings_section_name = None
    writer = SeparateWriter.get_plugin(sjson_dynamic.JSONDynamicSettingsPlugin)
    writer.set_setting("window_layout", "left")
    writer.save_settings()

    class SeparateConfig(
        adv_config.Configuration,
        options=cjson.json_source(
            file=SHARED_JSON,
            dynamic_file=OWN_DYNAMIC_JSON,
            dynamic_of=f"{__name__}.SeparateWriter",
        ),
    ):
        """The reader follows to the writer's own dynamic file."""

    SeparateConfig.get_plugin(
        cjson_dynamic.JSONDynamicSettingsPlugin
    ).dynamic_settings_section_name = None
    reader = SeparateConfig.get_plugin(cjson_dynamic.JSONDynamicSettingsPlugin)
    reader.load_configuration()
    print("the dynamic file:", sorted(json.loads(OWN_DYNAMIC_JSON.read_text(encoding="utf-8"))))
    print("the reader's snapshot:", reader.to_dict())


def the_toml_round_trip() -> None:
    section("the TOML twin")
    SHARED_TOML.unlink(missing_ok=True)
    writer = TomlWriter.get_plugin(stoml_dynamic.TOMLDynamicSettingsPlugin)
    writer.set_setting("dark_mode", True)
    writer.save_settings()
    print("the file stored by the writer:")
    print(SHARED_TOML.read_text(encoding="utf-8").strip())

    reader = TomlConfig.get_plugin(ctoml_dynamic.TOMLDynamicSettingsPlugin)
    reader.load_configuration()
    print("the reader's snapshot:", reader.to_dict())


def main() -> None:
    for path in (SHARED_JSON, OWN_DYNAMIC_JSON, SHARED_TOML):
        path.unlink(missing_ok=True)

    shared_file_round_trip()
    the_read_only_contract()
    the_flat_layout()
    the_own_dynamic_file()
    the_toml_round_trip()

    print()
    print(f"files left for inspection: {SHARED_JSON}, {OWN_DYNAMIC_JSON}, {SHARED_TOML}")


if __name__ == "__main__":
    main()
