"""Length constraints: ``min_length`` and ``max_length``.

The bounds check ``len(value)``, and the messages speak in lengths. A value
that has no length at all (an ``int`` under a length bound) is a violation
with its own wording, not a crash.
"""

from settings_validation_length_classes import (
    LENGTH_BOUNDS_JSON_FILE,
    NO_LENGTH_JSON_FILE,
    LengthBoundsSettings,
    NoLengthNumberSettings,
)
from settings_validation_storage_paths import prepare_storage_dir


def test_length_bounds_on_load():
    """A too-short member and a too-long member, one entry each."""
    prepare_storage_dir()
    LENGTH_BOUNDS_JSON_FILE.write_text(
        '{"short": "ab", "long": "abcdef"}',
        encoding="utf-8",
    )

    report = LengthBoundsSettings.load_settings()

    assert [str(entry) for entry in report] == [
        f"setting 'short' (key 'short' in the JSON file {LENGTH_BOUNDS_JSON_FILE}) "
        "of 'LengthBoundsSettings' fell back to its default: the value violates its "
        "constraints (length 2 must be at least 3)",
        f"setting 'long' (key 'long' in the JSON file {LENGTH_BOUNDS_JSON_FILE}) "
        "of 'LengthBoundsSettings' fell back to its default: the value violates its "
        "constraints (length 6 must be at most 5)",
    ]
    assert LengthBoundsSettings.short is None
    assert LengthBoundsSettings.long is None


def test_value_without_length_is_a_violation_not_a_crash():
    """An int value where the constraint asks for a length."""
    prepare_storage_dir()
    NO_LENGTH_JSON_FILE.write_text('{"number": 42}', encoding="utf-8")

    report = NoLengthNumberSettings.load_settings()

    assert [str(entry) for entry in report] == [
        f"setting 'number' (key 'number' in the JSON file {NO_LENGTH_JSON_FILE}) "
        "of 'NoLengthNumberSettings' fell back to its default: the value violates its "
        "constraints (value 42 has no length to check against min_length)"
    ]
    assert NoLengthNumberSettings.number is None
