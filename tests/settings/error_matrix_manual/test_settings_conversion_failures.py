"""Conversion failures: the value is there, but it has the wrong type.

Every member holds its stored value, but one of them holds ``"abc"`` where
an ``int`` is declared.

- On the required member, the load aborts over that member alone, and the
  class keeps the state that it had before the call. The values of the
  healthy members go back with the failed pass.
- On the optional members, nothing aborts. Each of them stands at its
  default, the load report carries both fallbacks, and a warning names each
  address that came up unusable.
- If both required members hold ``"abc"``, one abort carries both errors.
"""

import logging

import pytest
from settings_conversion_classes import (
    BAD_OPTIONAL_VALUE_DOTENV_FILE,
    BAD_OPTIONAL_VALUE_JSON_FILE,
    BAD_OPTIONAL_VALUE_TOML_FILE,
    BAD_REQUIRED_VALUE_DOTENV_FILE,
    BAD_REQUIRED_VALUE_JSON_FILE,
    BAD_REQUIRED_VALUE_TOML_FILE,
    BAD_REQUIRED_VALUES_DOTENV_FILE,
    BAD_REQUIRED_VALUES_JSON_FILE,
    BAD_REQUIRED_VALUES_TOML_FILE,
    BadOptionalValueDotenvSettings,
    BadOptionalValueEnvSettings,
    BadOptionalValueJsonSettings,
    BadOptionalValueTomlSettings,
    BadRequiredValueDotenvSettings,
    BadRequiredValueEnvSettings,
    BadRequiredValueJsonSettings,
    BadRequiredValuesDotenvSettings,
    BadRequiredValuesEnvSettings,
    BadRequiredValuesJsonSettings,
    BadRequiredValuesTomlSettings,
    BadRequiredValueTomlSettings,
)
from settings_storage_paths import prepare_storage_dir

from advexp.settings import AggregateLoadError, ConversionError, MemberLoadError

MATRIX_ENV_NAMES = ("EMX_ANSWER", "EMX_PLAIN", "EMX_KNOWN", "EMX_CONTROL")

# the conversion failure phrase for an ``int`` member fed ``"abc"``
UNCONVERTIBLE = "cannot convert 'abc' to int (invalid literal for int() with base 10: 'abc')"


# ---------------------------------------------------------------------------
# The required member holds an unconvertible value: the load aborts
# ---------------------------------------------------------------------------


def test_unconvertible_required_aborts_env(monkeypatch):
    """``EMX_ANSWER`` holds a value no conversion can take."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMX_ANSWER", "abc")
    monkeypatch.setenv("EMX_PLAIN", "22")
    monkeypatch.setenv("EMX_KNOWN", "33")
    monkeypatch.setenv("EMX_CONTROL", "44")

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValueEnvSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        "setting 'answer' (environment variable 'EMX_ANSWER') "
        "of 'BadRequiredValueEnvSettings' is required: "
        f"{UNCONVERTIBLE}"
    )
    # the abort leaves the class as the call found it: the healthy members'
    # loaded values ride with the failed pass, nothing is applied
    assert BadRequiredValueEnvSettings.plain is None
    assert BadRequiredValueEnvSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueEnvSettings.control


def test_unconvertible_required_aborts_dotenv():
    """The dotenv file holds a value no conversion can take."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUE_DOTENV_FILE.write_text(
        """EMX_ANSWER=abc
EMX_PLAIN=22
EMX_KNOWN=33
EMX_CONTROL=44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValueDotenvSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{BAD_REQUIRED_VALUE_DOTENV_FILE}) of 'BadRequiredValueDotenvSettings' "
        f"is required: {UNCONVERTIBLE}"
    )
    # the abort leaves the class untouched: the healthy members' values
    # ride with the failed pass
    assert BadRequiredValueDotenvSettings.plain is None
    assert BadRequiredValueDotenvSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueDotenvSettings.control


def test_unconvertible_required_aborts_json():
    """The JSON file holds a value no conversion can take."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUE_JSON_FILE.write_text(
        '{"answer": "abc", "plain": 22, "known": 33, "control": 44}',
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValueJsonSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the JSON file {BAD_REQUIRED_VALUE_JSON_FILE}) "
        f"of 'BadRequiredValueJsonSettings' is required: {UNCONVERTIBLE}"
    )
    # the abort leaves the class untouched: the healthy members' values
    # ride with the failed pass
    assert BadRequiredValueJsonSettings.plain is None
    assert BadRequiredValueJsonSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueJsonSettings.control


def test_unconvertible_required_aborts_toml():
    """The TOML file holds a value no conversion can take."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUE_TOML_FILE.write_text(
        """answer = "abc"
plain = 22
known = 33
control = 44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValueTomlSettings.load_settings()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the TOML file {BAD_REQUIRED_VALUE_TOML_FILE}) "
        f"of 'BadRequiredValueTomlSettings' is required: {UNCONVERTIBLE}"
    )
    # the abort leaves the class untouched: the healthy members' values
    # ride with the failed pass
    assert BadRequiredValueTomlSettings.plain is None
    assert BadRequiredValueTomlSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueTomlSettings.control


# ---------------------------------------------------------------------------
# The optional members hold unconvertible values: no abort, defaults served
# ---------------------------------------------------------------------------


def test_unconvertible_optional_falls_back_env(monkeypatch, caplog):
    """``EMX_PLAIN`` and ``EMX_KNOWN`` hold values no conversion can take."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMX_ANSWER", "11")
    monkeypatch.setenv("EMX_PLAIN", "abc")
    monkeypatch.setenv("EMX_KNOWN", "abc")
    monkeypatch.setenv("EMX_CONTROL", "44")

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = BadOptionalValueEnvSettings.load_settings()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        "setting 'plain' (environment variable 'EMX_PLAIN') "
        "of 'BadOptionalValueEnvSettings' fell back to its default: "
        f"{UNCONVERTIBLE}",
        "setting 'known' (environment variable 'EMX_KNOWN') "
        "of 'BadOptionalValueEnvSettings' fell back to its default: "
        f"{UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        "setting 'plain' (environment variable 'EMX_PLAIN') of 'BadOptionalValueEnvSettings': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        "setting 'known' (environment variable 'EMX_KNOWN') of 'BadOptionalValueEnvSettings': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    # no abort happened: the required members loaded, the optional stood at
    # their defaults
    assert BadOptionalValueEnvSettings.answer == 11
    assert BadOptionalValueEnvSettings.plain is None
    assert BadOptionalValueEnvSettings.known == 7
    assert BadOptionalValueEnvSettings.control == 44


def test_unconvertible_optional_falls_back_dotenv(caplog):
    """The dotenv file holds values no conversion can take."""
    prepare_storage_dir()
    BAD_OPTIONAL_VALUE_DOTENV_FILE.write_text(
        """EMX_ANSWER=11
EMX_PLAIN=abc
EMX_KNOWN=abc
EMX_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = BadOptionalValueDotenvSettings.load_settings()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        f"setting 'plain' (environment variable 'EMX_PLAIN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvSettings' "
        f"fell back to its default: {UNCONVERTIBLE}",
        f"setting 'known' (environment variable 'EMX_KNOWN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvSettings' "
        f"fell back to its default: {UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"setting 'plain' (environment variable 'EMX_PLAIN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvSettings': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        f"setting 'known' (environment variable 'EMX_KNOWN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvSettings': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert BadOptionalValueDotenvSettings.answer == 11
    assert BadOptionalValueDotenvSettings.plain is None
    assert BadOptionalValueDotenvSettings.known == 7
    assert BadOptionalValueDotenvSettings.control == 44


def test_unconvertible_optional_falls_back_json(caplog):
    """The JSON file holds values no conversion can take."""
    prepare_storage_dir()
    BAD_OPTIONAL_VALUE_JSON_FILE.write_text(
        '{"answer": 11, "plain": "abc", "known": "abc", "control": 44}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = BadOptionalValueJsonSettings.load_settings()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        f"setting 'plain' (key 'plain' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonSettings' fell back to its default: {UNCONVERTIBLE}",
        f"setting 'known' (key 'known' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonSettings' fell back to its default: {UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"setting 'plain' (key 'plain' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonSettings': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        f"setting 'known' (key 'known' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonSettings': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert BadOptionalValueJsonSettings.answer == 11
    assert BadOptionalValueJsonSettings.plain is None
    assert BadOptionalValueJsonSettings.known == 7
    assert BadOptionalValueJsonSettings.control == 44


def test_unconvertible_optional_falls_back_toml(caplog):
    """The TOML file holds values no conversion can take."""
    prepare_storage_dir()
    BAD_OPTIONAL_VALUE_TOML_FILE.write_text(
        """answer = 11
plain = "abc"
known = "abc"
control = 44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = BadOptionalValueTomlSettings.load_settings()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        f"setting 'plain' (key 'plain' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlSettings' fell back to its default: {UNCONVERTIBLE}",
        f"setting 'known' (key 'known' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlSettings' fell back to its default: {UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"setting 'plain' (key 'plain' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlSettings': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        f"setting 'known' (key 'known' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlSettings': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert BadOptionalValueTomlSettings.answer == 11
    assert BadOptionalValueTomlSettings.plain is None
    assert BadOptionalValueTomlSettings.known == 7
    assert BadOptionalValueTomlSettings.control == 44


# ---------------------------------------------------------------------------
# Both required members hold unconvertible values: one abort, both errors
# ---------------------------------------------------------------------------


def test_unconvertible_required_pair_aborts_env(monkeypatch):
    """``EMX_ANSWER`` and ``EMX_CONTROL`` hold values no conversion can take."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMX_ANSWER", "abc")
    monkeypatch.setenv("EMX_PLAIN", "22")
    monkeypatch.setenv("EMX_KNOWN", "33")
    monkeypatch.setenv("EMX_CONTROL", "abc")

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValuesEnvSettings.load_settings()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        "setting 'answer' (environment variable 'EMX_ANSWER') "
        "of 'BadRequiredValuesEnvSettings' is required: "
        f"{UNCONVERTIBLE}",
        "setting 'control' (environment variable 'EMX_CONTROL') "
        "of 'BadRequiredValuesEnvSettings' is required: "
        f"{UNCONVERTIBLE}",
    ]
    # the abort leaves the class as the call found it: the healthy members'
    # loaded values ride with the failed pass, nothing is applied
    assert BadRequiredValuesEnvSettings.plain is None
    assert BadRequiredValuesEnvSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesEnvSettings.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesEnvSettings.control


def test_unconvertible_required_pair_aborts_dotenv():
    """The dotenv file holds values no conversion can take on both required
    members."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUES_DOTENV_FILE.write_text(
        """EMX_ANSWER=abc
EMX_PLAIN=22
EMX_KNOWN=33
EMX_CONTROL=abc
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValuesDotenvSettings.load_settings()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{BAD_REQUIRED_VALUES_DOTENV_FILE}) of 'BadRequiredValuesDotenvSettings' "
        f"is required: {UNCONVERTIBLE}",
        f"setting 'control' (environment variable 'EMX_CONTROL' in the dotenv file "
        f"{BAD_REQUIRED_VALUES_DOTENV_FILE}) of 'BadRequiredValuesDotenvSettings' "
        f"is required: {UNCONVERTIBLE}",
    ]
    assert BadRequiredValuesDotenvSettings.plain is None
    assert BadRequiredValuesDotenvSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesDotenvSettings.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesDotenvSettings.control


def test_unconvertible_required_pair_aborts_json():
    """The JSON file holds values no conversion can take on both required
    members."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUES_JSON_FILE.write_text(
        '{"answer": "abc", "plain": 22, "known": 33, "control": "abc"}',
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValuesJsonSettings.load_settings()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        f"setting 'answer' (key 'answer' in the JSON file {BAD_REQUIRED_VALUES_JSON_FILE}) "
        f"of 'BadRequiredValuesJsonSettings' is required: {UNCONVERTIBLE}",
        f"setting 'control' (key 'control' in the JSON file {BAD_REQUIRED_VALUES_JSON_FILE}) "
        f"of 'BadRequiredValuesJsonSettings' is required: {UNCONVERTIBLE}",
    ]
    assert BadRequiredValuesJsonSettings.plain is None
    assert BadRequiredValuesJsonSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesJsonSettings.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesJsonSettings.control


def test_unconvertible_required_pair_aborts_toml():
    """The TOML file holds values no conversion can take on both required
    members."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUES_TOML_FILE.write_text(
        """answer = "abc"
plain = 22
known = 33
control = "abc"
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValuesTomlSettings.load_settings()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        f"setting 'answer' (key 'answer' in the TOML file {BAD_REQUIRED_VALUES_TOML_FILE}) "
        f"of 'BadRequiredValuesTomlSettings' is required: {UNCONVERTIBLE}",
        f"setting 'control' (key 'control' in the TOML file {BAD_REQUIRED_VALUES_TOML_FILE}) "
        f"of 'BadRequiredValuesTomlSettings' is required: {UNCONVERTIBLE}",
    ]
    assert BadRequiredValuesTomlSettings.plain is None
    assert BadRequiredValuesTomlSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesTomlSettings.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesTomlSettings.control
