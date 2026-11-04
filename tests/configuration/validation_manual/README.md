# The configuration validation matrix, by hand

This folder is the hand-readable companion of the validation machinery of
`advexp.configuration` — the sibling of
`tests/settings/validation_manual/`, built the same way: plain tests for
reading and live debugging. The parametrized suites
(`tests/configuration/test_configuration.py` and the settings-package
suites over the shared machinery) stay the source of truth; this folder
spells the user-facing scenarios out.

There is no parametrization and no dynamic class construction on purpose.
Every test reads the same way:

1. the configuration class stands declared once in the category's
   `configuration_validation_*_classes.py` module, beside the storage
   path it reads;
2. the test dumps the source file into `storage/` before the run (the
   env and memory scenarios set variables or nothing instead);
3. the test calls the method under test — for this read-only package the
   one runtime pass is `load_configuration()`;
4. the raised or reported error is compared with an expected string
   written out in full, right in the test.

## Files by category

| Category | Classes | Tests |
| --- | --- | --- |
| Comparison bounds (`gt/ge/lt/le/eq/ne`) | `configuration_validation_comparison_classes.py` | `test_configuration_validation_comparison.py` |
| Length bounds (`min_length/max_length`) | `configuration_validation_length_classes.py` | `test_configuration_validation_length.py` |
| `regex=` | `configuration_validation_regex_classes.py` | `test_configuration_validation_regex.py` |
| `validator=` | `configuration_validation_validator_classes.py` | `test_configuration_validation_validator.py` |
| `when=` (conditional constraints) | `configuration_validation_when_classes.py` | `test_configuration_validation_when.py` |
| The `class` statement's own checks | declared inside the tests | `test_configuration_validation_declaration.py` |
| Member-reference rules (`ge=min_port`) | `configuration_validation_member_rules_classes.py` | `test_configuration_validation_member_rules.py` |
| The `__validate__` hook | `configuration_validation_hook_classes.py` | `test_configuration_validation_hook.py` |

`configuration_validation_storage_paths.py` points every file-backed class
at its file inside `storage/`. The dumped files stay on disk after the
run. The folder holds generated output only; git ignores its contents.

The classes of the declaration category exist to fail their own creation,
so they are declared inside the tests — a module-level `class` statement
that raises would break the import of the whole suite. One scenario is
absent by construction: a cycle of member references cannot be written
with plain declarations (a bound must exist before the attribute
referencing it); the parametrized suites probe the cycle detector through
the library's internals.

## What is different from the settings twin

The machinery is the family's shared one; the differences are the
package's own vocabulary and its read-only seat:

- the messages say `member '...' of '...'` and log under the
  `advexp.configuration` channel; the method is `load_configuration()`;
- a member declared bare, without `default=`, is REQUIRED (this
  package's own default) — the flip against the settings package, where
  a bare member serves `None`;
- there is no boundaries category: the package has no assignment, no
  update, no save and no manual validation — every write path meets the
  read-only contract instead, pinned in
  `tests/configuration/error_matrix_manual/`. The constraints apply at
  the two points that remain: the `class` statement (against the
  declared defaults) and the load pass (soft — fatal for a required
  member, a fallback with a logged warning for an optional one, and a
  violated cross-member rule resets every member taking part in it; a
  violation no reset can settle aborts the load — a completed load is
  either consistent or did not complete).

## One class per test

Every configuration class in this suite belongs to exactly one test: a
class keeps the values an earlier load gave it, so sharing one between
tests would leak values from one test into the next. Any single test
runs alone, in any order.

## Running

The whole folder:

```bash
pytest tests/configuration/validation_manual
```

One category, one test:

```bash
pytest tests/configuration/validation_manual/test_configuration_validation_hook.py
pytest "tests/configuration/validation_manual/test_configuration_validation_hook.py::test_a_hook_finding_the_reset_cannot_settle_aborts_the_load"
```

To step through a scenario in a debugger, put a breakpoint in the test
(or in the library code it reaches) and run the single test from your
IDE. The dumped file in `storage/` — or the variables a test sets — is
the whole scenario setup; nothing else hides anywhere.
