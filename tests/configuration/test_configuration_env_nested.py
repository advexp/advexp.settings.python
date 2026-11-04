"""Nested environment addressing of the configuration source.

The read-only environment source resolves the same variables the settings
backend does: a dataclass member's fields arrive through the family's
``nested_delimiter`` and merge onto the declared default.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import pytest

from advexp.configuration import Configuration
from advexp.configuration.plugins.environment import NameCase
from advexp.configuration.plugins.environment.variables import (
    env_source,
    environment_variable_setting,
)

DELIMITER = "__"

_ENV_NAMES = (
    "TEST_CEN_DB",
    "TEST_CEN_DB__HOST",
    "TEST_CEN_DB__PORT",
    "TEST_CEN_DB__FLAG",
    "TEST_CEN_DB__DEEP",
    "TEST_CEN_DB__DEEP__V4",
    "TEST_CEN_MODE",
    "TEST_CEN_REQ__HOST",
    "TEST_CEN_REQ__PORT",
    "TEST_CENA_DB",
    "test_cena_db__host",
)


@dataclasses.dataclass
class Deep:
    v4: str = "v4-default"


@dataclasses.dataclass
class Db:
    host: str = "localhost"
    port: int = 5432
    flag: Optional[bool] = None
    deep: Deep = dataclasses.field(default_factory=Deep)


class AppConfig(
    Configuration,
    options=env_source(
        name_prefix="TEST_CEN_",
        name_case=NameCase.UPPER,
        nested_delimiter=DELIMITER,
    ),
):
    db: Db = environment_variable_setting(default=Db(host="declared-host"))
    mode: str = environment_variable_setting(default="production")


class RequiredConfig(
    Configuration,
    options=env_source(
        name_prefix="TEST_CEN_",
        name_case=NameCase.UPPER,
        nested_delimiter=DELIMITER,
    ),
):
    req: Db = environment_variable_setting()  # required: no stand-in value


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    yield


def test_one_variable_updates_one_field_the_rest_stays_declared(monkeypatch):
    monkeypatch.setenv("TEST_CEN_DB__PORT", "6543")

    AppConfig.load_configuration()

    assert AppConfig.db == Db(host="declared-host", port=6543)


def test_field_variables_win_over_the_whole_object_form(monkeypatch):
    monkeypatch.setenv("TEST_CEN_DB", '{"host": "json-host", "port": 1}')
    monkeypatch.setenv("TEST_CEN_DB__PORT", "2")

    AppConfig.load_configuration()

    assert AppConfig.db.host == "json-host"
    assert AppConfig.db.port == 2


def test_required_member_builds_from_field_variables(monkeypatch):
    monkeypatch.setenv("TEST_CEN_REQ__HOST", "req-host")
    monkeypatch.setenv("TEST_CEN_REQ__PORT", "1")

    RequiredConfig.load_configuration()

    assert RequiredConfig.req == Db(host="req-host", port=1)


# -- name_case=NameCase.ANY over nested addresses --------------------------


class AnyCaseConfig(
    Configuration,
    options=env_source(
        name_prefix="TEST_CENA_",
        name_case=NameCase.ANY,
        nested_delimiter=DELIMITER,
    ),
):
    db: Db = environment_variable_setting(default=Db(host="declared-host"))


def test_any_reads_a_field_address_in_any_spelling(monkeypatch):
    # the whole address — the prefix, the member and the field — is matched
    # case-insensitively
    monkeypatch.setenv("test_cena_db__host", "any-host")

    AnyCaseConfig.load_configuration()

    assert AnyCaseConfig.db == Db(host="any-host")
