"""
Example: using Advexp.Configuration with the TOML file source.

Run from the repository root with the package installed
(``pip install "advexp-configuration[toml]"``):

    python samples/configuration/toml_configuration.py

The sample walks through the read-only flow of a file source:

- the default file link of the module (``options=toml_source(file=...)``);
- loading with type conversion;
- keys that are located in the document tree through ``path=`` (a JSON
  Pointer);
- required members that abort the load with the error that has an entry for
  each member;
- the file itself, which is never written: a configuration source is only
  ever read.

The configuration file is written next to this script at startup (the own
hand of the sample, which stands in for whatever deploys configuration in a
real application), and it is removed afterwards, so every run starts clean.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import advexp.configuration as adv_config
import advexp.configuration.plugins.toml_settings as ts

SAMPLES_DIR = Path(__file__).resolve().parent
APP_CONFIG_FILE = SAMPLES_DIR / "app-configuration.toml"
WINDOW_CONFIG_FILE = SAMPLES_DIR / "window-configuration.toml"


@dataclass
class Proxy:
    """A user-defined value type: stored as a TOML table of its fields."""

    host: str
    port: int = 3128
    since: Optional[datetime] = None


class ServerConfig(
    adv_config.Configuration,
    options=ts.toml_source(file=APP_CONFIG_FILE),
):
    """Typed application configuration that is read from a TOML file.

    Declare members through the ``toml_setting`` factory. Assigning a
    ``TOMLSetting`` instance does the same thing at runtime, but type checkers
    report a type mismatch for it (they cannot see that the metaclass replaces
    the attribute with a value descriptor).
    """

    # explicit storage name: the file key is exactly "host"; no name=
    # builds the full pattern name (namespace.class.member)
    host: str = ts.toml_setting(name="host", default="localhost")
    debug: bool = ts.toml_setting(name="debug", default=False)
    started_at: Optional[datetime] = ts.toml_setting(name="started_at", default=None)
    # dataclasses work directly and inside Optional
    proxy: Optional[Proxy] = ts.toml_setting(name="proxy", default=None)
    # the optional path= locates the key in the document tree, as a JSON
    # Pointer: slash-separated segments (path=None or "" = the document
    # root); /service/database nests the key two levels deep
    db_host: str = ts.toml_setting(name="host", path="/service/database", default="localhost")
    db_port: int = ts.toml_setting(name="port", path="/service/database", default=5432)
    # a digits-only segment indexes into an array when the node it steps
    # into is one: the key lives inside that element
    primary_region: str = ts.toml_setting(name="region", path="/replicas/0", default="eu")
    secondary_region: str = ts.toml_setting(name="region", path="/replicas/1", default="us")


class WindowConfig(
    adv_config.Configuration,
    options=ts.toml_source(file=WINDOW_CONFIG_FILE),
):
    """A configuration class with its own file, independent of the module
    default."""

    width: int = ts.toml_setting(name="width", default=800)
    height: int = ts.toml_setting(name="height", default=600)


class SecretsConfig(
    adv_config.Configuration,
    options=ts.toml_source(file=SAMPLES_DIR / "secrets.toml"),
):
    """Required members of a file source: what their absence looks like."""

    api_key: str = ts.toml_setting(name="api_key")
    renew_after: Optional[datetime] = ts.toml_setting(name="renew_after", default=None)


def section(title: str) -> None:
    print(f"\n--- {title} ---", flush=True)


def write_app_file() -> None:
    """Deploy the configuration file: this is the own hand of the sample.

    The package never writes this file: its sources are read-only, and this is
    the main difference between it and ``advexp.settings``. The file is plain
    TOML that a person could have edited: datetimes are native, and the tables
    are laid out by hand.
    """
    APP_CONFIG_FILE.write_text(
        "\n".join(
            (
                'host = "db.example.com"',
                "debug = true",
                "started_at = 2026-10-09 12:30:00",
                "",
                "[proxy]",
                'host = "proxy.example"',
                "port = 8080",
                "",
                "[service.database]",
                'host = "db.internal"',
                "port = 5432",
                "",
                "[[replicas]]",
                'region = "eu-west"',
                "",
                "[[replicas]]",
                'region = "us-east"',
            )
        ),
        encoding="utf-8",
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="log: %(message)s")

    # every run starts from a clean slate
    APP_CONFIG_FILE.unlink(missing_ok=True)
    WINDOW_CONFIG_FILE.unlink(missing_ok=True)

    section("a missing file behaves as an empty one: defaults serve")
    ServerConfig.load_configuration()
    print(f"host       = {ServerConfig.host!r}")
    print(f"db_port    = {ServerConfig.db_port!r} (the default for the /service/database path)")

    section("the deployed file: values, conversion, JSON Pointers")
    write_app_file()
    ServerConfig.load_configuration()
    print(f"host       = {ServerConfig.host!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {ServerConfig.started_at!r}  (native TOML datetime)")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"proxy      = {ServerConfig.proxy!r}  (TOML table -> dataclass)")
    print(f"db_host    = {ServerConfig.db_host!r}  (read from the nested path /service/database)")
    print(f"replicas   = {ServerConfig.primary_region!r}, {ServerConfig.secondary_region!r}")
    print(
        "the file, which the package only reads and never "
        f"writes:\n{APP_CONFIG_FILE.read_text(encoding='utf-8')}"
    )

    section("a class's own link: options=toml_source(file=...)")
    WINDOW_CONFIG_FILE.write_text("width = 1024\nheight = 768\n", encoding="utf-8")
    WindowConfig.load_configuration()
    print(f"window     = {WindowConfig.width!r}x{WindowConfig.height!r} (its own file)")
    # the module default never served WindowConfig — and ServerConfig
    # keeps reading its own
    print(f"server     = {ServerConfig.host!r} (the file of its own link)")

    section("required members of a file source abort the load, all at once")
    try:
        SecretsConfig.load_configuration()  # no secrets.toml exists
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")

    # cleanup: the package never wrote any of these — the sample did
    APP_CONFIG_FILE.unlink(missing_ok=True)
    WINDOW_CONFIG_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
