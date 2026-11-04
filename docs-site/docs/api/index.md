---
# This page is its nav section's landing: the header's breadcrumb shows
# the section's name for it (docs-site/overrides/partials/header.html).
section_landing: true
---

# API reference

The reference is generated from the docstrings in the source code. It is
the code's own documentation, and it stays accurate because it lives right
next to the code. The reference has three parts:

- [Settings API](settings.md) — the application API of `advexp.settings`:
  the `Settings` class and its operations, the library configuration, the
  attribute parameters, the source builders with their file binders, the
  errors and sentinels, and the secret wrappers.
- [Configuration API](configuration.md) — the application API of
  `advexp.configuration`: the read-only `Configuration` class, its source
  chains and the links they are built from, the attribute parameters, the
  errors and sentinels, and the same secret wrappers.
- [Plugin API](plugin-api.md) — the contracts for backend and source
  authors: the vocabulary shared by the extension points of both packages,
  together with the layered side that the configuration package adds.

The bundled backends are documented on their own pages:
[Backends](../backends.md), [Configuration](../configuration.md) and
[Dynamic settings](../dynamic-settings.md). For these backends, the
docstrings of their packages serve as the reference.
