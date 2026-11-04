"""
Example: building a settings backend of your own on the plugin contracts.

Everything that a backend author needs ships in
``advexp.settings.plugin_api``. This file builds a complete backend on it:

- an in-memory storage with an own parameter, ``secure=``;
- behavior that is driven by member and class metadata;
- a configuration holder with a process-wide parameter, which settings
  modules declare for themselves through ``for_this_module``;
- a collection of dynamic settings.

The file then walks the backend through the pipeline. The application-side
API (declaring and using settings) is shown in
``samples/settings/settings_api.py``. Here, the backend itself is the
subject.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/custom_backend.py

A backend is three parts that are registered on the public contracts:

- a setting attribute (the class that is assigned to a member);
- a serializer (how values reach the storage and come back);
- a plugin object (the handle that user code reaches through
  ``adv_settings.Settings.get_plugin``).

In a real plugin, all of this lives in its own module, and the registration
lines run at import time: importing the module enables the plugin.
"""

import logging
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import advexp.settings as adv_settings
import advexp.settings.plugin_api as api

# ---------------------------------------------------------------------------
# Part one: the setting attribute and its checker-clean factory
# ---------------------------------------------------------------------------


class MemorySetting(api.SettingsAttribute):
    """Setting attribute: the value lives in the dictionary of this process.

    ``secure=`` is the own parameter of this backend, and the core does not read
    it. ``MemorySerializer`` picks it off the attribute and keeps such values in
    a separate partition of the storage. This is the pattern for switches that
    are specific to a backend: the parameter lives on the attribute class, and
    the serializer reads it from ``attr`` after narrowing it through
    ``SettingsBaseSerializer.attribute_of`` (the way the ``path=`` of the JSON
    backend works).

    ``metadata=`` is a different category. It is the metadata channel of the core,
    which is inherited from the attribute base of the package and seeded into the
    settings context at class creation. It is not a parameter that any
    serializer is obliged to read.
    """

    # ordinary Python construction: extend __init__, call the base with
    # name=/default=/metadata=/aliases= and the constraint parameters, set
    # the backend's own parameters on self. The conventions come from
    # the package's attribute base; a lighter attribute may implement the
    # api.ISettingAttribute contract alone
    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = api.NO_DEFAULT,
        metadata: Optional[Mapping[str, Any]] = None,
        aliases: Optional[Sequence[str]] = None,
        gt: Any = None,
        ge: Any = None,
        lt: Any = None,
        le: Any = None,
        eq: Any = None,
        ne: Any = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        regex: Optional[str] = None,
        validator: Optional[Callable[[Any], bool]] = None,
        when: Any = None,
        secure: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            default=default,
            metadata=metadata,
            aliases=aliases,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            eq=eq,
            ne=ne,
            min_length=min_length,
            max_length=max_length,
            regex=regex,
            validator=validator,
            when=when,
        )
        self.secure: bool = secure


def memory_setting(
    *,
    name: Optional[str] = None,
    default: Any = api.NO_DEFAULT,
    metadata: Optional[Mapping[str, Any]] = None,
    aliases: Optional[Sequence[str]] = None,
    gt: Any = None,
    ge: Any = None,
    lt: Any = None,
    le: Any = None,
    eq: Any = None,
    ne: Any = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    regex: Optional[str] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    when: Any = None,
    secure: bool = False,
) -> Any:
    """Declare a setting on this backend. This is the type-checker-friendly
    spelling of ``MemorySetting``.

    It is a thin counterpart of the attribute class (same parameters, same
    attribute), and it is the piece that a custom backend needs for static
    typing. Assigning the attribute instance to an annotated member is valid
    Python, but type checkers cannot see that the settings metaclass replaces it
    with a value descriptor, so they report a type mismatch. They accept a plain
    function that returns ``Any``. The bundled backends ship their factories in
    the same way (``json_setting``, ``environment_variable_setting``).
    """
    return MemorySetting(
        name=name,
        default=default,
        metadata=metadata,
        aliases=aliases,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        eq=eq,
        ne=ne,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        validator=validator,
        when=when,
        secure=secure,
    )


# ---------------------------------------------------------------------------
# Part two: the storage and the serializer
# ---------------------------------------------------------------------------


class MemoryStorage:
    """The storage of the backend, which is external to the serializer.

    Like a settings file or ``os.environ`` in real backends, the storage
    outlives the serializer instances that the pipeline creates for each pass.
    This is why it is a class-level dict: one storage that is shared by every
    pass of the backend.
    """

    data: Dict[str, Any] = {}
    # the partition values declared with secure=True land in
    secure_data: Dict[str, Any] = {}


class MemorySerializer(
    api.SettingsBaseSerializer,
    api.IDynamicSettingsInfo,
):
    """In-memory backend: values are keyed by the full setting name in
    ``MemoryStorage``.

    Declaring :class:`api.IDynamicSettingsInfo` adds the enumeration that a
    dynamic-settings plugin needs to discover what the storage holds.

    Overriding ``describe_setting_name`` of the base serializer adds the own
    spelling of the storage for names in load diagnostics. The demo below shows
    the fallback warning that quotes the secure partition.

    The settings context needs no plumbing of the own of the backend:
    ``SettingsBaseSerializer`` keeps the context that the pipeline delivers, and
    the :attr:`context <SettingsBaseSerializer.context>` property is the way to
    the metadata that ``save`` reads below, both declared and runtime metadata.
    """

    def _bucket(self, attr: Optional[api.ISettingAttribute]) -> Dict[str, Any]:
        # the backend's own parameter at work: secure=True of MemorySetting routes
        # the value into the protected partition (dynamic entries carry no attr)
        setting = self.attribute_of(attr, MemorySetting)
        if setting is not None and setting.secure:
            return MemoryStorage.secure_data
        return MemoryStorage.data

    def _redact_on_save(self, attr: Optional[api.ISettingAttribute]) -> bool:
        # metadata obtained inside the backend: user code marked the member
        # with metadata={"redact-on-save": True} in the declaration or with
        # set_setting_metadata(...) at runtime; no attribute parameter is
        # involved either way. Setting metadata is keyed by member
        # name, which is attr.bound_name; dynamic entries (attr=None) or an
        # unbound attribute carry none to read
        member = None if attr is None else attr.bound_name
        if member is None:
            return False
        return bool(self.context.get_setting_metadata(member, "redact-on-save"))

    def _dynamic_redacts(self, setting_name: str) -> bool:
        # a dynamic entry carries no attr: its runtime mark lives in the
        # dynamic plugin's metadata, keyed by the plain name; the context
        # strips it out of the full storage name (this serializer passes
        # itself, so its delimiter wish applies)
        context = self.context
        plain_name = context.get_dynamic_setting_name(setting_name, self)
        if plain_name is None:
            return False
        plugin = context.get_plugin(MemoryDynamicSettingsPlugin)
        try:
            return bool(plugin.get_setting_metadata(plain_name, "redact-on-save", False))
        except KeyError:
            return False  # a name the collection does not hold: no mark

    def _redacts_everything(self) -> bool:
        # the backend's own class-metadata option: one switch for the whole
        # class, read through the context like any metadata; the registry
        # the validator registered in guards what lands there
        options = self.context.get_class_metadata(MEMORY_OPTIONS_KEY) or {}
        return bool(options.get(MEMORY_REDACT_EVERYTHING))

    def _redaction(self) -> str:
        # the backend's process-wide parameter at work: the module's
        # for_this_module declaration wins over the plain attribute —
        # module_default_for is the lookup the plugin API ships for it
        declared = api.module_default_for(
            MemoryConfiguration,
            lambda configuration: configuration.redaction,
            self.context.settings_class.__module__,
        )
        return declared if declared is not None else MemoryConfiguration.redaction

    # -- ISettingsSerializer ---------------------------------------------------

    def load(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> Any:
        # the declared aliases widen the read — the pattern every bundled
        # backend follows: the delivered name first, then each alias, and
        # the first key found wins. setting_name_candidates is the shared
        # helper plugin_api ships for exactly this loop
        bucket = self._bucket(attr)
        for key in api.setting_name_candidates(setting_name, attr):
            value = bucket.get(key, api.NOT_FOUND)
            if value is not api.NOT_FOUND:
                return deepcopy(value)
        return api.NOT_FOUND

    def save(
        self,
        setting_name: str,
        attr: Optional[api.ISettingAttribute],
        value: Any,
    ) -> None:
        # per the save contract, None is a legitimate value and stays stored;
        # a backend with no null form (env vars, say) would drop the entry.
        # An in-memory backend copies mutable values: the class storage and
        # the backend's must not share objects (load deep-copies for the
        # same reason). The write serves the delivered name alone: aliases
        # are read addresses
        if self._redacts_everything() or self._redact_on_save(attr):
            value = self._redaction()
        elif attr is None and self._dynamic_redacts(setting_name):
            value = self._redaction()  # the mark reached a dynamic entry by its plain name
        self._bucket(attr)[setting_name] = deepcopy(value)

    def delete(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> None:
        # an alias left behind would resurrect the value at the next load
        bucket = self._bucket(attr)
        for key in api.setting_name_candidates(setting_name, attr):
            bucket.pop(key, None)

    def contains(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> bool:
        bucket = self._bucket(attr)
        return any(key in bucket for key in api.setting_name_candidates(setting_name, attr))

    # -- IDynamicSettingsInfo ---------------------------------------------------------------

    def get_dynamic_settings_names(self):
        # the entries of the bound class: the context split tells this
        # class's dynamic full names from everything else in the storage
        # (static names, other classes' entries)
        context = self.context
        return [
            name
            for name in MemoryStorage.data
            if context.get_dynamic_setting_name(name, self) is not None
        ]

    # -- ISettingNameDescriber ------------------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[api.ISettingAttribute]
    ) -> Optional[str]:
        """``secure memory key '<name>'`` for the secure partition, and ``None`` for the
        plain bucket (it keeps the pattern name). The aliases of the declaration are
        listed next to the address, in the shared spelling that every reader of the
        diagnostics of the family knows.
        """
        if attr is None:
            return None
        setting = self.attribute_of(attr, MemorySetting)
        if setting is not None and setting.secure:
            return api.spelled_with_aliases(f"secure memory key '{setting_name}'", attr.aliases)
        return None


# ---------------------------------------------------------------------------
# Part three: the plugin object and its registration
# ---------------------------------------------------------------------------


class MemoryPlugin(api.SettingsBasePlugin):
    """Plugin object; user code reaches it via ``adv_settings.Settings.get_plugin``.

    Deriving from ``api.SettingsBasePlugin`` is the easy way. It provides the
    context binding and the declarative binding: a declared
    ``api.AttributeSerializerBinding`` is registered by the ``setup()`` of the
    base class at import.

    A plugin may instead implement only the ``ISettingsPlugin`` contract. Its
    ``bind_context()`` hook receives the context, its ``context`` property
    returns it, and where to keep it is the own choice of the plugin.
    """

    # the declarative binding; the base setup() registers it
    binding = api.AttributeSerializerBinding(MemorySetting, MemorySerializer)

    @property
    def plugin_name(self) -> str:
        return "InMemory"

    @property
    def storage(self) -> Dict[str, Any]:
        """A plugin-specific operation exposed through get_plugin."""
        return MemoryStorage.data

    @property
    def secure_storage(self) -> Dict[str, Any]:
        """The partition values declared with secure=True land in."""
        return MemoryStorage.secure_data


adv_settings.LibraryConfiguration.register_settings_plugin(MemoryPlugin)

# a backend family can also own a class metadata key: register a validator
# for it, and the key becomes the family's checked options channel; an
# invalid declaration fails the class statement, an invalid runtime
# set_class_metadata raises before storing (keys with no validator stay the
# open channel: "config-version" of AppSettings stores whatever the
# application puts there). The bundled environment family works this way
# too: its environment_options sets name_prefix/name_case for every
# backend of the family at once
MEMORY_OPTIONS_KEY = "InMemory"
MEMORY_REDACT_EVERYTHING = "redact-everything"


def check_memory_options(value: Any) -> Optional[str]:
    """The registered validator: ``None`` when valid, a sentence when not."""
    if not isinstance(value, Mapping):
        return f"must be a mapping of option name to value, got {type(value).__name__}"
    unknown = sorted(set(value) - {MEMORY_REDACT_EVERYTHING})
    if unknown:
        return f"unknown option name(s): {', '.join(repr(name) for name in unknown)}"
    flag = value.get(MEMORY_REDACT_EVERYTHING, False)
    if not isinstance(flag, bool):
        return f"{MEMORY_REDACT_EVERYTHING} must be a boolean, got {flag!r}"
    return None


def memory_options(redact_everything: bool = False) -> Dict[str, Dict[str, Any]]:
    """Build the backend's ``class_metadata`` entry for ``options=`` or the body."""
    return {MEMORY_OPTIONS_KEY: {MEMORY_REDACT_EVERYTHING: redact_everything}}


adv_settings.LibraryConfiguration.register_class_metadata_validator(
    MEMORY_OPTIONS_KEY, check_memory_options
)

# ---------------------------------------------------------------------------
# Part four: the backend's configuration holder — a process-wide parameter that
# settings modules can declare for themselves
# ---------------------------------------------------------------------------


class MemoryConfiguration(metaclass=api.ModuleDefaultMeta):
    """The process-wide configuration of the backend (class-level state).

    A plain assignment sets the value for the whole application at once. A
    settings module declares its own value with ``for_this_module`` (a tool of
    the package root), and the declaration wins for the classes of that module
    only. The metaclass turns such an assignment into a declaration.

    ``register_module_default`` opens the parameter. The parameter is spelled as
    one attribute read of the holder below, so a renamed attribute makes the
    registration fail loudly. The registration also names the validator that
    every declared value passes at the line of the assignment.
    """

    redaction: str = "***"
    """The storage spelling of a redacted value."""


def check_redaction(value: Any) -> Optional[str]:
    """The parameter's validator: ``None`` when valid, a sentence when not."""
    if isinstance(value, str) and value:
        return None
    return f"must be a non-empty string, got {value!r}"


api.register_module_default(
    MemoryConfiguration,
    lambda configuration: configuration.redaction,
    check_redaction,
)


class MemoryDynamicSettingsPlugin(api.DynamicSettingsBasePlugin):
    """Dynamic settings in the same in-memory storage as ``MemorySetting``.

    The base class needs one mandatory binding (the pin attribute whose
    serializer also serves the dynamic entries). Everything else comes with it:
    the storage passes, the typed reads, and the collection that behaves like a
    dict.

    The pin is the namespaced form ``DynamicSettingAttribute[MemorySetting]``. It
    has its own registry slot, so the dynamic entries get their serializer
    without touching the binding that ``MemoryPlugin`` registers for the static
    members.
    """

    binding = api.AttributeSerializerBinding(
        # the runtime subscription builds a concrete subclass of MemorySetting;
        # the static type application cannot express that
        api.DynamicSettingAttribute[MemorySetting],  # type: ignore[type-abstract]
        MemorySerializer,
    )

    @property
    def plugin_name(self) -> str:
        return "InMemoryDynamic"


adv_settings.LibraryConfiguration.register_settings_plugin(MemoryDynamicSettingsPlugin)

# ---------------------------------------------------------------------------
# A settings class served by the backend, and the walkthrough
# ---------------------------------------------------------------------------


class AppSettings(
    adv_settings.Settings,
    # several option mappings go into one options= sequence: the backend
    # family's helper entry and the application's free keys
    options=(memory_options(), {"config-version": 2}),
):
    """The demo class served by the backend built in this file."""

    mode: str = memory_setting(name="app.mode", default="production")
    retries: int = memory_setting(name="retries", default=3)
    debug: bool = memory_setting(name="debug", default=False)
    # aliases declare additional full storage keys: a load tries the primary
    # key first, then each alias — the rename migration seat, the old key
    # keeps serving the member. A backend honors them through the shared
    # setting_name_candidates helper, the way MemorySerializer below does
    session_ttl: int = memory_setting(name="session.ttl", aliases=["app.ttl"], default=1800)
    # secure=True is the backend's own parameter: the value lands in the
    # protected partition of the storage. A secret wrapper is the typed
    # view of it: the storage keeps the plain form (the pipeline opens
    # the wrapper on save), reads and reprs mask the payload
    api_token: adv_settings.SecretStr = memory_setting(
        name="api-token", default="none", secure=True
    )


class AuditSettings(
    adv_settings.Settings,
    options=memory_options(redact_everything=True),
):
    """Declared through the ``options=`` keyword of the ``class`` statement.

    The readable spelling of the ``class_metadata`` declaration accepts the
    helper of any family: the bundled environment helper and the
    ``memory_options`` of this file alike. The ``class_metadata`` of the body
    goes the same way: both spellings are one channel, and they are merged. The
    entry of the family is stored under its own key, and the free keys of the
    application are stored next to it.

    The class saves redacted from the first pass, with no runtime call
    involved, and its options belong to the class itself: ``AppSettings`` above
    keeps the defaults.
    """

    class_metadata = {"config-version": 2}

    login: str = memory_setting(name="audit-login", default="nobody")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    section("the pipeline through the backend: assign, save, reload")
    AppSettings.retries = 5
    AppSettings.mode = "staging"
    AppSettings.save_settings()
    # the explicit names= are "app.mode" and similar ones; the save wrote
    # every member, the secure one into its own partition
    print(f"storage    = {dict(MemoryStorage.data)}")
    print(
        f"secure     = {dict(MemoryStorage.secure_data)}  (members with secure=True "
        "are stored separately)"
    )
    AppSettings.reset_settings()
    print(f"defaults   = retries={AppSettings.retries!r}, mode={AppSettings.mode!r}")
    report = AppSettings.load_settings()
    print(f"reloaded   = retries={AppSettings.retries!r}, mode={AppSettings.mode!r}")
    print(f"report     = {report} (every member was loaded; nothing fell back to a default)")

    section("aliases: the declared keys widen the read")
    # only the pre-rename key sits in the storage: the alias serves the member
    MemoryStorage.data.pop("session.ttl", None)
    MemoryStorage.data["app.ttl"] = 900
    AppSettings.load_settings()
    print(f"session_ttl = {AppSettings.session_ttl!r}  (read from the alias key 'app.ttl')")
    # saving writes the primary key alone; delete clears every key of the
    # member, so a removed value cannot come back through an old one
    AppSettings.session_ttl = 1200
    AppSettings.save_setting("session_ttl")
    print(
        f"after save: 'session.ttl' = {MemoryStorage.data['session.ttl']!r}, "
        f"'app.ttl' = {MemoryStorage.data['app.ttl']!r}"
    )
    AppSettings.delete_setting("session_ttl")
    print(f"after delete: 'app.ttl' in storage = {'app.ttl' in MemoryStorage.data}")

    section("a backend's own parameter: secure= on the attribute")
    # the core never reads the parameter: the serializer picks it off the
    # attribute and routes the value; that is the pattern behind path= of
    # the JSON backend and every backend-specific switch. The plain string
    # converts to the wrapper at the assignment: the checker cannot see the
    # descriptor doing it
    AppSettings.api_token = "s3cr3t"  # type: ignore[assignment]
    AppSettings.save_setting(lambda s: s.api_token)
    print(f"secure     = {dict(MemoryStorage.secure_data)}")
    AppSettings.load_setting(lambda s: s.api_token)
    print(f"api_token  = {AppSettings.api_token!r} (read back from the partition)")

    section("load diagnostics quote the storage's own name: ISettingNameDescriber")
    # a bad value in the storage makes the load fall back with a warning,
    # and the warning names the setting the way this backend spells it (the
    # secure partition's key), because the serializer implements the
    # optional capability; a backend without it keeps the plain messages.
    # A secret annotation keeps the payload out of the log into the
    # bargain. The family's verbosity is the library's parameter: set_log_level
    # reaches every channel of the family
    adv_settings.LibraryConfiguration.set_log_level(logging.WARNING)
    MemoryStorage.secure_data["api-token"] = ["not", "a", "string"]
    AppSettings.load_setting(lambda s: s.api_token)
    print(f"api_token  = {AppSettings.api_token!r} (a bad value fell back to the default)")
    MemoryStorage.secure_data["api-token"] = "s3cr3t"

    section("member metadata reaching the backend: redact-on-save")
    # the serializer reads the mark through the context the pipeline handed
    # it: set at the declaration (metadata=) or flipped at runtime; here
    # runtime, a switch without touching the class declaration
    AppSettings.set_setting_metadata(lambda s: s.api_token, "redact-on-save", True)
    AppSettings.save_settings()
    print(f"api-token  = {MemoryStorage.secure_data['api-token']!r} (redacted by the serializer)")

    section("class-metadata options of a backend family")
    # AppSettings declared memory_options() in its class_metadata, and the
    # registered validator guards the key: an invalid declaration fails
    # the class statement, an invalid runtime set raises before storing
    try:

        class WrongSettings(adv_settings.Settings):
            class_metadata = {MEMORY_OPTIONS_KEY: {MEMORY_REDACT_EVERYTHING: "yes"}}
            flag: bool = memory_setting(default=False)

    except TypeError as error:
        print(f"bad option -> TypeError: {error}")
    try:
        AppSettings.set_class_metadata(MEMORY_OPTIONS_KEY, {MEMORY_REDACT_EVERYTHING: "yes"})
    except TypeError as error:
        print(f"bad set    -> TypeError: {error}")
    try:
        # a name declared on both sides is a blocked class, not a silent
        # last-write: the error names the class and the shared names
        class OverlapSettings(
            adv_settings.Settings, options=(memory_options(), {"config-version": 2})
        ):
            class_metadata = {"config-version": 3}
            flag: bool = memory_setting(default=False)

    except TypeError as error:
        print(f"overlap    -> TypeError: {error}")
    # a valid flip reaches the backend on the next pass: every save redacts
    # while the switch is on, the member mark above included
    AppSettings.set_class_metadata(MEMORY_OPTIONS_KEY, {MEMORY_REDACT_EVERYTHING: True})
    AppSettings.save_settings()
    redacted_all = all(MemoryStorage.data[name] == "***" for name in ("app.mode", "debug"))
    print(f"redact-all = {redacted_all} (one class-level switch)")
    AppSettings.set_class_metadata(MEMORY_OPTIONS_KEY, {MEMORY_REDACT_EVERYTHING: False})
    AppSettings.save_settings()  # plain values back; api_token keeps its own mark

    # the same options declared at the class statement: options= takes any
    # family's helper (here the backend's own), and the class saves
    # redacted from the first pass, while AppSettings, with its own
    # metadata, stays plain (options are per class)
    AuditSettings.login = "alice"
    AuditSettings.save_settings()
    print(
        f"audit save = {MemoryStorage.data['audit-login']!r} (the class declares that "
        "everything is redacted)"
    )
    print(f"app mode   = {MemoryStorage.data['app.mode']!r} (AppSettings unaffected)")
    merged = AuditSettings.get_class_all_metadata()
    print(
        f"merged     = {merged} (options= and the class_metadata declared in the class body,"
        "merged into one channel)"
    )

    section("plugin access")
    plugin = AppSettings.get_plugin(MemoryPlugin)
    print(f"plugin     = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")
    print(f"storage    = {dict(plugin.storage)}, secure = {dict(plugin.secure_storage)}")
    # the context accepts the same setting-reference forms as the facade:
    # the member-name string or a getter lambda
    plugin.context.set_setting_metadata(lambda s: s.mode, "ctx-mark", 7)
    print(f"ctx mark   = {plugin.context.get_setting_metadata(lambda s: s.mode, 'ctx-mark')!r}")

    section("dynamic settings: runtime names through a plugin")
    # names that appear at runtime (user-added, plugin-provided) live in the
    # dynamic plugin bound to the class: no member is declared for them
    dynamic = AppSettings.get_plugin(MemoryDynamicSettingsPlugin)
    dynamic.set_setting("dark_mode", True)
    dynamic.set_setting("last_opened", datetime(2026, 9, 13, 9, 45, 0))
    dynamic.save_settings()
    print(f"names      = {list(dynamic)}")
    # the default's type drives the conversion, like the annotated conversion
    # of declared settings; without one, the raw storage form comes back
    print(f"dark_mode  = {dynamic.get_setting('dark_mode', default=False)!r}")
    print(f"last_opened = {dynamic.get_setting('last_opened', default=datetime(2026, 1, 1))!r}")
    print(f"raw        = {dynamic.get_setting('last_opened')!r}")
    dynamic.load_settings()  # rebuild the collection from the storage
    print(f"reloaded   = {list(dynamic)}, len = {len(dynamic)}")
    # the iteration order is class metadata: listed names first, then the rest
    AppSettings.set_class_metadata(
        MemoryDynamicSettingsPlugin.ITERATION_ORDER_METADATA, ["last_opened", "dark_mode"]
    )
    print(f"ordered    = {list(dynamic)}")
    snapshot = dynamic.to_dict()
    dynamic.update_from_dict({"refresh": 30})  # a new name is a new setting
    print(f"snapshot   = {snapshot}; after adding refresh -> {list(dynamic)}")
    # dynamic names carry metadata of their own, the runtime state of the
    # plugin's collection: just as the member side checks its declarations,
    # every metadata operation requires a name the collection holds
    dynamic.set_setting_metadata("refresh", "ui-label", "Refresh interval")
    print(f"dyn meta   = {dynamic.get_setting_metadata('refresh', 'ui-label')!r}")
    print(f"dyn all    = {dynamic.get_setting_all_metadata('refresh')!r}")
    # loads bring values only: the storage holds no metadata, so a load
    # resets it; annotate afresh after one
    dynamic.set_setting_metadata("dark_mode", "ui-label", "Dark mode")
    dynamic.load_setting("dark_mode")
    print(
        f"dark_mode  = {dynamic.get_setting('dark_mode', default=False)!r} (the "
        "value has been set), "
        f"ui-label kept = {dynamic.contains_setting_metadata('dark_mode', 'ui-label')}"
    )
    # deleting the setting takes its metadata along; and a name the
    # collection no longer holds is a typo, not data
    dynamic.delete_setting("refresh")
    try:
        dynamic.set_setting_metadata("refresh", "ui-label", "typo")
    except KeyError as error:
        print(f"no name    -> KeyError: {error}")
    # every entry of one name goes with a single call
    dynamic.set_setting_metadata("dark_mode", "ui-label", "Dark mode")
    dynamic.set_setting_metadata("dark_mode", "hint", "Try the dark look")
    dynamic.delete_setting_all_metadata("dark_mode")
    print(
        f"all gone   = {not dynamic.contains_setting_metadata('dark_mode', 'ui-label')}, "
        f"setting kept = {'dark_mode' in dynamic}"
    )
    # the runtime channel reaches the dynamic entries through the plain
    # name: the serializer strips it out of the full storage name and reads
    # the plugin's metadata (the same redact-on-save mark as the static side)
    dynamic.set_setting_metadata("dark_mode", "redact-on-save", True)
    dynamic.save_settings()
    redacted = [key for key, value in MemoryStorage.data.items() if value == "***"]
    print(f"redacted   = {redacted}")
    # the name channel behind that: the context builds the full storage
    # name of an entry and splits it back: one the inverse of the other,
    # the same pair the serializer used above
    full_name = dynamic.context.get_dynamic_setting_full_name("dark_mode")
    plain_name = dynamic.context.get_dynamic_setting_name(full_name)
    print(f"full name  = {full_name!r} -> {plain_name!r}")
    dynamic.delete_settings()  # the dynamic entries only; statics unaffected
    print(f"after delete_settings: names = {list(dynamic)}, mode = {AppSettings.mode!r}")

    section("serializer base: the two storage forms of a value")
    # value-form helpers every serializer inherits: string-oriented backends
    # (env vars) save with to_storage_string, JSON-like ones with to_json_value.
    # The memory backend stores Python values as-is, so it never calls them
    moment = datetime(2026, 9, 12, 12, 30)
    print(f"as string  = {MemorySerializer().to_storage_string(moment)!r}")
    print(f"as json    = {MemorySerializer().to_json_value([1, moment])!r}")

    section("the configuration holder: a process-wide parameter, a module's declaration")
    # MemoryConfiguration keeps the backend's process-wide state: a plain
    # assignment sets the marker for the whole process, for_this_module
    # declares it for this module's classes alone, and the declaration is
    # an import-time statement — declared_module_defaults (the package
    # root's reader) hands it to a tool that never runs the application
    MemoryConfiguration.redaction = adv_settings.for_this_module("[filtered]")

    class FilteredSettings(adv_settings.Settings):
        secret: Optional[str] = memory_setting(
            name="filtered-secret", default=None, metadata={"redact-on-save": True}
        )

    FilteredSettings.secret = "s3cr3t"
    FilteredSettings.save_settings()
    print(
        f"stored     = {MemoryStorage.data['filtered-secret']!r} (the marker defined by the module)"
    )
    declared = adv_settings.declared_module_defaults()
    print(f"declared   = {declared[(MemoryConfiguration, 'redaction', __name__)]!r}")

    # clean up the demo storage
    MemoryStorage.data.clear()
    MemoryStorage.secure_data.clear()


if __name__ == "__main__":
    main()
