"""
Example: the application-side API of Advexp.Configuration.

The bundled sources serve the walkthrough together as one chain:
environment variables, a dotenv file, a JSON file, and a dictionary that is
declared in code. The class resolves each member from top to bottom, and the
first link that provides a value wins. Building a source of your own is
shown in ``samples/configuration/custom_source.py``.

Run from the repository root with the package installed
(``pip install "advexp-configuration[dotenv]"``):

    python samples/configuration/configuration_api.py

The sample deploys its files next to this script, in the way that whatever
deploys configuration would do in a real application. It removes them at
startup, so every run starts from a clean slate. The package itself never
writes them: its sources are read-only.

The sample walks through the following topics:

- declaring members: the plain spellings (a bare annotation for a required
  member, an annotated assignment for a member with a default), next to the
  family factories and ``chain_setting``;
- effective defaults before any load;
- the one aggregate load error, with an entry for each failed member;
- the retry after the sources are fixed;
- the load overrides above the whole chain;
- member name aliases (an old file key that serves a renamed member);
- path parameters (an environment variable that picks the file that a link
  reads);
- the read-only guards (class, instance, and snapshot);
- frozen dict and object snapshots;
- inheritance, which composes members into the own storage of a subclass;
- access to the plugin.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.dotenv as env_file
import advexp.configuration.plugins.environment.variables as env
import advexp.configuration.plugins.json_settings as js
from advexp.configuration.plugins.mapping_source import mapping_source

SAMPLES_DIR = Path(__file__).resolve().parent
JSON_FILE = SAMPLES_DIR / "configuration-api-sample.json"
DOTENV_FILE = SAMPLES_DIR / "configuration-api-sample.env"
REGION_BASE_FILE = SAMPLES_DIR / "configuration-api-region.json"
# the overlay file of one environment: the slot spells the variable's
# name, the load unfolds it per pass
REGION_OVERLAY_TEMPLATE = "configuration-api-region-{DEMO_CONF_APP_ENV}.json"

# the environment members' full variable names
MODE_VAR = "DEMO_CONF_MODE"
FACTOR_VAR = "DEMO_CONF_FACTOR"
# the variable one parameterized link reads; the whitelist guards it and
# the declared default serves an unset variable
APP_ENV_VAR = "DEMO_CONF_APP_ENV"
app_env = adv_config.env_parameter(APP_ENV_VAR, choices=("dev", "prod"), default="dev")

# the chain's bottom layer: defaults the code itself states
BASE_DEFAULTS = {"retries": 3}


class AppConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(name_prefix="DEMO_CONF_", name_case=env.NameCase.UPPER),
        js.json_source(file=JSON_FILE),
        env_file.dotenv_source(file=DOTENV_FILE),
        mapping_source(BASE_DEFAULTS),
    ),
):
    """Typed application configuration that is read from a chain of sources:
    environment variables, a JSON file, a dotenv file, and a dictionary that is
    declared in code, in that order. The first link that provides a value wins.

    The ``options=`` keyword carries the chain. A single builder that is passed
    to it alone is the one-link chain of the same class.
    """

    # a bare annotation is required: the chain must provide the value
    mode: str
    # an annotated assignment is the declared default; a family factory
    # narrows the member to its family's links alone
    retries: int = js.json_setting(name="retries", default=3)
    # the dotenv links read the bound file's variable lines; the names
    # build by the family's shared rules (the env link declared them)
    debug: bool = env_file.dotenv_setting(default=False)
    started_at: Optional[datetime] = js.json_setting(name="started_at", default=None)
    # a default in its storage form: converted to the annotation at class
    # creation, before any source access
    workers: int = env_file.dotenv_setting(default="4")
    # aliases: the file may still carry the pre-rename key; a load looks the
    # primary key up first, then each alias, and the first found wins
    timeout: int = js.json_setting(name="timeout", aliases=["ttl"], default=30)
    # the chain's own rich spelling: constraints on a neutral member
    port: int = adv_config.chain_setting(ge=1, le=65535, default=8080)
    # a constant member: no link is asked, no override reaches it
    schema_version: str = adv_config.constant_setting(default="v2")


class ServiceConfig(AppConfig):
    """A subclass composes the members of its base and gets its own storage."""

    endpoint: str = js.json_setting(name="endpoint", default="https://api.example")


class StrictConfig(
    adv_config.Configuration,
    options=env.env_source(),
):
    """Required members of the environment source: what their absence
    looks like."""

    mode: str = env.environment_variable_setting(name=MODE_VAR)
    factor: int = env.environment_variable_setting(name=FACTOR_VAR)


class RegionConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        # the overlay of one environment: the variable picks the file this
        # link reads, above the per-deployment base file — the chain
        # resolves the overlay first, the base serves what it misses
        js.json_source(
            file=SAMPLES_DIR / REGION_OVERLAY_TEMPLATE,
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
        js.json_source(file=REGION_BASE_FILE, name_pattern="{FieldName}"),
    ),
):
    """A deployment's endpoints with one overlay file per environment."""

    endpoint: str = "https://api.example"


def section(title: str) -> None:
    print(f"\n--- {title} ---", flush=True)


def deploy_sources() -> None:
    """Deploy the configuration: the sample's own hand.

    The package never writes these files or variables: its sources are
    read-only, and this is exactly the line between it and
    ``advexp.settings``.
    """
    os.environ[MODE_VAR] = "production"
    JSON_FILE.write_text(
        # "ttl" is the pre-rename key of timeout: the alias serves the member
        json.dumps({"retries": 5, "started_at": "2026-10-10T12:00:00", "ttl": 45}),
        encoding="utf-8",
    )
    DOTENV_FILE.write_text(
        "DEMO_CONF_DEBUG=True\nDEMO_CONF_WORKERS=8\nDEMO_CONF_PORT=9000\n", encoding="utf-8"
    )
    REGION_BASE_FILE.write_text(
        json.dumps({"endpoint": "https://.internal.example"}), encoding="utf-8"
    )
    for environment, endpoint in (
        ("dev", "https://dev.example"),
        ("prod", "https://example.com"),
    ):
        overlay = SAMPLES_DIR / REGION_OVERLAY_TEMPLATE.format(**{APP_ENV_VAR: environment})
        overlay.write_text(json.dumps({"endpoint": endpoint}), encoding="utf-8")


def describe_sources() -> None:
    variables = {name: os.environ[name] for name in (MODE_VAR, FACTOR_VAR) if name in os.environ}
    print(f"env vars   = {variables}")
    print(f".env file  = {DOTENV_FILE.read_text(encoding='utf-8').splitlines()!r}")
    print(f"json file  = {json.loads(JSON_FILE.read_text(encoding='utf-8'))}")
    print(f"defaults   = {BASE_DEFAULTS}")


def main() -> None:
    # optional: the library reports problems (conversion fallbacks, source
    # errors) as warnings on the "advexp.configuration" channel. logger()
    # hands out the family's root channel — one object every record of
    # every package passes through — configured here with a handler of
    # the application's own format and the propagation off, so the
    # records go to this handler alone (adv_config.Configuration.logger() hands out
    # this package's channel alone, for configuring one package without
    # the rest of the family)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("log: %(message)s"))
    library_logger = adv_config.LibraryConfiguration.logger()
    library_logger.addHandler(handler)
    library_logger.setLevel(logging.INFO)
    library_logger.propagate = False

    # every run starts from a clean slate
    JSON_FILE.unlink(missing_ok=True)
    DOTENV_FILE.unlink(missing_ok=True)
    REGION_BASE_FILE.unlink(missing_ok=True)
    for environment in ("dev", "prod"):
        overlay = SAMPLES_DIR / REGION_OVERLAY_TEMPLATE.format(**{APP_ENV_VAR: environment})
        overlay.unlink(missing_ok=True)
    for name in (MODE_VAR, FACTOR_VAR, APP_ENV_VAR):
        os.environ.pop(name, None)

    section("declare once: effective defaults before any source access")
    print(f"retries    = {AppConfig.retries!r}")
    print(f"port       = {AppConfig.port!r}")
    try:
        print(AppConfig.mode)
    except Exception as error:  # reading a required member before its load
        print(f"mode       -> {type(error).__name__}: {error}")

    section("a clean load: the chain provides the values")
    deploy_sources()
    describe_sources()
    AppConfig.load_configuration()
    print(f"mode       = {AppConfig.mode!r} (from the environment)")
    print(f"retries    = {AppConfig.retries!r} (from the JSON file, not the default)")
    print(f"debug      = {AppConfig.debug!r} (from the dotenv file)")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {AppConfig.started_at!r}  (ISO text -> datetime)")
    print(f"timeout    = {AppConfig.timeout!r} (the member was read from the alias key 'ttl')")
    print(f"port       = {AppConfig.port!r} (from the dotenv link; the constraint was satisfied)")

    section("the load overrides: a layer above the whole chain")
    AppConfig.load_configuration(overrides={"mode": "override", "retries": 9})
    print(f"mode       = {AppConfig.mode!r}, retries = {AppConfig.retries!r}")
    print(f"schema     = {AppConfig.schema_version!r} (a constant: it cannot be overridden)")
    AppConfig.load_configuration()

    section("values are read-only: the guards on every write path")
    try:
        AppConfig.retries = 10
    except TypeError as error:
        print(f"class write -> TypeError: {error}")
    instance = AppConfig()
    try:
        instance.retries = 10
    except TypeError as error:
        print(f"instance   -> TypeError: {error}")
    # new values come from a reload, after the sources change
    os.environ[MODE_VAR] = "staging"
    document = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    document["retries"] = 7
    JSON_FILE.write_text(json.dumps(document), encoding="utf-8")
    AppConfig.load_configuration()
    print(f"mode       = {AppConfig.mode!r}, retries = {AppConfig.retries!r} (reloaded)")

    section("required members that find nothing usable abort the load — all at once")
    # mode is gone, factor holds garbage: one abort carries both failures,
    # each as its own error class
    os.environ.pop(MODE_VAR)
    os.environ[FACTOR_VAR] = "abc"
    try:
        StrictConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")

    section("the pass is retryable: fix the sources, load again")
    os.environ[MODE_VAR] = "production"
    os.environ[FACTOR_VAR] = "4"
    StrictConfig.load_configuration()
    print(f"Strict     = mode={StrictConfig.mode!r}, factor={StrictConfig.factor!r}")

    section("path parameters: an environment variable picks the file a link reads")
    os.environ[APP_ENV_VAR] = "prod"
    RegionConfig.load_configuration()
    print(f"endpoint   = {RegionConfig.endpoint!r} (APP_ENV=prod: the prod overlay is used)")
    os.environ[APP_ENV_VAR] = "dev"
    RegionConfig.load_configuration()
    print(f"endpoint   = {RegionConfig.endpoint!r} (APP_ENV=dev: the dev overlay is used)")
    os.environ.pop(APP_ENV_VAR)
    RegionConfig.load_configuration()
    print(f"endpoint   = {RegionConfig.endpoint!r} (unset: the declared default=dev is used)")
    # the whitelist guards the variable before any file is touched: a typo
    # fails loudly instead of becoming a missing file the chain walks past.
    # The member has a default, so the broken link aborts the load as
    # itself — the served default must not mask the condition
    os.environ[APP_ENV_VAR] = "prodd"
    try:
        RegionConfig.load_configuration()
    except ValueError as error:
        print(f"typo       -> {type(error).__name__}: {error}")
    os.environ.pop(APP_ENV_VAR)

    section("snapshots: to_dict (a frozen mapping) and to_object (a frozen instance)")
    snapshot = AppConfig.to_dict()
    print(f"snapshot   = {dict(snapshot)}")
    try:
        snapshot["retries"] = 0  # type: ignore[index]  # the read-only contract under test
    except TypeError as error:
        print(f"item write -> TypeError: {error}")
    state = AppConfig.to_object()
    print(f"state      = mode={state.mode!r}, retries={state.retries!r} (its own copy)")
    try:
        state.retries = 0
    except TypeError as error:
        print(f"write      -> TypeError: {error}")

    section("inheritance: members compose, storage stays per class")
    ServiceConfig.load_configuration()  # loads the inherited members too
    print(f"Service    = mode={ServiceConfig.mode!r}, endpoint={ServiceConfig.endpoint!r}")
    print(f"AppConfig  = mode = {AppConfig.mode!r} (its own storage, untouched)")

    section("plugin access")
    plugin = AppConfig.get_plugin(env.EnvironmentVariablesPlugin)
    print(f"plugin     = {plugin.plugin_name!r}, serves {plugin.context.settings_class.__name__}")

    # cleanup: the package never wrote any of these — the sample did
    JSON_FILE.unlink(missing_ok=True)
    DOTENV_FILE.unlink(missing_ok=True)
    for name in (MODE_VAR, FACTOR_VAR):
        os.environ.pop(name, None)


if __name__ == "__main__":
    main()
