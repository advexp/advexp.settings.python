"""Nested environment addressing: partial updates, whole-object forms, round trips.

A member annotated with a dataclass is a nested object; with the family's
``nested_delimiter`` option the environment addresses its fields through
the delimiter (``TEST_EN_DB__PORT``), loading merges them onto the
declared default, saving stores each field in its own variable.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from typing import Optional

import pytest

from advexp.settings import AggregateLoadError, ConversionError, Settings
from advexp.settings.plugins.environment import (
    ENVIRONMENT_METADATA_OPTIONS,
    NESTED_DELIMITER,
    NameCase,
)
from advexp.settings.plugins.environment.variables import env_source, environment_variable_setting
from advexp.settings_base.required import REQUIRED

DELIMITER = "__"

_ENV_NAMES = (
    "TEST_EN_DB",
    "TEST_EN_DB__HOST",
    "TEST_EN_DB__PORT",
    "TEST_EN_DB__FLAG",
    "TEST_EN_DB__DEEP",
    "TEST_EN_DB__DEEP__V4",
    "TEST_EN_PLAIN",
    "TEST_ENN_DB__HOST",
    "TEST_ENN_DB__PORT",
    "TEST_ENL_db__host",
    "TEST_ENL_db__port",
    "TEST_ENR_DB__HOST",
    "TEST_ENR_DB__PORT",
    "TEST_ENR_STRICT__HOST",
    "TEST_ENR_STRICT__PORT",
    "TEST_EN_CHILD_EXTRA__PORT",
    "my_db__HOST",
    "my_db__PORT",
    "TEST_ENA_DB",
    "TEST_ENA_DB__HOST",
    "TEST_ENA_DB__PORT",
    "test_ena_db__host",
    "Test_Ena_Db__Port",
    "TEST_ENA_db__port",
    "TEST_ENA_db__deep__v4",
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


class NestedSettings(
    Settings,
    options=env_source(
        name_prefix="TEST_EN_",
        name_case=NameCase.UPPER,
        nested_delimiter=DELIMITER,
    ),
):
    db: Db = environment_variable_setting(default=Db(host="declared-host"))
    plain: str = environment_variable_setting(default="plain-default")


class NoDefaultSettings(
    Settings,
    options=env_source(
        name_prefix="TEST_ENN_",
        name_case=NameCase.UPPER,
        nested_delimiter=DELIMITER,
    ),
):
    db: Db = environment_variable_setting()  # no default: None stands in


class LowerCaseSettings(
    Settings,
    options=env_source(
        name_prefix="TEST_ENL_",
        name_case=NameCase.LOWER,
        nested_delimiter=DELIMITER,
    ),
):
    db: Db = environment_variable_setting(default=Db())


class NamedSettings(
    Settings,
    options=env_source(name_case=NameCase.UPPER, nested_delimiter=DELIMITER),
):
    db: Db = environment_variable_setting(name="my_db", default=Db())


@dataclasses.dataclass
class Strict:
    host: str  # no default: the environment alone must supply it
    port: int = 5432


class RequiredSettings(
    Settings,
    options=env_source(
        name_prefix="TEST_ENR_",
        name_case=NameCase.UPPER,
        nested_delimiter=DELIMITER,
    ),
):
    db: Db = environment_variable_setting(default=REQUIRED)
    strict: Strict = environment_variable_setting(default=REQUIRED)


class FlatSettings(
    Settings,
    options=env_source(name_prefix="TEST_EN_", name_case=NameCase.UPPER),
):
    db: Db = environment_variable_setting(default=Db(host="declared-host"))


class AnyCaseNestedSettings(
    Settings,
    options=env_source(
        name_prefix="TEST_ENA_",
        name_case=NameCase.ANY,
        nested_delimiter=DELIMITER,
    ),
):
    db: Db = environment_variable_setting(default=Db(host="declared-host"))


class ChildSettings(
    NestedSettings,
    options=env_source(
        name_prefix="TEST_EN_CHILD_",
        name_case=NameCase.UPPER,
        nested_delimiter=DELIMITER,
    ),
):
    extra: Db = environment_variable_setting(default=Db())


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    yield


def test_one_variable_updates_one_field_the_rest_stays_declared(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB__PORT", "6543")

    NestedSettings.load_settings()

    # the declared default instance is the base: host keeps its declared
    # value, only the addressed field moves
    assert NestedSettings.db == Db(host="declared-host", port=6543)


def test_without_a_declared_default_the_dataclass_defaults_fill(monkeypatch):
    monkeypatch.setenv("TEST_ENN_DB__PORT", "1")

    NoDefaultSettings.load_settings()

    assert NoDefaultSettings.db == Db(port=1)


def test_field_variables_win_over_the_whole_object_form(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB", '{"host": "json-host", "port": 1}')
    monkeypatch.setenv("TEST_EN_DB__PORT", "2")

    NestedSettings.load_settings()

    assert NestedSettings.db.host == "json-host"
    assert NestedSettings.db.port == 2


def test_whole_object_form_merges_onto_the_default_too(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB", '{"port": 7}')

    NestedSettings.load_settings()

    assert NestedSettings.db == Db(host="declared-host", port=7)


def test_addresses_descend_to_any_depth(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB__DEEP__V4", "leaf")
    NestedSettings.load_settings()
    assert NestedSettings.db.deep == Deep(v4="leaf")

    NestedSettings.reset_settings()
    monkeypatch.delenv("TEST_EN_DB__DEEP__V4")
    monkeypatch.setenv("TEST_EN_DB__DEEP", '{"v4": "whole"}')
    NestedSettings.load_settings()
    assert NestedSettings.db.deep == Deep(v4="whole")
    assert NestedSettings.db.host == "declared-host"


def test_broken_whole_object_form_falls_back_with_a_report(monkeypatch, caplog):
    monkeypatch.setenv("TEST_EN_DB", "not-an-object")
    monkeypatch.setenv("TEST_EN_DB__PORT", "6543")
    caplog.set_level(logging.WARNING, logger="advexp.settings")

    NestedSettings.load_settings()

    assert NestedSettings.db == Db(host="declared-host")
    assert any("cannot convert" in record.message for record in caplog.records)


def test_without_the_delimiter_the_member_stays_flat(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB__PORT", "6543")

    FlatSettings.load_settings()

    # no delimiter option: the variable addresses nothing and the member
    # keeps its default
    assert FlatSettings.db == Db(host="declared-host")

    monkeypatch.delenv("TEST_EN_DB__PORT")
    monkeypatch.setenv("TEST_EN_DB", '{"port": 9}')
    FlatSettings.load_settings()
    assert FlatSettings.db.port == 9


def test_explicit_name_is_the_nested_base(monkeypatch):
    monkeypatch.setenv("my_db__PORT", "7")

    NamedSettings.load_settings()

    assert NamedSettings.db.port == 7


def test_the_case_option_applies_to_the_field_parts(monkeypatch):
    monkeypatch.setenv("TEST_ENL_db__port", "9")

    LowerCaseSettings.load_settings()

    assert LowerCaseSettings.db.port == 9


def test_required_member_builds_from_field_variables(monkeypatch):
    monkeypatch.setenv("TEST_ENR_DB__HOST", "req-host")
    monkeypatch.setenv("TEST_ENR_DB__PORT", "1")
    monkeypatch.setenv("TEST_ENR_STRICT__HOST", "strict-host")

    report = RequiredSettings.load_settings()

    # both members are required and both found their fields: a clean load
    # reports nothing
    assert report == ()
    assert RequiredSettings.db == Db(host="req-host", port=1)
    assert RequiredSettings.strict == Strict(host="strict-host")


def test_required_member_with_missing_fields_aborts_the_load(monkeypatch):
    # Strict.host has no default of its own and the environment does not
    # supply it: the object cannot be built, and a required member that
    # cannot be built aborts the load
    monkeypatch.setenv("TEST_ENR_DB__HOST", "req-host")
    monkeypatch.setenv("TEST_ENR_STRICT__PORT", "1")

    with pytest.raises(AggregateLoadError) as info:
        RequiredSettings.load_settings()

    kinds = [type(entry) for entry in info.value.errors]
    assert kinds == [ConversionError]
    assert "missing field 'host'" in str(info.value.errors[0])


def test_save_writes_each_field_and_drops_the_whole_object_variable(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB", '{"host": "stale"}')
    NestedSettings.db = Db(host="h", port=1, flag=True, deep=Deep(v4="z"))

    NestedSettings.save_settings()

    assert "TEST_EN_DB" not in os.environ
    assert os.environ["TEST_EN_DB__HOST"] == "h"
    assert os.environ["TEST_EN_DB__PORT"] == "1"
    assert os.environ["TEST_EN_DB__FLAG"] == "True"
    assert os.environ["TEST_EN_DB__DEEP__V4"] == "z"

    NestedSettings.reset_settings()
    NestedSettings.load_settings()
    assert NestedSettings.db == Db(host="h", port=1, flag=True, deep=Deep(v4="z"))


def test_save_unsets_none_fields(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB__FLAG", "True")
    NestedSettings.db = Db(host="h")

    NestedSettings.save_settings()

    assert "TEST_EN_DB__FLAG" not in os.environ


def test_delete_drops_the_whole_subtree(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB", '{"host": "whole"}')
    monkeypatch.setenv("TEST_EN_DB__DEEP", '{"v4": "mid"}')
    monkeypatch.setenv("TEST_EN_DB__PORT", "1")

    NestedSettings.delete_settings()

    assert not [name for name in os.environ if name.startswith("TEST_EN_DB")]
    assert NestedSettings.db == Db(host="declared-host")


def test_contains_sees_the_nested_addresses(monkeypatch):
    assert not NestedSettings.contains_setting(lambda s: s.db)

    monkeypatch.setenv("TEST_EN_DB__PORT", "6543")
    assert NestedSettings.contains_setting(lambda s: s.db)

    NestedSettings.delete_setting(lambda s: s.db)
    assert not NestedSettings.contains_setting(lambda s: s.db)


def test_subclass_options_do_not_move_inherited_addresses(monkeypatch):
    monkeypatch.setenv("TEST_EN_DB__PORT", "5")
    monkeypatch.setenv("TEST_EN_CHILD_EXTRA__PORT", "6")

    ChildSettings.load_settings()

    assert ChildSettings.db == Db(host="declared-host", port=5)
    assert ChildSettings.extra == Db(port=6)


def test_the_delimiter_option_lands_in_the_stored_entry():
    entry = env_source(nested_delimiter=DELIMITER)[ENVIRONMENT_METADATA_OPTIONS]
    assert entry[NESTED_DELIMITER] == DELIMITER


# -- name_case=NameCase.ANY over nested addresses --------------------------


def test_any_reads_a_field_address_in_any_spelling(monkeypatch):
    monkeypatch.setenv("test_ena_db__host", "any-host")

    AnyCaseNestedSettings.load_settings()

    # the field address resolves case-insensitively; the rest stays declared
    assert AnyCaseNestedSettings.db == Db(host="any-host")


def test_any_save_touches_found_spellings_and_writes_new_ones_built(monkeypatch):
    monkeypatch.setenv("test_ena_db__host", "stale")

    AnyCaseNestedSettings.db = Db(host="new-host", port=7000)
    AnyCaseNestedSettings.save_settings()

    # the found spelling is updated; an address with no spelling lands
    # built — under ANY as declared, the member and the field as written
    assert os.environ["test_ena_db__host"] == "new-host"
    assert os.environ["TEST_ENA_db__port"] == "7000"
    assert "TEST_ENA_db" not in os.environ


def test_any_delete_drops_the_found_spellings_of_the_subtree(monkeypatch):
    monkeypatch.setenv("Test_Ena_Db__Port", "1")
    assert AnyCaseNestedSettings.contains_setting("db")

    AnyCaseNestedSettings.delete_setting("db")

    assert not [name for name in os.environ if name.upper().startswith("TEST_ENA_DB")]
