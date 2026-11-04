"""The regex constraint.

``regex=`` runs an unanchored ``re.search``; a miss is a violation naming
the pattern, and a non-string value gets its own wording.
"""

from configuration_validation_regex_classes import (
    NON_STRING_JSON_FILE,
    REGEX_CODE_JSON_FILE,
    NonStringDigitConfiguration,
    RegexCodeConfiguration,
)
from configuration_validation_storage_paths import prepare_storage_dir


def test_regex_mismatch_on_load():
    """The stored value misses the pattern."""
    prepare_storage_dir()
    REGEX_CODE_JSON_FILE.write_text('{"code": "ABC"}', encoding="utf-8")

    report = RegexCodeConfiguration.load_configuration()

    assert [str(entry) for entry in report] == [
        f"member 'code' (key 'code' in the JSON file {REGEX_CODE_JSON_FILE}) "
        "of 'RegexCodeConfiguration' fell back to its default: the value violates "
        "its constraints (value 'ABC' does not match regex '^[a-z]+$')"
    ]
    assert RegexCodeConfiguration.code is None


def test_non_string_value_is_a_violation_not_a_match_attempt():
    """An int value where the constraint asks for a pattern match."""
    prepare_storage_dir()
    NON_STRING_JSON_FILE.write_text('{"digit": 42}', encoding="utf-8")

    report = NonStringDigitConfiguration.load_configuration()

    assert [str(entry) for entry in report] == [
        f"member 'digit' (key 'digit' in the JSON file {NON_STRING_JSON_FILE}) "
        "of 'NonStringDigitConfiguration' fell back to its default: the value violates "
        "its constraints (value 42 is not a string to match regex '^[a-z]+$')"
    ]
    assert NonStringDigitConfiguration.digit is None
