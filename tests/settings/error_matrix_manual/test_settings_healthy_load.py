"""The healthy baseline: every declaration state that is present loads cleanly.

There is one test for each bundled backend. The storage holds all four
members, so the class shape that the failure scenarios break is first seen
working. Each test pins three things: an empty load report, no warnings on
the channel of the package, and every member holding its stored value.
"""

import logging

from settings_healthy_classes import (
    HEALTHY_DOTENV_FILE,
    HEALTHY_JSON_FILE,
    HEALTHY_TOML_FILE,
    HealthyDotenvSettings,
    HealthyEnvSettings,
    HealthyJsonSettings,
    HealthyTomlSettings,
)
from settings_storage_paths import prepare_storage_dir


def test_healthy_load_env_vars(monkeypatch, caplog):
    """All four members present in the process environment."""
    for name in ("EMX_ANSWER", "EMX_PLAIN", "EMX_KNOWN", "EMX_CONTROL"):
        # a variable leaking in from the developer's shell must not feed the test
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMX_ANSWER", "11")
    monkeypatch.setenv("EMX_PLAIN", "22")
    monkeypatch.setenv("EMX_KNOWN", "33")
    monkeypatch.setenv("EMX_CONTROL", "44")

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = HealthyEnvSettings.load_settings()

    assert report == ()
    assert not caplog.records
    assert HealthyEnvSettings.answer == 11
    assert HealthyEnvSettings.plain == 22
    assert HealthyEnvSettings.known == 33
    assert HealthyEnvSettings.control == 44


def test_healthy_load_dotenv(caplog):
    """All four members present in the dotenv file."""
    prepare_storage_dir()
    HEALTHY_DOTENV_FILE.write_text(
        """EMX_ANSWER=11
EMX_PLAIN=22
EMX_KNOWN=33
EMX_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = HealthyDotenvSettings.load_settings()

    assert report == ()
    assert not caplog.records
    assert HealthyDotenvSettings.answer == 11
    assert HealthyDotenvSettings.plain == 22
    assert HealthyDotenvSettings.known == 33
    assert HealthyDotenvSettings.control == 44


def test_healthy_load_json(caplog):
    """All four members present in the JSON file."""
    prepare_storage_dir()
    HEALTHY_JSON_FILE.write_text(
        '{"answer": 11, "plain": 22, "known": 33, "control": 44}',
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = HealthyJsonSettings.load_settings()

    assert report == ()
    assert not caplog.records
    assert HealthyJsonSettings.answer == 11
    assert HealthyJsonSettings.plain == 22
    assert HealthyJsonSettings.known == 33
    assert HealthyJsonSettings.control == 44


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

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        report = HealthyTomlSettings.load_settings()

    assert report == ()
    assert not caplog.records
    assert HealthyTomlSettings.answer == 11
    assert HealthyTomlSettings.plain == 22
    assert HealthyTomlSettings.known == 33
    assert HealthyTomlSettings.control == 44
