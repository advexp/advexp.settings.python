"""
Example: Advexp.Settings and Advexp.Configuration in one application.

The two packages coexist without collisions, because every storage address
belongs to a class, not to a package. The environment families have their
own per-class prefixes, and file bindings name their own files. A shared file
is a deliberate choice: it is made by giving the members of both classes the
same explicit ``name=``. The packages share one plugin registry (importing
the modules of both plugins enables both), and their logging channels stay
separate.

Run from the repository root with the packages installed
(``pip install advexp-settings advexp-configuration``):

    python samples/both_packages/one_app.py

The scenario is as follows. An application starts over deployed
configuration (a read-only ``Configuration`` class) and keeps its
user-tunable state in a ``Settings`` class. It then re-reads that state
through the configuration side (one file, two views of it). Finally, it
hands deployed values over to the settings side, in two ways: a point
assignment and the update by the intersection of names.
"""

import logging
import os
from pathlib import Path

# the naming vocabulary is the family's shared one, but each package
# spells its own helpers: the built entry carries the package's name, and
# a class of the other package refuses it at the class statement — a mix
# that would otherwise retune a wrong class's variables silently
import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as cenv
import advexp.configuration.plugins.json_settings as cjs
import advexp.settings as adv_settings
import advexp.settings.plugins.environment.variables as senv
import advexp.settings.plugins.json_settings as sjs

SAMPLES_DIR = Path(__file__).resolve().parent
STATE_FILE = SAMPLES_DIR / "one-app-state.json"


class WindowSettings(
    adv_settings.Settings,
    options=sjs.json_file(STATE_FILE),
):
    """The user-tunable state: a settings class owns it read-write."""

    # an explicit name= is the file key exactly; RuntimeConfig below reads
    # the same key on purpose — the one file, two views of it
    theme: str = sjs.json_setting(name="theme", default="dark")
    font_size: int = sjs.json_setting(name="font_size", default=12)


class FeatureSettings(
    adv_settings.Settings,
    options=senv.env_source(name_prefix="APP_SETTINGS_", name_case=senv.NameCase.UPPER),
):
    """Settings that can be tuned at runtime: their variables live under the own
    prefix of the application, built per class (``APP_SETTINGS_`` plus the
    member name).
    """

    retries: int = senv.environment_variable_setting(default=3)
    timeout: int = senv.environment_variable_setting(default=30)


class RuntimeConfig(
    adv_config.Configuration,
    options=adv_config.Sources(
        cenv.env_source(name_prefix="APP_CONFIG_", name_case=cenv.NameCase.UPPER),
        cjs.json_source(file=STATE_FILE),
    ),
):
    """The deployed configuration: read-only, from its own variables — and
    a read-only view over the settings file, through the shared keys."""

    # no name=: the class's prefix builds the variable (APP_CONFIG_URL);
    # an explicit name= would be the variable's full address instead
    url: str = cenv.environment_variable_setting()
    timeout: int = cenv.environment_variable_setting(default=60)
    theme: str = cjs.json_setting(name="theme", default="dark")


def section(title: str) -> None:
    print(f"\n--- {title} ---", flush=True)


def main() -> None:
    # the packages log on their own channels (advexp.settings,
    # advexp.configuration) under the family root; a level can be set per
    # package when one of them gets chatty:
    # logging.getLogger("advexp.configuration").setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.INFO, format="log: %(message)s")

    # every run starts from a clean slate
    STATE_FILE.unlink(missing_ok=True)
    for name in list(os.environ):
        if name.startswith(("APP_SETTINGS_", "APP_CONFIG_")):
            del os.environ[name]

    section("startup: the deployed configuration loads")
    os.environ["APP_CONFIG_URL"] = "https://api.example"  # the deploy's hand
    os.environ["APP_CONFIG_TIMEOUT"] = "90"
    RuntimeConfig.load_configuration()
    print(
        f"url    = {RuntimeConfig.url!r}, timeout = {RuntimeConfig.timeout!r} (its own variables)"
    )

    section("the settings side: defaults first, then the user's choice")
    print(f"theme  = {WindowSettings.theme!r} (nothing stored yet)")
    WindowSettings.theme = "light"
    WindowSettings.font_size = 14
    WindowSettings.save_settings()
    print(f"state file = {STATE_FILE.read_text(encoding='utf-8')}")

    section("the configuration side re-reads the shared file")
    RuntimeConfig.load_configuration()
    print(f"theme  = {RuntimeConfig.theme!r} (the value the settings side saved)")
    try:
        RuntimeConfig.theme = "dark"
    except TypeError as error:
        print(f"write  -> TypeError: {error}")

    section("same member names, different addresses: the prefixes keep them apart")
    os.environ["APP_SETTINGS_TIMEOUT"] = "45"  # the app's own parameter, not the deployed one
    FeatureSettings.load_settings()
    print(
        f"APP_SETTINGS_TIMEOUT = {os.environ['APP_SETTINGS_TIMEOUT']!r} -> "
        f"FeatureSettings.timeout = {FeatureSettings.timeout!r}"
    )
    print(
        f"APP_CONFIG_TIMEOUT   = {os.environ['APP_CONFIG_TIMEOUT']!r} -> "
        f"RuntimeConfig.timeout = {RuntimeConfig.timeout!r}"
    )
    print("(two members named timeout, two variables: each class's prefix selects its own)")

    section("configuration -> settings: a point value and a name intersection")
    # a point value is a plain assignment: the configuration side validated
    # the value at its load, the settings side runs its own constraints on
    # the write. The other direction is no assignment at all — the shared
    # file above is that path: the settings side saves, the configuration
    # side reloads
    FeatureSettings.timeout = RuntimeConfig.timeout
    print(
        f"timeout = {FeatureSettings.timeout!r} (the deployed value adopted as the initial value)"
    )
    # a whole handover goes through update_from_dict over the shared names
    # only: the update is strict about unknown names on purpose (a typo must
    # fail, not vanish), and which members are "the same" is the
    # application's knowledge, not the library's guess
    config_values = RuntimeConfig.to_dict()
    known = FeatureSettings.to_dict()
    shared = {name: value for name, value in config_values.items() if name in known}
    print(f"names shared by the two classes: {sorted(shared)} (url and theme are not shared)")
    FeatureSettings.update_from_dict(shared)
    print(
        f"timeout = {FeatureSettings.timeout!r} (the same value, obtained via the "
        "intersection route)"
    )

    # cleanup: the settings package wrote the file; the sample removes it
    STATE_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
