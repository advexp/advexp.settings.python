# The configuration error matrix, by hand

This folder is the hand-readable twin of
[`test_configuration_error_matrix.py`](../test_configuration_error_matrix.py):
the same failure scenarios against every bundled backend, spelled out as
plain tests for reading and live debugging. The original suite stays the
source of truth — it holds the parametrized table and the coverage guard.
Nothing here replaces it; when the library changes, the original changes
and this twin follows by hand. The settings package has its own twin at
`tests/settings/error_matrix_manual/`, built the same way.

There is no parametrization and no dynamic class construction on purpose.
Every test reads the same way:

1. the configuration class stands declared once in the category's
   `configuration_*_classes.py` module, beside the storage path it reads;
2. the test dumps the source file into `storage/` before the run (the env
   tests set variables instead);
3. the test calls the method under test;
4. the raised or reported error is compared with an expected string
   written out in full, right in the test.

## Files by category

| Category | Classes | Tests |
| --- | --- | --- |
| The healthy baseline | `configuration_healthy_classes.py` | `test_configuration_healthy_load.py` |
| Missing values | `configuration_missing_values_classes.py` | `test_configuration_missing_values.py` |
| Conversion failures | `configuration_conversion_classes.py` | `test_configuration_conversion_failures.py` |
| A broken serializer | `configuration_serializer_classes.py` | `test_configuration_broken_serializer.py` |
| A broken storage | `configuration_broken_storage_classes.py` | `test_configuration_broken_storage.py` |
| Several sources on one class | `configuration_multiple_sources_classes.py` | `test_configuration_multiple_sources.py` |
| The read-only contract | `configuration_read_only_classes.py` | `test_configuration_read_only_contract.py` |

`configuration_storage_paths.py` points every class at its file inside
`storage/`. The dumped files stay on disk after the run — open `storage/`
to see the exact document each test fed the library. The folder holds
generated output only; git ignores its contents.

The module names carry the `configuration_` prefix (and the settings twin's
carry `settings_`) because pytest imports test modules by their bare file
name: two plain `storage_paths.py` in two folders would collide in one
run, the same way the repo's own suites are named `test_settings_*` and
`test_configuration_*`.

## The member shape

The failure categories share one class shape, the matrix of the
declaration states — and here sits this package's flip against the
settings package: a member declared bare, without `default=`, is REQUIRED
(the package's own default), and `NO_DEFAULT` is the opt-out:

- `answer` — declared bare: REQUIRED, no default; the scenarios usually
  break this one,
- `plain` — `NO_DEFAULT`: the opt-out; serves `None` when nothing is
  stored,
- `known` — a declared default (7),
- `control` — the explicit `REQUIRED` spelling, always stored, so a broken
  run still shows a healthy load beside the failures.

The package is read-only: there is no save pass and no dynamic collection
here, and writing to a member meets the read-only contract — its own
category at the end of the table.

## One class per test

Every configuration class in this suite belongs to exactly one test. A
configuration class keeps the values an earlier load gave it — a failed
load does not clear them — so sharing one class between tests would leak
values from one test into the next. One class per test also makes every
test independent: any single test runs alone, in any order.

## Running

The whole folder:

```bash
pytest tests/configuration/error_matrix_manual
```

One category, one test:

```bash
pytest tests/configuration/error_matrix_manual/test_configuration_missing_values.py
pytest "tests/configuration/error_matrix_manual/test_configuration_missing_values.py::test_missing_required_reports_through_the_aggregate_json"
```

To step through a scenario in a debugger, put a breakpoint in the test (or
in the library code it reaches) and run the single test from your IDE. The
dumped file in `storage/` and the variables set by `monkeypatch` are the
whole scenario setup — nothing else hides anywhere.
