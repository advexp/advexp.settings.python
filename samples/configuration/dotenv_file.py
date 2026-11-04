"""
Example: using Advexp.Configuration with the Dotenv source (a ``.env`` file).

Run from the repository root with the package and its extra installed
(``pip install "advexp-configuration[dotenv]"``):

    python samples/configuration/dotenv_file.py

The sample walks through the read-only flow of the package over a ``.env``
file:

- declaring members (required by default, with an occasional ``default=``
  standing in);
- the naming options of the environment family, declared on the own link of
  the class (per declaring class, so the own naming of a subclass never
  changes the variables of inherited members);
- nested objects, addressed field by field through the delimiter of the
  family;
- loading with type conversion and constraints;
- load errors, which are reported all at once;
- the write guard;
- snapshots;
- the file of the link, and plugin access.

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
from typing import Dict, Iterator, List, Optional

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.dotenv as env_file


class AppConfig(
    adv_config.Configuration,
    options=env_file.dotenv_source(
        file=".env", name_prefix="DEMO_APP_", name_case=env_file.NameCase.UPPER
    ),
):
    """Typed application configuration that is read from a ``.env`` file.

    Importing ``advexp.configuration.plugins.environment.dotenv`` is what
    enables the source. No registration calls are needed, because the plugin
    registers its attribute when its module is imported.

    The ``options=`` keyword of the class carries the source link. Its ``file=``
    names the file, and the naming parameters declare the dictionary of the
    environment family for this class. The variable name is
    ``name_prefix + name_case(member name)``, so ``host`` reads
    ``DEMO_APP_HOST``. An explicit ``name=`` (``legacy_token`` below) is the full
    address in the storage and stays untouched. It is the escape hatch for
    variables that must keep their exact spelling.
    """

    # members are declared through the dotenv_setting factory: assigning a
    # DotenvSetting instance is the same thing at runtime, but the analyzer
    # flags it (it cannot see the metaclass swapping the attribute for a
    # value descriptor)

    # no default= given: the member is required; the package's sources
    # default to REQUIRED, so the value must come from the file and nothing
    # stands in when the variable is missing
    host: str = env_file.dotenv_setting()  # DEMO_APP_HOST
    started_at: datetime = env_file.dotenv_setting()  # DEMO_APP_STARTED_AT
    # a collection is annotated with its item type; the value arrives as a
    # JSON array string: a file variable holds strings only
    allowed_hosts: List[str] = env_file.dotenv_setting()  # DEMO_APP_ALLOWED_HOSTS
    # an integration variable with a fixed name: name= opts out of the
    # family's prefix and case
    legacy_token: str = env_file.dotenv_setting(name="DEMO_LEGACY_TOKEN")

    # a default is the opt-in stand-in: the member takes it when the
    # variable holds nothing usable. One or two per class is the healthy
    # shape: a configuration class full of defaults configures nothing
    port: int = env_file.dotenv_setting(default=8080, ge=1, le=65535)
    debug: bool = env_file.dotenv_setting(default=False)


class ServiceConfig(
    adv_config.Configuration,
    options=env_file.dotenv_source(
        file=".env", name_prefix="DEMO_SVC_", name_case=env_file.NameCase.UPPER
    ),
):
    """The link and the own keys of the application in one class.

    ``options=`` carries the source link, and the ``class_metadata`` of the body
    carries the own keys of the application. The two channels are merged at the
    ``class`` statement: the chain is stored under its own key, and the free keys
    are stored next to it.
    """

    class_metadata = {"config-version": 2}

    mode: str = env_file.dotenv_setting(default="production")  # DEMO_SVC_MODE


class TunedConfig(
    ServiceConfig,
    options=env_file.dotenv_source(
        file=".env", name_prefix="DEMO_TUNED_", name_case=env_file.NameCase.UPPER
    ),
):
    """The own naming of a subclass never changes the variables of inherited
    members.

    The naming dictionary is stored per declaring class. The link of this class
    governs the members that it declares (``region`` below), while the inherited
    ``mode`` keeps resolving by the entry of ``ServiceConfig`` (``DEMO_SVC_MODE``,
    not renamed here).
    """

    region: str = env_file.dotenv_setting(default="eu")  # DEMO_TUNED_REGION


class RetunedConfig(
    ServiceConfig,
    options=env_file.dotenv_source(
        file=".env", name_prefix="DEMO_RETUNED_", name_case=env_file.NameCase.UPPER
    ),
):
    """Retune a branch, for this class and below only.

    The own chain of the subclass replaces the chain of its base class for the
    subclass. A member that is redeclared in the subclass resolves by the naming
    of the subclass: here ``mode`` reads ``DEMO_RETUNED_MODE`` inside
    ``RetunedConfig``, while ``ServiceConfig`` itself and its other subclasses
    keep their own variables.
    """

    mode: str = env_file.dotenv_setting(default="production")  # DEMO_RETUNED_MODE


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
    """A nested object: one member that holds a chain of dataclasses.

    ``pool`` makes the chain three classes deep, so a variable may address a
    field of any level through the nested delimiter of the family.
    """

    host: str = "localhost"
    port: int = 5432
    pool: PoolConfig = dataclasses.field(default_factory=PoolConfig)


class DatabaseConfig(
    adv_config.Configuration,
    options=env_file.dotenv_source(
        file="database.env",
        name_prefix="DEMO_DB_",
        name_case=env_file.NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    """A class with its own file and nested addressing, both declared on the link.

    The ``file=`` of the link names the file that the class reads, and the
    nested delimiter of the family opens the fields of the dataclass members to
    the variables. ``DEMO_DB_CONN__PORT`` addresses the ``port`` field of
    ``conn``, and ``DEMO_DB_CONN__POOL__HEALTH__TIMEOUT`` addresses the
    ``timeout`` field of ``conn.pool.health``.

    Loading updates the object partially: the declared default instance is the
    base, and fields that no variable addresses keep the declared values. A
    required member assembles its object from the field variables alone, and a
    branch of the chain that no variable addresses takes the own field defaults
    of the dataclass. The whole-object form also works: the own variable of the
    member may carry the object as a JSON object, and a per-field variable wins
    over it.
    """

    conn: DbConfig = env_file.dotenv_setting(default=DbConfig(host="declared-host"))
    reader: DbConfig = env_file.dotenv_setting()  # required: assembled by fields


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


def write_env(name: str, lines: List[str]) -> None:
    Path(name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def app_env(**overrides: Optional[str]) -> List[str]:
    """The ``.env`` lines of the full set of variables of ``AppConfig``, retuned per
    keyword.

    A keyword replaces the value of one variable, and ``None`` drops the
    variable. The file is rewritten as a whole, so the sections below retune one
    or two members while the rest of the set stays in place.
    """
    values: Dict[str, Optional[str]] = {
        "DEMO_APP_HOST": "db.example.com",
        "DEMO_APP_DEBUG": "True",
        "DEMO_APP_STARTED_AT": "2026-09-03T10:15:30",
        "DEMO_APP_ALLOWED_HOSTS": '["db-1.example.com", "db-2.example.com"]',
        "DEMO_LEGACY_TOKEN": "legacy-value",
    }
    values.update(overrides)
    return [f"{name}={value}" for name, value in values.items() if value is not None]


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # Optional: see what the library does under the hood
    adv_config.LibraryConfiguration.set_log_level(logging.INFO)

    with scratch_directory():
        # simulate a file the deployment / a teammate wrote by hand;
        # DEMO_APP_PORT is left out on purpose: the default stands in
        write_env(
            ".env",
            [
                "# managed by the deployment team",
                "DEMO_APP_HOST=db.example.com",
                "DEMO_APP_DEBUG=True  # parsed with the bool annotation in mind",
                "DEMO_APP_STARTED_AT=2026-09-03T10:15:30",
                'DEMO_APP_ALLOWED_HOSTS=["db-1.example.com", "db-2.example.com"]',
                "DEMO_LEGACY_TOKEN=legacy-value",
            ],
        )

        section("declare once, load anywhere")
        AppConfig.load_configuration()
        print(f"host          = {AppConfig.host!r}")
        print(f"port          = {AppConfig.port!r}  (no variable -> default)")
        print(f"debug         = {AppConfig.debug!r}")
        print(f"started_at    = {AppConfig.started_at!r}  (parsed ISO datetime)")
        print(f"allowed_hosts = {AppConfig.allowed_hosts!r}  (parsed from a JSON array string)")
        print(f"legacy_token  = {AppConfig.legacy_token!r}  (name= keeps its exact spelling)")

        section("the link and the body's free keys — one channel")
        # ServiceConfig (above) uses both spellings: the environment
        # family's entry goes into options=, the free "config-version" key
        # sits in the body's class_metadata; it is one channel, merged at
        # the class statement
        write_env(".env", ["DEMO_SVC_MODE=staging"])
        ServiceConfig.load_configuration()
        print(f"mode           = {ServiceConfig.mode!r}  (DEMO_SVC_ + the upper-cased member name)")
        metadata = ServiceConfig.get_plugin(env_file.DotenvPlugin).context.get_class_metadata(
            "config-version"
        )
        print(
            f"config-version = {metadata!r}  (the key declared in the class body is read "
            "through the same channel)"
        )

        section("per-class family entries: a subclass keeps the inherited names")
        # TunedConfig declares its own options: they build its own member's
        # variable, while the inherited mode keeps ServiceConfig's
        # variable; the entry of the class that declared the member
        # governs it
        write_env(".env", ["DEMO_SVC_MODE=production", "DEMO_TUNED_REGION=us"])
        TunedConfig.load_configuration()
        print(
            f"mode   = {TunedConfig.mode!r}   (the base class's DEMO_SVC_MODE; the "
            "variable is not renamed)"
        )
        print(f"region = {TunedConfig.region!r}  (the subclass's own DEMO_TUNED_ prefix)")
        # RetunedConfig retunes the branch inside itself only: its own
        # chain and the redeclared member read by its own naming
        write_env(".env", ["DEMO_RETUNED_MODE=staging"])
        RetunedConfig.load_configuration()
        print(f"mode   = {RetunedConfig.mode!r}  (redeclared, so the subclass's naming applies)")
        write_env(".env", ["DEMO_SVC_MODE=production"])
        ServiceConfig.load_configuration()
        print(f"mode   = {ServiceConfig.mode!r}   (the ancestor itself keeps its variable)")

        section("nested objects: one variable per field, a partial update on load")
        # conn declares a default: the single addressed field moves, the rest
        # of the object keeps the declared values
        # reader is required: the file assembles its object from the field
        # variables alone; the health branch no variable addresses takes the
        # dataclass's own field defaults
        write_env(
            "database.env",
            [
                "DEMO_DB_CONN__PORT=6543",
                # the same partial update three classes deep: conn -> pool -> health
                "DEMO_DB_CONN__POOL__HEALTH__TIMEOUT=2.5",
                "DEMO_DB_READER__HOST=reader.example.com",
                "DEMO_DB_READER__POOL__SIZE=5",
            ],
        )
        DatabaseConfig.load_configuration()
        print(f"conn   = {DatabaseConfig.conn!r}")
        print("  (DEMO_DB_CONN__PORT changed only the port; the default host is kept)")
        print(f"reader = {DatabaseConfig.reader!r}  (assembled from three variables)")
        # the whole-object form: the member's own variable may carry the
        # object as a JSON object, a per-field variable winning over it
        write_env(
            "database.env",
            ['DEMO_DB_CONN={"host": "json-host", "port": 1}', "DEMO_DB_READER__HOST=r.example.com"],
        )
        DatabaseConfig.load_configuration()
        print(f"conn   = {DatabaseConfig.conn!r}  (the whole object given as JSON)")

        section("a constraint-violating value falls back to the default")
        # app_env() writes AppConfig's full set; a keyword retunes one
        # variable, None drops it
        write_env(".env", app_env(DEMO_APP_PORT="70000"))
        AppConfig.load_configuration()
        print(f"port = {AppConfig.port!r}  (70000 violates le=65535 -> default, see the log)")

        section("a member without a default is required")
        write_env(".env", app_env(DEMO_APP_HOST=None))
        try:
            # the failing load is the point of the demo: the checker cannot
            # see it raising
            AppConfig.load_configuration()
        except adv_config.AggregateLoadError as error:
            # one failure or several: the abort is always adv_config.AggregateLoadError
            print(f"load aborted: {error}")
        # the failed member keeps the value the last successful load
        # brought in: a required member never serves a stand-in
        print(f"host = {AppConfig.host!r}  (the last loaded value is kept)")
        write_env(".env", app_env())
        AppConfig.load_configuration()
        print(f"host = {AppConfig.host!r}  (loaded again once the variable is restored)")

        section("several failing members report all at once")
        # two members fail in one pass: a missing variable and a value
        # that does not convert; the pass walks every member, then one
        # abort lists both failures
        write_env(".env", app_env(DEMO_APP_HOST=None, DEMO_APP_STARTED_AT="not-a-timestamp"))
        try:
            # the failing load is the point of the demo: the checker cannot
            # see it raising
            AppConfig.load_configuration()
        except adv_config.AggregateLoadError as error:
            print(f"load aborted, {len(error.errors)} members failed:")
            for member_error in error.errors:
                print(f"  - {member_error}")
        # the failed members keep their last loaded values; every other member
        # of the pass reloaded as usual
        print(
            f"started_at = {AppConfig.started_at!r}  (a value that cannot be "
            "converted is never stored)"
        )
        write_env(".env", app_env())
        AppConfig.load_configuration()
        print(
            f"started_at = {AppConfig.started_at!r}  (both load again once the variables are fixed)"
        )

        section("the values are read-only: the load is the one writer")
        try:
            AppConfig.host = "blocked.example.com"
        except TypeError as error:
            print(f"assignment blocked: {error}")

        section("snapshots: a frozen view of the loaded values")
        as_dict = AppConfig.to_dict()
        print(f"to_dict() = {as_dict}")
        try:
            # the failing assignment is the point of the demo: the checker cannot
            # see it raising
            as_dict["host"] = "blocked.example.com"  # type: ignore[index]
        except TypeError as error:
            print(f"item write blocked: {error}")
        # dict(...) hands out the mutable copy; it shares nothing with the class
        mutable = dict(as_dict)
        mutable["host"] = "mutated"
        print(f"after mutating the copy: host = {AppConfig.host!r}")

        as_object = AppConfig.to_object()
        print(f"to_object() = {type(as_object).__name__} with fields of its own")
        try:
            # a snapshot is frozen too; the checker cannot see the raise
            as_object.host = "blocked.example.com"
        except TypeError as error:
            print(f"snapshot write blocked: {error}")

        section("plugin access")
        plugin = AppConfig.get_plugin(env_file.DotenvPlugin)
        print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")
        # the files are the links' own: each class reads the one its chain
        # names — .env for AppConfig, database.env for DatabaseConfig
        print("AppConfig reads .env, DatabaseConfig reads database.env (each through its own link)")


if __name__ == "__main__":
    main()
