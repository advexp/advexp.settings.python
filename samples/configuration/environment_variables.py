"""
Example: using Advexp.Configuration with the Environment Variables source.

Run from the repository root with the package installed
(``pip install advexp-configuration``):

    python samples/configuration/environment_variables.py

The sample walks through the read-only flow of the package:

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
- snapshots and plugin access.
"""

import dataclasses
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as env


class AppConfig(
    adv_config.Configuration,
    options=env.env_source(name_prefix="DEMO_APP_", name_case=env.NameCase.UPPER),
):
    """Typed application configuration that is read from environment variables.

    Importing ``advexp.configuration.plugins.environment.variables`` is what
    enables the source. No registration calls are needed, because the plugin
    registers its attribute when its module is imported.

    The ``options=`` keyword of the class carries the source link, and its
    naming parameters declare the dictionary of the environment family for this
    class. The variable name is ``name_prefix + name_case(member name)``, so
    ``host`` reads ``DEMO_APP_HOST``. An explicit ``name=`` (``legacy_token``
    below) is the full address in the storage and stays untouched. It is the
    escape hatch for variables that must keep their exact spelling.
    """

    # members are declared through the env.environment_variable_setting factory:
    # assigning an EnvironmentVariableSetting instance is the same thing at
    # runtime, but the analyzer flags it (it cannot see the metaclass
    # swapping the attribute for a value descriptor)

    # no default= given: the member is required; the package's sources
    # default to REQUIRED, so the value must come from the environment and
    # nothing stands in when the variable is missing
    host: str = env.environment_variable_setting()  # DEMO_APP_HOST
    started_at: datetime = env.environment_variable_setting()  # DEMO_APP_STARTED_AT
    # a collection is annotated with its item type; the value arrives as a
    # JSON array string: the environment holds strings only
    allowed_hosts: List[str] = env.environment_variable_setting()  # DEMO_APP_ALLOWED_HOSTS
    # an integration variable with a fixed name: name= opts out of the
    # family's prefix and case
    legacy_token: str = env.environment_variable_setting(name="DEMO_LEGACY_TOKEN")

    # a renamed variable: the old spelling keeps serving the member. Aliases
    # are full addresses like name=, and a load tries them after the primary
    # name — the deployment that still sets the old variable keeps working
    session_ttl: int = env.environment_variable_setting(
        default=1800, aliases=["DEMO_APP_TTL"]
    )  # primary: DEMO_APP_SESSION_TTL

    # a default is the opt-in stand-in: the member takes it when the
    # variable holds nothing usable. One or two per class is the healthy
    # shape: a configuration class full of defaults configures nothing
    port: int = env.environment_variable_setting(default=8080, ge=1, le=65535)
    debug: bool = env.environment_variable_setting(default=False)


class ServiceConfig(
    adv_config.Configuration,
    options=env.env_source(name_prefix="DEMO_SVC_", name_case=env.NameCase.UPPER),
):
    """Both spellings of the metadata declaration of the class, in one class.

    ``options=`` carries the source link, and the ``class_metadata`` of the body
    carries the own keys of the application. The two channels are merged at the
    ``class`` statement: the chain is stored under its own key, and the free keys
    are stored next to it.
    """

    class_metadata = {"config-version": 2}

    mode: str = env.environment_variable_setting(default="production")  # DEMO_SVC_MODE


class TunedConfig(
    ServiceConfig,
    options=env.env_source(name_prefix="DEMO_TUNED_", name_case=env.NameCase.UPPER),
):
    """The own naming of a subclass never changes the variables of inherited
    members.

    The naming dictionary is stored per declaring class. The link of this class
    governs the members that it declares (``region`` below), while the inherited
    ``mode`` keeps resolving by the entry of ``ServiceConfig`` (``DEMO_SVC_MODE``,
    not renamed here). Each class holds its own storage, so the two coexist.
    """

    region: str = env.environment_variable_setting(default="eu")  # DEMO_TUNED_REGION


class RetunedConfig(
    ServiceConfig,
    options=env.env_source(name_prefix="DEMO_RETUNED_", name_case=env.NameCase.UPPER),
):
    """Retune a branch, for this class and below only.

    The own chain of the subclass replaces the chain of its base class for the
    subclass. A member that is redeclared in the subclass resolves by the naming
    of the subclass: here ``mode`` reads ``DEMO_RETUNED_MODE`` inside
    ``RetunedConfig``, while ``ServiceConfig`` itself and its other subclasses
    keep their own variables.
    """

    mode: str = env.environment_variable_setting(default="production")  # DEMO_RETUNED_MODE


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
    options=env.env_source(
        name_prefix="DEMO_DB_",
        name_case=env.NameCase.UPPER,
        nested_delimiter="__",
    ),
):
    """Nested addressing: one variable may carry one field of any level.

    The nested delimiter of the family opens the fields of the dataclass members
    to the variables. ``DEMO_DB_CONN__PORT`` addresses the ``port`` field of
    ``conn``, and ``DEMO_DB_CONN__POOL__HEALTH__TIMEOUT`` addresses the
    ``timeout`` field of ``conn.pool.health``. These are three classes nested
    into one another, and the addressing works to any depth.

    Loading updates the object partially: the declared default instance is the
    base, and fields that no variable addresses keep the declared values. A
    required member assembles its object from the field variables alone, and a
    branch of the chain that no variable addresses takes the own field defaults
    of the dataclass. The whole-object form also works: the own variable of the
    member may carry the object as a JSON object, and a per-field variable wins
    over it.
    """

    conn: DbConfig = env.environment_variable_setting(default=DbConfig(host="declared-host"))
    reader: DbConfig = env.environment_variable_setting()  # required: assembled by fields


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # Optional: see what the library does under the hood
    adv_config.LibraryConfiguration.set_log_level(logging.INFO)

    # simulate an environment configured by the deployment / CI / .env file;
    # DEMO_APP_PORT is left out on purpose: the default stands in
    os.environ["DEMO_APP_HOST"] = "db.example.com"
    os.environ["DEMO_APP_DEBUG"] = "True"  # parsed with the bool annotation in mind
    os.environ["DEMO_APP_STARTED_AT"] = "2026-09-03T10:15:30"
    os.environ["DEMO_APP_ALLOWED_HOSTS"] = '["db-1.example.com", "db-2.example.com"]'
    os.environ["DEMO_LEGACY_TOKEN"] = "legacy-value"

    section("declare once, load anywhere")
    AppConfig.load_configuration()
    print(f"host          = {AppConfig.host!r}")
    print(f"port          = {AppConfig.port!r}  (no env var -> default)")
    print(f"debug         = {AppConfig.debug!r}")
    print(f"started_at    = {AppConfig.started_at!r}  (parsed ISO datetime)")
    print(f"allowed_hosts = {AppConfig.allowed_hosts!r}  (parsed from a JSON array string)")
    print(f"legacy_token  = {AppConfig.legacy_token!r}  (name= keeps its exact spelling)")
    print(f"session_ttl   = {AppConfig.session_ttl!r}  (no variable -> default)")

    section("aliases: a renamed variable keeps the old spelling working")
    # only the pre-rename variable is set: the alias serves the member
    os.environ["DEMO_APP_TTL"] = "900"
    AppConfig.load_configuration()
    print(f"session_ttl = {AppConfig.session_ttl!r}  (read from the alias DEMO_APP_TTL)")
    # the primary name outranks every alias once it is set
    os.environ["DEMO_APP_SESSION_TTL"] = "1200"
    AppConfig.load_configuration()
    print(
        f"session_ttl = {AppConfig.session_ttl!r}  (the primary "
        "DEMO_APP_SESSION_TTL takes precedence)"
    )

    section("options= — one mapping for every source")
    # ServiceConfig (above) uses both spellings: the environment family's
    # entry goes into options=, the free "config-version" key sits in the
    # body's class_metadata; it is one channel, merged at the class
    # statement
    os.environ["DEMO_SVC_MODE"] = "staging"
    ServiceConfig.load_configuration()
    print(f"mode           = {ServiceConfig.mode!r}  (DEMO_SVC_ + the upper-cased member name)")
    metadata = ServiceConfig.get_plugin(env.EnvironmentVariablesPlugin).context.get_class_metadata(
        "config-version"
    )
    print(
        f"config-version = {metadata!r}  (the key declared in the class body is read "
        "through the same channel)"
    )
    del os.environ["DEMO_SVC_MODE"]
    # a name declared on both sides is a blocked class, not a silent
    # last-write: the error names the class and the shared names
    try:
        # the failing class statement is the point of the demo: the checker
        # cannot see it raising
        class OverlapConfig(
            adv_config.Configuration,
            options=env.env_source(name_prefix="DEMO_X_"),
        ):
            class_metadata: Dict[str, Any] = {env.ENVIRONMENT_METADATA_OPTIONS: {}}
    except TypeError as error:
        print(f"overlap blocked: {error}")

    section("per-class family entries: a subclass keeps the inherited names")
    # TunedConfig declares its own options: they build its own member's
    # variable, while the inherited mode keeps ServiceConfig's variable;
    # the entry of the class that declared the member governs it
    os.environ["DEMO_SVC_MODE"] = "production"
    os.environ["DEMO_TUNED_REGION"] = "us"
    TunedConfig.load_configuration()
    print(
        f"mode   = {TunedConfig.mode!r}   (the base class's DEMO_SVC_MODE; the "
        "variable is not renamed)"
    )
    print(f"region = {TunedConfig.region!r}  (the subclass's own DEMO_TUNED_ prefix)")
    # RetunedConfig retunes ServiceConfig's entry, inside itself only
    os.environ["DEMO_RETUNED_MODE"] = "staging"
    RetunedConfig.load_configuration()
    print(f"mode   = {RetunedConfig.mode!r}  (redeclared, so the subclass's naming applies)")
    ServiceConfig.load_configuration()
    print(f"mode   = {ServiceConfig.mode!r}   (the ancestor itself keeps its variable)")
    del os.environ["DEMO_SVC_MODE"]
    del os.environ["DEMO_TUNED_REGION"]
    del os.environ["DEMO_RETUNED_MODE"]

    section("nested objects: one variable per field, a partial update on load")
    # conn declares a default: the single addressed field moves, the rest
    # of the object keeps the declared values
    os.environ["DEMO_DB_CONN__PORT"] = "6543"
    # the same partial update three classes deep: conn -> pool -> health
    os.environ["DEMO_DB_CONN__POOL__HEALTH__TIMEOUT"] = "2.5"
    # reader is required: the environment assembles its object from the
    # field variables alone; the health branch no variable addresses takes
    # the dataclass's own field defaults
    os.environ["DEMO_DB_READER__HOST"] = "reader.example.com"
    os.environ["DEMO_DB_READER__PORT"] = "6432"
    os.environ["DEMO_DB_READER__POOL__SIZE"] = "5"
    DatabaseConfig.load_configuration()
    print(f"conn   = {DatabaseConfig.conn!r}")
    print("  (DEMO_DB_CONN__PORT changed only the port; the default host is kept)")
    print("  (DEMO_DB_CONN__POOL__HEALTH__TIMEOUT changed only the timeout)")
    print(f"reader = {DatabaseConfig.reader!r}  (assembled from three variables)")
    del os.environ["DEMO_DB_CONN__PORT"]
    del os.environ["DEMO_DB_CONN__POOL__HEALTH__TIMEOUT"]
    del os.environ["DEMO_DB_READER__HOST"]
    del os.environ["DEMO_DB_READER__PORT"]
    del os.environ["DEMO_DB_READER__POOL__SIZE"]

    section("a constraint-violating value falls back to the default")
    os.environ["DEMO_APP_PORT"] = "70000"  # above the declared le=65535
    AppConfig.load_configuration()
    print(f"port = {AppConfig.port!r}  (70000 violates le=65535 -> default, see the log)")

    section("a member without a default is required")
    del os.environ["DEMO_APP_HOST"]
    try:
        # the failing load is the point of the demo: the checker cannot
        # see it raising
        AppConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        # one failure or several: the abort is always adv_config.AggregateLoadError
        print(f"load aborted: {error}")
    # the failed member keeps the value the last successful load brought
    # in: a required member never serves a stand-in
    print(f"host = {AppConfig.host!r}  (the last loaded value is kept)")
    os.environ["DEMO_APP_HOST"] = "cache.example.com"
    AppConfig.load_configuration()
    print(f"host = {AppConfig.host!r}  (loaded again once the variable is restored)")

    section("several failing members report all at once")
    # two members fail in one pass: a missing variable and a value that
    # does not convert; the pass walks every member, then one abort
    # lists both failures
    del os.environ["DEMO_APP_HOST"]
    os.environ["DEMO_APP_STARTED_AT"] = "not-a-timestamp"
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
    print(f"host       = {AppConfig.host!r}  (the last loaded value is kept)")
    print(
        f"started_at = {AppConfig.started_at!r}  (a value that cannot be converted is never stored)"
    )
    os.environ["DEMO_APP_HOST"] = "cache.example.com"
    os.environ["DEMO_APP_STARTED_AT"] = "2026-09-03T10:15:30"
    AppConfig.load_configuration()
    print(f"host       = {AppConfig.host!r}")
    print(f"started_at = {AppConfig.started_at!r}  (both load again once the variables are fixed)")

    section("the values are read-only: the load is the one writer")
    try:
        AppConfig.host = "blocked.example.com"
    except TypeError as error:
        print(f"assignment blocked: {error}")

    # new values come from the sources: change one and load again
    del os.environ["DEMO_APP_PORT"]
    AppConfig.load_configuration()
    print(f"port = {AppConfig.port!r}  (back to the default)")

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
        as_object.host = "blocked.example.com"  # a snapshot is frozen too
    except TypeError as error:
        print(f"snapshot write blocked: {error}")
    try:
        # not even a non-member lands; the checker cannot see the raise
        as_object.unrelated = "blocked"  # type: ignore[attr-defined]
    except TypeError as error:
        print(f"arbitrary write blocked: {error}")

    section("plugin access")
    plugin = AppConfig.get_plugin(env.EnvironmentVariablesPlugin)
    print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")

    # clean up the variables this example created
    for name in (
        "DEMO_APP_HOST",
        "DEMO_APP_DEBUG",
        "DEMO_APP_STARTED_AT",
        "DEMO_APP_ALLOWED_HOSTS",
        "DEMO_APP_PORT",
        "DEMO_APP_SESSION_TTL",
        "DEMO_APP_TTL",
        "DEMO_LEGACY_TOKEN",
        "DEMO_SVC_MODE",
        "DEMO_TUNED_REGION",
        "DEMO_RETUNED_MODE",
        "DEMO_DB_CONN__PORT",
        "DEMO_DB_CONN__POOL__HEALTH__TIMEOUT",
        "DEMO_DB_READER__HOST",
        "DEMO_DB_READER__PORT",
        "DEMO_DB_READER__POOL__SIZE",
    ):
        os.environ.pop(name, None)


if __name__ == "__main__":
    main()
