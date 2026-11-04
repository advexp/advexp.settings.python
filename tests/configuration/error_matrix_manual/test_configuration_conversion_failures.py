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
from configuration_conversion_classes import (
    BAD_OPTIONAL_VALUE_DOTENV_FILE,
    BAD_OPTIONAL_VALUE_JSON_FILE,
    BAD_OPTIONAL_VALUE_TOML_FILE,
    BAD_REQUIRED_VALUE_DOTENV_FILE,
    BAD_REQUIRED_VALUE_JSON_FILE,
    BAD_REQUIRED_VALUE_TOML_FILE,
    BAD_REQUIRED_VALUES_DOTENV_FILE,
    BAD_REQUIRED_VALUES_JSON_FILE,
    BAD_REQUIRED_VALUES_TOML_FILE,
    BadOptionalValueDotenvConfiguration,
    BadOptionalValueEnvConfiguration,
    BadOptionalValueJsonConfiguration,
    BadOptionalValueTomlConfiguration,
    BadRequiredValueDotenvConfiguration,
    BadRequiredValueEnvConfiguration,
    BadRequiredValueJsonConfiguration,
    BadRequiredValuesDotenvConfiguration,
    BadRequiredValuesEnvConfiguration,
    BadRequiredValuesJsonConfiguration,
    BadRequiredValuesTomlConfiguration,
    BadRequiredValueTomlConfiguration,
)
from configuration_storage_paths import prepare_storage_dir

from advexp.configuration import AggregateLoadError, ConversionError, MemberLoadError

MATRIX_ENV_NAMES = ("EMC_ANSWER", "EMC_PLAIN", "EMC_KNOWN", "EMC_CONTROL")

# the conversion failure phrase for an ``int`` member fed ``"abc"``
UNCONVERTIBLE = "cannot convert 'abc' to int (invalid literal for int() with base 10: 'abc')"


# ---------------------------------------------------------------------------
# The required member holds an unconvertible value: the load aborts
# ---------------------------------------------------------------------------


def test_unconvertible_required_aborts_env(monkeypatch):
    """``EMC_ANSWER`` holds a value no conversion can take."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMC_ANSWER", "abc")
    monkeypatch.setenv("EMC_PLAIN", "22")
    monkeypatch.setenv("EMC_KNOWN", "33")
    monkeypatch.setenv("EMC_CONTROL", "44")

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValueEnvConfiguration.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        "member 'answer' (environment variable 'EMC_ANSWER') "
        "of 'BadRequiredValueEnvConfiguration' is required: "
        f"{UNCONVERTIBLE}"
    )
    # the abort leaves the class as the call found it: the healthy members'
    # loaded values ride with the failed pass, nothing is applied
    assert BadRequiredValueEnvConfiguration.plain is None
    assert BadRequiredValueEnvConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueEnvConfiguration.control


def test_unconvertible_required_aborts_dotenv():
    """The dotenv file holds a value no conversion can take."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUE_DOTENV_FILE.write_text(
        """EMC_ANSWER=abc
EMC_PLAIN=22
EMC_KNOWN=33
EMC_CONTROL=44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValueDotenvConfiguration.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{BAD_REQUIRED_VALUE_DOTENV_FILE}) of 'BadRequiredValueDotenvConfiguration' "
        f"is required: {UNCONVERTIBLE}"
    )
    # the abort leaves the class untouched: the healthy members' values
    # ride with the failed pass
    assert BadRequiredValueDotenvConfiguration.plain is None
    assert BadRequiredValueDotenvConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueDotenvConfiguration.control


def test_unconvertible_required_aborts_json():
    """The JSON file holds a value no conversion can take."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUE_JSON_FILE.write_text(
        '{"answer": "abc", "plain": 22, "known": 33, "control": 44}',
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValueJsonConfiguration.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the JSON file {BAD_REQUIRED_VALUE_JSON_FILE}) "
        f"of 'BadRequiredValueJsonConfiguration' is required: {UNCONVERTIBLE}"
    )
    # the abort leaves the class untouched: the healthy members' values
    # ride with the failed pass
    assert BadRequiredValueJsonConfiguration.plain is None
    assert BadRequiredValueJsonConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueJsonConfiguration.control


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
        BadRequiredValueTomlConfiguration.load_configuration()

    (error,) = info.value.errors
    assert isinstance(error, ConversionError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the TOML file {BAD_REQUIRED_VALUE_TOML_FILE}) "
        f"of 'BadRequiredValueTomlConfiguration' is required: {UNCONVERTIBLE}"
    )
    # the abort leaves the class untouched: the healthy members' values
    # ride with the failed pass
    assert BadRequiredValueTomlConfiguration.plain is None
    assert BadRequiredValueTomlConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValueTomlConfiguration.control


# ---------------------------------------------------------------------------
# The optional members hold unconvertible values: no abort, defaults served
# ---------------------------------------------------------------------------


def test_unconvertible_optional_falls_back_env(monkeypatch, caplog):
    """``EMC_PLAIN`` and ``EMC_KNOWN`` hold values no conversion can take."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMC_ANSWER", "11")
    monkeypatch.setenv("EMC_PLAIN", "abc")
    monkeypatch.setenv("EMC_KNOWN", "abc")
    monkeypatch.setenv("EMC_CONTROL", "44")

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = BadOptionalValueEnvConfiguration.load_configuration()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        "member 'plain' (environment variable 'EMC_PLAIN') "
        "of 'BadOptionalValueEnvConfiguration' fell back to its default: "
        f"{UNCONVERTIBLE}",
        "member 'known' (environment variable 'EMC_KNOWN') "
        "of 'BadOptionalValueEnvConfiguration' fell back to its default: "
        f"{UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        "member 'plain' (environment variable 'EMC_PLAIN') of 'BadOptionalValueEnvConfiguration': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        "member 'known' (environment variable 'EMC_KNOWN') of 'BadOptionalValueEnvConfiguration': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    # no abort happened: the required members loaded, the optional stood at
    # their defaults
    assert BadOptionalValueEnvConfiguration.answer == 11
    assert BadOptionalValueEnvConfiguration.plain is None
    assert BadOptionalValueEnvConfiguration.known == 7
    assert BadOptionalValueEnvConfiguration.control == 44


def test_unconvertible_optional_falls_back_dotenv(caplog):
    """The dotenv file holds values no conversion can take."""
    prepare_storage_dir()
    BAD_OPTIONAL_VALUE_DOTENV_FILE.write_text(
        """EMC_ANSWER=11
EMC_PLAIN=abc
EMC_KNOWN=abc
EMC_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = BadOptionalValueDotenvConfiguration.load_configuration()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        f"member 'plain' (environment variable 'EMC_PLAIN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvConfiguration' "
        f"fell back to its default: {UNCONVERTIBLE}",
        f"member 'known' (environment variable 'EMC_KNOWN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvConfiguration' "
        f"fell back to its default: {UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"member 'plain' (environment variable 'EMC_PLAIN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvConfiguration': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        f"member 'known' (environment variable 'EMC_KNOWN' in the dotenv file "
        f"{BAD_OPTIONAL_VALUE_DOTENV_FILE}) of 'BadOptionalValueDotenvConfiguration': "
        f"{UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert BadOptionalValueDotenvConfiguration.answer == 11
    assert BadOptionalValueDotenvConfiguration.plain is None
    assert BadOptionalValueDotenvConfiguration.known == 7
    assert BadOptionalValueDotenvConfiguration.control == 44


def test_unconvertible_optional_falls_back_json(caplog):
    """The JSON file holds values no conversion can take."""
    prepare_storage_dir()
    BAD_OPTIONAL_VALUE_JSON_FILE.write_text(
        '{"answer": 11, "plain": "abc", "known": "abc", "control": 44}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = BadOptionalValueJsonConfiguration.load_configuration()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        f"member 'plain' (key 'plain' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonConfiguration' fell back to its default: {UNCONVERTIBLE}",
        f"member 'known' (key 'known' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonConfiguration' fell back to its default: {UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"member 'plain' (key 'plain' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonConfiguration': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        f"member 'known' (key 'known' in the JSON file {BAD_OPTIONAL_VALUE_JSON_FILE}) "
        f"of 'BadOptionalValueJsonConfiguration': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert BadOptionalValueJsonConfiguration.answer == 11
    assert BadOptionalValueJsonConfiguration.plain is None
    assert BadOptionalValueJsonConfiguration.known == 7
    assert BadOptionalValueJsonConfiguration.control == 44


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

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = BadOptionalValueTomlConfiguration.load_configuration()

    assert {type(entry) for entry in report} == {ConversionError}
    assert [str(entry) for entry in report] == [
        f"member 'plain' (key 'plain' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlConfiguration' fell back to its default: {UNCONVERTIBLE}",
        f"member 'known' (key 'known' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlConfiguration' fell back to its default: {UNCONVERTIBLE}",
    ]
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"member 'plain' (key 'plain' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlConfiguration': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert (
        f"member 'known' (key 'known' in the TOML file {BAD_OPTIONAL_VALUE_TOML_FILE}) "
        f"of 'BadOptionalValueTomlConfiguration': {UNCONVERTIBLE}; using the default value"
    ) in warning_messages
    assert BadOptionalValueTomlConfiguration.answer == 11
    assert BadOptionalValueTomlConfiguration.plain is None
    assert BadOptionalValueTomlConfiguration.known == 7
    assert BadOptionalValueTomlConfiguration.control == 44


# ---------------------------------------------------------------------------
# Both required members hold unconvertible values: one abort, both errors
# ---------------------------------------------------------------------------


def test_unconvertible_required_pair_aborts_env(monkeypatch):
    """``EMC_ANSWER`` and ``EMC_CONTROL`` hold values no conversion can take."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMC_ANSWER", "abc")
    monkeypatch.setenv("EMC_PLAIN", "22")
    monkeypatch.setenv("EMC_KNOWN", "33")
    monkeypatch.setenv("EMC_CONTROL", "abc")

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValuesEnvConfiguration.load_configuration()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        "member 'answer' (environment variable 'EMC_ANSWER') "
        "of 'BadRequiredValuesEnvConfiguration' is required: "
        f"{UNCONVERTIBLE}",
        "member 'control' (environment variable 'EMC_CONTROL') "
        "of 'BadRequiredValuesEnvConfiguration' is required: "
        f"{UNCONVERTIBLE}",
    ]
    # the abort leaves the class as the call found it: the healthy members'
    # loaded values ride with the failed pass, nothing is applied
    assert BadRequiredValuesEnvConfiguration.plain is None
    assert BadRequiredValuesEnvConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesEnvConfiguration.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesEnvConfiguration.control


def test_unconvertible_required_pair_aborts_dotenv():
    """The dotenv file holds values no conversion can take on both required
    members."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUES_DOTENV_FILE.write_text(
        """EMC_ANSWER=abc
EMC_PLAIN=22
EMC_KNOWN=33
EMC_CONTROL=abc
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValuesDotenvConfiguration.load_configuration()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{BAD_REQUIRED_VALUES_DOTENV_FILE}) of 'BadRequiredValuesDotenvConfiguration' "
        f"is required: {UNCONVERTIBLE}",
        f"member 'control' (environment variable 'EMC_CONTROL' in the dotenv file "
        f"{BAD_REQUIRED_VALUES_DOTENV_FILE}) of 'BadRequiredValuesDotenvConfiguration' "
        f"is required: {UNCONVERTIBLE}",
    ]
    assert BadRequiredValuesDotenvConfiguration.plain is None
    assert BadRequiredValuesDotenvConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesDotenvConfiguration.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesDotenvConfiguration.control


def test_unconvertible_required_pair_aborts_json():
    """The JSON file holds values no conversion can take on both required
    members."""
    prepare_storage_dir()
    BAD_REQUIRED_VALUES_JSON_FILE.write_text(
        '{"answer": "abc", "plain": 22, "known": 33, "control": "abc"}',
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        BadRequiredValuesJsonConfiguration.load_configuration()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        f"member 'answer' (key 'answer' in the JSON file {BAD_REQUIRED_VALUES_JSON_FILE}) "
        f"of 'BadRequiredValuesJsonConfiguration' is required: {UNCONVERTIBLE}",
        f"member 'control' (key 'control' in the JSON file {BAD_REQUIRED_VALUES_JSON_FILE}) "
        f"of 'BadRequiredValuesJsonConfiguration' is required: {UNCONVERTIBLE}",
    ]
    assert BadRequiredValuesJsonConfiguration.plain is None
    assert BadRequiredValuesJsonConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesJsonConfiguration.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesJsonConfiguration.control


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
        BadRequiredValuesTomlConfiguration.load_configuration()

    assert {type(error) for error in info.value.errors} == {ConversionError}
    assert [str(error) for error in info.value.errors] == [
        f"member 'answer' (key 'answer' in the TOML file {BAD_REQUIRED_VALUES_TOML_FILE}) "
        f"of 'BadRequiredValuesTomlConfiguration' is required: {UNCONVERTIBLE}",
        f"member 'control' (key 'control' in the TOML file {BAD_REQUIRED_VALUES_TOML_FILE}) "
        f"of 'BadRequiredValuesTomlConfiguration' is required: {UNCONVERTIBLE}",
    ]
    assert BadRequiredValuesTomlConfiguration.plain is None
    assert BadRequiredValuesTomlConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesTomlConfiguration.answer
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BadRequiredValuesTomlConfiguration.control
