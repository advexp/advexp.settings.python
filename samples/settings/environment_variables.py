"""
Example: using Advexp.Settings with the Environment Variables plugin.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/environment_variables.py

The sample walks through the whole API that is available in the current
milestone: declaring settings, loading with type conversion, saving,
operations on a single setting, metadata, and plugin access.
"""

import dataclasses
import logging
import os
from datetime import datetime
from typing import List, Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as env


class ServerSettings(adv_settings.Settings):
    """Typed application settings that are backed by environment variables.

    Importing ``advexp.settings.plugins.environment.variables`` is what enables
    the backend. No registration calls are needed, because the plugin registers
    its attribute when its module is imported.
    """

    # members are declared through the env.environment_variable_setting factory:
    # assigning an EnvironmentVariableSetting instance is the same thing at
    # runtime, but the analyzer flags it (it cannot see the metaclass
    # swapping the attribute for a value descriptor)
    # explicit environment variable name; the annotated type drives conversion
    host: str = env.environment_variable_setting(name="DEMO_HOST", default="localhost")
    port: int = env.environment_variable_setting(name="DEMO_PORT", default=8080)
    debug: bool = env.environment_variable_setting(name="DEMO_DEBUG", default=False)
    started_at: Optional[datetime] = env.environment_variable_setting(
        name="DEMO_STARTED_AT", default=None
    )

    # a collection is annotated with its item type; the value round-trips
    # as JSON (an env var holds a JSON array string, the JSON backend an array)
    allowed_hosts: List[str] = env.environment_variable_setting(
        name="DEMO_ALLOWED_HOSTS", default=["localhost"]
    )

    # no name= given: the member name becomes the variable name ("maintainer")
    maintainer: str = env.environment_variable_setting(default="ops@example.com")


class WorkerSettings(
    adv_settings.Settings,
    options=env.env_source(name_prefix="DEMO_WORKER_", name_case=env.NameCase.UPPER),
):
    """The naming options of the whole environment family, declared once per class.

    The variable name is ``name_prefix + name_case(member name)``. An explicit
    ``name=`` (as ``legacy`` shows) is the full address and stays untouched.
    """

    mode: str = env.environment_variable_setting(default="standby")  # DEMO_WORKER_MODE
    cache_ttl: int = env.environment_variable_setting(default=300)  # DEMO_WORKER_CACHE_TTL
    legacy: str = env.environment_variable_setting(name="legacy_flag", default="off")

    # a renamed variable: the old spelling keeps serving the member beside the
    # new one. Aliases are full addresses like name= — the prefix and case
    # never touch them — and a load looks them up after the primary name,
    # so the deployment that still sets the old variable keeps working
    session_ttl: int = env.environment_variable_setting(
        name="DEMO_WORKER_SESSION_TTL", aliases=["DEMO_WORKER_TTL"], default=1800
    )


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
    options=env.env_source(
        name_prefix="DEMO_SITE_",
        name_case=env.NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    """Nested addressing: one variable may carry one field of any level.

    ``DEMO_SITE_DB__PORT`` addresses the ``port`` field of ``db`` through the
    nested delimiter of the family. ``DEMO_SITE_DB__POOL__HEALTH__TIMEOUT``
    addresses the ``timeout`` field of ``db.pool.health``, which is three
    classes nested into one another.

    Loading merges such variables onto the declared defaults (a partial update
    at every level), and saving stores each leaf field in its own variable.
    """

    db: DbConfig = env.environment_variable_setting(default=DbConfig(host="declared-host"))


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # Optional: see what the library does under the hood
    adv_settings.LibraryConfiguration.set_log_level(logging.INFO)

    # simulate an environment configured by the deployment / CI / .env file
    os.environ["DEMO_HOST"] = "db.example.com"
    os.environ["DEMO_DEBUG"] = "True"  # parsed with the bool annotation in mind
    os.environ["DEMO_STARTED_AT"] = "2026-09-03T10:15:30"
    os.environ["DEMO_ALLOWED_HOSTS"] = '["db-1.example.com", "db-2.example.com"]'

    section("declare once, load anywhere")
    ServerSettings.load_settings()
    print(f"host       = {ServerSettings.host!r}")
    print(f"port       = {ServerSettings.port!r}  (no env var -> default)")
    print(f"debug      = {ServerSettings.debug!r}")
    # (Optional members print None at times; None does define __repr__, the
    # checker's stub view says otherwise)
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {ServerSettings.started_at!r}  (parsed ISO datetime)")
    print(f"maintainer = {ServerSettings.maintainer!r}  (falls back to the member name)")
    print(f"allowed_hosts = {ServerSettings.allowed_hosts!r}  (parsed from a JSON array string)")

    section("assign and save")
    ServerSettings.port = 5432
    # single setting; the lambda names the setting as code and is never called
    ServerSettings.save_setting(lambda s: s.port)
    print(f"DEMO_PORT in environment = {os.environ['DEMO_PORT']!r}")

    ServerSettings.debug = False
    ServerSettings.save_settings()  # every declared setting at once
    ServerSettings.load_settings()
    print(f"DEMO_DEBUG in environment = {os.environ['DEMO_DEBUG']!r}")

    section("inspect and delete")
    print(f"contains_setting('port') = {ServerSettings.contains_setting('port')}")
    ServerSettings.delete_setting(lambda s: s.port)
    print(
        f"after delete: contains = {ServerSettings.contains_setting('port')}, "
        f"value = {ServerSettings.port!r} (back to the default)"
    )

    section("reset to defaults without touching the environment")
    ServerSettings.reset_settings()
    print(f"host = {ServerSettings.host!r}, debug = {ServerSettings.debug!r}")

    section("runtime metadata (a channel between your code and a backend)")
    ServerSettings.set_setting_metadata(lambda s: s.host, "my-backend-parameter", "some-value")
    print(f"metadata = {ServerSettings.get_setting_metadata('host', 'my-backend-parameter')!r}")
    ServerSettings.set_class_metadata("environment", "production")
    print(f"class metadata = {ServerSettings.get_class_metadata('environment')!r}")

    section("naming options of the environment family (prefix + case)")
    os.environ["DEMO_WORKER_MODE"] = "running"
    WorkerSettings.load_settings()
    print(f"mode      = {WorkerSettings.mode!r}  (read from DEMO_WORKER_MODE)")
    WorkerSettings.cache_ttl = 600
    WorkerSettings.save_settings()
    print(
        f"cache_ttl was written as DEMO_WORKER_CACHE_TTL = {os.environ['DEMO_WORKER_CACHE_TTL']!r}"
    )
    print("legacy keeps the spelling given by its explicit name=: legacy_flag is written as is")

    section("aliases: a renamed variable keeps the old spelling working")
    # only the pre-rename variable is set: the alias serves the member (the
    # save above wrote the primary name; a fresh deployment sets none of them)
    os.environ.pop("DEMO_WORKER_SESSION_TTL", None)
    os.environ["DEMO_WORKER_TTL"] = "900"
    WorkerSettings.load_settings()
    print(f"session_ttl = {WorkerSettings.session_ttl!r}  (read from the alias DEMO_WORKER_TTL)")
    # the primary name outranks every alias once it is set
    os.environ["DEMO_WORKER_SESSION_TTL"] = "1200"
    WorkerSettings.load_settings()
    print(f"session_ttl = {WorkerSettings.session_ttl!r}  (the primary name takes precedence)")
    # the write direction serves the primary name alone
    WorkerSettings.session_ttl = 1500
    WorkerSettings.save_setting(lambda s: s.session_ttl)
    print(f"after save: DEMO_WORKER_SESSION_TTL = {os.environ['DEMO_WORKER_SESSION_TTL']!r}")
    # and delete clears both addresses, so the value cannot come back
    WorkerSettings.delete_setting(lambda s: s.session_ttl)
    print(
        f"after delete: DEMO_WORKER_TTL was removed from the environment "
        f"({'DEMO_WORKER_TTL' not in os.environ})"
    )

    # the options are regular class metadata: one runtime call re-aims the
    # whole class (the stored entry is replaced wholesale; no case here)
    WorkerSettings.set_class_metadata(
        env.ENVIRONMENT_METADATA_OPTIONS, {env.NAME_PREFIX: "DEMO_TMP_"}
    )
    WorkerSettings.reset_settings()
    WorkerSettings.mode = "switched"
    WorkerSettings.save_settings()
    print(f"after set_class_metadata: DEMO_TMP_mode = {os.environ['DEMO_TMP_mode']!r}")
    os.environ.pop("DEMO_TMP_mode", None)
    os.environ.pop("DEMO_WORKER_CACHE_TTL", None)

    section("nested objects: one variable per field, a partial update on load")
    os.environ["DEMO_SITE_DB__PORT"] = "6543"
    # the same partial update three classes deep: db -> pool -> health
    os.environ["DEMO_SITE_DB__POOL__HEALTH__TIMEOUT"] = "2.5"
    DatabaseSettings.load_settings()
    print(f"db = {DatabaseSettings.db!r}")
    print("  (DEMO_SITE_DB__PORT changed only the port; the default host is kept)")
    print("  (DEMO_SITE_DB__POOL__HEALTH__TIMEOUT changed only the timeout)")
    DatabaseSettings.save_settings()
    print(
        "after save, each field is written separately: DEMO_SITE_DB__HOST = "
        f"{os.environ['DEMO_SITE_DB__HOST']!r}"
    )
    deep_leaf = "DEMO_SITE_DB__POOL__HEALTH__TIMEOUT"
    print(f"and the leaf at the third nesting level: {deep_leaf} = {os.environ[deep_leaf]!r}")
    DatabaseSettings.delete_settings()

    section("plugin access")
    plugin = ServerSettings.get_plugin(env.EnvironmentVariablesPlugin)
    print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")

    # clean up the variables this example created
    for name in ("DEMO_HOST", "DEMO_DEBUG", "DEMO_STARTED_AT", "DEMO_ALLOWED_HOSTS"):
        os.environ.pop(name, None)
    ServerSettings.delete_settings()


if __name__ == "__main__":
    main()
