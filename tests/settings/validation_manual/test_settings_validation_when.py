"""The conditional constraint: ``when=``.

``when=`` references a sibling member: while the referenced member is
falsy, none of the constraints of the member apply. The two load tests
differ only in the stored value of the condition.

The declaration test pins the guard itself: ``when=`` accepts only a member
reference. A literal is refused at the ``class`` statement, because a
constant condition is either always on (then write the constraints without
``when=``) or always off (then delete the member).
"""

import pytest
from settings_validation_storage_paths import prepare_storage_dir
from settings_validation_when_classes import (
    WHEN_OFF_JSON_FILE,
    WHEN_ON_JSON_FILE,
    WhenConditionOffSettings,
    WhenConditionOnSettings,
)

from advexp.settings import Settings, non_storage_setting


def test_condition_off_ignores_the_constraints():
    """The condition member is false: 99 stands, no report, no warning."""
    prepare_storage_dir()
    WHEN_OFF_JSON_FILE.write_text(
        '{"enabled": false, "retries": 99}',
        encoding="utf-8",
    )

    report = WhenConditionOffSettings.load_settings()

    assert report == ()
    assert WhenConditionOffSettings.enabled is False
    assert WhenConditionOffSettings.retries == 99


def test_condition_on_applies_the_constraints():
    """The condition member is true: the bound rejects 99, the default
    stands."""
    prepare_storage_dir()
    WHEN_ON_JSON_FILE.write_text(
        '{"enabled": true, "retries": 99}',
        encoding="utf-8",
    )

    report = WhenConditionOnSettings.load_settings()

    assert [str(entry) for entry in report] == [
        f"setting 'retries' (key 'retries' in the JSON file {WHEN_ON_JSON_FILE}) "
        "of 'WhenConditionOnSettings' fell back to its default: the value violates "
        "its constraints (value 99 must be less than or equal to 5)"
    ]
    assert WhenConditionOnSettings.retries == 3


def test_when_literal_fails_the_class_statement():
    """``when=`` takes a member reference only; a literal is refused."""
    with pytest.raises(TypeError) as info:

        class LiteralConditionSettings(Settings):
            flag: bool = non_storage_setting(default=False)
            tag: str = non_storage_setting(default="xx", min_length=2, when=True)

    assert str(info.value) == (
        "when must reference a member of the same class, got True; "
        "use the __validate__ hook for compound conditions"
    )
