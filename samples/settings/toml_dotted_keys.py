"""
Example: dotted keys and quoted segments in the TOML plugin of
Advexp.Settings.

Run from the repository root with the package installed
(``pip install "advexp-settings[toml]"``):

    python samples/settings/toml_dotted_keys.py

Every dot in the key of a setting is a table level, and the last part is the
key. For example, ``name="app.ServiceConfig.port"`` stores ``port = 8080``
inside the ``[app.ServiceConfig]`` table, and never a quoted flat key such
as ``"app.ServiceConfig.port"``.

A ``path=`` segment is never split at a dot. ``path="/endpoints/api.internal"``
steps into the table whose key is ``api.internal``, and the key is written in
quotes, because a bare TOML key cannot contain a dot.

A segment that consists only of digits indexes an array. The array grows by
one element at its tail and no further: TOML has no null to fill a gap with,
so the save of a slot beyond the tail is refused with an error that says so.

The settings file is written next to this script and removed at startup, so
every run starts from a clean slate.
"""

from pathlib import Path

import advexp.settings as adv_settings
import advexp.settings.plugins.toml_settings as ts


class ServiceConfig(adv_settings.Settings):
    """A dotted name: every dot nests a table level."""

    port: int = ts.toml_setting(name="app.ServiceConfig.port", default=8080)
    region: str = ts.toml_setting(name="app.ServiceConfig.region", default="eu")


class Endpoint(adv_settings.Settings):
    """A dot inside a path segment: the key lands in quotes."""

    api: str = ts.toml_setting(name="api", path="/endpoints/api.internal", default="v1")


class MirrorSlot(adv_settings.Settings):
    """A digits-only segment: a slot of an array of tables."""

    host: str = ts.toml_setting(name="host", path="/mirrors/0", default="primary.example")


class MirrorTail(adv_settings.Settings):
    """The slot right after the current tail: the array grows to it."""

    host: str = ts.toml_setting(name="host", path="/mirrors/1", default="secondary.example")


class FarMirror(adv_settings.Settings):
    """A slot beyond the tail: a gap would be needed, and the save refuses."""

    host: str = ts.toml_setting(name="host", path="/mirrors/5", default="far.example")


SAMPLES_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = SAMPLES_DIR / "dotted-keys-settings.toml"


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def show_file() -> None:
    print(SETTINGS_FILE.read_text(encoding="utf-8"), end="")


def main() -> None:
    # every run starts from a clean slate
    SETTINGS_FILE.unlink(missing_ok=True)
    ts.TOMLSettingsConfiguration.file_path = SETTINGS_FILE

    section("a digits-only segment: a slot of an array of tables")
    MirrorSlot.host = "core.example"
    MirrorSlot.save_settings()
    show_file()
    print("(slot /0 created the first [[mirrors]] row)")

    section("the tail grows by one element, no further")
    MirrorTail.host = "backup.example"
    MirrorTail.save_settings()
    show_file()
    FarMirror.host = "far.example"
    try:
        FarMirror.save_settings()
    except ValueError as error:
        print(f"slot /5 was refused -> ValueError: {error}")

    section("a dotted name and a dotted path segment join the document")
    ServiceConfig.save_settings()
    Endpoint.save_settings()
    show_file()
    print('(the name was split into nested tables; the path segment "api.internal" is quoted)')

    section("delete: the emptied path tables go with the setting")
    # the lambda names the setting as code and is never called
    Endpoint.delete_setting(lambda s: s.api)
    show_file()
    print('(the [endpoints."api.internal"] table has been removed; ServiceConfig is kept)')

    section("a file written by another application: slots load from it")
    SETTINGS_FILE.write_text(
        '[[mirrors]]\nhost = "core.example"\n\n[[mirrors]]\nhost = "backup.example"\n',
        encoding="utf-8",
    )
    MirrorTail.load_settings()
    print(f"loaded /1 host = {MirrorTail.host!r} (the row written by the other application)")

    print(f"\nfile left for inspection: {SETTINGS_FILE}")


if __name__ == "__main__":
    main()
