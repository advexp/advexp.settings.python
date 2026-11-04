"""
Example: the plain declaration style of Advexp.Configuration.

Members are typed annotations, and the source chain of the class names the
storages. This is a declaration style without any factory for a particular
source. The tour walks through the style in full:

- the three plain spellings (a bare annotation, an annotated assignment, and
  ``ClassVar``);
- the rich ``chain_setting(...)`` form next to them;
- the constant members outside the chain;
- ``Sources(...)`` and the chain of a single builder;
- the mapping link in its two forms (a dictionary that is passed in at the
  declaration, and the live form that is filled at runtime);
- the cases in which the ``class`` statement fails with an error;
- the read-only guards;
- inheritance of the chain;
- a file per environment, through ``env_parameter``.

Run from the repository root with the package installed
(``pip install advexp-configuration``):

    python samples/configuration/plain_declarations.py

The sample deploys its files next to this script and removes them at
startup, so every run starts from a clean slate. The package itself never
writes them: its sources are read-only.
"""

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as env
import advexp.configuration.plugins.json_settings as js
from advexp.configuration.plugins.mapping_source import mapping_source, mapping_source_for

SAMPLES_DIR = Path(__file__).resolve().parent
JSON_FILE = SAMPLES_DIR / "plain-declarations-configuration.json"
SINGLE_FILE = SAMPLES_DIR / "plain-declarations-single.json"
# one overlay file per environment: the template's slot is filled per pass
OVERLAY_TEMPLATE = "plain-declarations-overlay-{DEMO_PLAIN_ENV}.json"

# the environment members' variable names
TOKEN_VAR = "DEMO_PLAIN_TOKEN"
TTL_VAR = "DEMO_PLAIN_SESSION_TTL"
ENV_VAR = "DEMO_PLAIN_ENV"

# the chain's bottom layer: defaults the code itself states
BASE_DEFAULTS = {"host": "defaults.example", "retries": 2}


class AppConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        env.env_source(name_prefix="DEMO_PLAIN_", name_case=env.NameCase.UPPER),
        js.json_source(file=JSON_FILE, name_pattern="{FieldName}"),
        mapping_source(BASE_DEFAULTS),
    ),
):
    """One class, one chain, plain members.

    A plain member reads the whole chain from top to bottom. Every named link
    builds the address of the member by its own rules: the variable
    ``DEMO_PLAIN_TOKEN`` in the environment, the key ``token`` in the JSON file,
    and the member name in the mapping. The first link that provides a value
    wins.

    The naming dictionary of the environment family is declared on its link. The
    JSON keys here are bare member names, which is the pattern of a file that a
    person edits by hand.
    """

    # a bare annotation: a required member — the chain must provide the
    # value or the load aborts
    token: str
    # an annotated assignment: that value is the member's declared
    # default, written in its typed form — the implicit last layer of
    # the chain
    session_ttl: timedelta = timedelta(minutes=30)
    host: str = "localhost"
    # the rich spelling of the same member: name= is the full literal
    # address in every named link — the environment prefix and case
    # never touch it, the key pattern neither — and the keyword
    # parameters past it are the declared value constraints
    port: int = adv_config.chain_setting(name="port", ge=1, le=65535, default=8080)
    # aliases: full literal addresses the same way, tried after the
    # primary address in every named link
    region: str = adv_config.chain_setting(aliases=["zone"], default="eu")
    # a constant member: outside the chain altogether — no link is ever
    # asked for it, and the load overrides skip it
    schema_version: str = adv_config.constant_setting(default="v2")
    # a constant can carry constraints: they check the declared value,
    # while no link of the chain is ever asked for it
    pinned_url: str = adv_config.constant_setting(default="https://api.example", regex=r"^https://")
    # a ClassVar annotation is not a member at all: the plain class
    # attribute it always was
    schema_note: ClassVar[str] = "application configuration, layout v1"


class SingleFileConfig(
    adv_config.Configuration,
    options=js.json_source(file=SINGLE_FILE, name_pattern="{FieldName}"),
):
    """A single builder that is passed to ``options=`` alone is the one-link chain
    of the same class. ``Sources(...)`` spells a chain of several links.
    """

    token: str = "single-default"


# the overlay link's file spells a slot the parameter fills per pass
app_env = adv_config.env_parameter(ENV_VAR, choices=("dev", "prod"), default="dev")


class OverlayConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        # the overlay of one environment, above the shared base file
        js.json_source(
            file=SAMPLES_DIR / OVERLAY_TEMPLATE,
            name_pattern="{FieldName}",
            parameters=app_env,
        ),
        js.json_source(file=SINGLE_FILE, name_pattern="{FieldName}"),
    ),
):
    """The file of the environment that a variable names, above a base file.

    The whitelist guards the variable before anything touches the file system.
    The chain resolves the overlay first, and the base serves what the overlay
    misses.
    """

    token: str = "none"


class ServiceConfig(AppConfig):
    """A subclass composes the members of its base class and reads the same chain.
    The chain is a declaration of the class itself, and a subclass without a
    chain of its own inherits the nearest one above it.
    """

    endpoint: str = js.json_setting(name="endpoint", default="https://api.example")


class RuntimeConfig(
    adv_config.Configuration,
    options=mapping_source(),
):
    """The live mapping link: a dictionary that arrives at runtime.

    ``mapping_source()`` (the builder called without a dictionary) declares an
    empty layer. The application fills its dictionary through the resolver
    ``mapping_source_for(cls)`` before a load reads it. A layer that nothing has
    filled is a plain miss: the chain walks on below it, to the declared
    defaults.
    """

    token: str = "untold"
    host: str = "localhost"


def section(title: str) -> None:
    print(f"\n--- {title} ---", flush=True)


def deploy_sources() -> None:
    """Deploy the configuration: this is the own hand of the sample.

    The package never writes these files or variables: its sources are
    read-only, and this is the main difference between it and
    ``advexp.settings``.
    """
    os.environ[TOKEN_VAR] = "env-token"
    JSON_FILE.write_text(
        # "zone" is the pre-rename key of region: the alias serves the
        # member; "retries" names no member here — the mapping below
        # carries that one
        json.dumps({"zone": "eu-west", "session_ttl": "1:30:00"}),
        encoding="utf-8",
    )
    SINGLE_FILE.write_text(json.dumps({"token": "base-file"}), encoding="utf-8")
    for environment, token in (
        ("dev", "dev-token"),
        ("prod", "prod-token"),
    ):
        overlay = SAMPLES_DIR / OVERLAY_TEMPLATE.format(**{ENV_VAR: environment})
        overlay.write_text(json.dumps({"token": token}), encoding="utf-8")


def describe_sources() -> None:
    variables = {name: os.environ[name] for name in (TOKEN_VAR, TTL_VAR) if name in os.environ}
    print(f"env vars   = {variables}")
    print(f"json file  = {json.loads(JSON_FILE.read_text(encoding='utf-8'))}")
    print(f"defaults   = {BASE_DEFAULTS}")


def main() -> None:
    # optional: the library reports problems (conversion fallbacks, source
    # errors) as warnings on the "advexp.configuration" channel. logger()
    # hands out the family's root channel, configured here with a handler
    # of the application's own format and the propagation off, so the
    # records go to this handler alone
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("log: %(message)s"))
    library_logger = adv_config.LibraryConfiguration.logger()
    library_logger.addHandler(handler)
    library_logger.setLevel(logging.INFO)
    library_logger.propagate = False

    # every run starts from a clean slate
    JSON_FILE.unlink(missing_ok=True)
    SINGLE_FILE.unlink(missing_ok=True)
    for environment in ("dev", "prod"):
        (SAMPLES_DIR / OVERLAY_TEMPLATE.format(**{ENV_VAR: environment})).unlink(missing_ok=True)
    for name in (TOKEN_VAR, TTL_VAR, ENV_VAR):
        os.environ.pop(name, None)

    section("the plain spellings: what the class body declares")
    # the three spellings land as members of one kind: a bare annotation
    # required, an annotated assignment defaulted, chain_setting() the
    # same member in its rich form. A ClassVar stays out of the machinery
    print(f"members    = {list(AppConfig.__settings_members__)}")
    print(f"ClassVar   = {AppConfig.schema_note!r} (a plain class attribute)")
    print(f"host       = {AppConfig.host!r} (the declared default)")
    print(f"pinned_url = {AppConfig.pinned_url!r} (a constrained constant)")
    try:
        print(AppConfig.token)
    except Exception as error:  # reading a required member before its load
        print(f"token      -> {type(error).__name__}: {error}")

    section("a bare annotation is required: no value, no load")
    # nothing is deployed yet: the chain provides nothing for the token,
    # and the abort names the member and the links it never found it in
    try:
        AppConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        print(f"abort      -> {type(error.errors[0]).__name__}: {error.errors[0]}")

    section("the chain provides: the first link holding a value wins")
    deploy_sources()
    describe_sources()
    # the walk: session_ttl comes from the JSON file, region from the
    # alias key the file still carries, host from the mapping layer —
    # the declared default is the implicit last layer and stands down
    AppConfig.load_configuration()
    print(f"token      = {AppConfig.token!r} (the environment value takes precedence)")
    print(f"session_ttl = {AppConfig.session_ttl!r} (from the JSON file, converted)")
    print(f"region     = {AppConfig.region!r} (read from the alias key 'zone' in the file)")
    print(f"host       = {AppConfig.host!r} (from the mapping layer, not the default)")
    os.environ[TTL_VAR] = "0:45:00"  # the environment outranks the file
    AppConfig.load_configuration()
    print(f"session_ttl = {AppConfig.session_ttl!r} (the environment takes precedence over it)")
    os.environ.pop(TTL_VAR)

    section("chain_setting(name=...): the literal address in every link")
    # the name= of the rich spelling is the full address wherever the
    # member is looked up: the variable is exactly "port" — the link's
    # DEMO_PLAIN_ prefix and upper case never touch it — and so is the
    # file key
    os.environ["port"] = "9000"
    AppConfig.load_configuration()
    print(f"port       = {AppConfig.port!r} (from the variable 'port', converted)")
    del os.environ["port"]
    document = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    document["port"] = 9001
    JSON_FILE.write_text(json.dumps(document), encoding="utf-8")
    AppConfig.load_configuration()
    print(f"port       = {AppConfig.port!r} (from the literal key 'port' in the file)")

    section("constraints travel with the member")
    # chain_setting(ge=1, le=65535) is checked on whatever the chain
    # provides: a violating value never becomes the member's — the load
    # falls back to the declared default, and the report the pass
    # returns carries the entry. The address is the literal "port"
    # again — the name= the member declares is the address everywhere
    os.environ["port"] = "70000"
    report = AppConfig.load_configuration()
    print(f"report     = {report[0]}")
    print(f"port       = {AppConfig.port!r} (the declared default was used instead)")
    del os.environ["port"]

    section("constant members: the load leaves them alone")
    # a reload serves each constant's declared value again — no link is
    # ever asked for one, and the load overrides skip them
    AppConfig.load_configuration()
    print(f"schema     = {AppConfig.schema_version!r} (the declared constant)")
    print(f"pinned_url = {AppConfig.pinned_url!r} (the declared constant)")
    AppConfig.load_configuration(
        overrides={"token": "override", "schema_version": "v9", "no-such": 1}
    )
    print(f"token      = {AppConfig.token!r} (a layer above the whole chain)")
    print(f"schema     = {AppConfig.schema_version!r} (a constant: it cannot be overridden)")
    # the keys naming no member and the constant drop out quietly: a
    # foreign dictionary never fails the load

    section("the mapping link speaks member names alone")
    # the dictionary the application hands in is the chain's bottom
    # layer here: its keys are member names, and a name= or an alias
    # changes nothing for it
    print(f"host       = {AppConfig.host!r} (the value came from BASE_DEFAULTS['host'])")

    section("the live mapping link: the dictionary arrives at runtime")
    # mapping_source() without a dictionary: the layer starts empty, and
    # set() fills it — the resolver hands the link of the class's chain,
    # and the next load reads the dictionary it then holds. set()
    # replaces the whole dictionary, not a merge into the old one
    RuntimeConfig.load_configuration()
    print(f"token      = {RuntimeConfig.token!r} (an empty layer is just a miss)")
    mapping_source_for(RuntimeConfig).set({"token": "runtime-token", "host": "runtime.example"})
    RuntimeConfig.load_configuration()
    print(f"token      = {RuntimeConfig.token!r} (the dictionary that was set before the load)")
    mapping_source_for(RuntimeConfig).set({"token": "replaced"})
    RuntimeConfig.load_configuration()
    print(f"token      = {RuntimeConfig.token!r}")
    print(f"host       = {RuntimeConfig.host!r} (set() replaced the whole dictionary)")

    section("values are read-only: new values come from a reload")
    # the loaded values are frozen on every write path; the sources
    # change, and the load reads them anew
    try:
        AppConfig.token = "written"
    except TypeError as error:
        print(f"class write -> TypeError: {error}")
    os.environ[TOKEN_VAR] = "rotated"
    AppConfig.load_configuration()
    print(f"token      = {AppConfig.token!r} (reloaded after the change)")

    section("the class statement refuses what it cannot resolve")
    # a neutral member must have a chain to read: the class statement
    # itself refuses one without it, a builder sitting loose in the
    # options sequence, and a family factory whose family no link of
    # the chain serves
    try:

        class Unchained(adv_config.Configuration):
            token: str

    except TypeError as error:
        print(f"no chain   -> TypeError: {error}")
    try:

        class LooseBuilders(
            adv_config.Configuration,
            options=(js.json_source(file=JSON_FILE), env.env_source()),
        ):
            token: str = "t"

    except TypeError as error:
        print(f"loose      -> TypeError: {error}")
    try:

        class NoJsonLink(
            adv_config.Configuration,
            options=env.env_source(),
        ):
            port: int = js.json_setting(default=1)

    except TypeError as error:
        print(f"no link    -> TypeError: {error}")

    section("a single builder is the one-link chain")
    # options=json_source(...) without Sources(...) is the same chain
    # declaration, one link long
    SingleFileConfig.load_configuration()
    print(f"token      = {SingleFileConfig.token!r} (the file of the single link)")

    section("inheritance: the chain travels down")
    # the subclass reads the same chain with the base's members and its
    # own, into its own storage — the base keeps its own values
    ServiceConfig.load_configuration()
    print(f"Service    = token={ServiceConfig.token!r}, host={ServiceConfig.host!r}")
    print(f"AppConfig  = token = {AppConfig.token!r} (its own storage, untouched)")

    section("a file per environment: the chain's templated link")
    # the variable picks the file the overlay link reads, above the base
    # file the second link serves; the whitelist guards the variable
    # before anything touches the file system
    os.environ[ENV_VAR] = "prod"
    OverlayConfig.load_configuration()
    print(f"token      = {OverlayConfig.token!r} (the prod overlay is used)")
    os.environ[ENV_VAR] = "dev"
    OverlayConfig.load_configuration()
    print(f"token      = {OverlayConfig.token!r} (the dev overlay is used)")
    os.environ.pop(ENV_VAR)
    OverlayConfig.load_configuration()
    print(f"token      = {OverlayConfig.token!r} (selected by default=dev)")
    # a typo fails loudly instead of quietly becoming a missing file the
    # chain would walk past — the silent way a production process ends
    # up on development values
    os.environ[ENV_VAR] = "prodd"
    try:
        OverlayConfig.load_configuration()
    except ValueError as error:
        print(f"typo       -> {type(error).__name__}: {error}")
    os.environ.pop(ENV_VAR)

    # cleanup: the package never wrote any of these — the sample did
    JSON_FILE.unlink(missing_ok=True)
    SINGLE_FILE.unlink(missing_ok=True)
    os.environ.pop(TOKEN_VAR, None)
    for environment in ("dev", "prod"):
        (SAMPLES_DIR / OVERLAY_TEMPLATE.format(**{ENV_VAR: environment})).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
