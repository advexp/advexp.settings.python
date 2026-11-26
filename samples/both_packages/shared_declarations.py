"""
Example: one set of member declarations for both packages.

A declaration base — a plain class marked with ``SettingDeclarations`` —
holds the members that a settings class and a configuration class inherit
together. The base answers what each value is and from which source family
it reads; the body of each inheriting class configures the sources of that
class. This sample walks the whole story:

- plain annotations pour in too: a value becomes the default, a bare
  annotation a required member;
- the rich spellings work in the base: ``setting(...)`` for a member of the
  class's own source, and the family members beside it — ``json_setting``,
  ``environment_variable_setting``, ``dotenv_setting`` — each reading the
  source of its own family that the class declares;
- references between members (``ge=``) follow the poured copies, and a
  reference from a body onto a member of the base (``ge=Base.low``) turns
  onto the copy of the same class;
- a member without ``default=`` is required in every context: a load that
  finds no value aborts naming the member;
- the body of a class wins over the pour under the same name;
- the base is a blueprint: a change to it after the classes were created
  reaches nothing, and mutable defaults are copied, never shared;
- one combination is refused — the body overriding a name that a reference
  points at — and the message names the way out.

Run from the repository root with both packages installed
(``pip install advexp-settings advexp-configuration``):

    python samples/both_packages/shared_declarations.py
"""

import os
from pathlib import Path

import advexp.configuration as adv_config
import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as sdotenv
import advexp.settings.plugins.environment.variables as senv
import advexp.settings.plugins.json_settings as sjs
from advexp.configuration.plugins.environment.dotenv import (
    dotenv_source as config_dotenv_source,
)
from advexp.configuration.plugins.environment.variables import (
    env_source as config_env_source,
)
from advexp.configuration.plugins.json_settings import (
    json_source as config_json_source,
)
from advexp.settings_base import (
    SettingDeclarations,
    dotenv_setting,
    environment_variable_setting,
    json_setting,
    setting,
)

SAMPLES_DIR = Path(__file__).resolve().parent
STATE_FILE = SAMPLES_DIR / "shared-declarations.json"
DOTENV_FILE = SAMPLES_DIR / "shared-declarations.env"
REGION_VARIABLE = "SHARED_APP_REGION"


class AppDeclarations(SettingDeclarations):
    """The members both classes share. A plain class: it loads nothing."""

    # the plain spellings: a value is the declared default...
    retries: int = 3
    tags: list = ["a"]  # ...and a mutable one pours in as a copy, per class
    # ...while a bare annotation declares a member that a source must provide
    api_token: str = setting(name="api_token")

    # the rich spelling of the class's own source, with a reference:
    # high stays no less than low in every class that inherits this base
    low: int = setting(default=1, name="low")
    high: int = setting(default=10, ge=low, name="high")

    # members of the source families: each class serves them through the
    # source of that family it declares — AppSettings below binds only JSON
    # and leaves the environment and dotenv families to their module
    # defaults, while AppConfig spells a chain link for every family
    port: int = json_setting(name="port", default=8080)
    region: str = environment_variable_setting(name=REGION_VARIABLE, default="eu")
    operator_email: str = dotenv_setting(name="OPERATOR_EMAIL", default="ops@example.com")


class AppSettings(
    AppDeclarations,
    adv_settings.Settings,
    options=sjs.json_source(file=STATE_FILE),
):
    """The read-write side: one JSON binding serves every poured member."""

    # the body's own members sit beside the poured ones
    debug: bool = setting(default=False)
    # the body wins under the same name: this retries replaces the pour
    retries: int = 9
    # a reference from the body onto a member of the base turns onto the
    # poured copy of this class
    margin: int = setting(default=2, ge=AppDeclarations.low)


class AppConfig(
    AppDeclarations,
    adv_config.Configuration,
    options=adv_config.Sources(
        config_env_source(),
        config_dotenv_source(file=DOTENV_FILE),
        config_json_source(file=STATE_FILE),
    ),
):
    """The read-only side: the same declarations through a chain of sources."""

    # a member of the environment family in a body of its own: the chain
    # link of that family serves it, beside the JSON members of the base
    region: str = environment_variable_setting(name=REGION_VARIABLE, default="eu")


def section(title: str) -> None:
    print(f"\n--- {title} ---", flush=True)


def main() -> None:
    os.environ.pop(REGION_VARIABLE, None)
    STATE_FILE.write_text('{"port": 9000}', encoding="utf-8")
    DOTENV_FILE.write_text("OPERATOR_EMAIL=ops@advexp.net\n", encoding="utf-8")
    # the settings class binds one source (its neutral members need exactly
    # one); the environment and dotenv families serve their members through
    # the module defaults instead, and the dotenv default names this file
    sdotenv.DotenvConfiguration.file_path = DOTENV_FILE
    # importing the modules of the families enables their module
    # defaults: the environment family reads the process environment
    assert senv is not None

    section("a required member aborts the load until a source provides it")
    try:
        AppSettings.load_settings()
    except adv_settings.AggregateLoadError as error:
        # one abort reports every failed member: print them all
        for entry in error.errors:
            print(f"the settings side refused: {entry}")
    try:
        AppConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"the configuration side refused: {entry}")

    section("the same declarations in both classes, one file behind them")
    STATE_FILE.write_text(
        '{"port": 9000, "api_token": "secret-42"}',
        encoding="utf-8",
    )
    os.environ[REGION_VARIABLE] = "us-east-1"
    AppSettings.load_settings()
    print(f"settings    : retries={AppSettings.retries} port={AppSettings.port}")
    print(f"            : api_token={AppSettings.api_token!r} debug={AppSettings.debug}")
    print(f"            : margin={AppSettings.margin} (its bound is the poured low)")
    print(
        f"            : region={AppSettings.region!r} (the module default"
        " reads the process environment)"
    )
    AppConfig.load_configuration()
    print(f"configuration: retries={AppConfig.retries} port={AppConfig.port}")
    print(f"             : region={AppConfig.region!r} (the chain's env link)")
    print(
        f"operator_email={AppSettings.operator_email!r} on both sides"
        f" ({AppConfig.operator_email!r}): the dotenv file behind them"
    )

    section("references follow the loaded values on both sides")
    # low loads as 5; high 4 and margin 2 stand below it: the load resets the
    # violating cluster to the declared defaults and names every member
    STATE_FILE.write_text(
        '{"port": 9000, "api_token": "secret-42", "low": 5, "high": 4}',
        encoding="utf-8",
    )
    report = AppSettings.load_settings()
    print(
        f"after the violating load: low={AppSettings.low} high={AppSettings.high}"
        f" margin={AppSettings.margin}"
    )
    for entry in report:
        print(f"the report names it: {entry}")

    section("mutable defaults are copies: the classes never share them")
    AppSettings.tags.append("b")
    print(f"settings tags    : {AppSettings.tags}")
    print(f"the base kept its own: {AppDeclarations.tags}")

    section("the base is a blueprint: later changes reach nothing")
    changed_port = json_setting(name="port", default=9999)
    AppDeclarations.port = changed_port
    print(
        f"the base default is {changed_port.default} now,"
        f" the loaded port is still {AppSettings.port}"
    )

    section("overriding a name that a reference points at is refused")
    try:

        class Broken(
            AppDeclarations,
            adv_settings.Settings,
            options=sjs.json_source(file=STATE_FILE),
        ):
            low: int = setting(default=50)  # high inherited ge=low — the target

    except TypeError as error:
        print(error)


if __name__ == "__main__":
    main()
