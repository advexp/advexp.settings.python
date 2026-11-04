"""
Example: the application-side API of Advexp.Settings.

The bundled plugins serve the walkthrough together: environment variables, a
dotenv file, and a JSON file. One class has members of several backends, and
each member goes through the own factory of its plugin. Building a backend of
your own (backend parameters, behavior driven by metadata, and dynamic
settings) is shown in ``samples/settings/custom_backend.py``.

Run from the repository root with the package installed
(``pip install "advexp-settings[dotenv]"``):

    python samples/settings/settings_api.py

The sample writes its files next to this script and removes them at startup,
so every run starts from a clean slate.

The sample walks through the following topics:

- declaring settings and effective defaults;
- startup validation of declared defaults (they are converted to the
  annotated type, or the ``class`` statement fails);
- plain declarations (a bare annotation is a required member, an annotated
  assignment gives a default, ``setting(...)`` is the rich spelling, and
  ``ClassVar`` is not a member at all);
- a file per environment through ``env_parameter`` (the write lands in the
  environment that the load read);
- a default file for the whole module through ``for_this_module`` (a
  declaration that a tool collects by import, without running the code);
- class-level load, save, and delete passes across the three storages (the
  load report of the members that fell back, and the aggregate abort when a
  ``adv_settings.REQUIRED`` member got nothing usable);
- operations on a single setting (by name string and by getter lambda);
- an unconvertible stored value (a warning is logged, and the default is
  restored);
- value constraints (a taste: the bounds of a member and one rule across
  members; the full tour is ``samples/settings/validation.py``);
- dict snapshots (``to_dict`` and ``update_from_dict``);
- iteration over the declared settings (``to_dict().items()``);
- access by textual name (``getattr``, ``setattr``, and the checked
  ``update_from_dict``);
- object snapshots (``to_object`` and ``update_from_object``);
- dataclass values;
- secret values;
- member name aliases (an old storage key that serves a renamed member);
- metadata, instances, and inheritance.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar, List, Optional

import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as env_file
import advexp.settings.plugins.environment.variables as env
import advexp.settings.plugins.json_settings as js

# ---------------------------------------------------------------------------
# adv_settings.Settings classes
# ---------------------------------------------------------------------------

SAMPLES_DIR = Path(__file__).resolve().parent
JSON_FILE = SAMPLES_DIR / "settings-api-sample.json"
DOTENV_FILE = SAMPLES_DIR / "settings-api-sample.env"

# the module's default file, declared at the module's top level: the
# classes without a binding of their own (ModuleDefaults below) read it,
# and every module of the application declares its own this way. One
# location for the whole process is the plain assignment instead:
# js.JSONSettingsConfiguration.file_path = MODULE_DEFAULTS_FILE
MODULE_DEFAULTS_FILE = SAMPLES_DIR / "settings-api-module-defaults.json"
js.JSONSettingsConfiguration.file_path = adv_settings.for_this_module(MODULE_DEFAULTS_FILE)

# the environment members' full variable names
MODE_VAR = "DEMO_API_MODE"
TOKEN_VAR = "DEMO_API_TOKEN"


@dataclass
class Proxy:
    """A structured value: dataclasses round-trip as objects of their fields."""

    host: str
    port: int = 3128


class Endpoint:
    """A custom type outside the conversion contract.

    The conversion leaves its values alone (the JSON backend stores such objects
    as they are), so a declared default must already be an instance of the
    class. This is what startup validation checks for such types.
    """

    def __init__(self, url: str) -> None:
        self.url = url


class AppSettings(
    adv_settings.Settings,
    options=(
        js.json_file(JSON_FILE),
        env_file.dotenv_file(DOTENV_FILE),
    ),
):
    """Typed application settings that are served by three bundled plugins at once:
    environment variables, a dotenv file, and a JSON file.

    The ``options=`` keyword names the files of the families that need them (a
    sequence composes several entries). The environment family needs none,
    because its storage is the process environment itself.
    """

    # class metadata: the reserved class-level name; every settings class
    # along the MRO contributes its own mapping, the most derived one
    # winning per key (the file-binding idiom). Readable before any
    # set_class_metadata call
    class_metadata = {"config-version": 2}

    # members are declared through each plugin's factory: the spelling
    # static checkers accept. Assigning the attribute instance works exactly
    # the same at runtime (`mode: str = EnvironmentVariableSetting(...)`),
    # but the analyzer will flag it: it cannot see the metaclass swapping
    # the attribute for a value descriptor, so it reports a type mismatch.
    # explicit storage name: the variable is exactly DEMO_API_MODE;
    # metadata= is carried by the same declaration: the member's initial
    # metadata, seeded into the class at creation
    mode: str = env.environment_variable_setting(
        name=MODE_VAR, default="production", metadata={"ui-label": "Mode", "ui-order": 1}
    )
    # no name=: the key is the full pattern name (module.class.member)
    retries: int = js.json_setting(default=3, metadata={"ui-label": "Retry count"})
    # the dotenv backend reads and writes the bound file's variable lines
    debug: bool = env_file.dotenv_setting(name="DEBUG", default=False)
    # a JSON member holds None as null, lists and objects as they are
    started_at: Optional[datetime] = js.json_setting(name="started_at", default=None)
    tags: List[str] = js.json_setting(name="tags", default=[])
    proxy: Optional[Proxy] = js.json_setting(name="proxy", default=None)
    # the secret mark is declared inert data: whatever consumer reads it
    # (a UI hiding the value, say) reads it statically, without a set_* call;
    # adv_settings.SecretStr is the masking itself: prints and messages show '**********'
    api_token: Optional[adv_settings.SecretStr] = env.environment_variable_setting(
        name=TOKEN_VAR, default=None, metadata={"secret": True}
    )
    # a default in its storage form: converted to the annotation at class
    # creation, before any storage access
    workers: int = env_file.dotenv_setting(name="WORKERS", default="4")
    # aliases: the storage may still carry the pre-rename key; a load looks
    # the primary key up first, then each alias, and the first found wins
    # (saving writes the primary key alone — the rename migrates on the next
    # save, the old deployment keeps working until then)
    timeout: int = js.json_setting(name="timeout", aliases=["ttl"], default=30)


class DevSettings(AppSettings):
    """A subclass composes the members of its base and gets its own storage."""

    mock_api: bool = env.environment_variable_setting(name="DEMO_API_MOCK", default=True)


class NetSettings(
    adv_settings.Settings,
    options=js.json_file(JSON_FILE),
):
    """Members with declared value constraints.

    This class shows a taste of the two levels: the own bounds of a member
    (``ge=1, le=65535``) and a rule across members (``ge=min_port``, which
    compares the value with the current value of the referenced member). The
    full tour covers every constraint parameter, the ``when=`` conditions, the
    ``__validate__`` hook, and every point at which the checks run. It is in
    ``samples/settings/validation.py``.
    """

    port: int = js.json_setting(name="net.port", default=8080, ge=1, le=65535)
    min_port: int = js.json_setting(name="net.min-port", default=1024)
    max_port: int = js.json_setting(name="net.max-port", default=65535, ge=min_port)


class ModuleDefaults(adv_settings.Settings):
    """A class on the default file that the module declared.

    This class has no ``options=`` of its own. The members of the family read the
    file that the module declared at its top level with ``for_this_module`` (see
    the constants above). The declaration holds for the classes of this module
    only, and the process-wide assignment stays the channel for the classes of
    every other module.
    """

    retries: int = js.json_setting(name="retries", default=5)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def describe_storages() -> None:
    """Print the three storages the class is spread over."""
    variables = {name: os.environ[name] for name in (MODE_VAR, TOKEN_VAR) if name in os.environ}
    print(f"env vars   = {variables}")
    print(f".env file  = {DOTENV_FILE.read_text(encoding='utf-8').splitlines()!r}")
    print(f"json file  = {json.loads(JSON_FILE.read_text(encoding='utf-8'))}")


def main() -> None:
    # optional: the library reports problems (conversion fallbacks, backend
    # errors) as warnings on the "advexp.settings" channel. logger() hands
    # out the family's root channel — one object every record of every
    # package passes through — and the application configures it without
    # knowing the channel's name: a handler with its own format here, and
    # the propagation off, so the records go to this handler alone
    # (adv_settings.Settings.logger() hands out this package's channel alone, for
    # configuring one package without the rest of the family)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("log: %(message)s"))
    library_logger = adv_settings.LibraryConfiguration.logger()
    library_logger.addHandler(handler)
    library_logger.setLevel(logging.INFO)
    library_logger.propagate = False

    # every run starts from a clean slate
    JSON_FILE.unlink(missing_ok=True)
    DOTENV_FILE.unlink(missing_ok=True)
    MODULE_DEFAULTS_FILE.unlink(missing_ok=True)
    for name in (MODE_VAR, TOKEN_VAR, "DEMO_API_MOCK"):
        os.environ.pop(name, None)

    section("declare once: effective defaults before any storage access")
    print(f"mode       = {AppSettings.mode!r}")
    print(f"retries    = {AppSettings.retries!r}")
    # (Optional members print None at times; None does define __repr__, the
    # checker's stub view says otherwise)
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {AppSettings.started_at!r}")

    section("declared defaults: validated and converted at class creation")
    # default= goes through the same conversion a load applies: the "4"
    # declared for an int member is served as 4, before any storage access.
    # A default that cannot convert, or is not an instance of a custom
    # annotated class outside the conversion contract, fails the class
    # statement itself, every offending member listed at once
    print(f'workers    = {AppSettings.workers!r} (declared as "4", returned as an int)')
    try:

        class Broken(adv_settings.Settings):
            when: datetime = env.environment_variable_setting(default="not-a-timestamp")
            endpoint: Endpoint = js.json_setting(default="https://x.example")

    except TypeError as error:
        print(f"Broken rejected at creation:\n{error}")

    section("plain declarations: the class's source reads typed members")
    # the plain spellings: a bare annotation is a required member the
    # storage must provide, an annotated assignment declares the default,
    # and setting(...) is the same member in its rich form — constraints,
    # an explicit address. A ClassVar annotation is not a member: the
    # plain class attribute it always was
    plain_file = SAMPLES_DIR / "settings-api-plain.json"
    plain_file.unlink(missing_ok=True)

    class PlainSettings(
        adv_settings.Settings,
        options=js.json_source(file=plain_file, name_pattern="{ClassName}.{FieldName}"),
    ):
        token: str  # REQUIRED: the file or the load's abort
        session_ttl: timedelta = timedelta(minutes=30)
        host: str = "localhost"
        port: int = adv_settings.setting(name="port", ge=1, le=65535, default=8080)
        debug_mode: bool = True

    class WithConstant(
        adv_settings.Settings,
        options=js.json_source(file=plain_file, name_pattern="{ClassName}.{FieldName}"),
    ):
        token: str = "none"
        is_sample: ClassVar[bool] = True  # not a member: stays a class attribute

    print(f"members    = {list(PlainSettings.__settings_members__)}")
    print(f"ClassVar   = {list(WithConstant.__settings_members__)} (is_sample is not included)")
    try:
        PlainSettings.load_settings()  # the file holds no token
    except adv_settings.AggregateLoadError as error:
        print(f"required   -> abort: {error.errors[0]}")
    # setting(name="port") is the full address: the pattern never touches it
    plain_file.write_text(
        json.dumps({"PlainSettings.token": "abc", "port": 9000}),
        encoding="utf-8",
    )
    report = PlainSettings.load_settings()
    print(f"report     = {report} (empty: every member was loaded or fell back to its default)")
    print(
        f"loaded     = token={PlainSettings.token!r}, "
        f"port={PlainSettings.port!r}, session_ttl={PlainSettings.session_ttl!r}"
    )
    plain_file.unlink()

    section("a file per environment: env_parameter templates the path")
    # the binding's file may spell slots an environment variable fills;
    # the whitelist guards the variable against a typo, the declared
    # default serves an unset variable, and a save lands in the file of
    # the environment the load read — the values always return to the
    # storage they came from
    app_env = adv_settings.env_parameter("DEMO_API_APP_ENV", choices=("dev", "prod"), default="dev")

    class EnvSettings(
        adv_settings.Settings,
        options=js.json_source(
            file=SAMPLES_DIR / "settings-api-{DEMO_API_APP_ENV}.json",
            parameters=app_env,
        ),
    ):
        token: str = "none"

    os.environ["DEMO_API_APP_ENV"] = "dev"
    EnvSettings.load_settings()
    EnvSettings.token = "dev-value"
    EnvSettings.save_settings()
    dev_file = SAMPLES_DIR / "settings-api-dev.json"
    dev_key = f"{EnvSettings.__module__}.EnvSettings.token"
    print(
        f"saved      = settings-api-dev.json: "
        f"{json.loads(dev_file.read_text(encoding='utf-8'))[dev_key]!r}"
    )
    os.environ["DEMO_API_APP_ENV"] = "prod"  # the variable moved on
    EnvSettings.token = "still-the-loaded-environment"
    EnvSettings.save_settings()
    print(
        f"saved      = dev file again: "
        f"{json.loads(dev_file.read_text(encoding='utf-8'))[dev_key]!r} "
        "(the save goes to the file chosen at load time, not to the current value of the variable)"
    )
    assert not (SAMPLES_DIR / "settings-api-prod.json").exists()
    for name in ("DEMO_API_APP_ENV",):
        os.environ.pop(name, None)
    for leftover in ("settings-api-dev.json",):
        (SAMPLES_DIR / leftover).unlink(missing_ok=True)

    section("a file for the whole module: for_this_module declares it")
    # ModuleDefaults carries no options=: its members read the file the
    # module declared at its top level. The declaration wins over the
    # process-wide assignment for this module's classes alone; a tool
    # that imports the settings modules reads every declaration in one
    # call, without running the application
    ModuleDefaults.retries = 9
    ModuleDefaults.save_settings()
    print(f"saved      = {MODULE_DEFAULTS_FILE.name}: retries = {ModuleDefaults.retries!r}")
    declared = adv_settings.declared_module_defaults()
    entry = declared[(js.JSONSettingsConfiguration, "file_path", __name__)]
    print(f"declared   = {entry}")

    section("assign and save (one class-level pass, three storages)")
    AppSettings.retries = 5
    AppSettings.debug = True
    AppSettings.started_at = datetime(2026, 9, 7, 12, 30, 0)
    AppSettings.tags = ["primary", "eu"]
    AppSettings.proxy = Proxy("proxy.example", 8080)
    # the save path stores the secret's plain payload (storages hold
    # payloads); adv_settings.SecretStr keeps the member's value masked everywhere else
    AppSettings.api_token = adv_settings.SecretStr("s3cr3t")
    AppSettings.save_settings()
    # MODE_VAR was never assigned away from its default but is saved too;
    # "retries" has no name=, so its key is built from the name pattern
    describe_storages()

    section("reload: values come back from the storages")
    AppSettings.reset_settings()
    print(f"retries    = {AppSettings.retries!r} (defaults first)")
    AppSettings.load_settings()
    print(f"retries    = {AppSettings.retries!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {AppSettings.started_at!r}  (datetime restored)")
    print(f"tags       = {AppSettings.tags!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"proxy      = {AppSettings.proxy!r}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"api_token  = {AppSettings.api_token!r}  (wrapped again on load)")

    section("aliases: an old storage key keeps serving a renamed member")
    # the file carries only the pre-rename key: the alias serves the member
    JSON_FILE.write_text(json.dumps({"ttl": 45}), encoding="utf-8")
    AppSettings.load_settings()
    print(f"timeout    = {AppSettings.timeout!r}  (read from the alias key 'ttl')")
    # the primary key outranks the alias once the file carries it
    JSON_FILE.write_text(json.dumps({"ttl": 45, "timeout": 60}), encoding="utf-8")
    AppSettings.load_settings()
    print(f"timeout    = {AppSettings.timeout!r}  (the primary key takes precedence)")
    # saving writes the primary key alone: the rename migrates on the next save
    AppSettings.timeout = 90
    AppSettings.save_setting("timeout")
    print(f"json file  = {json.loads(JSON_FILE.read_text(encoding='utf-8'))}")

    section("secret members: the wrapper keeps the payload out of prints")
    print(f"api_token  = {AppSettings.api_token!r}  (repr shows the mask)")
    print(
        f"get_secret_value() = {AppSettings.api_token.get_secret_value()!r}  (the only way to "
        "get the real value)"
    )
    as_dict = AppSettings.to_dict()
    print(f"to_dict()  = as_dict['api_token'] = {as_dict['api_token']!r}  (masked there too)")

    section("single-setting operations: name string and getter lambda")
    # the lambda names the setting as code and is never called; each member
    # talks to its own backend — retries to the JSON file, debug to the
    # dotenv file, mode to the environment
    print(
        f"contains_setting(lambda s: s.debug) = {AppSettings.contains_setting(lambda s: s.debug)}"
    )
    AppSettings.retries = 10
    AppSettings.save_setting(lambda s: s.retries)
    AppSettings.reset_setting(lambda s: s.retries)
    print(f"retries    = {AppSettings.retries!r} (one setting reset; no storage was accessed)")
    AppSettings.load_setting("retries")
    print(f"retries    = {AppSettings.retries!r} (loaded again by name)")
    AppSettings.delete_setting(lambda s: s.debug)
    print(
        f"after delete_setting: contains = {AppSettings.contains_setting('debug')}, "
        f"value = {AppSettings.debug!r} (back to the default)"
    )

    section("None is a stored value, not a deletion")
    # unlike the delete above, saving None keeps the key in the JSON file
    # (a null node); a string-only storage (env vars, dotenv lines) has no
    # null form and drops the entry instead
    AppSettings.started_at = None
    AppSettings.save_setting(lambda s: s.started_at)
    print(f"stored None: contains_setting = {AppSettings.contains_setting('started_at')}")
    # memory reset first: the member's default is None too, so the load below
    # is the sole source of the printed value
    AppSettings.reset_settings()
    AppSettings.load_setting("started_at")
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"started_at = {AppSettings.started_at!r} (the stored None, not a missing key)")

    section("a bad stored value: warning logged, default restored")
    # like a hand-edited file: the stored value no longer fits the annotation
    document = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    document["started_at"] = "not-a-timestamp"
    JSON_FILE.write_text(json.dumps(document), encoding="utf-8")
    entry = AppSettings.load_setting("started_at")
    # noinspection PyStringConversionWithoutDunderMethod
    print(
        f"started_at = {AppSettings.started_at!r} (the value cannot be converted -> default; a "
        "warning was logged)"
    )
    print(f"entry      = {entry}  (the member's entry in the report returned by load_settings)")

    section("the class-level load report: what fell back, as data")
    # the same bad value through the whole-class pass: every member loads,
    # the failing one falls back with its warning, and the fallback is an
    # entry of the report load_settings returns — data for a health check
    # or a CLI banner, not a log line to parse; a plain miss (a variable
    # simply not set) is no entry: that is the default's normal way
    report = AppSettings.load_settings()
    print(f"report     = {report}")
    # noinspection PyStringConversionWithoutDunderMethod
    print(
        f"started_at = {AppSettings.started_at!r} (the default; the report entry gives the reason)"
    )
    AppSettings.started_at = datetime(2026, 9, 7, 12, 30, 0)
    AppSettings.save_setting(lambda s: s.started_at)  # store a good value back

    section("default=adv_settings.REQUIRED: the value must come from a source")

    # the other channel: a required member that got nothing usable aborts
    # the load — one aggregate for every failure, with the same run's
    # optional fallbacks marked beside them (errors and fallbacks apart)
    class DeploySettings(adv_settings.Settings):
        token: str = env.environment_variable_setting(
            name="DEMO_API_DEPLOY_TOKEN", default=adv_settings.REQUIRED
        )
        workers: int = env.environment_variable_setting(name="DEMO_API_WORKERS", default=4, ge=1)

    os.environ["DEMO_API_WORKERS"] = "many"  # unconvertible: a fallback entry
    try:
        DeploySettings.load_settings()
    except adv_settings.AggregateLoadError as error:
        print(f"errors     = {error.errors}")
        print(f"fallbacks  = {error.fallbacks}")
    print(f"workers    = {DeploySettings.workers!r} (its default)")
    del os.environ["DEMO_API_WORKERS"]

    section("value constraints: declared on the member, enforced everywhere")
    # a taste of the two levels: the member's own bounds reject a bad
    # assignment, and the rule across members (ge=min_port) is the manual
    # check's to catch — an assignment never runs it. The full tour of
    # validation (every constraint parameter, when= conditions, the
    # __validate__ hook, the load's soft fallback, the strict updates and
    # saves) is samples/settings/validation.py
    print(f"port       = {NetSettings.port!r} (the default, within the bounds)")
    try:
        NetSettings.port = 70000
    except adv_settings.SettingValidationError as error:
        print(f"assignment rejected: {error}")
    NetSettings.min_port = 70000  # accepted: its own bounds hold
    try:
        NetSettings.validate_settings()
    except adv_settings.SettingValidationError as error:
        print(f"manual check rejected the pair: {error.problems}")
    NetSettings.min_port = 1024
    NetSettings.validate_settings()  # the pair agrees again

    section("snapshots: to_dict / update_from_dict (no storage access)")
    snapshot = AppSettings.to_dict()
    print(f"snapshot   = {snapshot}")
    snapshot["tags"].append("mutated")
    print(f"tags       = {AppSettings.tags!r}  (changing the snapshot does not affect the class)")
    AppSettings.retries = 99
    AppSettings.update_from_dict(snapshot)
    print(f"retries    = {AppSettings.retries!r} (restored from the snapshot)")
    snapshot["retries"] = 0  # the update deep-copied: later dict changes don't leak
    print(f"retries    = {AppSettings.retries!r} (class keeps its own copy)")
    AppSettings.update_from_dict({"retries": "8080"})  # converted like on load
    print(
        f"retries    = {AppSettings.retries!r} ({type(AppSettings.retries).__name__} from '8080')"
    )
    # a dataclass is rebuilt from a plain object of its fields: the form a
    # JSON file stores it in; missing fields take the dataclass defaults
    AppSettings.update_from_dict({"proxy": {"host": "other.example"}})
    # noinspection PyStringConversionWithoutDunderMethod
    print(f"proxy      = {AppSettings.proxy!r} (dataclass from a dict)")
    try:
        AppSettings.update_from_dict({"no-such": 1})
    except KeyError as error:
        print(f"unknown key -> KeyError: {error}")
    # a dictionary from elsewhere — the model_dump() of another model —
    # passes the opt-in: foreign keys drop with a debug record
    AppSettings.update_from_dict({"retries": 7, "computed": "extra"}, ignore_unknown=True)
    print(f"retries    = {AppSettings.retries!r} (foreign key ignored)")

    section("iterate the declared settings: to_dict().items()")
    # the walk over every declared setting: names in declaration order,
    # values the effective ones (members never assigned report their
    # defaults). The values are deep-copied, like every to_dict snapshot
    for name, value in AppSettings.to_dict().items():
        print(f"{name:<10} = {value!r}")

    section("access by textual name: getattr / setattr / update_from_dict")
    # a member name may arrive as a string at runtime (config key, CLI
    # argument): getattr and setattr speak it natively, the metaclass routing
    # a member-name assignment into the class storage
    print(f"retries    = {getattr(AppSettings, 'retries')!r}")
    setattr(AppSettings, "retries", 5)
    print(f"retries    = {AppSettings.retries!r} (assigned by name)")
    try:
        getattr(AppSettings, "no_such")
    except AttributeError as error:
        print(f"read miss  -> AttributeError: {error}")
    # plain setattr checks nothing: a typo would silently create a stray class
    # attribute instead of failing, shown here and cleaned up right away
    setattr(AppSettings, "nmae", 1)
    print("typo write -> no error; a new stray class attribute 'nmae' was created")
    delattr(AppSettings, "nmae")
    # the checked by-name write: update_from_dict rejects unknown names (the
    # error listing every member) and converts the value like a load does
    AppSettings.update_from_dict({"retries": "8080"})
    print(f"retries    = {AppSettings.retries!r} (validated write; '8080' converted)")
    try:
        AppSettings.update_from_dict({"no_such": 1})
    except KeyError as error:
        print(f"write miss -> KeyError: {error}")

    section("snapshots: to_object / update_from_object (a detached instance)")
    # an instance of the settings class with storage of its own: the fields
    # keep the declared names and annotations, so after renaming a setting
    # every stale snapshot field access becomes a type-checker error (and an
    # AttributeError at runtime); unlike dict keys, which fail silently
    state = AppSettings.to_object()
    print(
        f"state      = mode={state.mode!r}, retries={state.retries!r} (its own copy of the values)"
    )
    state.retries = 5
    state.tags.append("checked")
    print(
        f"class      = retries={AppSettings.retries!r}, tags={AppSettings.tags!r} "
        "(writes to the snapshot stay local)"
    )
    AppSettings.update_from_object(state)
    print(
        f"class      = retries={AppSettings.retries!r}, tags={AppSettings.tags!r} "
        "(restored from the snapshot)"
    )
    state.tags.append("leaked?")
    print(
        f"class tags = {AppSettings.tags!r} (the update made a deep copy, so later changes do "
        "not affect the class)"
    )
    try:
        AppSettings.update_from_object(SimpleNamespace(no_such=1))
    except KeyError as error:
        print(f"unknown field -> KeyError: {error}")

    section("metadata: declared with the members, then layered at runtime")
    # the declarations open the storages: metadata= on the members,
    # class_metadata on the class. Both are readable before any
    # set_* call: what a UI or a schema generator reads statically, with
    # no ordering requirements on user code
    print(
        f"metadata   = "
        f"{AppSettings.get_setting_metadata(lambda s: s.mode, 'ui-label')!r} "
        "(declared)"
    )
    print(f"all of it  = {AppSettings.get_setting_all_metadata(lambda s: s.retries)!r}")
    print(f"all class  = {AppSettings.get_class_all_metadata()!r}")
    # the runtime channel works over the declarations: overrides, adds,
    # deletes; the declaration is the initial state, not a floor
    AppSettings.set_setting_metadata(lambda s: s.mode, "ui-label", "Application mode")
    print(
        f"metadata   = "
        f"{AppSettings.get_setting_metadata(lambda s: s.mode, 'ui-label')!r} "
        "(overridden)"
    )
    AppSettings.set_setting_metadata("retries", "hint", "Runtime-only entry")  # name-string form
    print(f"all of it  = {AppSettings.get_setting_all_metadata(lambda s: s.retries)!r}")
    # metadata values are isolated in both directions: set stores a deep
    # copy, get returns one; mutating either side stays local
    AppSettings.set_class_metadata("window", {"x": 10, "y": 20})
    frame = AppSettings.get_class_metadata("window")
    frame["x"] = 99
    print(f"window     = {AppSettings.get_class_metadata('window')!r} (get returned a copy)")
    # None is a stored value like any other; removal is an explicit delete
    AppSettings.set_setting_metadata(lambda s: s.mode, "ui-label", None)
    print(
        f"metadata   = "
        f"{AppSettings.get_setting_metadata(lambda s: s.mode, 'ui-label')!r} "
        "(stored None)"
    )
    # contains tells the stored None above from a missing entry; get
    # returns its default for both
    print(f"has label? = {AppSettings.contains_setting_metadata(lambda s: s.mode, 'ui-label')}")
    print(f"has mark?  = {AppSettings.contains_setting_metadata(lambda s: s.mode, 'no-such')}")
    print(f"has cfg?   = {AppSettings.contains_class_metadata('config-version')} (declared)")
    AppSettings.delete_setting_metadata(lambda s: s.mode, "ui-label")
    print(
        f"metadata   = {AppSettings.get_setting_metadata(lambda s: s.mode, 'ui-label')!r} "
        "(after delete)"
    )
    # a declared entry goes the same way: the declaration seeds the storage
    # once; it is not brought back
    AppSettings.delete_class_metadata("config-version")
    print(
        f"class meta = {AppSettings.get_class_metadata('config-version')!r} "
        "(the declared entry was deleted)"
    )
    # the whole class storage goes with one call, the window entry included
    AppSettings.delete_class_all_metadata()
    print(f"all class  = {AppSettings.get_class_all_metadata()!r} (after clear)")
    # the file bindings ride the same class metadata: the clear above took
    # them too, and the imperative spelling puts them back (validated like
    # every binding write)
    AppSettings.set_class_metadata(js.JSON_FILE_METADATA, JSON_FILE)
    AppSettings.set_class_metadata(env_file.DOTENV_FILE_METADATA, DOTENV_FILE)
    # a member the class does not declare is a typo, not data: rejected
    # loudly instead of storing an entry no backend would ever read
    try:
        AppSettings.set_setting_metadata("mod", "ui-label", "typo")
    except KeyError as error:
        print(f"no member  -> KeyError: {error}")

    section("the class is the singleton; instances share its storage")
    instance = AppSettings()
    instance.retries = 7
    print(f"the class sees the write made through the instance: retries = {AppSettings.retries!r}")
    try:
        del AppSettings.mode
    except TypeError as error:
        print(f"del rejected: {error}")

    section("inheritance: members compose, storage stays per class")
    DevSettings.mock_api = False
    DevSettings.retries = 1
    DevSettings.save_settings()  # saves the inherited members too, under its own keys
    DevSettings.reset_settings()
    print(f"defaults   = retries={DevSettings.retries!r}, mock_api={DevSettings.mock_api!r}")
    DevSettings.load_settings()
    print(f"loaded     = retries={DevSettings.retries!r}, mock_api={DevSettings.mock_api!r}")
    print(f"AppSettings: retries = {AppSettings.retries!r} (its own keys, untouched)")
    # declared metadata follows the member by MRO: DevSettings seeded its own
    # copy of mode's declaration at its creation, so the deletes AppSettings
    # suffered above left it intact
    print(
        f"mode label = {DevSettings.get_setting_metadata('mode', 'ui-label')!r}"
        "(declared, inherited)"
    )

    section("delete_settings: storages emptied, defaults restored")
    AppSettings.delete_settings()
    DevSettings.delete_settings()
    describe_storages()
    print(f"mode       = {AppSettings.mode!r} (default)")


if __name__ == "__main__":
    main()
