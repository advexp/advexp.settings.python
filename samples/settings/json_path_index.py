"""
Example: array indices in the ``path=`` of the JSON plugin of Advexp.Settings.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/json_path_index.py

A segment that consists only of digits in the ``path=`` JSON Pointer binds a
setting to a slot of an array in the settings file: ``path="/endpoints/1"``
stores the key inside the second element of ``endpoints``.

The walkthrough shows three things:

- loading slot-bound settings from a file that another application wrote;
- saving into a slot beyond the current end (the array grows with nulls up to
  it);
- deleting: an emptied element becomes a null (its siblings keep their
  positions), a foreign key inside an element survives, and an array in which
  every element is a null is dropped entirely.

The settings file is written next to this script and removed at startup, so
every run starts from a clean slate.
"""

import json
from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class FailoverSettings(adv_settings.Settings):
    """Every slot of the endpoints array is its own group of settings."""

    # declared through the json_setting factory: assigning a JSONSetting
    # instance is the same thing at runtime, but the analyzer flags it
    # (it cannot see the metaclass swapping the attribute for a descriptor)
    primary_host: str = js.json_setting(name="host", path="/endpoints/0", default="primary.example")
    primary_port: int = js.json_setting(name="port", path="/endpoints/0", default=80)
    secondary_host: str = js.json_setting(
        name="host", path="/endpoints/1", default="secondary.example"
    )
    secondary_port: int = js.json_setting(name="port", path="/endpoints/1", default=443)


class TertiarySettings(adv_settings.Settings):
    """A slot beyond the current end of the array."""

    host: str = js.json_setting(name="host", path="/endpoints/3", default="tertiary.example")


class OwnedArraySettings(adv_settings.Settings):
    """An array the library owns alone: deletable down to the last null."""

    host: str = js.json_setting(name="host", path="/standalone/0", default="solo.example")


SAMPLES_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = SAMPLES_DIR / "path-index-settings.json"


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def show_file() -> None:
    print(SETTINGS_FILE.read_text(encoding="utf-8"), end="")


def main() -> None:
    # every run starts from a clean slate
    SETTINGS_FILE.unlink(missing_ok=True)
    js.JSONSettingsConfiguration.file_path = SETTINGS_FILE

    section("a file written by another application: slots load from it")
    SETTINGS_FILE.write_text(
        json.dumps(
            {
                "endpoints": [
                    {"host": "core.example", "port": 8080},
                    {"host": "backup.example", "port": 443, "weight": 2},
                ]
            }
        ),
        encoding="utf-8",
    )
    FailoverSettings.load_settings()
    print(f"primary   = {FailoverSettings.primary_host!r}:{FailoverSettings.primary_port}")
    print(f"secondary = {FailoverSettings.secondary_host!r}:{FailoverSettings.secondary_port}")
    TertiarySettings.load_settings()
    print(f"tertiary  = {TertiarySettings.host!r}  (slot [3] does not exist -> default)")

    section("assign and save: values land inside the array elements")
    FailoverSettings.primary_host = "core-new.example"
    FailoverSettings.secondary_port = 8443
    TertiarySettings.host = "tertiary-new.example"
    TertiarySettings.save_settings()
    FailoverSettings.save_settings()
    show_file()
    print("(saving slot /3 extended the array, with a null at index 2; 'weight' is preserved)")

    section("delete one setting inside a shared element: only that key goes")
    # the lambda names the setting as code and is never called
    FailoverSettings.delete_setting(lambda s: s.secondary_port)
    show_file()
    print("(the element still has other keys, so it is kept as is)")

    section("delete all of the class: emptied elements become null")
    FailoverSettings.delete_settings()
    show_file()
    print("(/0 emptied -> null; /1 keeps its foreign 'weight' key; /3 is untouched)")

    section("the array survives while any element holds data")
    TertiarySettings.delete_setting(lambda s: s.host)
    show_file()
    print("(/3 emptied -> null; the foreign 'weight' key keeps the array from being dropped)")

    section("an array the library owns alone: all-null -> dropped")
    OwnedArraySettings.host = "solo.example"
    OwnedArraySettings.save_settings()
    show_file()
    OwnedArraySettings.delete_setting(lambda s: s.host)
    show_file()
    print("(the emptied slot 0 turned into a null, and an all-null array is dropped)")

    print(f"\nfile left for inspection: {SETTINGS_FILE}")


if __name__ == "__main__":
    main()
