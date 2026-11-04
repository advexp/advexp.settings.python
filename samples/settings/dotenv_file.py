"""
Example: using Advexp.Settings with the Dotenv plugin (a ``.env`` file).

Run from the repository root with the package and its extra installed
(``pip install "advexp-settings[dotenv]"``):

    python samples/settings/dotenv_file.py

The sample walks through the file backend of the environment family:

- declaring settings that live in a ``.env`` file;
- loading with type conversion;
- saving through the line editing of python-dotenv (comments and foreign
  lines stay as they were written);
- operations on a single setting;
- the naming options that are shared with the process environment backend;
- nested objects, addressed field by field;
- the binding of a class to a file.

The example works in a scratch directory that it creates and removes
afterwards. The process environment is never touched.
"""

import dataclasses
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as env_file


class ServerSettings(adv_settings.Settings):
    """Typed application settings that are backed by a ``.env`` file.

    Importing ``advexp.settings.plugins.environment.dotenv`` is what enables the
    backend. No registration calls are needed, because the plugin registers its
    attribute when its module is imported. The file is the module default:
    ``DotenvConfiguration.file_path``, which is ``.env`` in the working
    directory.
    """

    # members are declared through the dotenv_setting factory: assigning a
    # DotenvSetting instance is the same thing at runtime, but the analyzer
    # flags it (it cannot see the metaclass swapping the attribute for a
    # value descriptor)
    # explicit variable name; the annotated type drives conversion
    host: str = env_file.dotenv_setting(name="DEMO_HOST", default="localhost")
    port: int = env_file.dotenv_setting(name="DEMO_PORT", default=8080)
    debug: bool = env_file.dotenv_setting(name="DEMO_DEBUG", default=False)
    started_at: Optional[datetime] = env_file.dotenv_setting(name="DEMO_STARTED_AT", default=None)

    # a collection is annotated with its item type; the value round-trips
    # as JSON (a file variable holds a JSON array string)
    allowed_hosts: List[str] = env_file.dotenv_setting(
        name="DEMO_ALLOWED_HOSTS", default=["localhost"]
    )

    # no name= given: the member name becomes the variable name ("maintainer")
    maintainer: str = env_file.dotenv_setting(default="ops@example.com")


class WorkerSettings(
    adv_settings.Settings,
    options=env_file.dotenv_source(name_prefix="DEMO_WORKER_", name_case=env_file.NameCase.UPPER),
):
    """The naming options of the whole environment family, declared once per class.

    The options of the family govern this backend in exactly the same way as
    they govern the process environment backend. The variable name is
    ``name_prefix + name_case(member name)``, and an explicit ``name=`` (as
    ``legacy`` shows) is the full address and stays untouched.
    """

    mode: str = env_file.dotenv_setting(default="standby")  # DEMO_WORKER_MODE
    cache_ttl: int = env_file.dotenv_setting(default=300)  # DEMO_WORKER_CACHE_TTL
    legacy: str = env_file.dotenv_setting(name="legacy_flag", default="off")


@dataclasses.dataclass
class HealthConfig:
    """Level three of the nesting: an object inside an object inside one."""

    enabled: bool = True
    timeout: float = 5.0


@dataclasses.dataclass
class PoolConfig:
    """Level two: the database's pool, its health probe an object again."""

    size: int = 10
    health: HealthConfig = dataclasses.field(default_factory=HealthConfig)


@dataclasses.dataclass
class DbConfig:
    """A nested object: one settings member that holds a chain of dataclasses.

    ``pool`` makes the chain three classes deep, so a variable may address a
    field of any level through the nested delimiter of the family.
    """

    host: str = "localhost"
    port: int = 5432
    pool: PoolConfig = dataclasses.field(default_factory=PoolConfig)


class DatabaseSettings(
    adv_settings.Settings,
    # the backend's source builder carries the family's naming parameters
    # and the file in one declaration
    options=env_file.dotenv_source(
        file="database.env",
        name_prefix="DEMO_SITE_",
        name_case=env_file.NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    """A class with its own file and nested addressing, both declared on the class.

    ``dotenv_source(file=...)`` binds the class to a file of its own, and it wins
    over ``DotenvConfiguration.file_path``. This is the spelling for classes
    whose variables do not go into the single ``.env`` of the project.

    The nested delimiter opens the fields of the dataclass member:
    ``DEMO_SITE_DB__POOL__HEALTH__TIMEOUT`` addresses the ``timeout`` field of
    ``db.pool.health``, which is three classes nested into one another. Loading
    merges such variables onto the declared defaults (a partial update at every
    level), and saving stores each leaf field in its own variable.
    """

    db: DbConfig = env_file.dotenv_setting(default=DbConfig(host="declared-host"))


@contextmanager
def scratch_directory() -> Iterator[Path]:
    """Run the example inside a directory it owns and removes afterwards."""
    with tempfile.TemporaryDirectory() as scratch:
        previous = Path.cwd()
        os.chdir(scratch)
        try:
            yield Path(scratch)
        finally:
            os.chdir(previous)


def show_file(name: str) -> None:
    print(f"{name}:")
    for line in Path(name).read_text(encoding="utf-8").splitlines():
        print(f"    {line}")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # Optional: see what the library does under the hood
    adv_settings.LibraryConfiguration.set_log_level(logging.INFO)

    with scratch_directory():
        # simulate a file the deployment / a teammate wrote by hand: comments,
        # export lines and foreign variables live next to the settings'
        Path(".env").write_text(
            "# managed by the deployment team\n"
            "export DEMO_HOST=db.example.com\n"
            "DEMO_DEBUG=True  # parsed with the bool annotation in mind\n"
            "DEMO_STARTED_AT=2026-09-03T10:15:30\n"
            'DEMO_ALLOWED_HOSTS=["db-1.example.com", "db-2.example.com"]\n'
            "OTHER_TOOL_HOME=/opt/other\n",
            encoding="utf-8",
        )

        section("declare once, load anywhere")
        ServerSettings.load_settings()
        print(f"host          = {ServerSettings.host!r}")
        print(f"port          = {ServerSettings.port!r}  (no variable -> default)")
        print(f"debug         = {ServerSettings.debug!r}")
        # (Optional members print None at times; None does define __repr__, the
        # checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        print(f"started_at    = {ServerSettings.started_at!r}  (parsed ISO datetime)")
        print(f"maintainer    = {ServerSettings.maintainer!r}  (falls back to the member name)")
        print(
            f"allowed_hosts = {ServerSettings.allowed_hosts!r}  (parsed from a JSON array string)"
        )

        section("assign and save: only the saved lines move")
        ServerSettings.port = 5432
        # single setting; the string names the setting as code
        ServerSettings.save_setting("port")
        ServerSettings.maintainer = "dev@example.com"
        ServerSettings.save_settings()  # every declared setting at once
        show_file(".env")
        print("  (comments, export prefixes and foreign lines are kept exactly as written)")

        section("inspect and delete")
        print(f"contains_setting('port') = {ServerSettings.contains_setting('port')}")
        ServerSettings.delete_setting("port")
        print(
            f"after delete: contains = {ServerSettings.contains_setting('port')}, "
            f"value = {ServerSettings.port!r} (back to the default)"
        )

        section("reset to defaults without touching the file")
        ServerSettings.reset_settings()
        print(f"host = {ServerSettings.host!r}, debug = {ServerSettings.debug!r}")

        section("naming options of the environment family (prefix + case)")
        Path(".env").write_text("DEMO_WORKER_MODE=running\n", encoding="utf-8")
        WorkerSettings.load_settings()
        print(f"mode      = {WorkerSettings.mode!r}  (read from DEMO_WORKER_MODE)")
        WorkerSettings.cache_ttl = 600
        WorkerSettings.save_settings()
        print("cache_ttl was written as DEMO_WORKER_CACHE_TTL:")
        show_file(".env")
        print("legacy keeps the spelling given by its explicit name=: legacy_flag is written as is")

        # the options are regular class metadata: one runtime call re-aims the
        # whole class (the stored entry is replaced wholesale; no case here)
        WorkerSettings.set_class_metadata(
            env_file.ENVIRONMENT_METADATA_OPTIONS, {env_file.NAME_PREFIX: "DEMO_TMP_"}
        )
        WorkerSettings.reset_settings()
        WorkerSettings.mode = "switched"
        WorkerSettings.save_settings()
        print("after set_class_metadata, DEMO_TMP_mode was written to the file:")
        show_file(".env")

        section("nested objects: one variable per field, a partial update on load")
        Path("database.env").write_text(
            "DEMO_SITE_DB__PORT=6543\n"
            # the same partial update three classes deep: db -> pool -> health
            "DEMO_SITE_DB__POOL__HEALTH__TIMEOUT=2.5\n",
            encoding="utf-8",
        )
        DatabaseSettings.load_settings()
        print(f"db = {DatabaseSettings.db!r}")
        print("  (DEMO_SITE_DB__PORT changed only the port; the default host is kept)")
        print("  (DEMO_SITE_DB__POOL__HEALTH__TIMEOUT changed only the timeout)")
        DatabaseSettings.save_settings()
        show_file("database.env")
        DatabaseSettings.delete_settings()
        print("after delete_settings(): every address of the member has been removed")
        show_file("database.env")

        section("plugin access")
        plugin = ServerSettings.get_plugin(env_file.DotenvPlugin)
        print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")


if __name__ == "__main__":
    main()
