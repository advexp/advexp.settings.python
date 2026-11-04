# The validation matrix, by hand

This folder is the hand-readable companion of the validation machinery of
`advexp.settings` — the sibling of the error-matrix twins
(`tests/settings/error_matrix_manual/`,
`tests/configuration/error_matrix_manual/`), built the same way: plain
tests for reading and live debugging. The parametrized suites
(`tests/settings/test_cross_validation.py`,
`tests/settings/test_default_validation.py`) stay the source of truth;
this folder spells the user-facing scenarios out.

There is no parametrization and no dynamic class construction on purpose.
Every test reads the same way:

1. the settings class stands declared once in the category's
   `settings_validation_*_classes.py` module, beside the storage path it
   reads;
2. the test dumps the source file into `storage/` before the run (the
   env and memory scenarios set variables or nothing instead);
3. the test calls the method under test — a load, an assignment, an
   update, a save, the manual validation;
4. the raised or reported error is compared with an expected string
   written out in full, right in the test.

## Files by category

| Category | Classes | Tests |
| --- | --- | --- |
| Comparison bounds (`gt/ge/lt/le/eq/ne`) | `settings_validation_comparison_classes.py` | `test_settings_validation_comparison.py` |
| Length bounds (`min_length/max_length`) | `settings_validation_length_classes.py` | `test_settings_validation_length.py` |
| `regex=` | `settings_validation_regex_classes.py` | `test_settings_validation_regex.py` |
| `validator=` | `settings_validation_validator_classes.py` | `test_settings_validation_validator.py` |
| `when=` (conditional constraints) | `settings_validation_when_classes.py` | `test_settings_validation_when.py` |
| The `class` statement's own checks | declared inside the tests | `test_settings_validation_declaration.py` |
| Member-reference rules (`ge=min_port`) | `settings_validation_member_rules_classes.py` | `test_settings_validation_member_rules.py` |
| The `__validate__` hook | `settings_validation_hook_classes.py` | `test_settings_validation_hook.py` |
| The boundaries (assign, update, save, validate) | `settings_validation_boundaries_classes.py` | `test_settings_validation_boundaries.py` |

`settings_validation_storage_paths.py` points every file-backed class at
its file inside `storage/`. The dumped files stay on disk after the run.
The folder holds generated output only; git ignores its contents.

The classes of the declaration category exist to fail their own creation,
so they are declared inside the tests — a module-level `class` statement
that raises would break the import of the whole suite. One scenario is
absent by construction: a cycle of member references cannot be written
with plain declarations (a bound must exist before the attribute
referencing it); the parametrized suites probe the cycle detector through
the library's internals.

## Where the constraints apply

A single member's constraints are declared as keyword parameters of its
setting (`gt=`, `regex=`, `validator=`, `when=` …). Two forms bind
several members: a comparison bound may reference a sibling
(`ge=min_port`), and the `__validate__` class hook returns a dict of
member name to problem. The check points, each with its own policy:

- the **class statement** — the declared defaults and the declaration
  itself are checked; a failure is a `TypeError` (or `ValueError` for a
  bad pattern) raised by the `class` line;
- a **load** — soft: a required member's violation aborts through the
  aggregate, an optional one falls back to its default with a logged
  warning, and a violated cross-member rule resets every member taking
  part in it; a violation no reset can settle aborts the load — a
  completed load is either consistent or did not complete;
- an **assignment** — strict for the member's own constraints; the
  cross-member checks never run here (a rule may be broken between two
  related assignments);
- an **update** (`update_from_dict`) and a **save** — strict: one error
  collects every finding, and nothing is applied or written;
- **`validate_settings()`** — the strict manual check; reports the same
  findings and changes nothing.

## One class per test

Every settings class in this suite belongs to exactly one test: a class
keeps the values an earlier load or assignment gave it, so sharing one
between tests would leak values from one test into the next. Any single
test runs alone, in any order.

## Running

The whole folder:

```bash
pytest tests/settings/validation_manual
```

One category, one test:

```bash
pytest tests/settings/validation_manual/test_settings_validation_hook.py
pytest "tests/settings/validation_manual/test_settings_validation_hook.py::test_a_hook_finding_the_reset_cannot_settle_aborts_the_load"
```

To step through a scenario in a debugger, put a breakpoint in the test
(or in the library code it reaches) and run the single test from your
IDE. The dumped file in `storage/` — or the variables a test sets — is
the whole scenario setup; nothing else hides anywhere.
