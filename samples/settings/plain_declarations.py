"""
Example: the plain declaration style of Advexp.Settings.

Members are typed annotations, and the source binding of the class names the
storage. This is a declaration style without any factory for a particular
backend. The tour walks through the style in full:

- the three plain spellings (a bare annotation, an annotated assignment, and
  ``ClassVar``);
- the rich ``setting(...)`` form next to them;
- the ``*_source`` builders of the families;
- the dictionary storage of the class (``mapping_source``);
- the JSON file seat next to a foreign binding (``json_file``);
- the cases in which the ``class`` statement fails with an error;
- inheritance of the binding;
- a file per environment, through ``env_parameter``;
- the members that stand outside the reach of the style
  (``non_storage_setting``, and the family factories of a multi-storage
  class).

Run from the repository root with the package installed
(``pip install "advexp-settings[dotenv]"``):

    python samples/settings/plain_declarations.py

The sample writes its files next to this script and removes them at startup,
so every run starts from a clean slate.
"""

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as env_file
import advexp.settings.plugins.environment.variables as env
import advexp.settings.plugins.json_settings as js
from advexp.settings.plugins.mapping_source import mapping_source, mapping_source_for

SAMPLES_DIR = Path(__file__).resolve().parent
APP_FILE = SAMPLES_DIR / "plain-declarations-app.json"
EDITOR_FILE = SAMPLES_DIR / "plain-declarations-editor.json"
DOTENV_FILE = SAMPLES_DIR / "plain-declarations.env"
SEAT_FILE = SAMPLES_DIR / "plain-declarations-seat.json"
DOTENV_SEAT_FILE = SAMPLES_DIR / "plain-declarations-seat.env"
# one file per environment: the template's slot is filled per pass, and
# the slot spells "env" — not the variable's own name
DEPLOY_TEMPLATE = "plain-declarations-{env}.json"

# the environment members' variable names
MODE_VAR = "DEMO_PLAIN_MODE"
ENV_VAR = "DEMO_PLAIN_ENV"


class ServiceSettings(
    adv_settings.Settings,
    options=js.json_source(file=APP_FILE, name_pattern="{ClassName}.{FieldName}"),
):
    """One class, one storage, plain members.

    A plain member reads the single source of the class: the JSON binding that
    is declared here. The family of the binding builds the key of each member by
    its own rules (here, the ``{ClassName}.{FieldName}`` pattern), in the way
    that the storage that the member actually reads spells it.
    """

    # a bare annotation: a required member — the file must provide the
    # value or the load aborts
    token: str
    # an annotated assignment: that value is the member's declared
    # default, written in its typed form
    session_ttl: timedelta = timedelta(minutes=30)
    host: str = "localhost"
    # the rich spelling of the same member: name= is the full literal
    # address in the file — the key pattern never touches it — and the
    # keyword parameters past it are the declared value constraints
    port: int = adv_settings.setting(name="port", ge=1, le=65535, default=8080)
    # aliases: full literal addresses too; a load tries the primary
    # address first, then each alias, and saving writes the primary one
    region: str = adv_settings.setting(aliases=["zone"], default="eu")
    # a ClassVar annotation is not a member at all: the plain class
    # attribute it always was, no pass ever touches it
    schema_note: ClassVar[str] = "service settings, layout v1"


class EnvSettings(
    adv_settings.Settings,
    options=env.env_source(name_prefix="DEMO_PLAIN_", name_case=env.NameCase.UPPER),
):
    """The process environment as the single source of the class.

    These are the same plain members, in the naming of the environment family:
    the member ``mode`` is the variable ``DEMO_PLAIN_MODE``. The prefix and the
    case come from the binding, and the member name stays as declared.
    """

    mode: str = "production"
    session_ttl: timedelta = timedelta(minutes=30)


class FeatureSettings(
    adv_settings.Settings,
    options=env_file.dotenv_source(
        file=DOTENV_FILE, name_prefix="DEMO_PLAIN_", name_case=env_file.NameCase.UPPER
    ),
):
    """A ``.env`` file as the single source of the class.

    The file backend reads and writes the variable lines of the bound file. The
    names are built by the shared rules of the environment family, so the member
    ``beta_ui`` is the variable ``DEMO_PLAIN_BETA_UI``.
    """

    beta_ui: bool = False


class SeatedSettings(
    adv_settings.Settings,
    options=(
        env.env_source(name_prefix="DEMO_PLAIN_", name_case=env.NameCase.UPPER),
        js.json_file(SEAT_FILE),
        env_file.dotenv_file(DOTENV_SEAT_FILE),
    ),
):
    """Plain members on one source, and file members on the seats of the families.

    The binding of the class is the environment, so the plain members keep their
    single source. ``json_file`` and ``dotenv_file`` seat the files that the
    members of their families read. These are the declarative files of a class
    whose binding is held by another family. The variable name of the dotenv
    member is built by the shared dictionary of the environment family.
    """

    mode: str = "production"

    # the key "retries" in the seated JSON file
    retries: int = js.json_setting(name="retries", default=3)

    # DEMO_PLAIN_FLAG in the seated .env file
    flag: bool = env_file.dotenv_setting(default=False)


class Limits(adv_settings.Settings):
    """A class with no source binding at all.

    A member without a storage needs no backend module, so the class declares no
    storage. It also declares no plain member, because a plain member would have
    nothing to read.
    """

    retries: int = adv_settings.non_storage_setting(default=3, ge=0)


class DictionarySettings(
    adv_settings.Settings,
    options=mapping_source({"token": "seed-token", "foreign": 42}),
):
    """The dictionary storage of the class: a source that is bound like a file.

    The dictionary is seeded at the declaration, and from then on it lives as the
    own storage of the class. Loads read it, and saves write the member keys into
    it. Between the passes, the ``set()`` and ``get()`` of the resolver replace
    the whole dictionary and take a snapshot of it.
    """

    token: str = "fallback"
    window: int = 60


# the template's slot may spell another name than the variable: slot=
# renames it, and the template's checks go by slot names
deploy_env = adv_settings.env_parameter(ENV_VAR, choices=("dev", "prod"), default="dev", slot="env")


class DeploySettings(
    adv_settings.Settings,
    options=js.json_source(
        file=SAMPLES_DIR / DEPLOY_TEMPLATE,
        name_pattern="{FieldName}",
        parameters=deploy_env,
    ),
):
    """The file of the environment that a variable names.

    The file of the binding spells a slot that the parameter fills on each pass.
    The whitelist guards the variable before anything touches the file system,
    and a save lands in the file of the environment that the load read.
    """

    token: str = "none"


class WindowSettings(ServiceSettings):
    """A subclass without its own binding inherits the nearest binding above it.

    The class composes the members of its base class with its own members, and
    it keeps reading the file of the base class, under its own keys.
    """

    width: int = 800


class EditorSettings(
    ServiceSettings,
    options=js.json_source(file=EDITOR_FILE, name_pattern="{FieldName}"),
):
    """A subclass with its own binding switches to it for itself alone.

    The pattern changes too (bare member names, for a file that a person edits by
    hand), while the base class keeps reading its own storage, untouched.
    """

    tab_width: int = 4


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # every run starts from a clean slate
    APP_FILE.unlink(missing_ok=True)
    EDITOR_FILE.unlink(missing_ok=True)
    DOTENV_FILE.unlink(missing_ok=True)
    SEAT_FILE.unlink(missing_ok=True)
    DOTENV_SEAT_FILE.unlink(missing_ok=True)
    for environment in ("dev", "prod"):
        (SAMPLES_DIR / DEPLOY_TEMPLATE.format(env=environment)).unlink(missing_ok=True)
    for name in (MODE_VAR, ENV_VAR):
        os.environ.pop(name, None)

    section("the plain spellings: what the class body declares")
    # the three spellings land as members of one kind: a bare annotation
    # required, an annotated assignment defaulted, setting(...) the same
    # member in its rich form. A ClassVar stays out of the machinery
    print(f"members    = {list(ServiceSettings.__settings_members__)}")
    print(f"ClassVar   = {ServiceSettings.schema_note!r} (a plain class attribute)")
    print(f"host       = {ServiceSettings.host!r} (the declared default)")
    print(f"session_ttl = {ServiceSettings.session_ttl!r} (typed, as declared)")

    section("a bare annotation is required: no value, no load")
    # the file holds nothing yet: the required member aborts the load,
    # and the abort names the member and the key the file never carried
    try:
        ServiceSettings.load_settings()
    except adv_settings.AggregateLoadError as error:
        print(f"abort      -> {type(error.errors[0]).__name__}: {error.errors[0]}")
    # the file provides the value: the same load completes
    APP_FILE.write_text(json.dumps({"ServiceSettings.token": "abc"}), encoding="utf-8")
    ServiceSettings.load_settings()
    print(f"token      = {ServiceSettings.token!r} (loaded)")

    section("the storage form converts to the annotation")
    # a hand-edited file speaks the storage form; the load converts it,
    # the way it converted nothing here yet — "1:30:00" is a timedelta
    # string, and the printed value is the parsed object, not the text
    document = json.loads(APP_FILE.read_text(encoding="utf-8"))
    document["ServiceSettings.session_ttl"] = "1:30:00"
    document["port"] = 9000  # the literal address of setting(name="port")
    APP_FILE.write_text(json.dumps(document), encoding="utf-8")
    ServiceSettings.load_settings()
    print(f"session_ttl = {ServiceSettings.session_ttl!r} (parsed, not a string)")
    print(f"port       = {ServiceSettings.port!r} (the literal key, not the pattern)")

    section("aliases: an old storage key keeps serving a renamed member")
    # the file carries the pre-rename key alone: the alias serves the
    # member, and the next save writes the primary key — the rename
    # migrates on its own schedule
    document = json.loads(APP_FILE.read_text(encoding="utf-8"))
    document["zone"] = document.pop("ServiceSettings.region", "eu")
    APP_FILE.write_text(json.dumps(document), encoding="utf-8")
    ServiceSettings.load_settings()
    print(f"region     = {ServiceSettings.region!r} (read from the alias key 'zone')")
    ServiceSettings.region = "eu-central"
    ServiceSettings.save_settings()
    stored = json.loads(APP_FILE.read_text(encoding="utf-8"))
    print(f"zone       = {stored['zone']!r} (the alias key is unchanged)")
    print(f"region key = {stored['ServiceSettings.region']!r} (the primary key that was written)")

    section("constraints travel with the member")
    # setting(ge=1, le=65535) is checked on every boundary: a violating
    # assignment never reaches the class storage
    try:
        ServiceSettings.port = 70000
    except adv_settings.SettingValidationError as error:
        print(f"rejected   -> {error}")
    print(f"port       = {ServiceSettings.port!r} (unchanged)")

    section("assign, save, reload — the plain member is a full member")
    # every pass of the class-level API serves the plain member exactly
    # as it serves a factory-declared one
    ServiceSettings.host = "db.example.com"
    ServiceSettings.save_settings()
    print(f"file keys  = {sorted(json.loads(APP_FILE.read_text(encoding='utf-8')))}")
    ServiceSettings.reset_settings()
    ServiceSettings.load_settings()
    print(f"host       = {ServiceSettings.host!r} (loaded back from the file)")
    # the single-setting passes speak it too: save one member, delete one
    ServiceSettings.port = 9001
    ServiceSettings.save_setting(lambda s: s.port)
    ServiceSettings.delete_setting(lambda s: s.region)
    print(
        f"port       = {ServiceSettings.port!r}, "
        f"region = {ServiceSettings.region!r} (deleted, back to its default)"
    )

    section("the process environment as the class's single source")
    # the same plain spellings over another family's binding: the member
    # names become variables by the binding's prefix and case
    os.environ[MODE_VAR] = "staging"
    os.environ["DEMO_PLAIN_SESSION_TTL"] = "0:45:00"
    EnvSettings.load_settings()
    print(f"mode       = {EnvSettings.mode!r} (from DEMO_PLAIN_MODE)")
    print(f"session_ttl = {EnvSettings.session_ttl!r} (converted from '0:45:00')")
    # saving the environment family writes the process environment itself
    EnvSettings.mode = "production"
    EnvSettings.save_settings()
    print(f"after save = {os.environ[MODE_VAR]!r} (the variable was written)")
    for name in (MODE_VAR, "DEMO_PLAIN_SESSION_TTL"):
        os.environ.pop(name, None)

    section("a .env file as the class's single source")
    DOTENV_FILE.write_text("DEMO_PLAIN_BETA_UI=True\n", encoding="utf-8")
    FeatureSettings.load_settings()
    print(f"beta_ui    = {FeatureSettings.beta_ui!r} (converted from 'True')")
    FeatureSettings.beta_ui = False
    FeatureSettings.save_settings()
    print(f"file lines = {DOTENV_FILE.read_text(encoding='utf-8').splitlines()!r}")

    section("the class's dictionary storage")
    # the storage is a dictionary: seeded at the declaration, read by the
    # loads, written by the saves — and the resolver hands it over, set()
    # replacing it whole and get() snapshotting what stands
    DictionarySettings.load_settings()
    print(f"token      = {DictionarySettings.token!r} (from the initial dictionary)")
    mapping_source_for(DictionarySettings).set(
        {"token": "runtime-token", "window": 90, "extra": "kept"}
    )
    DictionarySettings.load_settings()
    print(
        f"window     = {DictionarySettings.window!r} (after set(), "
        "the whole dictionary is replaced)"
    )
    DictionarySettings.token = "saved"
    DictionarySettings.save_settings()
    snapshot = mapping_source_for(DictionarySettings).get()
    print(f"dictionary = {snapshot!r} (only the member keys were saved)")

    section("the class statement refuses what it cannot resolve")
    # a plain member must have exactly one source to read: the class
    # statement itself refuses none and several, naming the member
    try:

        class Unbound(adv_settings.Settings):
            token: str

    except TypeError as error:
        print(f"no source  -> TypeError: {error}")
    try:

        class BoundTwice(
            adv_settings.Settings,
            options=(js.json_source(file=APP_FILE), env.env_source()),
        ):
            token: str

    except TypeError as error:
        print(f"two sources -> TypeError: {error}")
    # the dictionary storage is the plain members' one binding: no order
    # between the bindings exists for a member to follow, so the pair
    # refuses the same way
    try:

        class Shared(
            adv_settings.Settings,
            options=(mapping_source(), js.json_source(file=APP_FILE)),
        ):
            token: str

    except TypeError as error:
        print(f"dict+file  -> TypeError: {error}")
    # the same members stand once they pick their storages through the
    # family factories — the factory narrows the member to its own
    # family's builder, several families or not

    class Spread(
        adv_settings.Settings,
        options=(js.json_source(file=APP_FILE), env.env_source()),
    ):
        token: str = js.json_setting(name="token", default="none")
        mode: str = env.environment_variable_setting(name=MODE_VAR, default="production")

    os.environ[MODE_VAR] = "staging"
    Spread.load_settings()
    print(f"factories  = token={Spread.token!r}, mode={Spread.mode!r} (a valid class)")
    os.environ.pop(MODE_VAR, None)

    section("a file seat: plain members keep the single source")
    # json_file and dotenv_file seat the class's files while the env
    # binding stays the class's single source: the plain members live,
    # the factory members read their seated files, and the plugin
    # handles read the same seats
    SEAT_FILE.write_text(json.dumps({"retries": 7}), encoding="utf-8")
    DOTENV_SEAT_FILE.write_text("DEMO_PLAIN_FLAG=true\n", encoding="utf-8")
    SeatedSettings.load_settings()
    print(f"mode       = {SeatedSettings.mode!r} (a plain member: the declared default)")
    print(f"retries    = {SeatedSettings.retries!r} (the 7 from the seated file)")
    print(f"flag       = {SeatedSettings.flag!r} (from the seated .env file)")
    handle = SeatedSettings.get_plugin(js.JSONSettingsPlugin)
    print(f"seat file  = {handle.file_path!r} (the runtime view of the seat)")
    SeatedSettings.retries = 5
    SeatedSettings.save_setting(lambda s: s.retries)
    stored = json.loads(SEAT_FILE.read_text(encoding="utf-8"))
    print(f"saved      = retries {stored['retries']!r} (into the seated file)")

    section("a member without a storage: nothing to read, nothing to write")
    # non_storage_setting needs no backend module and no class binding:
    # the core import alone carries a working class, and its load and
    # save passes run clean — no storage is ever asked
    Limits.load_settings()
    print(f"retries    = {Limits.retries!r} (the declared default)")
    Limits.retries = 5
    Limits.save_settings()
    print(f"after save = {Limits.retries!r} (assigned only; no storage was accessed)")
    Limits.load_settings()
    print(f"after load = {Limits.retries!r} (the load restores the declared default)")

    section("inheritance: the nearest binding above, or the subclass's own")
    # a subclass without its own binding reads the base's file, under
    # its own keys; a subclass with one switches to it for itself alone.
    # The required token came along in the inheritance: it needs a value
    # before a save can store it, so the pass gets one here
    WindowSettings.token = "window"
    WindowSettings.width = 1024
    WindowSettings.save_settings()
    base_keys = sorted(json.loads(APP_FILE.read_text(encoding="utf-8")))
    print(f"base file  = {base_keys} (the WindowSettings keys were added to it)")
    EDITOR_FILE.write_text(json.dumps({"token": "editor"}), encoding="utf-8")
    EditorSettings.load_settings()
    EditorSettings.tab_width = 2
    EditorSettings.save_settings()
    print(f"own file   = {json.loads(EDITOR_FILE.read_text(encoding='utf-8'))}")
    print(f"base keeps = {ServiceSettings.host!r} (its own storage, untouched)")

    section("a file per environment: the binding's templated file")
    # the variable picks the file the binding reads; the whitelist
    # guards it before anything touches the file system, and the write
    # follows the load, not the variable
    dev_file = SAMPLES_DIR / DEPLOY_TEMPLATE.format(env="dev")
    prod_file = SAMPLES_DIR / DEPLOY_TEMPLATE.format(env="prod")
    os.environ[ENV_VAR] = "dev"
    DeploySettings.load_settings()
    DeploySettings.token = "dev-value"
    DeploySettings.save_settings()
    print(f"saved      = {dev_file.name}: {json.loads(dev_file.read_text(encoding='utf-8'))}")
    os.environ[ENV_VAR] = "prod"  # the variable moved on
    DeploySettings.token = "prod-value"
    DeploySettings.save_settings()
    print(
        f"saved      = {dev_file.name} again (the save goes to the file chosen at "
        "load time, not to the current value of the variable)"
    )
    assert not prod_file.exists()
    # a typo fails loudly instead of quietly becoming a missing file
    os.environ[ENV_VAR] = "prodd"
    try:
        DeploySettings.load_settings()
    except ValueError as error:
        print(f"typo       -> {type(error).__name__}: {error}")
    os.environ.pop(ENV_VAR)
    DeploySettings.load_settings()
    print(f"unset      = {DeploySettings.token!r} (default=dev selected the file above)")


if __name__ == "__main__":
    main()
