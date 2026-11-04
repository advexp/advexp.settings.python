"""Missing values: the declaration states decide the channel.

If one required member is missing, the load aborts with an aggregate error.
The optional members are attached to the abort as misses, and each of them
shows where its default came from. If nothing is stored at all, every
required member is reported.

A storage that is full of addresses that the class never reads (the wrong
prefix, the wrong case, or a foreign key) looks the same as an empty
storage, and the debug log names the exact address that has to be provided.

The last test covers the naming options of the environment family: a
variable that the pattern does not build is a miss, even when variables with
similar names exist in the environment.
"""

import logging

import pytest
from settings_missing_values_classes import (
    NOTHING_STORED_DOTENV_FILE,
    NOTHING_STORED_JSON_FILE,
    NOTHING_STORED_TOML_FILE,
    ONLY_CONTROL_DOTENV_FILE,
    ONLY_CONTROL_JSON_FILE,
    ONLY_CONTROL_TOML_FILE,
    WRONG_ADDRESSES_DOTENV_FILE,
    WRONG_ADDRESSES_JSON_FILE,
    WRONG_ADDRESSES_TOML_FILE,
    EnvNamePatternSettings,
    NothingStoredDotenvSettings,
    NothingStoredEnvSettings,
    NothingStoredJsonSettings,
    NothingStoredTomlSettings,
    OnlyControlStoredDotenvSettings,
    OnlyControlStoredEnvSettings,
    OnlyControlStoredJsonSettings,
    OnlyControlStoredTomlSettings,
    WrongAddressesDotenvSettings,
    WrongAddressesEnvSettings,
    WrongAddressesJsonSettings,
    WrongAddressesTomlSettings,
)
from settings_storage_paths import prepare_storage_dir

from advexp.settings import AggregateLoadError, MemberLoadError, MissingValueError

MATRIX_ENV_NAMES = ("EMX_ANSWER", "EMX_PLAIN", "EMX_KNOWN", "EMX_CONTROL")


# ---------------------------------------------------------------------------
# Only ``control`` is stored: one required member aborts, the optional ones
# ride the abort as misses
# ---------------------------------------------------------------------------


def test_missing_required_reports_through_the_aggregate_env(monkeypatch):
    """Only ``EMX_CONTROL`` is set in the process environment."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMX_CONTROL", "44")

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredEnvSettings.load_settings()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        "setting 'answer' (environment variable 'EMX_ANSWER') "
        "of 'OnlyControlStoredEnvSettings' is required: "
        "the process environment provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        "setting 'plain' (environment variable 'EMX_PLAIN') "
        "of 'OnlyControlStoredEnvSettings': "
        "the process environment provided no value",
        "setting 'known' (environment variable 'EMX_KNOWN') "
        "of 'OnlyControlStoredEnvSettings': "
        "the process environment provided no value",
    ]
    message = str(info.value)
    assert "advexp.settings error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    # the abort leaves the class as the call found it: nothing the failed
    # pass produced is applied — an optional member reads its declared
    # default, a required one holds nothing
    assert OnlyControlStoredEnvSettings.plain is None
    assert OnlyControlStoredEnvSettings.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredEnvSettings.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredEnvSettings.answer


def test_missing_required_reports_through_the_aggregate_dotenv():
    """Only ``control`` is stored in the dotenv file."""
    prepare_storage_dir()
    ONLY_CONTROL_DOTENV_FILE.write_text(
        """EMX_CONTROL=44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredDotenvSettings.load_settings()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{ONLY_CONTROL_DOTENV_FILE}) of 'OnlyControlStoredDotenvSettings' is required: "
        "the dotenv file provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        f"setting 'plain' (environment variable 'EMX_PLAIN' in the dotenv file "
        f"{ONLY_CONTROL_DOTENV_FILE}) of 'OnlyControlStoredDotenvSettings': "
        "the dotenv file provided no value",
        f"setting 'known' (environment variable 'EMX_KNOWN' in the dotenv file "
        f"{ONLY_CONTROL_DOTENV_FILE}) of 'OnlyControlStoredDotenvSettings': "
        "the dotenv file provided no value",
    ]
    message = str(info.value)
    assert "advexp.settings error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    assert OnlyControlStoredDotenvSettings.plain is None
    assert OnlyControlStoredDotenvSettings.known == 7
    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredDotenvSettings.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredDotenvSettings.answer


def test_missing_required_reports_through_the_aggregate_json():
    """Only ``control`` is stored in the JSON file."""
    prepare_storage_dir()
    ONLY_CONTROL_JSON_FILE.write_text('{"control": 44}', encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredJsonSettings.load_settings()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the JSON file {ONLY_CONTROL_JSON_FILE}) "
        "of 'OnlyControlStoredJsonSettings' is required: "
        "the JSON file provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        f"setting 'plain' (key 'plain' in the JSON file {ONLY_CONTROL_JSON_FILE}) "
        "of 'OnlyControlStoredJsonSettings': "
        "the JSON file provided no value",
        f"setting 'known' (key 'known' in the JSON file {ONLY_CONTROL_JSON_FILE}) "
        "of 'OnlyControlStoredJsonSettings': "
        "the JSON file provided no value",
    ]
    message = str(info.value)
    assert "advexp.settings error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    assert OnlyControlStoredJsonSettings.plain is None
    assert OnlyControlStoredJsonSettings.known == 7
    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredJsonSettings.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredJsonSettings.answer


def test_missing_required_reports_through_the_aggregate_toml():
    """Only ``control`` is stored in the TOML file."""
    prepare_storage_dir()
    ONLY_CONTROL_TOML_FILE.write_text(
        """control = 44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredTomlSettings.load_settings()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the TOML file {ONLY_CONTROL_TOML_FILE}) "
        "of 'OnlyControlStoredTomlSettings' is required: "
        "the TOML file provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        f"setting 'plain' (key 'plain' in the TOML file {ONLY_CONTROL_TOML_FILE}) "
        "of 'OnlyControlStoredTomlSettings': "
        "the TOML file provided no value",
        f"setting 'known' (key 'known' in the TOML file {ONLY_CONTROL_TOML_FILE}) "
        "of 'OnlyControlStoredTomlSettings': "
        "the TOML file provided no value",
    ]
    message = str(info.value)
    assert "advexp.settings error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    assert OnlyControlStoredTomlSettings.plain is None
    assert OnlyControlStoredTomlSettings.known == 7
    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredTomlSettings.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredTomlSettings.answer


# ---------------------------------------------------------------------------
# Nothing stored at all: every required member is reported
# ---------------------------------------------------------------------------


def test_nothing_stored_reports_every_required_member_env(monkeypatch):
    """No variable of the class exists in the process environment."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredEnvSettings.load_settings()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.settings error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        "setting 'answer' (environment variable 'EMX_ANSWER') "
        "of 'NothingStoredEnvSettings' is required: "
        "the process environment provided no value"
    )


def test_nothing_stored_reports_every_required_member_dotenv():
    """The dotenv file does not exist, so for the load it is as good as empty."""
    prepare_storage_dir()
    if NOTHING_STORED_DOTENV_FILE.exists():
        NOTHING_STORED_DOTENV_FILE.unlink()  # the storage must hold nothing at all

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredDotenvSettings.load_settings()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.settings error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{NOTHING_STORED_DOTENV_FILE}) of 'NothingStoredDotenvSettings' is required: "
        "the dotenv file provided no value"
    )


def test_nothing_stored_reports_every_required_member_json():
    """The JSON file does not exist, so for the load it is as good as empty."""
    prepare_storage_dir()
    if NOTHING_STORED_JSON_FILE.exists():
        NOTHING_STORED_JSON_FILE.unlink()  # the storage must hold nothing at all

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredJsonSettings.load_settings()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.settings error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        f"setting 'answer' (key 'answer' in the JSON file {NOTHING_STORED_JSON_FILE}) "
        "of 'NothingStoredJsonSettings' is required: "
        "the JSON file provided no value"
    )


def test_nothing_stored_reports_every_required_member_toml():
    """The TOML file does not exist, so for the load it is as good as empty."""
    prepare_storage_dir()
    if NOTHING_STORED_TOML_FILE.exists():
        NOTHING_STORED_TOML_FILE.unlink()  # the storage must hold nothing at all

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredTomlSettings.load_settings()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.settings error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        f"setting 'answer' (key 'answer' in the TOML file {NOTHING_STORED_TOML_FILE}) "
        "of 'NothingStoredTomlSettings' is required: "
        "the TOML file provided no value"
    )


# ---------------------------------------------------------------------------
# The storage is full, but under addresses the class never reads
# ---------------------------------------------------------------------------


def test_wrong_addresses_are_invisible_env(monkeypatch, caplog):
    """Variables with a ``typo_`` in the name: the load sees the same
    emptiness as with nothing set."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMX_TYPO_ANSWER", "11")
    monkeypatch.setenv("EMX_TYPO_PLAIN", "22")
    monkeypatch.setenv("EMX_TYPO_KNOWN", "33")
    monkeypatch.setenv("EMX_TYPO_CONTROL", "44")

    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesEnvSettings.load_settings()

    # the failure names the address to provide, in the spelling the class reads
    error = info.value.errors[0]
    assert str(error) == (
        "setting 'answer' (environment variable 'EMX_ANSWER') "
        "of 'WrongAddressesEnvSettings' is required: "
        "the process environment provided no value"
    )
    # the stored addresses nobody reads stay out of the report
    assert "typo_" not in str(info.value)
    # the debug log names each address that came up empty
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        "setting 'plain' (environment variable 'EMX_PLAIN') of 'WrongAddressesEnvSettings': the "
        "process environment provided no value; using the default value"
    ) in debug_messages
    assert WrongAddressesEnvSettings.known == 7


def test_wrong_addresses_are_invisible_dotenv(caplog):
    """Dotenv lines with a ``typo_`` in the name: the load sees the same
    emptiness as with nothing stored."""
    prepare_storage_dir()
    WRONG_ADDRESSES_DOTENV_FILE.write_text(
        """EMX_TYPO_ANSWER=11
EMX_TYPO_PLAIN=22
EMX_TYPO_KNOWN=33
EMX_TYPO_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesDotenvSettings.load_settings()

    error = info.value.errors[0]
    assert str(error) == (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{WRONG_ADDRESSES_DOTENV_FILE}) of 'WrongAddressesDotenvSettings' is required: "
        "the dotenv file provided no value"
    )
    assert "typo_" not in str(info.value)
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"setting 'plain' (environment variable 'EMX_PLAIN' in the dotenv file "
        f"{WRONG_ADDRESSES_DOTENV_FILE}) of 'WrongAddressesDotenvSettings': "
        "the dotenv file provided no value; using the default value"
    ) in debug_messages
    assert WrongAddressesDotenvSettings.known == 7


def test_wrong_addresses_are_invisible_json(caplog):
    """JSON keys with a ``typo_`` prefix: the load sees the same emptiness
    as with nothing stored."""
    prepare_storage_dir()
    WRONG_ADDRESSES_JSON_FILE.write_text(
        '{"typo_answer": 11, "typo_plain": 22, "typo_known": 33, "typo_control": 44}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesJsonSettings.load_settings()

    error = info.value.errors[0]
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the JSON file {WRONG_ADDRESSES_JSON_FILE}) "
        "of 'WrongAddressesJsonSettings' is required: "
        "the JSON file provided no value"
    )
    assert "typo_" not in str(info.value)
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"setting 'plain' (key 'plain' in the JSON file {WRONG_ADDRESSES_JSON_FILE}) "
        "of 'WrongAddressesJsonSettings': the JSON file provided no value; using the default "
        "value"
    ) in debug_messages
    assert WrongAddressesJsonSettings.known == 7


def test_wrong_addresses_are_invisible_toml(caplog):
    """TOML keys with a ``typo_`` prefix: the load sees the same emptiness
    as with nothing stored."""
    prepare_storage_dir()
    WRONG_ADDRESSES_TOML_FILE.write_text(
        """typo_answer = 11
typo_plain = 22
typo_known = 33
typo_control = 44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesTomlSettings.load_settings()

    error = info.value.errors[0]
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the TOML file {WRONG_ADDRESSES_TOML_FILE}) "
        "of 'WrongAddressesTomlSettings' is required: "
        "the TOML file provided no value"
    )
    assert "typo_" not in str(info.value)
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"setting 'plain' (key 'plain' in the TOML file {WRONG_ADDRESSES_TOML_FILE}) "
        "of 'WrongAddressesTomlSettings': the TOML file provided no value; using the default "
        "value"
    ) in debug_messages
    assert WrongAddressesTomlSettings.known == 7


# ---------------------------------------------------------------------------
# The env family's naming options: a name the pattern does not build
# ---------------------------------------------------------------------------


def test_env_name_the_pattern_does_not_build_is_a_miss(monkeypatch, caplog):
    """The variables are set, but in spellings the pattern never builds:
    the wrong case and the missing prefix both read as absent."""
    monkeypatch.delenv("EMX_MODE", raising=False)
    monkeypatch.setenv("emx_mode", "debug")  # the wrong case
    monkeypatch.setenv("MODE", "debug")  # the missing prefix

    with caplog.at_level(logging.DEBUG, logger="advexp.settings"):
        report = EnvNamePatternSettings.load_settings()

    assert report == ()
    assert EnvNamePatternSettings.mode == "production"
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        "setting 'mode' (environment variable 'EMX_MODE') of 'EnvNamePatternSettings': the "
        "process environment provided no value; using the default value"
    ) in debug_messages
