"""Length constraints: ``min_length`` and ``max_length``.

The bounds check ``len(value)``, and the messages speak in lengths. A value
that has no length at all (an ``int`` under a length bound) is a violation
with its own wording, not a crash.
"""

from configuration_validation_length_classes import (
    LENGTH_BOUNDS_JSON_FILE,
    NO_LENGTH_JSON_FILE,
    LengthBoundsConfiguration,
    NoLengthNumberConfiguration,
)
from configuration_validation_storage_paths import prepare_storage_dir


def test_length_bounds_on_load():
    """A too-short member and a too-long member, one entry each."""
    prepare_storage_dir()
    LENGTH_BOUNDS_JSON_FILE.write_text(
        '{"short": "ab", "long": "abcdef"}',
        encoding="utf-8",
    )

    report = LengthBoundsConfiguration.load_configuration()

    assert [str(entry) for entry in report] == [
        f"member 'short' (key 'short' in the JSON file {LENGTH_BOUNDS_JSON_FILE}) "
        "of 'LengthBoundsConfiguration' fell back to its default: the value violates "
        "its constraints (length 2 must be at least 3)",
        f"member 'long' (key 'long' in the JSON file {LENGTH_BOUNDS_JSON_FILE}) "
        "of 'LengthBoundsConfiguration' fell back to its default: the value violates "
        "its constraints (length 6 must be at most 5)",
    ]
    assert LengthBoundsConfiguration.short is None
    assert LengthBoundsConfiguration.long is None


def test_value_without_length_is_a_violation_not_a_crash():
    """An int value where the constraint asks for a length."""
    prepare_storage_dir()
    NO_LENGTH_JSON_FILE.write_text('{"number": 42}', encoding="utf-8")

    report = NoLengthNumberConfiguration.load_configuration()

    assert [str(entry) for entry in report] == [
        f"member 'number' (key 'number' in the JSON file {NO_LENGTH_JSON_FILE}) "
        "of 'NoLengthNumberConfiguration' fell back to its default: the value violates "
        "its constraints (value 42 has no length to check against min_length)"
    ]
    assert NoLengthNumberConfiguration.number is None
