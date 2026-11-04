# The error matrix, by hand

This folder is the hand-readable twin of
[`test_settings_error_matrix.py`](../test_settings_error_matrix.py): the
same failure scenarios against every bundled backend, spelled out as plain
tests for reading and live debugging. The original suite stays the source
of truth — it holds the parametrized table and the coverage guard. Nothing
here replaces it; when the library changes, the original changes and this
twin follows by hand.

There is no parametrization and no dynamic class construction on purpose.
Every test reads the same way:

1. the settings class stands declared once in the category's
   `*_classes.py` module, beside the storage path it reads;
2. the test dumps the source file into `storage/` before the run (the env
   tests set variables instead);
3. the test calls the method under test;
4. the raised or reported error is compared with an expected string
   written out in full, right in the test.

## Files by category

| Category | Classes | Tests |
| --- | --- | --- |
| The healthy baseline | `settings_healthy_classes.py` | `test_settings_healthy_load.py` |
| Missing values | `missing_values_classes.py` | `test_settings_missing_values.py` |
| Conversion failures | `conversion_classes.py` | `test_settings_conversion_failures.py` |
| A broken serializer | `serializer_classes.py` | `test_settings_broken_serializer.py` |
| A broken storage | `broken_storage_classes.py` | `test_settings_broken_storage.py` |
| Several sources on one class | `multiple_sources_classes.py` | `test_settings_multiple_sources.py` |
| Dynamic collections | `dynamic_collections_classes.py` | `test_settings_dynamic_collections.py` |

`settings_storage_paths.py` points every class at its file inside `storage/`. The
dumped files stay on disk after the run — open `storage/` to see the exact
document each test fed the library. The folder holds generated output
only; git ignores its contents.

## The member shape

The failure categories share one class shape, the matrix of the
declaration states:

- `answer` — `REQUIRED`: no default; the scenarios usually break this one,
- `plain` — `NO_DEFAULT`: a bare member; serves `None` when nothing is stored,
- `known` — a declared default (7),
- `control` — `REQUIRED` and always stored, so a broken run still shows a
  healthy load beside the failures.

## One class per test

Every settings class in this suite belongs to exactly one test. A settings
class keeps the values an earlier load gave it — a failed load does not
clear them — so sharing one class between tests would leak values from one
test into the next. One class per test also makes every test independent:
any single test runs alone, in any order.

## Running

The whole folder:

```bash
pytest tests/settings/error_matrix_manual
```

One category, one test:

```bash
pytest tests/settings/error_matrix_manual/test_settings_missing_values.py
pytest "tests/settings/error_matrix_manual/test_settings_missing_values.py::test_missing_required_reports_through_the_aggregate_json"
```

To step through a scenario in a debugger, put a breakpoint in the test (or
in the library code it reaches) and run the single test from your IDE. The
dumped file in `storage/` and the variables set by `monkeypatch` are the
whole scenario setup — nothing else hides anywhere.
