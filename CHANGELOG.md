# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-26

### Changed

- 2026-11-26 — the Installation section of the advexp-configuration
  README names its extras, as the advexp-settings README already does:
  dotenv, TOML below Python 3.11, YAML, and the pydantic model source.

- 2026-11-26 — the error message of a parameterized file that an unset
  profile variable leaves unresolved no longer ends with a stray `=`: the
  sentence ends with its reason.

- 2026-11-26 — the Migrating from pydantic-settings page declares its
  `api_token` as a `SecretStr` in the pydantic model, so the closing
  example that frees the secret before `update_from_dict` runs against
  the model of the page.

- 2026-11-26 — two documentation examples are corrected to run as printed.
  The second example of the Shared declarations page called `env_source`
  through the root of advexp.configuration, which never exports it; it now
  imports the environment plugin of that package and binds the chain
  through the plugin's own builder. The Dynamic collections example of the
  Setting metadata page used a class and a plugin alias that the page never
  established; it now declares the writing class and seeds the entry whose
  metadata it annotates.

- 2026-11-24 — the distributions carry 0.2.0 ahead of the release: the
  `version` of advexp-settings and advexp-configuration and the
  source-checkout fallback of their `__version__` modules move from
  0.1.0; advexp-settings-base already reads 0.2.0, and the lockstep
  dependencies `advexp-settings-base==0.2.0` stand unchanged.

- 2026-11-24 — the PyPI plaques of the public repository README are
  stamped with v0.2.0 ahead of the release sync: the version lives in the
  aria-label, the title, and the text of each SVG, and in the alt
  attributes of the README. Until the sync ships the release, the plaques
  rest in the overlay and reach no reader.

- 2026-11-23 — the Where-to-go-next list of the settings overview is
  reordered: Shared declarations moves under Setting metadata, and the
  Configuration counterpart stands before Samples.

- 2026-11-23 — the Where-to-go-next list of the configuration overview is
  reordered: Shared declarations and Migrating from pydantic-settings move
  after Dynamic settings, and the Settings counterpart stands before
  Samples.

- 2026-11-23 — the ClassVar note of the settings getting-started page
  becomes a highlighted block with its own title and moves before the
  `setting(...)` section: as two plain sentences after the factory example
  it was easy to miss, and the topic belongs to plain annotations, closing
  them before the factories begin. The block also says plainly that a
  `ClassVar` value is never loaded, saved, or included in a snapshot.

- 2026-11-23 — everywhere the quick example lives — both tabs on the index
  page, the overview pages of both packages, and both getting-started
  pages — the comment over `mode` names the APP_MODE environment variable
  outright instead of the bare `APP_MODE:` shorthand; the package READMEs,
  generated from the overview pages, follow, and so do the root READMEs of
  both repositories (2026-11-24).

- 2026-11-23 — the configuration class of the shared-declarations example
  closes its empty body with a docstring instead of the ellipsis
  shorthand: the class reads as complete, not as a cut-off.

- 2026-11-23 — the factory declarations of the shared-declarations
  examples — the shared-declarations page, the pydantic migration page,
  and the samples of both packages — now carry their type annotations
  (`retries: int = setting(default=3)`). An annotation is the only carrier
  of a member's type: without it a loaded value reaches the member
  unconverted, and the examples were demonstrating exactly that.

- 2026-11-23 — the introduction of the documentation index page drops the
  sentence that announced the two-package list: the list now follows the
  opening line directly.

- 2026-11-23 — the quick example on the documentation index page is split
  into tabs: the Settings tab keeps the read-write example, and the new
  Configuration tab shows the same declarations read through a source
  chain. Each tab carries its own closing paragraph about where the plain
  members come from.

- 2026-11-19 — the sample of the cross-package exchange of a dynamic
  collection is renamed: `samples/both_packages/dynamic_exchange.py` becomes
  `samples/both_packages/dynamic_settings_exchange.py`. The site pages that
  point at the sample follow the new name.

- 2026-11-19 — the read-only dynamic collection of `advexp.configuration`
  carries the runtime metadata of its entries. The six metadata methods
  refused with a `TypeError` before; they now work exactly as on the
  writing collection of `advexp.settings`: the annotations are the reading
  collection's own runtime state (the writer's metadata is the state of
  the writing process and is never stored), a name must be one that the
  collection holds, and the next `load_configuration()` clears the
  annotations with the rebuild. The refusal keeps covering the methods
  that write values or storage.

- 2026-11-19 — a load miss that walked a whole chain of sources empty no
  longer piles the storage addresses into one parenthesized line: the entry
  of the miss lists one address per line beneath the message, every link
  the pass checked. A member with a single storage keeps the message it
  always had. The log records stay single-line in the old spelling.
- 2026-11-19 — the shared-declarations sample prints the entry of the
  failed member (all of them, one line each) instead of the bare header
  line of the abort.

### Added

- 2026-11-19 — `advexp.configuration` gains `contains_member()`: a probe
  that asks the class's source chain whether any link holds a value for
  one member, without loading. The chain is walked the way a load
  walks it, and the first link that holds a value answers `True`; a member
  of a sourceless family and a chain-wide miss answer `False`. The probe
  builds no state — the values of the class stand as they were — and it
  checks presence alone: the stored value is neither converted nor
  validated, so a member whose value would fail a load still answers
  `True`. A broken source is the caller's error to see: a plain storage
  error leaves as is, and a user-facing one is raised unwrapped, as the
  inner exception.
- 2026-11-18 — `to_dict()` takes a `missing=` mode that says what a
  required member without a value becomes in the snapshot. The
  default keeps today's behavior: the read of such a member fails the
  snapshot. `MISSING_NONE` exports the member as `None`, keeping every
  member name in the dict — the shape a model with optional fields
  accepts; `MISSING_SKIP` leaves the member out, so the dict holds only
  the members that have a value. Both package roots export the three
  constants, and an unknown mode fails the call with a `ValueError` that
  lists the accepted ones.
- 2026-11-18 — `update_from_dict()` and `update_from_object()` record a
  warning when a member whose annotation does not include `None` (not
  `Optional`, not `Any`) receives `None`. The value is stored as
  any other — `None` is a value a member may hold — and the warning names
  the member and its annotation on the package's logging channel, so a
  mistaken key surfaces in the log instead of passing silently.

### Changed

- 2026-11-17 — The profile argument of the source builders is
  `settings_profile=` now, and it takes one profile. Before, the
  argument was spelled `parameters=` and accepted a sequence of
  `settings_profile(...)` declarations; the sequence form was a dead
  generality — no example, sample, or test ever passed more than one
  profile — and it is gone. A file path template still spells its slot and
  the profile fills it; a template that spells a slot no profile declares
  fails the builder call, as before. The link parameter key follows the
  argument: `LINK_PARAMETERS_PARAM` is `LINK_SETTINGS_PROFILE_PARAM` now,
  for the authors of third-party sources.
- 2026-11-17 — `env_parameter(...)` is renamed to `settings_profile(...)`
  and its class to `SettingsProfile`. The old name read as
  the vocabulary of the environment-variables family (`env_source(...)`
  and its plugin), while the declaration belongs to the core and serves
  every file backend: it declares one profile of the settings — a named
  slot of a templated file path whose value one environment variable
  provides, with the whitelist of its values and an explicit default.
  One file per profile, the `appsettings.{env}.json` convention. The
  rename is the migration: change the import and the call. The template
  slots, the `parameters=` argument of the source builders, and the
  module defaults machinery keep their names.
- 2026-11-17 — The family factories of the member vocabulary live in the
  package of their family only: `json_setting`, `toml_setting`,
  `yaml_setting`, `dotenv_setting`, and `environment_variable_setting`
  are no longer re-exported from the roots of `advexp.settings` and
  `advexp.configuration`. A member of a single backend is declared with
  the factory of that backend's package, and importing the package is
  what enables the backend — the factory and the backend arrive together,
  and there is no spelling that declares a member of a family whose
  plugin was never imported (before, the root re-export let the
  declaration in, and the `class` statement refused it later). The core
  factories stay in the roots: `setting`, `sourceless_setting`, and the
  shared re-exports of both packages. A declaration base keeps importing
  the family factories from `advexp.settings_base`, the storage of the
  family-wide vocabulary.
- 2026-11-16 — The `chain_setting(...)` alias of `advexp.configuration` is
  gone. The factory that declares a neutral member — one that the
  class's own chain resolves, with `name=`, `aliases=`, and the value
  constraints — has been family-wide since the shared-declarations wave,
  and both packages re-export it under the one name: `setting(...)`. The
  second name was the configuration-side spelling of the same function,
  and it retires now; the migration is the rename of the import and the
  call. Both packages carry the same member factories after it:
  `setting`, `sourceless_setting`, and the five family factories.

- 2026-11-15 — `non_storage_setting` and `constant_setting` are one factory
  now, `sourceless_setting(...)`. The member declares a value that
  no source or storage ever serves: the load pass serves the declared
  default without asking any source, the load overrides skip the member,
  and the write passes leave it alone. The factory lives in
  `advexp.settings_base` and both package roots re-export it, together
  with the attribute class, `SourcelessSetting`. On `advexp.settings` the
  member keeps the in-memory channels: an assignment sets it, the bulk
  updates set it like any other member, `to_dict` includes it, a save and
  a membership probe skip it, and a delete or a new load returns it to
  the declared value. The old spellings are gone:
  `non_storage_setting(...)` of `advexp.settings` and
  `constant_setting(...)` with `ConstantSetting` of `advexp.configuration`
  retire together with the no-op serializer pair; the unified member
  carries the `SOURCELESS` mark that both load pipelines already honor.
  The factory no longer takes `name=` and still refuses a declaration
  without `default=`.

### Added

- 2026-11-15 — The JSON, TOML, and YAML backends spell the dynamic file
  seat of their family: `json_dynamic_file(...)`,
  `toml_dynamic_file(...)`, and `yaml_dynamic_file(...)`. The seat names
  the file of the runtime-named entries of a class whose binding is held
  by another family — the class that `*_source(dynamic_file=...)` cannot
  serve, because the source builder would bind the class to the file
  storage of its own family. The seat is the same metadata entry as the
  `dynamic_file=` parameter: the plugin's `file_path` property reads and
  writes it, and a subclass inherits the nearest entry along the class
  chain. Declaring the parameter and the seat of one family together
  fails the `class` statement, as for every metadata name declared twice.
  The walkthrough samples of the three file backends seat the file of a
  foreign-bound class next to the per-class binding.
- 2026-11-15 — `SettingRef`, the type of the `setting_name` parameter of
  the per-member and the metadata methods, is re-exported from the root
  of `advexp.settings`. The name used to live only in
  `advexp.settings.plugin_api`, so typing a wrapper over those methods
  meant importing the plugin module. The docstrings and the guide pages
  now name the getter spelling `SettingRef` instead of describing it in
  prose.
- 2026-11-14 — Three reset methods restore the declared state of the
  metadata channel. `reset_setting_all_metadata` returns the
  metadata of one member to its `metadata=` declaration,
  `reset_all_settings_metadata` does the same for every member of the
  class, and `reset_class_all_metadata` returns the class-level storage to
  the state of the end of the `class` statement: entries added at runtime
  are dropped, and declared entries that were deleted or overridden at
  runtime come back. The restored state is the snapshot taken when the
  class was created, so changes to the declared mappings after the `class`
  statement never reach a reset. The service records (the file bindings,
  the source chain of a configuration class) are part of the declared
  state, and they return with the rest. Both facades carry the methods —
  fifteen per class now — and the plugin API stays as it was: dynamic
  collections have no declarations to restore.
- 2026-11-14 — The metadata API of the configuration package. A
  configuration class now carries the same metadata methods as a settings
  class: `set_setting_metadata`, `get_setting_metadata`,
  `get_setting_all_metadata`, `contains_setting_metadata`,
  `delete_setting_metadata`, `delete_setting_all_metadata`, and the six
  class-level twins. The methods delegate to the class's context and keep
  the read-only contract untouched: the contract covers the values and the
  sources, metadata is a separate channel, and no load ever touches it. The
  "Setting metadata" page of the documentation site describes both packages
  now.
- 2026-11-14 — `delete_setting_all_metadata` completes the metadata channel
  of `advexp.settings`: the member's whole metadata bucket goes with one
  call, declared entries and runtime ones together. The plugin API carried
  the form from the start; the context and the facade now have it too, so
  both packages expose the same complete set.
- 2026-11-12 — Shared declarations and the unified declaration vocabulary.
  A plain class marked with `SettingDeclarations` holds the member
  declarations that a settings class and a configuration class inherit
  together: the class statement pours the declarations of the base into the
  inheriting class, one deep-copied set per class, with the references
  between members (`ge=`, `when=`) following the copies. A reference from
  the body of the class onto a member of the base (`ge=Base.low`) turns
  onto the poured copy; overriding a referenced name refuses the class
  statement with a message that names the way out. The member factories are
  now family-wide: `setting`, `json_setting`, `toml_setting`, `yaml_setting`,
  `dotenv_setting`, and `environment_variable_setting` live in
  `advexp.settings_base`, both packages re-export them, and a member
  declared without `default=` is required in every context. The printed
  member classes of the packages (`Setting`, `ChainSetting`, and the
  per-family attribute classes) retired: the source links of the families
  carry the member class and the serializer of their package, and the
  serializer registry of the library keys its slots by distribution family,
  so one process holds both packages without a conflict. The full picture:
  the "Shared declarations" page of the documentation site. The dedicated sample
  `samples/both_packages/shared_declarations.py` walks the whole story:
  the spellings in the base, references that follow the poured copies, the
  required member, the winning body, the copied mutable defaults, the
  inert blueprint, and the one refused combination.
- 2026-11-12 — A member factory called without `default=` now declares a
  required member in the settings package too, as it always did in the
  configuration package. In 0.1.0 the family factories of the settings
  package served `None` for a member that no storage provided; that silent
  stand-in also swallowed misspelled storage names. A member that may be
  absent now says so explicitly with `default=None` — and a missing value of
  a required member aborts the load naming the member and every address
  that was checked. The plain rich factory `setting()` keeps its behavior:
  it was already required-by-default.

### Added

- 2026-11-10 — Extension plugins: the second plugin kind. An extension
  registers no setting attribute and no serializer — it only registers
  itself — and adds its own operations to one settings class, which keeps
  ecosystem-oriented functionality (a bridge to another library's models,
  and similar) out of the settings class API. The plugin contracts grew a
  common root `IPlugin` with the three members every plugin implements,
  and two disjoint kinds under it: `ISettingsPlugin` for storage backends
  and the new `IExtensionPlugin` for extensions, alongside the
  `ExtensionBasePlugin` base (context binding; a `binding` declaration on
  it fails the class statement). Both kinds register and are reached the
  same way: `register_settings_plugin(...)` at import,
  `get_plugin(...)` at the class, one instance per class. Exported from
  the `plugin_api` of both packages; the machinery ships in
  advexp.settings-base 0.2.0 and the dependency pins follow. Documented on
  the Extending page and the Plugin API reference; the `custom_backend.py`
  sample builds one; matrix rows U1–U3 cover both packages.
- 2026-11-07 — The documentation site is now measured through a Google
  Tag Manager container: every built page loads the container script in
  its head. The change reaches docs.advexp.net with the next publication
  of the public repository.
- 2026-11-07 — New Guide page "Migrating from pydantic-settings": a
  step-by-step walk of a working application onto Advexp.Configuration
  through the pydantic model source. The model becomes one link of the
  source chain, members move to their real sources one by one, and the move
  ends in either the full switch or a permanent hybrid. The closing
  sections show writing values back with Advexp.Settings on the same file
  and the bulk transfer of a whole model into a settings class. The page is
  reachable from the Guide navigation, the Configuration overview, and the
  switching page.
- 2026-11-06 — New configuration source `pydantic_source(model)`: a
  pydantic model read as one link of the source chain. The class form
  constructs the model on every load, so the model keeps resolving its own
  sources; the instance form freezes the values of one given instance at
  the declaration. The layer speaks member names, serves native types
  through the common conversion, and unwraps `SecretStr`/`SecretBytes`
  fields itself. A model that fails to construct is a broken source, like
  a file that cannot be parsed. The source rides the new `pydantic` extra:
  `pip install "advexp-configuration[pydantic]".

### Changed

- 2026-11-15 — Deleting a settings member through an instance is a designed
  refusal now, in both directions of the instance story. A `del` on a
  plain instance used to fail with a bare `AttributeError: __delete__`, an
  accident of the descriptor protocol with no message; it now raises
  `TypeError` that says the instance shares the class storage and names
  `delete_setting` as the tool that removes the stored value. On a snapshot
  of `to_object()` the same `del` now works: it removes the member's own
  value from the snapshot, the next read serves the declared default, and
  the class is untouched; a second delete raises `AttributeError`, because
  the snapshot holds no own value for the member anymore. Attributes that
  the class never declared as members keep plain Python semantics on
  instances, as they have on the class. The configuration package is not
  touched: its instances stay read-only with their own message.
- 2026-11-15 — A `del` on the `class_metadata` attribute of a settings
  class is now refused with a `TypeError` that names the runtime channel.
  The attribute is the declaration of the class body, while the
  copies that the readers see live in the class context: deleting it
  changed nothing that a metadata getter could notice, and a later direct
  read of the attribute failed with a bare `AttributeError`. Stored
  entries are removed through `delete_class_metadata` and
  `delete_class_all_metadata`, and the error message says so. The guard
  of the shared metaclass covers both packages and the `options=`
  spelling of the declaration alike.
- 2026-11-15 — `SourceLink.param` follows the dictionary rule too: reading a
  parameter the link does not carry raises `KeyError` without `default=`,
  and serves the fallback with it. The reads of the machinery spell the
  optional answer (`default=None`) explicitly, and the read-only dynamic
  twin mirrors the `NO_DEFAULT` spelling of the metadata getters it refuses.
- 2026-11-15 — A missing metadata entry follows the dictionary rule in
  `get_setting_metadata` and `get_class_metadata`, on both facades. Without
  `default=` the read raises `KeyError` that lists the metadata the member or
  the class carries and names the way out; with `default=`, the fallback is
  served. Before this change a missing entry silently answered `None`, which
  made a mistyped metadata name indistinguishable from an absent entry — the
  same silent stand-in the member defaults dropped earlier. A stored `None`
  remains a value that the read serves as it is, and `contains_*` still tells
  it from a missing entry. The writer's dynamic collection follows the same
  rule: `get_setting_metadata` of `DynamicSettingsBasePlugin` raises for a
  missing entry without `default=` too, mirroring its own `get_setting`.
  The serializer context follows the rule as well: its two metadata getters
  raise for a missing entry without `default=`, and the passes of the
  machinery spell the fallback they mean (`default=None`) explicitly.
- 2026-11-14 — The guard that rejects ``del`` on a settings member and the
  docstrings of ``delete_setting`` and ``delete_settings`` state the scope of
  a delete: it removes the stored value alone, while the member itself stays
  declared with its metadata, and a later load can bring the value back.
- 2026-11-14 — The "Changing metadata at runtime" intro says what the
  `set_*` methods actually do: they store an entry, overriding an existing
  key or adding a new one, while removal belongs to the `delete_*` methods.
- 2026-11-14 — The metadata page and the ``set_`` and ``get_setting_metadata``
  docstrings state the addressing rule of the channel: a member is addressed
  by its name in the class body, while the attribute's ``name=`` spelling,
  its aliases, and ``path=`` belong to the storages alone, and a metadata
  operation does not recognize them.
- 2026-11-14 — The Setting metadata page documents the independence of the
  metadata channel from the value passes. The new section "Metadata
  and the value passes" states the behavior of the shared base: a load
  rebuilds the values alone, a save writes the values and nothing else,
  delete and reset leave the stored metadata exactly as it was, and
  removing metadata is the job of the channel's own methods. One rule
  covers both packages.
- 2026-11-14 — `get_class_all_metadata` lists the open channel alone.
  The service records of the machinery — the keys of the reserved prefix and
  the per-class entries of registered families, the source chain and the file
  bindings among them — stay in the storage and remain addressable by their
  exact names, but the snapshot hides them, so a reader sees the keys that
  applications write. Reads, writes, and deletes by exact name are
  unchanged.
- 2026-11-14 — The reserved spellings of the machinery's own class metadata
  keys carry the `__ADVEXP_SETTINGS_BASE_` prefix now (before, they started
  with a bare double underscore: `__SourceChain`,
  `__JSONSettingsFile`, and the rest). One constant builds every reserved
  key from the prefix, and code addresses the keys through their own
  constants, so nothing in an application changes; a dump of the raw storage
  names the owner of every service record.
- 2026-11-14 — The API reference page of the configuration package now
  lists every public method of the `Configuration` class. Its member list
  carried the load pass alone and missed the snapshot methods and the
  plugin accessor: `to_dict`, `to_object`, and `get_plugin`.
- 2026-11-05 — The v0.1.0 tag now marks the release snapshot in this
  repository, the state whose code is published on PyPI as 0.1.0.
- 2026-11-05 — The Switching page received a proofread pass: clearer
  wording throughout (the priority of a source, the reason the naming
  rules are shared, "extra" instead of "foreign" fields), reworded code
  comments, and a plainer title of the pydantic-models section; no code,
  identifiers, or links changed.
- 2026-11-05 — On the Switching page, the read-write example now shows
  `save_settings()` commented out, as the alternative to the
  `save_setting` call above it.
- 2026-11-05 — On the Switching page, the dynaconf example now names the
  file of the current environment with a concrete example instead of the
  former "settings-dev.toml and its siblings" wording.
- 2026-11-05 — On the Switching page, the pydantic-settings example now
  says plainly that the bounds of `Field` become declaration parameters
  under the same names, both in the code comment and in the mapping list.
- 2026-11-05 — The Advexp.Configuration getting-started page now lists the
  value constraints among the parameters of the family factories
  (`json_setting`, `toml_setting`, and the others), matching what the
  factories accept.
- 2026-11-05 — The Switching page of the documentation site now shows the
  migration examples from pydantic-settings, python-decouple, and dynaconf
  on Advexp.Configuration: the layered reading of all three libraries maps
  to the source chain, and a file per environment covers dynaconf's
  environments. Advexp.Settings, with writing values back, moved to one
  section of its own at the end of the page; the pydantic-models section
  follows the configuration side of the exchange.
- 2026-11-05 — The public repository carries its own REUSE.toml: the
  overlay now ships one, with the public paths (`assets/` for the
  badges, no `scripts/` or `texts/`), and sync_public.sh no longer
  filters the private annotations — the overlay file replaces them
  wholesale. The filtered variant left the badge assets uncovered: the
  private path `scripts/public-overlay/assets/*` never matched their
  place in the public tree, which surfaced the first time `reuse` was
  actually on the PATH during a sync.
- 2026-11-05 — The repository READMEs carry the same quick example as
  the documentation site: `session_ttl` is declared through the
  `setting` factory, and the example shows the save pass. Both hand
  copies — the root README and the public overlay variant — had kept
  the older spelling while the site pages moved on.

## [0.1.0] - 2026-11-05

### Added

- 2026-11-05 — The first public release of the family: the
  advexp-settings, advexp-settings-base and advexp-configuration
  distributions, version 0.1.0, are published on PyPI.
