# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- 2026-10-23 — The default-reset pass is renamed:
  `load_default_settings()` is now `reset_settings()` and
  `load_default_setting(...)` is now `reset_setting(...)`. The old
  names said "load" about a pass that touches no storage — every other
  `load*` method reads one — so the names now say what the pass does,
  in the `verb_settings` / `verb_setting` grid of the other passes.
  The package has had no release yet, so the old spellings are removed
  outright.

- 2026-10-13 — `NO_DEFAULT` leaves the application facades
  `advexp.settings` and `advexp.configuration`. The application spelling
  of "no default" is an omitted `default=` (in `advexp.configuration`,
  where the factories' own default is `REQUIRED`, an optional member is
  an explicit `default=` — a value or `None`), and the sentinel is the
  backend authors' vocabulary: it stays exported from the `plugin_api`
  of both packages, where factory signatures receive it as their
  `default=` parameter's value. A member declared without a default
  behaves exactly as before. Migration: drop the explicit
  `default=NO_DEFAULT` — the omitted parameter says the same — or import
  the sentinel from `plugin_api` where a custom factory's signature
  needs it.

- 2026-10-07 — The JSON backends bind a settings class to its file through
  `options=`, the way the dotenv backend does. The `@JSONSettingsFile(...)`
  decorators of `advexp.settings` and `advexp.configuration` are gone: a
  class names its own file with `json_file(...)` in the `class` statement's
  `options=` keyword, and the dynamic side's own file is
  `json_dynamic_file(...)` beside it. The bindings are class metadata with
  shared keys in `advexp.settings_base.json_file`, inherit along the class
  chain (a
  subclass's own binding wins while the base keeps its file), and resolve
  live at read time. The plugin instances' `file_path` properties are the
  imperative spelling over the same entries, and removing a binding is
  `delete_class_metadata` — assigning `None` no longer unbinds, the value
  is validated now. `JSONSettingsConfiguration.file_path` and
  `JSONDynamicSettingsConfiguration.file_path` remain the module defaults.

- 2026-10-07 — The English prose of the project now reads as plain English.
  The package READMEs, the docstrings and the comments of the sources,
  tests and samples are rewritten in complete sentences; the old
  telegraphic style, with its chains of dashes and verbless insertions,
  is gone. Only the wording changed: every statement of behavior,
  defaults and contracts says what it said before.

- 2026-10-06 — The environment-variables samples now address nested objects
  three classes deep: the nested member in both
  `samples/settings/environment_variables.py` and
  `samples/configuration/environment_variables.py` now holds a pool whose
  health probe is an object again, so a variable such as
  `DEMO_SITE_DB__POOL__HEALTH__TIMEOUT` shows the delimiter reaching every
  level of the chain.

- 2026-10-06 — A family's per-class entry must address a class in the
  inheritance chain: `environment_options_for(...)` given a class that the
  declaring class does not inherit from now fails the `class` statement with
  a `TypeError`, and a runtime `set_class_metadata` call with such a
  composite key raises before storing anything. Resolution walks the
  inheritance chain alone, so such an entry used to be silently ignored: it
  retuned nothing, and there was no sign of the mistake.

- 2026-10-06 — The `advexp.configuration` README no longer mentions a runtime
  `set_class_metadata` call: the read-only `Configuration` class has no
  runtime metadata API. Its metadata are the declarations in the class body,
  and fresh values come from calling `load_configuration()` again. The
  paragraph on naming options now mentions only a hand-written
  `class_metadata` entry that spells the case as the stored string
  (`"upper"`/`"lower"`).

- 2026-10-05 — Member metadata now resolves the inheritance chain by the same
  rule as class metadata (a `ChainMap` along the MRO, with the most derived
  entry winning per key). A `metadata=` declaration lands in the storage of
  the class that declared the member. A runtime `set_setting_metadata` on a
  base class reaches its subclasses, whether they were created before or
  after the write, and adds keys on top of the inherited ones without
  erasing them. A member redeclared in a subclass carries only the
  redeclaration's metadata (its chain ends at the subclass).
  `delete_class_metadata` and `delete_setting_metadata` now return whether
  the class's own entry existed and was removed; a missing own entry is
  still not an error, and an ancestor's entry stays visible to readers of
  the chain.

- 2026-10-05 — The documented way to combine several option helpers (or a
  helper with free metadata keys) in one `options=` value is the dict union
  operator: `options=environment_options(...) | environment_options_for(...)`.
  The docs, samples and tests use this one spelling; the `{**helper(...), ...}`
  dict-literal spread is gone from them.

- 2026-10-05 — Class-level metadata now resolves the inheritance chain live,
  the way class attribute lookup does. A runtime `set_class_metadata` on a
  base class reaches its subclasses (created before or after the write;
  declarations and runtime writes now follow one rule), while a subclass's
  write never touches its bases. A runtime retune of a family entry (the
  environment prefix, for example) rebuilds the names of inherited members
  in every subclass in the same way. `delete_class_metadata` and
  `delete_class_all_metadata` remove only the class's *own* entries: an
  ancestor's entry stays visible to readers of the chain, just as deleting
  an attribute on a subclass falls back to the base's.
  `get_class_all_metadata` returns the entries visible to the class, both
  its own and those of the chain, with each family entry under its composite
  per-class key.

- 2026-10-04 — `advexp.configuration` now mirrors the layout of
  `advexp.settings`: all implementation modules moved into the `_internal`
  subpackage, and the package root keeps exactly two public import sites,
  `__init__.py` (the application API) and `plugin_api.py` (for source
  authors). Both facades read the internals through the new
  `_internal/facade_sources.py`, which has the same single-import-site role
  as in `advexp.settings`. It stays inside `_internal` by design: the root
  lists the public surface and nothing else. The privacy boundary is
  enforced in the same way: a ruff `TID251` ban on
  `advexp.configuration._internal` (root `pyproject.toml`) and
  `tests/test_no_internal_imports.py`, which now guards both private
  packages. The `advexp-configuration` packaging allowlist ships the new
  subpackage. There is no public API change: the two facades re-export the
  same names.

- 2026-10-04 — The logging channel declaration is renamed to
  `__logger_name__` (was `__settings_logger_name__`). The contract of the
  base is family-wide: the root class of a distribution declares its
  channel, and the configuration root declares one exactly as the settings
  root does, so the spelling carries no distribution's name. The
  constant holding the attribute name in the base is `LOGGER_NAME_ATTR`. The
  old name was never released.

- 2026-10-04 — A source family's options are now stored per declaring class.
  The machinery stores each class's declaration under the family key joined
  with the class's module and name (a key that is never typed by hand), so a
  subclass that declares its own `environment_options(...)` adds its own
  entry while the base's entry stays. A member's variable is built from the
  entry of the class that declared the member or, if that class declared
  none, from the nearest entry above it in the inheritance chain, so a
  subclass's own options never change the variables of inherited members.
  The new `environment_options_for(AncestorClass, ...)` helper (re-exported
  by both plugins packages) retunes an ancestor's entry from a subclass, for
  that subclass and its descendants only. It goes through the `options=`
  class keyword like the options of any family: either alone, or spread
  with the class's own `environment_options(...)` in one dict literal. The
  flat family key of the runtime channel addresses the class's
  own entry in `set_class_metadata`; reads and deletes address the nearest
  one. The attribute contract gains `declaring_class`, the class whose body
  declared the member, written by the machinery at class creation;
  hand-written `ISettingAttribute` implementations must add this property
  alongside `bound_name`. Family validators cover the per-class entries of
  their key, and the `plugin_api` of both packages re-exports
  `family_entry_key` for backend authors.

- 2026-10-04 — A settings or configuration class may now declare its class
  metadata through both spellings at once: `options=` (the entries of source
  families) and the body's `class_metadata` (the application's own keys) are
  merged, where the class statement used to raise "use one spelling". The
  two sides do not collide by design, since a source family's key is a long,
  distinctive name of its own. A name declared on both sides fails the
  `class` statement with a `TypeError` naming the class and the shared
  names, because a silent last-write-wins would clobber one side in a way
  that is hard to notice.

- 2026-10-03 — The class metadata key of the environment family is renamed
  across the board: the constant is now `ENVIRONMENT_METADATA_OPTIONS` (was
  `ENVIRONMENT_METADATA_NAME`) and its value is
  `"EnvironmentMetadataOptions"` (was `"Environment"`). The entry under the
  key is the family's options mapping, and both names now say what the entry
  holds. Runtime `set_class_metadata` calls that spelled out the old value
  by hand must switch to the new one. The constant is re-exported by both
  plugins packages; the old names were never released.

- 2026-10-03 — Load diagnostics of `advexp.configuration` now name the
  member's storage name in the storage's own terms. The environment
  variables source answers through the new optional serializer capability
  `ISettingNameDescriber` (re-exported by the `plugin_api` of both
  packages), and the abort and fallback messages quote it:
  `setting 'host' (environment variable 'DEMO_APP_HOST') of 'AppConfig'`
  instead of the pattern-built name (`module.Class.member`) that the
  environment never reads. A required member whose variable is missing now
  tells the reader exactly which variable to provide. Backends without the
  capability keep the previous wording. The load fallback warnings of the
  settings package quote the described name in the same way. The
  plugin-author sample (`samples/settings/custom_backend.py`) implements the
  capability and demonstrates the warning.

- 2026-10-03 — The vocabulary of the environment family moved to the
  family's foundation: `advexp.settings_base.environment_options` and
  `advexp.settings_base.name_case` now hold the metadata key, the option
  constants, the validator, the helper and the name-building function. The
  variable namespace spans distributions (a settings backend and a read-only
  configuration source read the same variables), so the shared vocabulary
  lives where both distributions can reach it. The import path on the
  settings side is unchanged: `advexp.settings.plugins.environment`
  re-exports everything. The options and name-case modules that used to live
  there are gone (they were never released). The configuration sample now
  declares required members by default with `environment_options` applied,
  and keeps a pair of `default=` members as the opt-in alternative.

- 2026-10-03 — The settings samples are now split by audience.
  `samples/settings/settings_api.py` tours the application-side API on a
  minimal in-memory backend (an attribute, a serializer and a plugin object,
  the smallest set that can serve the passes); the full custom backend lives
  in `samples/settings/custom_backend.py`. References in the README, the
  package docstrings and the docs point to the new locations.

- 2026-10-03 — Class metadata validators: a plugin family can register a
  validator for its `class_metadata` key
  (`SettingsConfiguration.register_class_metadata_validator`). The key then
  holds the family's options: an invalid declaration fails the `class`
  statement with a `TypeError` naming the class and the key, and a runtime
  `set_class_metadata` call raises before storing. Keys with no validator
  remain an open channel and store whatever the application puts there.

- 2026-10-03 — Naming options for the family of environment backends:
  `environment_options(name_prefix=..., name_case=...)` builds a ready-made
  options mapping for the `options=` keyword of the class statement
  (`class AppSettings(Settings, options=environment_options(...))`). The body
  assignment (`class_metadata = environment_options(...)`) is equivalent,
  and combining it with another family's entry or free keys goes through a
  dict literal. The entry is stored under the family's single
  `"EnvironmentMetadataOptions"` key. The variable name becomes
  `name_prefix + name_case(member name)`: the prefix is added as written, an
  explicit `name=` is the full address in the storage and is left untouched,
  and without options names keep their form (backward compatible). At the
  helper, the case is given only as a `NameCase` enum member
  (`name_case=NameCase.UPPER` / `NameCase.LOWER`, exported next to the
  helper); the stored entry keeps the plain string values of the members,
  which is also the data form accepted by the raw metadata channel (a
  hand-written entry or a runtime `set_class_metadata` call). The process
  environment and a future `.env` backend share one namespace, so the
  name-building function is shared vocabulary of the family in
  `advexp.settings.plugins.environment`, which keeps the backends of the
  family from drifting apart. The entry is replaced as a whole along the MRO
  (per the general per-key merge) and by a runtime `set_class_metadata` call.
  The constants `ENVIRONMENT_METADATA_OPTIONS`, `NAME_PREFIX` and
  `NAME_CASE` spell the keys.

- 2026-10-03 — `SettingsAttribute` in `advexp.settings`, exported by its
  `plugin_api` as the base class for source authors: the family skeleton
  with the package's own defaults, where an omitted `default=` means
  `NO_DEFAULT` and `None` stands in. The family base
  (`advexp.settings_base.BaseAttribute`) no longer carries default parameter
  values: each distribution's attribute base is the one place where its
  defaults live (settings: `NO_DEFAULT`; configuration:
  `ConfigurationAttribute` with `REQUIRED`), so a derived class cannot
  inherit the semantics of the neighboring package. The bundled settings
  attributes (`Setting`, `EnvironmentVariableSetting`, `JSONSetting`) derive
  from the package base; `plugin_api` no longer exports the family skeleton.

- 2026-10-03 — Secret value types `SecretStr` and `SecretBytes`, re-exported
  from both `advexp.settings` and `advexp.configuration` (the classes live
  in the shared base). Use them as the annotated type of a member that holds
  a secret: loading wraps the source's payload, `repr` and `str` return
  `'**********'` (casual prints, log records, tracebacks), and
  `get_secret_value()` is the only way to get the value itself. Constraint
  checks apply to the wrapped payload, while their messages keep the mask.
  Load-time conversion failures of secret members report `<secret>` instead
  of the payload, both in fallback warnings and in `ConversionError`. The
  storage form is the plain payload: the save path and the value-form
  helpers (`to_storage_string`/`to_json_value`) unwrap it, so serializers
  need not know about the wrappers. Both wrappers are part of the
  value-types round-trip contract (the conversion docstring, the "Value
  types" section of the settings README, and the parameterized round-trip
  list in the core tests).

- 2026-10-03 — The environment variables plugin moved from
  `advexp.settings.plugins.environment_variables` to
  `advexp.settings.plugins.environment.variables`, under the shared package
  of the environment family, `advexp.settings.plugins.environment` (the
  family's options module lives at its root). No release has shipped the old
  path.

- 2026-10-02 — Required members in `advexp.configuration`: a member without
  a default must get its value from a source. `REQUIRED`, the sentinel for
  this (re-exported from `advexp.configuration` and its `plugin_api`), is the
  default value of the `default` parameter in the bundled sources
  (`environment_variable_setting`, `json_setting`), so omitting `default=`
  has the same meaning. Requiredness is carried by the attribute alone, and
  `resolved_default()` in the shared base raises when asked to serve it.
  `NO_DEFAULT` keeps its family-wide meaning: the member is optional and
  `None` stands in. The package's own attribute base,
  `ConfigurationAttribute` (exported by its `plugin_api` and used by the
  bundled sources), declares `REQUIRED` as the value of its `default`
  parameter, so a third-party source is also required by default, with no
  sentinel to remember. When the load pass asks for the default of a
  required member (because the source provided no value, or the value did
  not convert or violated the constraints), it aborts with a dedicated error
  class naming the member, its setting and the class: `MissingValueError`
  for no value, `ConversionError` for a value that cannot be converted (the
  message shows the value and the type), `ConstraintViolationError` for a
  constraint violation (all violations are listed), and `SourceLoadError`
  for a source that raised while loading (its error is carried in the
  message and chained as the cause). All four subclass `RequiredMemberError`
  (a `ValueError`), which is also raised when reading a member that was
  never loaded, and when taking a snapshot of a class that was never loaded.
  The load fallback warning (`... using the default value`) fires only when
  a default is really served, never before a required-member abort.
  `advexp.settings` is unchanged: a member without a default still reads as
  `None` there.

- 2026-10-02 — The `advexp.configuration` package now has its public API:
  `Configuration`, the base class for user configuration classes, with the
  class-level `load_configuration()` pass, the snapshot layer
  (`to_dict`/`to_object`) and `get_plugin`, plus `plugin_api` for source
  authors. The package is the read-only sibling of `advexp.settings`:
  sources are only ever read and there is no write-back pass, and loaded
  values have no in-memory write layer either. Assigning a declared member,
  on the class or on an instance, raises `TypeError`; a `to_object` snapshot
  is completely frozen (no attribute can be written or deleted), and the
  `to_dict` snapshot is a read-only mapping (a `MappingProxyType`;
  `dict(...)` gives a mutable copy). The load pass is the only writer.
  Members are declared exactly as in the settings package, with the same
  attribute conventions, constraints and conversion, and the machinery comes
  from the shared `advexp.settings-base` dependency (`advexp.configuration`
  imports nothing from `advexp.settings`, and a repository test guards this
  boundary). Two bundled sources ship with it: `environment_variables` and
  `json_settings`, which are the backends of the settings package in
  read-only form (the JSON source keeps the pointer paths, the per-class
  file bindings and the document shared within a pass, and drops the write
  machinery and the dynamic-settings section, which belongs to the settings
  package). The logging channel of the classes of the new distribution is
  `advexp.configuration`.

- 2026-10-02 — Value validation: constraints and custom validators on
  setting members. A setting declaration accepts value constraints as
  keyword parameters: `gt`/`ge`/`lt`/`le` (ordering bounds), `eq`/`ne`
  (equality), `min_length`/`max_length` (applied to `len(value)`, for
  strings and collections alike), `regex` (an unanchored pattern for `str`
  values) and `validator` (a callable that returns whether the value
  passes). They apply wherever a value reaches the member. Declared defaults
  are checked at class creation in their converted form (a violation fails
  the `class` statement, like an unconvertible default). Assignments and
  `update_from_dict`/`update_from_object` raise `SettingValidationError` (a
  new `ValueError` subclass exported from `advexp.settings`) before anything
  is written. A load falls back to the default with a logged warning (its
  existing policy for values that do not convert), and a save does not
  persist a violating value. `None` passes the ordering, length and regex
  constraints (the `Optional` semantics) but takes part in `eq`/`ne`. The
  declaration itself is validated: a `regex` that does not compile fails
  with `ValueError`, and a non-callable `validator`, or a mix of ordering
  bounds with length/regex ones, fails with `TypeError`. Cross-field rules
  stay in the application layer; the README shows the pattern.

- 2026-10-02 — Declarative metadata: `metadata=` on the setting declaration
  and `class_metadata` on the settings class. `metadata=` is a keyword-only
  parameter of the base attribute, so every factory (`json_setting`,
  `environment_variable_setting`) and every custom attribute inherits it,
  and `class_metadata` is the reserved class-level name for class metadata.
  Both seed the metadata storages of the class at creation, so reads
  (`get_setting_metadata`, `get_class_all_metadata`, ...) work before any
  `set_*` call, giving a static view that a UI builder or a schema generator
  can read off the class. The runtime channel keeps working on top of the
  declarations: it overrides, adds and removes entries, and a deleted
  declared entry does not come back. Member metadata follows the member
  along the MRO (a redeclaration in a subclass replaces it as a whole, with
  no per-key merge), while `class_metadata` is merged along the MRO, with
  the most derived declaration winning per key. Values can be arbitrary and
  are isolated by deep copies in both directions; a declaration that is not
  a mapping fails at the declaration site (the `class` statement for
  `class_metadata`).

- 2026-10-02 — Release builds are now assembled in the repository-root
  `dist/`: the publish and TestPyPI workflows build both distributions with
  an explicit `--outdir dist` there. (The tool's default, a `dist` inside
  the package catalog, never reached the `twine check` and the artifact
  upload, which both expect the root one.) Build intermediates stay out of
  the shared source tree: each catalog carries a `setup.cfg` that keeps its
  `egg-info` next to the catalog metadata instead of in `src/`, and
  `scripts/build.sh` moves the transient scratch files to `dist/.build`.

- 2026-10-01 — The base machinery of the library (the settings context,
  value conversion, the attribute/plugin/serializer machinery and the name
  helpers, 24 modules in all) was extracted from `advexp.settings._internal`
  into the `advexp.settings_base` package. This is the upcoming
  `advexp.settings-base` distribution on PyPI, the shared foundation of
  `advexp.settings` and the planned `advexp.configuration`.
  `advexp.settings` now depends on `advexp.settings-base`; the public API of
  `advexp.settings` is unchanged, as the facades re-export the same names.
  The base is fully self-contained: it does not mention `advexp.settings`
  anywhere, neither in imports (not even typing-only ones) nor in
  docstrings; the settings class in its signatures is typed as
  `SettingsMeta`, and a test guards the boundary. The log records of the
  machinery go to the logging channel of the distribution that drives it:
  the root settings class declares the channel (`advexp.settings` declares
  `"advexp.settings"`, inherited by every subclass; a sibling distribution
  declares its own in the same way), the context carries the logger, and
  `SettingsConfiguration.set_log_level` now sets the level on the family
  root `advexp`, covering all channels at once. With this change, the
  context-free diagnostics of the base (unresolvable dataclass annotations
  in conversion) moved to the base's own `advexp.settings_base` channel.

- 2026-09-30 — Package URLs moved to the new project domain: `Homepage` in
  every package `pyproject.toml` is now `https://advexp.net`, and
  `Documentation` now points to the source repository
  (`https://github.com/advexp/advexp.settings.python`). Links in prose to
  the product site (the package READMEs) now use
  `https://advexp.net/advexp.settings/`.

- 2026-09-29 — Wording of the package's one-line descriptions: the PyPI
  summary is shortened to "Application settings for Python", and the README
  tagline now reads "Typed application settings with pluggable backends".

- 2026-09-29 — The import package is renamed to `advexp.settings`, a dotted
  name in the `advexp` namespace (PEP 420), instead of the flat
  `advexp_settings`. The PyPI distribution is still `advexp-settings`. Every
  import changes: `from advexp.settings import Settings` for applications,
  the bundled backends at `advexp.settings.plugins.*`, and the API for
  backend authors at `advexp.settings.plugin_api`. The logger channel still
  follows the import package (`advexp.settings`). Nothing has been released
  to PyPI yet, so there is no old spelling to migrate from.

- 2026-09-22 — The internal machinery of the bundled serializers
  (`JSONSettingsSerializer`, `EnvironmentVariablesSerializer`) is now
  name-mangled, completing the sweep over the plugin classes: a subclass can
  no longer shadow or reach the document caches, the file resolution, the
  container walks and the other private helpers. The sweep stops at the
  override point: `_setting_segments` stays protected (it is the inheritance
  contract that a subclass implements), and ordinary `_names` stay free for
  the subclasses' own helpers. Everything else a backend needs was already
  public (the storage operations, the value-form helpers, `attribute_of`,
  the name wishes).

- 2026-09-22 — The backing state of the binding properties of the bundled
  plugin classes (`file_path` of both JSON plugins and the dynamic section
  knobs of `JSONDynamicSettingsPlugin`) is now name-mangled, like the state
  of the plugin base classes: a same-named attribute in a subclass can no
  longer shadow or reach it. The properties themselves are unchanged, and
  the `_raw_dynamic_section_*` readers keep their single underscore, since
  they are a cross-module contract of the JSON serializer, not part of the
  surface for subclasses.

- 2026-09-22 — Setting attribute classes now take their constructor
  parameters in `__init__` (keyword-only). A subclass extends it with a
  `super().__init__(name=..., default=...)` call and keeps its knobs as
  instance fields. The previous `__new__` convention is gone: construction
  in `__new__` with the `__init_fields`/`__init_knobs` hooks, and the guard
  that raised `TypeError` on a subclass `__init__`. It existed to keep type
  checkers accepting class-form declarations, a job that the declaration
  factories now do. Assigning an attribute instance in a declaration still
  works at runtime and is now flagged uniformly by checkers (previously
  PyCharm accepted it).

- 2026-09-21 — Repository layout: the metadata of the free package
  (`pyproject.toml`, `README.md`, `LICENSE`) moved from the repository root
  to `packages/advexp-settings/`, the packaging catalog of the distribution.
  The source tree stays shared at the root (`src/`) and is reachable from
  the catalog through a committed `src` symlink, so builds and editable
  installs are the ordinary src-layout commands run against the catalog
  directory; the packaging allowlist travels with the package's
  `pyproject.toml`. The workspace tool configuration (ruff, mypy, pytest)
  moved to a new root `pyproject.toml` without a `[project]` table, since
  the root is the monorepo workspace, not a package.

- 2026-09-21 — Declared defaults are now served in their converted form:
  `default="8080"` on an `int` member reads as `8080`, and
  `default={"host": "h"}` on a dataclass member reads as an instance, before
  any storage access, which is the same shape that a load produces.
  Well-typed defaults are served exactly as before (the conversion is the
  identity for them); the declaration itself keeps the value as written.

- 2026-09-20 — `SettingsBaseSerializer.set_serializer_params` now keeps the
  delivered context instead of ignoring it, and the new `context` property
  (mirroring the plugin side's) reads it back. A backend subclass no longer
  needs to override the method just to store the context in a field of its
  own: the bundled JSON and environment-variables serializers and the API
  sample dropped that boilerplate. The state is name-mangled in the base, so
  a subclass cannot shadow it. The property returns the context of the pass
  and raises `RuntimeError` on an instance outside a pass (before any
  delivery), where it used to return `None` (and the JSON serializer
  silently fell back to module-default files, flat keys and empty
  enumeration). The value-form helpers and the name wishes need no context
  and remain usable on a bare instance.

- 2026-09-20 — A serializer's `delimiter()` wish outside the supported
  `'.'` / `'_'` pair is no longer silently replaced by the default `'.'`:
  the library logs a warning naming the serializer class and the wish (once
  per serializer class) and keeps using `'.'`.

- 2026-09-20 — Metadata now stores `None` like any other value.
  `set_setting_metadata` / `set_class_metadata` with `None` used to remove
  the entry, the same "`None` means remove" reading that the serializer
  `save` contract has already dropped. Removal is now explicit:
  `Settings.delete_setting_metadata` and `Settings.delete_class_metadata`
  (a missing name is not an error). The getters return the caller's
  `default` only for an absent entry; a stored `None` comes back as `None`.

- 2026-09-20 — Internal hooks that are dispatched through `self` on classes
  that users subclass are now name-mangled, so a subclass that coins the
  same plain name for its own purposes can no longer shadow library
  machinery (each such collision broke construction or every storage pass,
  with an error that pointed into library code). The mangled names are:
  `BaseAttribute.__init_fields` and the contract storage it declares
  (`__name`, `__default`, `__bound_name`; the plain spellings could be
  silently clobbered by a subclass's own attributes of the same names),
  `JSONSetting.__init_knobs` (the `path=` knob; was `_init_knobs`), the
  `DynamicSettingsBasePlugin` machinery (`__values`, `__serializer`,
  `__full_name`, `__stored_names`, `__ordered_names`,
  `__delete_from_storage`, `__enumeration`, `__synchronize`) and
  `SettingsBasePlugin.__context` (the bound context). The plain names stay
  free for subclasses and for classes that implement only the contract.

- 2026-09-20 — The setting attribute of the environment variables backend is
  now `EnvironmentVariableSetting` (was `EnvironmentVariable`): the
  `Setting` suffix aligns it with `JSONSetting`, so the name says that it is
  a setting attribute, and the prefix says where the value lives.

- 2026-09-19 — `ISettingAttribute` declares its three data fields (`name`,
  `default`, `bound_name`) as abstract properties and is now an `abc.ABC`:
  an attribute class that lacks any of the fields fails at instantiation
  with a `TypeError` instead of misbehaving at the first storage pass.
  `BaseAttribute` implements the contract as properties over per-instance
  storage, so attributes that derive from it are unaffected. Known cost: an
  ABCMeta is back in the MRO of every attribute, and PyCharm may weakly flag
  constructor keyword arguments (`name=`, `default=`, ...). The enforced
  contract is worth more than that noise.

- 2026-09-14 — Saving `None` is now legitimate: the serializer `save`
  contract no longer reads `value=None` as "remove the setting". The JSON
  backend stores it as `null`: a key with `null` loads back as `None`, which
  is distinct from a missing key (that still falls back to the default), and
  `contains_setting` reports it as present. Storages with no null form (the
  environment variables backend) drop the entry instead: for them, `None`
  and absence coincide, and loading falls back to the default. Removing a
  setting explicitly remains the job of `delete_setting`. One visible side
  effect: `save_settings` now writes keys for members whose current value is
  `None` (as `null` in the JSON backend) instead of skipping them.

- 2026-09-14 — The remaining loose annotations now use the contracts:
  `SettingsConfiguration.register_settings_attribute` /
  `get_serializer_factory` and `SerializerCache.get_for_attribute_class`
  take `Type[ISettingAttribute]` (the registry itself is typed the same way;
  the registered value is typed `Type[ISettingsSerializer]`, since every
  registration passes a serializer class, so the registry deals in classes,
  not factories); `SettingsConfiguration.registered_plugin_classes()`
  returns `List[Type[ISettingsPlugin]]`; `set_serializer_params` (the wishes
  contract and `SettingsBaseSerializer`) receives `SettingsContext` instead
  of `Any`; the fields of the binding pair are typed
  `Type[ISettingAttribute]` / `Type[ISettingsSerializer]`; and the
  `attribute` of `get_full_setting_name` is `Optional[ISettingAttribute]`.
  These are annotation-only changes, with no change in behavior.

- 2026-09-14 — The serializer contracts now use typed attributes: the `attr`
  argument of `ISettingsSerializer.load/save/delete/contains` (and the
  redeclarations in `SettingsBaseSerializer`, `attribute_of` included) is
  now `Optional[ISettingAttribute]` instead of `Any`. Every call carries
  either the setting's attribute instance or `None` (a dynamic-settings
  entry, which has no attribute instance). Overrides declared with
  `attr: Any` still type-check; the environment variables and JSON
  serializers and the API sample now use the typed form. The environment
  variables backend also raises its "no name to build the environment
  variable name" `ValueError` for `attr=None` calls instead of crashing with
  `AttributeError`.

- 2026-09-14 — `JSONDynamicSettingsPlugin` pins the backend through
  `DynamicSettingAttribute[JSONSetting]` and declares
  `serializer_class = JSONSettingsSerializer` (registered by the base
  `setup()`, not by the shared `JSONSetting` pair): the dynamic and the
  static JSON plugins now hold separate registry slots, so importing or
  binding one can no longer clash with the registration of the other.
  Behavior is unchanged: the pin is registered to `JSONSettingsSerializer`,
  and importing the dynamic package alone still enables the backend.

- 2026-09-13 — `SettingsConfiguration.register_settings_attribute` now
  guards the registry: re-registering the same attribute-to-serializer pair
  is a no-op (several plugins may share one pair), while registering an
  already registered attribute class with a different serializer factory
  raises `ValueError` instead of silently replacing the first backend.

- 2026-09-12 — Failed storage flushes now reach the caller: errors raised
  from `synchronize()` and wrapped in `UserFacingError` propagate (as the
  inner exception) instead of being logged and skipped, which is the rule
  that member operations always followed. The JSON backend wraps its file
  access in `UserFacingError` (reading an existing but unreadable file, and
  the writing itself: mkdir, temp file, atomic replace), so a broken storage
  path (unwritable, missing permissions, a non-directory on the path) raises
  out of the pass instead of only being logged. A missing file still means
  an empty document. The first user-facing error aborts the whole pass:
  settings declared after the failing one, including the members of other
  backends and end-of-pass flushes, are not processed; ordinary backend
  errors are still logged and skipped.

- 2026-09-12 — The bundled `pyAttributes` copy is updated to upstream 2.5.1.
  Upstream's pyTooling dependencies are cut: the `@export` decorator is
  replaced by an explicit `__all__`, and `pyTooling.Common.isnestedclass` is
  inlined as a private helper, so the vendored module (and the whole
  package) still has no runtime dependencies. The update brings the new
  class-level attribute surface (`Attribute.GetClasses`, per-attribute
  `_classes` registration); the argparse part of upstream is not carried
  over.

- 2026-09-11 — The public API is now split by audience: the top-level
  `advexp.settings` exports only the application API (`Settings`,
  `SettingsConfiguration`, `NO_DEFAULT`, `PluginNotEnabledError`,
  `__version__`), and the new `advexp.settings.plugin_api` module is the
  import site for backend authors (`BaseAttribute`, `SettingsBasePlugin`,
  `SettingsBaseSerializer`, `ISettingsSerializer`,
  `ISettingsSerializerWishes`, `ISerializerNotificationSink`,
  `SettingsContext`, `NOT_FOUND`, `UserFacingError`, plus the shared
  `NO_DEFAULT`/`SettingsConfiguration`). The value-form converters
  `to_json_value` and `to_storage_string` are overridable methods of
  `SettingsBaseSerializer` (the storage side of the round-trip type
  contract), not free functions. `SettingDescriptor` left the public API
  entirely (it is metaclass machinery). The bundled plugins import
  `plugin_api` instead of `_internal`; both import sites are enforced by a
  repository test and a ruff `TID251` ban on `advexp.settings._internal`.

- 2026-09-11 — Class-to-file binding is now plugin state, not an attribute:
  the JSON backend's `JSONSettingsFile` is a plain decorator over the
  per-class plugin instance, and
  `WindowSettings.get_plugin(JSONSettingsPlugin).file_path = ...` is the
  imperative form. Binding resolution walks the MRO of the settings class:
  the most derived binding still wins entirely, and a subclass without its
  own binding inherits the base's file. The class-level info-attributes
  machinery is gone with this change: `get_class_attributes` left
  `plugin_api`, and `BaseAttribute` no longer attaches itself to classes
  (the pyAttributes class-slot workaround was removed from the core).

- 2026-09-11 — `Setting` left the application API: the standard attribute
  has no backend yet (declaring a setting with it raises
  `PluginNotEnabledError` at the first storage pass, which is by design and
  covered by a test), so exporting it promised storage that the library does
  not ship. It stays internal and will return to the public surface together
  with the local-settings backend, which will own its registration.

- 2026-09-11 — The storage backend contract is split: `ISettingsSerializer`
  now declares only the five storage operations (`load`, `save`, `delete`,
  `contains`, `synchronize`), all abstract. The optional parts moved to the
  new interfaces `ISettingsSerializerWishes` (`delimiter`,
  `remove_inappropriate_symbols`, `set_serializer_params`) and
  `ISerializerNotificationSink` (the `on_start/end_*` pairs for load, save,
  delete and contains; `contains_setting` fires the same bracket as the
  other passes, minus `synchronize`). The pipeline probes for the optional
  interfaces instead of requiring them: a backend that implements only
  `ISettingsSerializer` is valid (no context injection, default names, no
  notifications). The recommended path is the new `SettingsBaseSerializer`,
  which combines the interfaces and carries the former default
  implementations (no-op `synchronize` and notifications, the `'.'`
  delimiter, pass-through name sanitizing, an ignored context); only `load`,
  `save`, `delete` and `contains` must be implemented.

### Added

- 2026-10-06 — The environment family gets a dotenv file backend built on the
  python-dotenv package: `advexp.settings.plugins.environment.dotenv` for
  `advexp.settings` (loads and stores settings in a `.env` file) and
  `advexp.configuration.plugins.dotenv` for `advexp.configuration` (a
  read-only source for the same file). Both are installed with the `dotenv`
  extra of their distribution. The backend supports everything the process
  environment backend does: the family's naming options (prefix, case,
  nested delimiter) build the variable names, an explicit `name=` is the
  full address, dataclass members resolve field by field through the nested
  delimiter, saving `None` removes the variable's line, and a missing file
  behaves as an empty one. By default, the file of a class is the
  conventional `.env` in the working directory
  (`DotenvConfiguration.file_path`), or the file given by the class's own
  `dotenv_file(...)` binding, declared through the `options=` keyword of
  the `class` statement beside the other class options; the plugin
  instance's `file_path` property is the imperative spelling of the same
  binding. A pass reads the file once, and saving goes
  through python-dotenv's own line editing, so comments, `export` lines and
  variables that no member claims stay exactly as written.

- 2026-10-06 — The environment family addresses nested objects field by
  field. The new `nested_delimiter` option of `environment_options(...)`
  (`None` by default) makes a member annotated with a dataclass resolve its
  fields through the delimiter: with `"__"`, `APP_DB__PORT` is the `port`
  field of the `db` member, to any depth, and the case option applies to
  every part. Loading merges the variables onto the declared default
  instance (a partial update: fields that no variable addresses keep their
  declared values). A whole-object JSON variable still works under the
  member's own name and under the name of any nested object, and a
  per-field variable wins over it. Saving stores each field in its own
  variable and drops the whole-object ones, deleting removes the whole
  subtree, and the containment check sees any address. The `advexp.settings`
  backend and the read-only environment source of `advexp.configuration`
  resolve addresses by the same rules; the shared code lives in
  `advexp.settings_base.environment_nested`.

- 2026-10-05 — The `options=` keyword of the `class` statement accepts a
  sequence (a tuple or a list) of mappings as well as a single mapping, so
  the helpers of several families and free keys can share one keyword
  (`options=(environment_options(...), environment_options_for(...))`). The
  entries are combined left to right, and every name may be declared only
  once: a name declared by two entries fails the `class` statement with an
  error naming the class and every shared name, and a non-mapping entry is
  rejected with its own error. The READMEs, docstrings and samples show the
  sequence form as the way to combine them.

- 2026-10-04 — The `advexp.configuration` README and the environment
  variables sample now explain that `options=` carries one metadata mapping
  for all sources: each family that takes options fills its own entry
  (`environment_options()` returns a ready-made one-entry mapping), a class
  that reads from several such sources merges the helpers' results in one
  dict literal, and free keys of the open channel go in the same mapping, as
  the sample shows by reading them back through `get_class_metadata`. The
  per-class configuration of the JSON source remains the `@JSONSettingsFile`
  binding and takes no entry in the mapping.

- 2026-10-04 — A load pass of `advexp.configuration` no longer aborts at the
  first failing member. Every member gets its load, and a single abort at
  the end reports all failures at once. The abort is always one
  `AggregateLoadError` (a `RequiredMemberError` subclass), however many
  members failed, so the exception type never depends on the number of
  failures. Its message lists each failed member, and its `errors` tuple
  holds the individual exceptions (`MissingValueError`, `ConversionError`,
  `ConstraintViolationError`, `SourceLoadError`) in declaration order.
  Members that did load keep their values. A source's own user-facing error
  (a corrupt or unreadable file) becomes the member's `SourceLoadError` on a
  required member and is collected with the rest, so a JSON member among
  environment members is reported in the same single abort. On an optional
  member it still aborts the pass as itself, because a default must not
  mask it.

- 2026-10-04 — `samples/settings/custom_backend.py` now tours the `options=`
  class-statement spelling with the custom family's own helper:
  `AuditSettings` declares `memory_options(redact_everything=True)` right in
  the class statement and saves redacted from the first pass. This shows
  that the readable spelling is available to the options of any backend
  family, not only the bundled environment one, and that options remain per
  class. The secure-partition member is now a `SecretStr`: reads and reprs
  mask the payload while the storage keeps the plain form, and the
  fallback-warning demo shows the masked secret branch naming the
  partition's key.

- 2026-10-03 — The `class` statement of a settings or configuration class
  accepts a keyword of its own: `options=` is a readable spelling of the
  class's `class_metadata` declaration.
  `class AppSettings(Settings, options=environment_options(...))` lands in
  the same declared channel as the body assignment, with the same
  validation, the same MRO merge and the same runtime lifecycle. Declaring
  both spellings in one class body raises `TypeError`.

- 2026-10-03 — The environment variables source of `advexp.configuration`
  now honors the naming options of the environment family: `class_metadata`
  with `environment_options(name_prefix=..., name_case=...)` (the helper and
  the `NameCase` enum are re-exported by
  `advexp.configuration.plugins.environment_variables`) builds each variable
  name as `name_prefix + name_case(member name)`. The rule, the
  `"EnvironmentMetadataOptions"` key and the validation are the same as in
`advexp.settings`. An explicit `name=` remains the full address;
without options, names keep their form.

- 2026-10-03 — `samples/settings/custom_backend.py`, the sample for plugin
  authors. This custom backend covers what moved out of the API sample: the
  `secure=` attribute knob with a storage partition, behavior driven by
  member metadata (`redact-on-save`), the class-metadata options channel
  with a registered validator, plugin access, dynamic settings on the same
  storage, and the two value-form helpers of the serializer base.

- 2026-09-30 — The `advexp-configuration` distribution skeleton: an empty
  `advexp.configuration` package under `src/` (the second distribution in
  the `advexp` PEP 420 namespace) and its packaging catalog
  `packages/advexp-configuration/` (Apache-2.0, PyPI channel). The module
  exports nothing yet; the catalog builds and ships the skeleton so that
  the package is ready to grow its public API.

- 2026-09-24 — SPDX license headers on every distributed `.py` file
  (`src/`): a `Copyright` line and an `SPDX-License-Identifier` line above
  the module docstring, naming the license right in the file: `Apache-2.0`
  for the free core. `REUSE.toml` declares coverage for the files that
  carry no headers (tests, samples, package metadata), and `reuse lint`
  in CI keeps the headers from drifting.

- 2026-09-22 — `JSONSettingsSerializer._setting_segments` is the backend's
  placement hook, now a documented contract: every storage operation
  (`load`, `save`, `delete`, `contains`) calls it to locate a key in the
  document. Override it, calling `super()` for the stock placement, to
  relocate keys (for example, to nest them under a runtime-named object;
  `samples/json_custom_metadata.py` walks through the recipe). The base's
  reservation check, which refuses a placement inside the dynamic settings
  section, belongs to the base implementation: an override that bypasses
  `super()` is responsible for staying clear of the section.

- 2026-09-22 — Declaration factories `json_setting` and
  `environment_variable_setting` (in their plugin modules): the
  checker-friendly spelling of `JSONSetting` and `EnvironmentVariableSetting`.
  They take the same keyword parameters and produce the same attribute, but
  are plain functions returning `Any`, so
  `port: int = json_setting(default=8080)` passes type checking where
  assigning the attribute instance trips mypy (it cannot see the settings
  metaclass replacing the attribute with a value descriptor). The class
  spelling keeps working; custom backends ship a twin factory for their
  attribute in the same way (see `samples/settings_api.py`).

- 2026-09-21 — `SettingsContext.get_dynamic_setting_full_name` returns the
  full storage name of one dynamic entry of the context's settings class:
  the plain name expanded with the dynamic marker and the class part of the
  pattern. It is the counterpart of `get_dynamic_setting_name` (the split),
  for backends that lay out dynamic entries in their own structures and
  enumerate them through `IDynamicSettingsInfo`.

- 2026-09-21 — `SettingsContext.get_dynamic_setting_name` returns the plain
  setting name behind a dynamic full name of the context's settings class:
  it strips the `D` prefix and the class part of the pattern (the inverse of
  the dynamic mode of name building), and returns `None` for anything that
  is not a dynamic entry of the class (a static name, another class's
  entry, foreign data). It is meant for serializers that serve dynamic
  entries, since their plugin's metadata is keyed by the plain name; the
  optional `serializer` argument carries its delimiter wish. Walked through
  in `samples/settings_api.py`.

- 2026-09-21 — `get_class_all_metadata` and `delete_class_all_metadata` are
  the class-metadata counterparts of the snapshot getter and the bulk
  remover: the first returns every class-level entry as a deep-copied dict
  keyed by metadata name (empty when nothing is stored), and the second
  clears the whole class storage in one call, including every consumer's
  entry (a dynamic plugin's declared iteration order, for example).
  Available on `Settings` and `SettingsContext`.

- 2026-09-21 — `get_setting_all_metadata` returns every metadata entry of
  one setting as a dict keyed by metadata name, the enumeration that the
  point getters cannot give. It is available on `Settings` and
  `SettingsContext` (member name or getter, with the same declared-member
  check) and on `DynamicSettingsBasePlugin` (with the collection-member
  check). The dict is a deep-copied snapshot, like `to_dict`; a setting
  with nothing stored returns an empty dict.

- 2026-09-21 — Setting metadata for dynamic settings:
  `DynamicSettingsBasePlugin` gained `set_setting_metadata`,
  `get_setting_metadata`, `contains_setting_metadata`,
  `delete_setting_metadata` (one entry) and `delete_setting_all_metadata`
  (every entry of the name), keyed by the plain dynamic name. The entries
  live with the plugin's collection and are separate from the member
  metadata of the settings class, even where a dynamic name matches a member
  name. Every operation resolves the name against the collection: a dynamic
  setting exists exactly while it holds a value, and a name that the
  collection does not hold raises `KeyError` naming the collection (the
  same typo guard that the declared side applies to its members). The
  metadata is the collection's runtime state, not stored data:
  `delete_setting` drops the name's entries, `delete_settings` clears them
  along with the collection, and a load clears them too (all of them on
  `load_settings`, and the entry of the loaded name on `load_setting`; a
  load brings values, and the storage holds no metadata to bring).
  `delete_setting_metadata` removes a single entry only, while
  `delete_setting_all_metadata` removes every entry of the name. Values are
  deep-copied in both directions, `None` is a stored value like any other,
  and `contains` distinguishes a stored `None` from a missing entry. Walked
  through in `samples/json_dynamic_settings.py` and
  `samples/settings_api.py`.

- 2026-09-21 — Setting metadata now validates its target: every
  setting-metadata operation, on `Settings` and on `SettingsContext` alike,
  resolves the member name (or getter) against the declared members of the
  settings class and raises `KeyError` naming the available settings if the
  class declares no such member, instead of silently storing an entry that
  no backend would ever read. The check reuses the unknown-name error of the
  single-setting operations, which moved to `resolve_member` in the member
  registry module.

- 2026-09-21 — `SettingsContext` accepts a getter lambda in place of the
  member-name string in its setting-metadata operations, like the
  `Settings` facade. The normalization of the reference moved into the
  context, so code that reaches it through `self.context` can use either
  form. `SettingRef`, the public alias for the two reference forms (already
  the annotation of the facade's parameters), is now exported from
  `plugin_api`.

- 2026-09-21 — `Settings.contains_setting_metadata` and
  `Settings.contains_class_metadata` (with the same pair on
  `SettingsContext`, the surface that backend authors use) tell whether a
  metadata entry is stored under the name. This is the unambiguous
  alternative to the getters, which return their default both for a missing
  entry and for a stored `None`.

- 2026-09-21 — The isinstance tier of default validation now reaches inside
  containers: the element positions of a declared `List`/`Set`/`Tuple` and
  the key and value positions of a `Dict` are walked in lockstep with the
  converted default and checked against their annotated types. So
  `List[Point]` with a default of non-instances (including a JSON-shaped
  default of dicts) fails at class creation, with the offending index or key
  named in the error. `Union` positions and dataclass fields are not
  checked: a union with a custom-class arm accepts anything, matching what
  loading does.

- 2026-09-21 — Startup validation of declared defaults: creating a settings
  class converts every `default=` through the member's annotation (the same
  conversion that a load applies) and raises `TypeError` at the `class`
  statement when one cannot be converted, listing all offending members at
  once. Annotations outside the conversion contract (custom classes, `Any`)
  convert nothing; their defaults are checked with `isinstance` against the
  annotated class instead, so a default that is neither an instance nor
  `None` fails the class in the same way. Subclasses reuse the conversion
  that the declaring class already made on the shared descriptor.

- 2026-09-20 — A separate file for dynamic entries, apart from the static
  settings file: the module-wide `JSONDynamicSettingsConfiguration.file_path`
  (in the `json_dynamic_settings` package) or, per class, the `file_path`
  property of the class's `JSONDynamicSettingsPlugin`. The binding wins over
  the module default and follows the MRO of the settings class at storage
  time, in the same way as the static `JSONSettingsPlugin.file_path`. When
  both are unset (the default), dynamic entries still go into the static
  file, that is, the per-class `@JSONSettingsFile` binding of the class or
  the module-wide `JSONSettingsConfiguration.file_path`. When one is set,
  the dynamic collections go to the named file (setups with only dynamic
  settings then need no static file configured at all), and the static
  file's document no longer reserves the location of the dynamic section, so
  a static key named like the section is allowed there. If the dynamic file
  is the same file as the static one, the reservation is kept (one document,
  one layout). Switching files after saves does not migrate stored entries.
  Walked through in `samples/json_dynamic_settings.py`.

- 2026-09-20 — A recipe for custom attribute metadata: an attribute subclass
  declares its own knobs the way the stock `path=` is declared (`__new__`
  plus the `_init_knobs` hook), and a serializer subclass reacts to them:
  placement in `_setting_segments`, the stored value form in `save`/`load`
  around `super()`, with knobs read through `attribute_of`. The pair is
  registered with `SettingsConfiguration.register_settings_attribute` (the
  exact registry lookup gives the subclass its own slot, and the stock
  `JSONSetting` registration stays untouched). Documented as the README
  section "Custom attribute metadata". The walkthrough sample
  `samples/json_custom_metadata.py` covers the runtime layer of the recipe:
  member and class metadata (`Settings.set_setting_metadata` /
  `set_class_metadata`), read by the serializer through its `context`, which
  turns the same behaviors on and off without touching the declarations (an
  `obfuscate` member metadata that stores a value base64-encoded, and a
  `runtime_section` class metadata that relocates the path-less keys), with
  a bare `JSONSetting` subclass as the registry slot of the custom
  serializer.

- 2026-09-14 — `SettingsBaseSerializer.attribute_of(attr, attribute_class)`
  is the only way for a backend to narrow the `attr: Any` of the interface
  methods to its own attribute class and read backend-specific knobs
  (`path=` and the like) from the typed view. It returns `None` where the
  view does not apply: dynamic entries (calls that carry `attr=None`) and
  attributes of foreign classes that arrive through the global serializer
  override. The JSON serializer now reads `path=` through it, replacing its
  `getattr` probe.

- 2026-09-14 — Declarative plugin registration: the `binding` class
  attribute of `SettingsBasePlugin`, an
  `AttributeSerializerBinding(attribute_class, serializer_class)` pair. A
  plugin that derives from `SettingsBasePlugin` (the static base;
  `DynamicSettingsBasePlugin` inherits it) declares the binding, and the
  base `setup()` registers it at import, so no plugin-specific `setup()` is
  needed. A missing declaration registers nothing; the binding is atomic, so
  a half declaration is structurally impossible. On
  `DynamicSettingsBasePlugin` the binding is mandatory (validated at class
  definition), and its attribute class is the pin of the dynamic collection.
  The bundled plugins (JSON, environment variables, JSON dynamic) and the
  API sample use the declarative form.

- 2026-09-14 — `DynamicSettingAttribute` (in `plugin_api`) is the
  namespaced pin form of a setting attribute: `DynamicSettingAttribute[Attr]`
  yields a stable, per-base class (a subclass of `Attr`) that a dynamic
  plugin declares as the attribute class of its binding. The pin is the
  dynamic side's own slot in the serializer registry: the serializer that
  the pair binds serves the dynamic entries alone and never touches the
  registration of `Attr`, so the static and the dynamic bindings cannot
  conflict. The class itself carries the attribute contract only abstractly
  (it cannot be instantiated); an unregistered pin resolves like any
  unregistered attribute class, with `PluginNotEnabledError`.

- 2026-09-14 — The signatures now use interface/implementation splits.
  `ISettingsPlugin` is the plugin contract that `get_plugin` accepts (the
  bound of its TypeVar, the plugin registry): `plugin_name`, the `context`
  property and the `bind_context()` hook that delivers it; where the context
  is kept is up to the implementation. `SettingsBasePlugin` stays the base
  that provides the binding. `ISettingAttribute` defines what a setting
  attribute is: three data fields with fixed semantics (`default` holds the
  declared value or the `NO_DEFAULT` sentinel, since `None` is a legitimate
  default and absence therefore needs its own marker), declared as abstract
  properties, so an attribute class that lacks any of them fails at
  instantiation. The metaclass detects members by the interface, so an
  attribute class may implement it alone (no `__new__`-typing conventions,
  no pyAttributes machinery), and the dynamic plugin pin accepts it;
  `default_in_use` remains a convenience property of `BaseAttribute`. The
  environment variables serializer overrides now match the `attr: Any` of
  the serializer contract instead of narrowing it to the attribute class.

- 2026-09-13 — Dynamic settings: names that appear at runtime, without a
  declared class member. The collection lives in `DynamicSettingsBasePlugin`
  (`plugin_api`): a plugin pins the static backend it builds on through its
  mandatory `binding` pair and gets storage passes (`load_settings`,
  `save_settings`, `delete_settings`, and the single-setting forms), typed
  reads (`get_setting(name, default=...)` converts to the type of the
  default, like the annotated conversion of declared settings; without a
  default it returns the raw storage form, and a missing name raises
  `KeyError`), `set_setting`, a dict-like protocol (`len`, `in`, iteration,
  `to_dict`/`update_from_dict`) and the iteration order declared in code
  through the `dynamic_settings_order` class metadata. Backends opt into
  name discovery with the `IDynamicSettingsInfo` serializer capability.

- 2026-09-13 — `advexp.settings.plugins.json_dynamic_settings`, the first
  dynamic settings plugin: `JSONDynamicSettingsPlugin` keeps the
  runtime-named settings of a class in the same JSON file as its
  `JSONSetting` members. The dynamic entries occupy their own section of the
  document (`"dynamic"` by default, with one nested object per settings
  class; the static keys stay at the root). Two knobs control the layout,
  mirroring `name=`/`path=` of `JSONSetting`:
  `JSONDynamicSettingsPlugin.dynamic_settings_section_name` names the
  section key (`None` switches to flat, `D`-prefixed full-name keys at the
  document root), and the optional
  `JSONDynamicSettingsPlugin.dynamic_settings_section_path` places the
  section deeper in the tree (`"config"` nests it inside the `config`
  object; segments must not be empty). Both bindings follow the MRO of the
  settings class, each independently; changing them does not migrate entries
  that are already stored. A static setting whose location overlaps the
  section (is an ancestor of it, is inside it, or is equal to it) is
  rejected.

- 2026-09-13 — Object snapshots: `Settings.to_object()` and
  `Settings.update_from_object()` give the snapshot as a detached instance
  of the settings class instead of a dict. Its fields carry the declared
  names and annotations, so after a setting is renamed, stale access to a
  snapshot field becomes a type-checker error (and an `AttributeError`)
  instead of a silently missing dict key. Reads and writes on the snapshot
  stay on that instance; applying it back converts and deep-copies exactly
  like `update_from_dict`. Any object with a plain attribute namespace is
  accepted there (a `SimpleNamespace`, a dataclass), with its attribute names
  being member names; unknown names raise `KeyError`, as with dicts.
  Ordinary instances are unaffected: they keep sharing the class storage.

- 2026-09-11 — JSON backend: the optional `path=` argument of `JSONSetting`
  locates the setting in the document tree as a JSON Pointer (RFC 6901), one
  notation across the language ports of the library. `path="/net/proxy"`
  stores its key inside `net` → `proxy`, `path="/mirrors/1"` inside the
  second element of the `mirrors` array, and `path="/endpoints/api.internal"`
  under an object key that contains a dot (`~1` escapes `/`, `~0` escapes
  `~`); `path=None` or `""` keeps the key at the document root. A segment of
  only digits indexes an array when the node it steps into is one, and
  otherwise names an object key (leading zeros stay keys, since RFC array
  indexes have none). Reading through a missing key, or a missing or too
  short array, applies the default. Saving extends a missing or too short
  array with JSON nulls up to the indexed position, and a path step onto
  data of the wrong kind raises an error instead of overwriting it. Deleting
  a setting removes the path objects that it left empty: an emptied array
  element becomes a null (sibling positions stay stable), and an array in
  which every element is null is dropped. The name stays a plain key (dots
  included). The dynamic settings section path
  (`dynamic_settings_section_path`) uses the same Pointer form.

- 2026-09-10 — Dataclass values: a setting annotated with a dataclass
  (directly or inside `Optional`, `List`, `Dict`, `Tuple` or another
  dataclass) is stored as a plain object of its fields (a JSON object in the
  JSON backend, a JSON string in string-based backends) and rebuilt from the
  annotation on load, with each field converted by its own type. Fields that
  are missing in storage take the dataclass defaults, keys that the class no
  longer declares are ignored, and a missing required field falls back to
  the setting's default. Field annotations are resolved from the
  dataclass's module; a field whose string annotation cannot be resolved is
  loaded without conversion and reported in the log once per class.

- 2026-09-07 — Settings snapshots: `Settings.to_dict()` and
  `Settings.update_from_dict()` copy the current values of all declared
  settings into a plain dict and apply a dict back, with the same type
  conversion as on load. Values are deep-copied in both directions, so the
  class storage never shares mutable state with the snapshot. Unknown keys
  raise `KeyError`; a failed conversion applies nothing. A Python-side
  convenience over the singleton class storage.

- 2026-09-07 — Mutable defaults are isolated: `resolved_default()`
  deep-copies the declared default on each use, so in-place mutation of a
  setting (or of the value of an unset member) never corrupts the default,
  which subclasses share because it is the same attribute object. Setting
  and class metadata (`set/get_setting_metadata`, `set/get_class_metadata`)
  are deep-copied in both directions for the same reason. The
  `ISettingsSerializer.save` contract now notes that in-memory backends must
  copy the mutable values they retain.

- 2026-09-03 — Getter-lambda form for single-setting operations:
  `load_setting`, `save_setting`, `delete_setting`, `contains_setting`,
  `set_setting_metadata` and `get_setting_metadata` accept
  `lambda s: s.<member>` in place of the member-name string. The lambda is
  checked against the exact `lambda s: s.<member>` shape and is never called.

- 2026-09-03 — `reset_setting` resets a single setting to its
  default and accepts both the name string and the getter lambda.

- 2026-09-03 — Core settings contract: the `Settings` base class
  (class-level API: `load/save/delete_settings`, per-setting operations,
  metadata, `get_plugin`), setting attributes built on pyAttributes
  (`BaseAttribute`), the attribute-to-serializer registry
  (`SettingsConfiguration`), the storage backend contract
  (`ISettingsSerializer`), name formatting and value conversion. The API is
  a draft and will change until the first stable release.

- 2026-09-03 — Environment Variables plugin: importing
  `advexp.settings.plugins.environment_variables` enables the backend;
  settings are read from and written to the process environment.

- 2026-08-31 — Initial project structure: `pyproject.toml` packaging (src
  layout), tests, samples, CI and PyPI publishing workflows.

- 2026-08-31 — Bundled `py_attributes` utility package (vendored
  pyAttributes, Apache-2.0, © Patrick Lehmann) that provides .NET-like
  attribute decorators.

### Removed

- 2026-09-21 — **Breaking:** `DYNAMIC_SETTING_NAME_PREFIX` is removed from
  `plugin_api`: the dynamic marker of storage names is internal to the
  library. Backends should compose and read names through operations
  instead: build them with `SettingsContext.get_dynamic_setting_full_name`,
  split them with `SettingsContext.get_dynamic_setting_name`, and get the
  class part alone with `get_dynamic_settings_class_prefix`. Along with
  this, `IDynamicSettingsInfo.get_dynamic_settings_names` is narrowed to the
  contract that its only consumer ever needed: the names are returned for
  the settings class that the serializer's pass is bound to (entries of
  other classes in the same storage are the business of their own passes:
  the plugin filters what it reads down to its class, so the surplus names
  were inert). The enumeration in the bundled JSON serializer follows: its
  flat layout picks the full names of the bound class out of the document
  root, and its section enumerates only the bound class's object.

- 2026-09-14 — The vendored `py_attributes` package is removed: the whole
  `_external/` tree, its ruff/mypy exclusions and the third-party
  attribution in the README. `BaseAttribute` implements the
  `ISettingAttribute` contract alone; the metaclass has always detected
  setting members by that contract, not by the pyAttributes base, so runtime
  behavior is unchanged, and the distribution is now 100% original code.

- 2026-09-14 — **Breaking:** the `secure` flag is removed from the
  serializer contract and the standard attribute.
  `ISettingsSerializer.load/save/delete/contains` (and their declarations in
  `SettingsBaseSerializer`) no longer take the `secure: bool` parameter, and
  `Setting` no longer accepts `secure=`. Neither bundled backend ever read
  it: the free core has no storage with two classes of access, so the
  parameter was dead weight. A backend that does separate protected storage
  declares its own knob on its attribute class and reads it from `attr` in
  its serializer, the way `path=` of `JSONSetting` works.

### Fixed

- 2026-09-20 — A settings class that mixes attribute classes over one JSON
  file (the stock `JSONSetting` plus a registered subclass) no longer loses
  members' keys: the serializers over one file now share a single in-memory
  document, and each flush writes every pending change of the round, so the
  last serializer's private document no longer overwrites the keys of the
  others. The shared entry lives only between `on_start_serializer_action`
  and `on_end_serializer_action`, so a later pass still re-reads the file.
  To keep that contract, the dynamic collection passes (which drive their
  serializer directly, outside the class pipeline) now open the serializer
  notification bracket around their work too, and receive the start/end
  notifications as pipeline passes always have.

- 2026-09-14 — The whole package, tests and samples now type-check cleanly
  with mypy (default ruleset, `python_version = 3.9`, configured in
  pyproject.toml; the vendored `_external` stays excluded). The fixes are
  annotation-only: the metaclass-injected `__settings_members__` /
  `__settings_values__` / `__settings_context__` are declared on `Settings`
  with types that resolve at runtime, the pipeline helpers and the
  `JSONSettingsFile` decorator take `Type[Settings]`, and a few
  `Optional`/union annotations are narrowed in conversion and in the
  serializers. One behavior fix slipped in: a `Path` setting now also
  converts from its bytes round-trip form (previously this raised
  `TypeError`).

- 2026-09-14 — `Settings.get_plugin(...)` is now annotated to return the
  requested plugin class, not the `SettingsBasePlugin` base: type checkers
  (PyCharm, mypy) no longer flag plugin-specific attributes reached through
  the handle (`plugin.set_setting`, `plugin.dynamic_settings_section_name`,
  ...) as unresolved. Runtime behavior is unchanged: the handle was always
  an instance of the requested class.

- 2026-09-11 — Type checkers flagged every setting declaration
  (`host: str = Setting(...)`) as assigning a `Setting` where the annotation
  says `str`, because they cannot see the metaclass replacing the attribute
  with a value descriptor. Setting attributes are now initialized in
  `__new__`, typed to return `Any`, which clears the flag in checkers that
  honor the return type of `__new__` (PyCharm, pyright). mypy does not honor
  it, so annotated declarations remain a known mypy false positive (the CI
  check covers only the package sources, which declare no settings). Plugin
  authors should follow suit: custom attributes extend `__new__` instead of
  defining `__init__`.

- 2026-09-10 — `synchronize()` ran after the end notifications: the pipeline
  called it outside the `on_start/end_serializer_action` bracket, so hooks
  like `on_end_save_settings` fired while the backend still held unflushed
  changes. It now runs after the save/delete member loop and before the end
  notifications.

- 2026-09-10 — Items of a value that was already a list were not converted:
  a JSON document yields a list of raw strings for `List[datetime]`,
  `List[Enum]`, `List[Decimal]` and the like, and they were passed through
  as strings; the same happened with a tuple of raw values under
  `Tuple[int, ...]`. Only lists whose items need no conversion (`List[int]`,
  `List[str]`) worked.
