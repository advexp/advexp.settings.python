# Advexp.Settings-Base for Python

The shared machinery of the [Advexp.Settings](https://advexp.net/advexp.settings/)
family: the settings context, the value conversion, the attribute, plugin and
serializer machinery. `advexp.settings` builds its public API on top of this
package, `advexp.configuration` reuses it for read-only configuration.

This is a foundation distribution of the family, not an application entry
point: applications install `advexp-settings` and import from
`advexp.settings`.

> **Status:** the API is under development and will change until the first
> stable release of the family.

## Installation

The package is installed together with the editions that depend on it; to
install it explicitly:

```bash
pip install advexp-settings-base
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
