"""Comparison constraints: gt, ge, lt, le, eq, ne.

There is one member for each parameter, and one storage run violates all six
of them. The test pins each phrase of each parameter in one report.

The other tests cover the following cases:

- A required member shows the aborting channel.
- A string value against a numeric bound shows the case that cannot be
  compared (a violation, not a crash).
- The environment backend shows that the constraints live on the member and
  not on the storage.
- A satisfied bound closes the category with the passing side.
"""

import logging

import pytest
from settings_validation_comparison_classes import (
    CLEAN_JSON_FILE,
    INCOMPARABLE_JSON_FILE,
    PORT_REQUIRED_JSON_FILE,
    SIX_COMPARISONS_JSON_FILE,
    CleanComparisonSettings,
    EnvPortSettings,
    IncomparableLabelSettings,
    PortRequiredSettings,
    SixComparisonsSettings,
)
from settings_validation_storage_paths import prepare_storage_dir

from advexp.settings import AggregateLoadError, ConstraintViolationError


def test_six_comparison_phrases_on_load(caplog):
    """One report entry per violated comparison, each phrase exact."""
    prepare_storage_dir()
    SIX_COMPARISONS_JSON_FILE.write_text(
        '{"gt_member": 5, "ge_member": 5, "lt_member": 15, "le_member": 15,'
        ' "eq_member": 5, "ne_member": 10}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = SixComparisonsSettings.load_settings()

    assert [str(entry) for entry in report] == [
        f"setting 'gt_member' (key 'gt_member' in the JSON file {SIX_COMPARISONS_JSON_FILE}) "
        "of 'SixComparisonsSettings' fell back to its default: the value violates its "
        "constraints (value 5 must be greater than 10)",
        f"setting 'ge_member' (key 'ge_member' in the JSON file {SIX_COMPARISONS_JSON_FILE}) "
        "of 'SixComparisonsSettings' fell back to its default: the value violates its "
        "constraints (value 5 must be greater than or equal to 10)",
        f"setting 'lt_member' (key 'lt_member' in the JSON file {SIX_COMPARISONS_JSON_FILE}) "
        "of 'SixComparisonsSettings' fell back to its default: the value violates its "
        "constraints (value 15 must be less than 10)",
        f"setting 'le_member' (key 'le_member' in the JSON file {SIX_COMPARISONS_JSON_FILE}) "
        "of 'SixComparisonsSettings' fell back to its default: the value violates its "
        "constraints (value 15 must be less than or equal to 10)",
        f"setting 'eq_member' (key 'eq_member' in the JSON file {SIX_COMPARISONS_JSON_FILE}) "
        "of 'SixComparisonsSettings' fell back to its default: the value violates its "
        "constraints (value 5 must be equal to 10)",
        f"setting 'ne_member' (key 'ne_member' in the JSON file {SIX_COMPARISONS_JSON_FILE}) "
        "of 'SixComparisonsSettings' fell back to its default: the value violates its "
        "constraints (value 10 must not be equal to 10)",
    ]
    # every fallback is warned about, each address named
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"setting 'gt_member' (key 'gt_member' in the JSON file {SIX_COMPARISONS_JSON_FILE}) "
        "of 'SixComparisonsSettings': the value violates its constraints "
        "(value 5 must be greater than 10); using the default value"
    ) in warning_messages
    # every member stands at its default
    assert SixComparisonsSettings.gt_member is None
    assert SixComparisonsSettings.eq_member == 10


def test_required_member_violation_aborts_the_load():
    """A required member whose value breaks the bound: one fatal entry."""
    prepare_storage_dir()
    PORT_REQUIRED_JSON_FILE.write_text('{"port": 70000}', encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        PortRequiredSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConstraintViolationError)
    assert str(error) == (
        f"setting 'port' (key 'port' in the JSON file {PORT_REQUIRED_JSON_FILE}) "
        "of 'PortRequiredSettings' is required: the value violates its constraints "
        "(value 70000 must be less than or equal to 65535)"
    )


def test_incomparable_value_is_a_violation_not_a_crash():
    """A string value against a numeric bound: no comparison can run."""
    prepare_storage_dir()
    INCOMPARABLE_JSON_FILE.write_text('{"label": "abc"}', encoding="utf-8")

    report = IncomparableLabelSettings.load_settings()

    assert [str(entry) for entry in report] == [
        f"setting 'label' (key 'label' in the JSON file {INCOMPARABLE_JSON_FILE}) "
        "of 'IncomparableLabelSettings' fell back to its default: the value violates "
        "its constraints (value 'abc' is not comparable with the gt bound 10)"
    ]
    assert IncomparableLabelSettings.label is None


def test_env_var_backend_carries_the_same_bound(monkeypatch):
    """The constraint is declared on the member: the environment backend
    reports through its own address."""
    monkeypatch.delenv("VM_PORT", raising=False)
    monkeypatch.setenv("VM_PORT", "70000")

    report = EnvPortSettings.load_settings()

    assert [str(entry) for entry in report] == [
        "setting 'port' (environment variable 'VM_PORT') of 'EnvPortSettings' "
        "fell back to its default: the value violates its constraints "
        "(value 70000 must be less than or equal to 65535)"
    ]
    assert EnvPortSettings.port == 8080


def test_satisfied_bound_loads_cleanly():
    """The passing side: a value above the gt bound loads without a word."""
    prepare_storage_dir()
    CLEAN_JSON_FILE.write_text('{"pass_check": 20}', encoding="utf-8")

    report = CleanComparisonSettings.load_settings()

    assert report == ()
    assert CleanComparisonSettings.pass_check == 20
