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
from configuration_missing_values_classes import (
    NOTHING_STORED_DOTENV_FILE,
    NOTHING_STORED_JSON_FILE,
    NOTHING_STORED_TOML_FILE,
    ONLY_CONTROL_DOTENV_FILE,
    ONLY_CONTROL_JSON_FILE,
    ONLY_CONTROL_TOML_FILE,
    WRONG_ADDRESSES_DOTENV_FILE,
    WRONG_ADDRESSES_JSON_FILE,
    WRONG_ADDRESSES_TOML_FILE,
    EnvNamePatternConfiguration,
    NothingStoredDotenvConfiguration,
    NothingStoredEnvConfiguration,
    NothingStoredJsonConfiguration,
    NothingStoredTomlConfiguration,
    OnlyControlStoredDotenvConfiguration,
    OnlyControlStoredEnvConfiguration,
    OnlyControlStoredJsonConfiguration,
    OnlyControlStoredTomlConfiguration,
    WrongAddressesDotenvConfiguration,
    WrongAddressesEnvConfiguration,
    WrongAddressesJsonConfiguration,
    WrongAddressesTomlConfiguration,
)
from configuration_storage_paths import prepare_storage_dir

from advexp.configuration import AggregateLoadError, MemberLoadError, MissingValueError

MATRIX_ENV_NAMES = ("EMC_ANSWER", "EMC_PLAIN", "EMC_KNOWN", "EMC_CONTROL")


# ---------------------------------------------------------------------------
# Only ``control`` is stored: one required member aborts, the optional ones
# ride the abort as misses
# ---------------------------------------------------------------------------


def test_missing_required_reports_through_the_aggregate_env(monkeypatch):
    """Only ``EMC_CONTROL`` is set in the process environment."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMC_CONTROL", "44")

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredEnvConfiguration.load_configuration()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        "member 'answer' (environment variable 'EMC_ANSWER') "
        "of 'OnlyControlStoredEnvConfiguration' is required: "
        "the process environment provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        "member 'plain' (environment variable 'EMC_PLAIN') "
        "of 'OnlyControlStoredEnvConfiguration': "
        "the process environment provided no value",
        "member 'known' (environment variable 'EMC_KNOWN') "
        "of 'OnlyControlStoredEnvConfiguration': "
        "the process environment provided no value",
    ]
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    # the abort leaves the class as the call found it: nothing the failed
    # pass produced is applied — an optional member reads its declared
    # default, a required one holds nothing
    assert OnlyControlStoredEnvConfiguration.plain is None
    assert OnlyControlStoredEnvConfiguration.known == 7
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredEnvConfiguration.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredEnvConfiguration.answer


def test_missing_required_reports_through_the_aggregate_dotenv():
    """Only ``control`` is stored in the dotenv file."""
    prepare_storage_dir()
    ONLY_CONTROL_DOTENV_FILE.write_text(
        """EMC_CONTROL=44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredDotenvConfiguration.load_configuration()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{ONLY_CONTROL_DOTENV_FILE}) of 'OnlyControlStoredDotenvConfiguration' "
        "is required: the dotenv file provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        f"member 'plain' (environment variable 'EMC_PLAIN' in the dotenv file "
        f"{ONLY_CONTROL_DOTENV_FILE}) of 'OnlyControlStoredDotenvConfiguration': "
        "the dotenv file provided no value",
        f"member 'known' (environment variable 'EMC_KNOWN' in the dotenv file "
        f"{ONLY_CONTROL_DOTENV_FILE}) of 'OnlyControlStoredDotenvConfiguration': "
        "the dotenv file provided no value",
    ]
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    assert OnlyControlStoredDotenvConfiguration.plain is None
    assert OnlyControlStoredDotenvConfiguration.known == 7
    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredDotenvConfiguration.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredDotenvConfiguration.answer


def test_missing_required_reports_through_the_aggregate_json():
    """Only ``control`` is stored in the JSON file."""
    prepare_storage_dir()
    ONLY_CONTROL_JSON_FILE.write_text('{"control": 44}', encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredJsonConfiguration.load_configuration()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the JSON file {ONLY_CONTROL_JSON_FILE}) "
        "of 'OnlyControlStoredJsonConfiguration' is required: "
        "the JSON file provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        f"member 'plain' (key 'plain' in the JSON file {ONLY_CONTROL_JSON_FILE}) "
        "of 'OnlyControlStoredJsonConfiguration': "
        "the JSON file provided no value",
        f"member 'known' (key 'known' in the JSON file {ONLY_CONTROL_JSON_FILE}) "
        "of 'OnlyControlStoredJsonConfiguration': "
        "the JSON file provided no value",
    ]
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    assert OnlyControlStoredJsonConfiguration.plain is None
    assert OnlyControlStoredJsonConfiguration.known == 7
    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredJsonConfiguration.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredJsonConfiguration.answer


def test_missing_required_reports_through_the_aggregate_toml():
    """Only ``control`` is stored in the TOML file."""
    prepare_storage_dir()
    ONLY_CONTROL_TOML_FILE.write_text(
        """control = 44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        OnlyControlStoredTomlConfiguration.load_configuration()

    error = info.value.errors[0]
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the TOML file {ONLY_CONTROL_TOML_FILE}) "
        "of 'OnlyControlStoredTomlConfiguration' is required: "
        "the TOML file provided no value"
    )
    assert [str(miss) for miss in info.value.misses] == [
        f"member 'plain' (key 'plain' in the TOML file {ONLY_CONTROL_TOML_FILE}) "
        "of 'OnlyControlStoredTomlConfiguration': "
        "the TOML file provided no value",
        f"member 'known' (key 'known' in the TOML file {ONLY_CONTROL_TOML_FILE}) "
        "of 'OnlyControlStoredTomlConfiguration': "
        "the TOML file provided no value",
    ]
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 1 member:" in message
    assert "2 optional members served their defaults (their sources provided no value):" in message
    assert str(error) in message
    assert OnlyControlStoredTomlConfiguration.plain is None
    assert OnlyControlStoredTomlConfiguration.known == 7
    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredTomlConfiguration.control
    with pytest.raises(MemberLoadError, match="is required"):
        _ = OnlyControlStoredTomlConfiguration.answer


# ---------------------------------------------------------------------------
# Nothing stored at all: every required member is reported
# ---------------------------------------------------------------------------


def test_nothing_stored_reports_every_required_member_env(monkeypatch):
    """No variable of the class exists in the process environment."""
    for name in MATRIX_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredEnvConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        "member 'answer' (environment variable 'EMC_ANSWER') "
        "of 'NothingStoredEnvConfiguration' is required: "
        "the process environment provided no value"
    )


def test_nothing_stored_reports_every_required_member_dotenv():
    """The dotenv file does not exist, so for the load it is as good as empty."""
    prepare_storage_dir()
    if NOTHING_STORED_DOTENV_FILE.exists():
        NOTHING_STORED_DOTENV_FILE.unlink()  # the storage must hold nothing at all

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredDotenvConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{NOTHING_STORED_DOTENV_FILE}) of 'NothingStoredDotenvConfiguration' is required: "
        "the dotenv file provided no value"
    )


def test_nothing_stored_reports_every_required_member_json():
    """The JSON file does not exist, so for the load it is as good as empty."""
    prepare_storage_dir()
    if NOTHING_STORED_JSON_FILE.exists():
        NOTHING_STORED_JSON_FILE.unlink()  # the storage must hold nothing at all

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredJsonConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        f"member 'answer' (key 'answer' in the JSON file {NOTHING_STORED_JSON_FILE}) "
        "of 'NothingStoredJsonConfiguration' is required: "
        "the JSON file provided no value"
    )


def test_nothing_stored_reports_every_required_member_toml():
    """The TOML file does not exist, so for the load it is as good as empty."""
    prepare_storage_dir()
    if NOTHING_STORED_TOML_FILE.exists():
        NOTHING_STORED_TOML_FILE.unlink()  # the storage must hold nothing at all

    with pytest.raises(AggregateLoadError) as info:
        NothingStoredTomlConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    assert {type(error) for error in info.value.errors} == {MissingValueError}
    message = str(info.value)
    assert "advexp.configuration error: the load failed for 2 members:" in message
    assert str(info.value.errors[0]) == (
        f"member 'answer' (key 'answer' in the TOML file {NOTHING_STORED_TOML_FILE}) "
        "of 'NothingStoredTomlConfiguration' is required: "
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
    monkeypatch.setenv("EMC_TYPO_ANSWER", "11")
    monkeypatch.setenv("EMC_TYPO_PLAIN", "22")
    monkeypatch.setenv("EMC_TYPO_KNOWN", "33")
    monkeypatch.setenv("EMC_TYPO_CONTROL", "44")

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesEnvConfiguration.load_configuration()

    # the failure names the address to provide, in the spelling the class reads
    error = info.value.errors[0]
    assert str(error) == (
        "member 'answer' (environment variable 'EMC_ANSWER') "
        "of 'WrongAddressesEnvConfiguration' is required: "
        "the process environment provided no value"
    )
    # the stored addresses nobody reads stay out of the report
    assert "typo_" not in str(info.value)
    # the debug log names each address that came up empty
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        "member 'plain' (environment variable 'EMC_PLAIN') of 'WrongAddressesEnvConfiguration': "
        "the process environment provided no value; using the default value"
    ) in debug_messages
    assert WrongAddressesEnvConfiguration.known == 7


def test_wrong_addresses_are_invisible_dotenv(caplog):
    """Dotenv lines with a ``typo_`` in the name: the load sees the same
    emptiness as with nothing stored."""
    prepare_storage_dir()
    WRONG_ADDRESSES_DOTENV_FILE.write_text(
        """EMC_TYPO_ANSWER=11
EMC_TYPO_PLAIN=22
EMC_TYPO_KNOWN=33
EMC_TYPO_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesDotenvConfiguration.load_configuration()

    error = info.value.errors[0]
    assert str(error) == (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{WRONG_ADDRESSES_DOTENV_FILE}) of 'WrongAddressesDotenvConfiguration' "
        "is required: the dotenv file provided no value"
    )
    assert "typo_" not in str(info.value)
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"member 'plain' (environment variable 'EMC_PLAIN' in the dotenv file "
        f"{WRONG_ADDRESSES_DOTENV_FILE}) of 'WrongAddressesDotenvConfiguration': "
        "the dotenv file provided no value; using the default value"
    ) in debug_messages
    assert WrongAddressesDotenvConfiguration.known == 7


def test_wrong_addresses_are_invisible_json(caplog):
    """JSON keys with a ``typo_`` prefix: the load sees the same emptiness
    as with nothing stored."""
    prepare_storage_dir()
    WRONG_ADDRESSES_JSON_FILE.write_text(
        '{"typo_answer": 11, "typo_plain": 22, "typo_known": 33, "typo_control": 44}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesJsonConfiguration.load_configuration()

    error = info.value.errors[0]
    assert str(error) == (
        f"member 'answer' (key 'answer' in the JSON file {WRONG_ADDRESSES_JSON_FILE}) "
        "of 'WrongAddressesJsonConfiguration' is required: "
        "the JSON file provided no value"
    )
    assert "typo_" not in str(info.value)
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"member 'plain' (key 'plain' in the JSON file {WRONG_ADDRESSES_JSON_FILE}) "
        "of 'WrongAddressesJsonConfiguration': the JSON file provided no value; using the default "
        "value"
    ) in debug_messages
    assert WrongAddressesJsonConfiguration.known == 7


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

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            WrongAddressesTomlConfiguration.load_configuration()

    error = info.value.errors[0]
    assert str(error) == (
        f"member 'answer' (key 'answer' in the TOML file {WRONG_ADDRESSES_TOML_FILE}) "
        "of 'WrongAddressesTomlConfiguration' is required: "
        "the TOML file provided no value"
    )
    assert "typo_" not in str(info.value)
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"member 'plain' (key 'plain' in the TOML file {WRONG_ADDRESSES_TOML_FILE}) "
        "of 'WrongAddressesTomlConfiguration': the TOML file provided no value; using the default "
        "value"
    ) in debug_messages
    assert WrongAddressesTomlConfiguration.known == 7


# ---------------------------------------------------------------------------
# The env family's naming options: a name the pattern does not build
# ---------------------------------------------------------------------------


def test_env_name_the_pattern_does_not_build_is_a_miss(monkeypatch, caplog):
    """The variables are set, but in spellings the pattern never builds:
    the wrong case and the missing prefix both read as absent."""
    monkeypatch.delenv("EMC_MODE", raising=False)
    monkeypatch.setenv("emc_mode", "debug")  # the wrong case
    monkeypatch.setenv("MODE", "debug")  # the missing prefix

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        report = EnvNamePatternConfiguration.load_configuration()

    assert report == ()
    assert EnvNamePatternConfiguration.mode == "production"
    debug_messages = [record.getMessage() for record in caplog.records]
    assert (
        "member 'mode' (environment variable 'EMC_MODE') of 'EnvNamePatternConfiguration': the "
        "process environment provided no value; using the default value"
    ) in debug_messages
