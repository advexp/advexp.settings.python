# Samples

Runnable examples of the two packages. Each sample is a standalone
program: it writes its demo files next to itself and prints what happens
at every step. A sample's docstring names the `pip install` command it
needs, including the extras.

Run a sample from the repository root:

```bash
pip install "advexp-settings[dotenv]"
python samples/settings/settings_api.py
```

- `samples/settings/` — the read-write package: every bundled backend,
  dynamic collections, metadata, validation, and two samples built on the
  plugin-author API (`settings_api.py` and `custom_backend.py`).
- `samples/configuration/` — the read-only package: the bundled sources,
  the source chain, validation, and its own plugin-author sample
  (`custom_source.py`).
- `samples/both_packages/` — both packages in one application, and a
  dynamic collection that one package writes and the other reads back.

## Running against the working tree

The commands above install the published packages. To run a sample
against the working tree of this repository instead, install the family
in the editable form: the base package first, then the two packages that
depend on it.

```bash
pip install -e packages/advexp-settings-base
pip install -e packages/advexp-settings
pip install -e packages/advexp-configuration
```

A sample then runs the same way. Add the extras you need, for example
`pip install -e "packages/advexp-settings[yaml]"`.
