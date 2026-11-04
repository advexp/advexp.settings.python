"""The healthy baseline: every declaration state that is present loads cleanly.

There is one test for each bundled backend. The storage holds all four
members, so the class shape that the failure scenarios break is first seen
working. Each test pins three things: an empty load report, no warnings on
the channel of the package, and every member holding its stored value.
"""

import logging

from configuration_healthy_classes import (
    HEALTHY_DOTENV_FILE,
    HEALTHY_JSON_FILE,
    HEALTHY_TOML_FILE,
    HealthyDotenvConfiguration,
    HealthyEnvConfiguration,
    HealthyJsonConfiguration,
    HealthyTomlConfiguration,
)
from configuration_storage_paths import prepare_storage_dir


def test_healthy_load_env_vars(monkeypatch, caplog):
    """All four members present in the process environment."""
    for name in ("EMC_ANSWER", "EMC_PLAIN", "EMC_KNOWN", "EMC_CONTROL"):
        # a variable leaking in from the developer's shell must not feed the test
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMC_ANSWER", "11")
    monkeypatch.setenv("EMC_PLAIN", "22")
    monkeypatch.setenv("EMC_KNOWN", "33")
    monkeypatch.setenv("EMC_CONTROL", "44")

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = HealthyEnvConfiguration.load_configuration()

    assert report == ()
    assert not caplog.records
    assert HealthyEnvConfiguration.answer == 11
    assert HealthyEnvConfiguration.plain == 22
    assert HealthyEnvConfiguration.known == 33
    assert HealthyEnvConfiguration.control == 44


def test_healthy_load_dotenv(caplog):
    """All four members present in the dotenv file."""
    prepare_storage_dir()
    HEALTHY_DOTENV_FILE.write_text(
        """EMC_ANSWER=11
EMC_PLAIN=22
EMC_KNOWN=33
EMC_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = HealthyDotenvConfiguration.load_configuration()

    assert report == ()
    assert not caplog.records
    assert HealthyDotenvConfiguration.answer == 11
    assert HealthyDotenvConfiguration.plain == 22
    assert HealthyDotenvConfiguration.known == 33
    assert HealthyDotenvConfiguration.control == 44


def test_healthy_load_json(caplog):
    """All four members present in the JSON file."""
    prepare_storage_dir()
    HEALTHY_JSON_FILE.write_text(
        '{"answer": 11, "plain": 22, "known": 33, "control": 44}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = HealthyJsonConfiguration.load_configuration()

    assert report == ()
    assert not caplog.records
    assert HealthyJsonConfiguration.answer == 11
    assert HealthyJsonConfiguration.plain == 22
    assert HealthyJsonConfiguration.known == 33
    assert HealthyJsonConfiguration.control == 44


def test_healthy_load_toml(caplog):
    """All four members present in the TOML file."""
    prepare_storage_dir()
    HEALTHY_TOML_FILE.write_text(
        """answer = 11
plain = 22
known = 33
control = 44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        report = HealthyTomlConfiguration.load_configuration()

    assert report == ()
    assert not caplog.records
    assert HealthyTomlConfiguration.answer == 11
    assert HealthyTomlConfiguration.plain == 22
    assert HealthyTomlConfiguration.known == 33
    assert HealthyTomlConfiguration.control == 44
