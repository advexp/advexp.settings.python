"""The boundaries: where a value meets the declared constraints.

A load falls back leniently (see the categories above). Every other boundary
is strict, each in its own way:

- An assignment rejects the value that it is handed.
- An update collects every finding of the merged state into one error and
  applies nothing.
- A save of a class in violation writes nothing. Here, the violation is a
  member rule that an assignment has broken, which is the one route that the
  public API leaves open.
- The manual ``validate_settings()`` reports the same findings and changes
  nothing. On a consistent class, it passes quietly.
"""

import pytest
from settings_validation_boundaries_classes import (
    SAVE_STRICT_JSON_FILE,
    AssignmentPortSettings,
    SaveStrictSettings,
    UpdateRejectSettings,
    ValidateListSettings,
    ValidateQuietSettings,
)
from settings_validation_storage_paths import prepare_storage_dir

from advexp.settings import SettingValidationError


def test_assignment_rejects_a_violating_value():
    """Assigning past the bound: the assignment refuses, the value
    stands."""
    with pytest.raises(SettingValidationError) as info:
        AssignmentPortSettings.port = 70000

    assert str(info.value) == (
        "invalid value for setting 'port' of AssignmentPortSettings: "
        "value 70000 must be less than or equal to 65535"
    )
    assert AssignmentPortSettings.port == 8080


def test_update_collects_every_findings_and_applies_nothing():
    """Two bad values in one update: one error lists both findings, and
    neither value moved."""
    with pytest.raises(SettingValidationError) as info:
        UpdateRejectSettings.update_from_dict({"port": 70000, "tag": "x"})

    assert str(info.value) == (
        "invalid settings in UpdateRejectSettings:\n"
        "  - port: value 70000 must be less than or equal to 65535\n"
        "  - tag: length 1 must be at least 2"
    )
    assert info.value.problems == {
        "port": ["value 70000 must be less than or equal to 65535"],
        "tag": ["length 1 must be at least 2"],
    }
    assert UpdateRejectSettings.port == 8080
    assert UpdateRejectSettings.tag == "xx"


def test_save_of_a_class_in_violation_writes_nothing():
    """The pair loads in order, one assignment breaks the rule, and the
    save refuses: the file keeps exactly what the load read."""
    prepare_storage_dir()
    SAVE_STRICT_JSON_FILE.write_text(
        '{"lo": 2000, "hi": 9000}',
        encoding="utf-8",
    )
    SaveStrictSettings.load_settings()
    SaveStrictSettings.lo = 9500  # its own constraints pass; the rule with hi breaks

    with pytest.raises(SettingValidationError) as info:
        SaveStrictSettings.save_settings()

    assert str(info.value) == (
        "invalid settings in SaveStrictSettings:\n"
        "  - hi: value 9000 must be greater than or equal to the value of 'lo' (9500)"
    )
    assert SAVE_STRICT_JSON_FILE.read_text(encoding="utf-8") == '{"lo": 2000, "hi": 9000}'


def test_validate_settings_reports_and_changes_nothing():
    """The strict manual check over a broken rule: the same report, the
    values exactly as they were."""
    ValidateListSettings.high = 0  # the ge=low rule is not an assignment's business

    with pytest.raises(SettingValidationError) as info:
        ValidateListSettings.validate_settings()

    assert str(info.value) == (
        "invalid settings in ValidateListSettings:\n"
        "  - high: value 0 must be greater than or equal to the value of 'low' (1)"
    )
    assert info.value.problems == {
        "high": ["value 0 must be greater than or equal to the value of 'low' (1)"]
    }
    assert ValidateListSettings.high == 0


def test_validate_settings_passes_quietly_on_a_consistent_class():
    """A consistent class with a hook: the check returns nothing, and the
    values stand."""
    assert ValidateQuietSettings.validate_settings() is None
    assert ValidateQuietSettings.value == 5
