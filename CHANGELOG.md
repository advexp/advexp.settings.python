# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

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
