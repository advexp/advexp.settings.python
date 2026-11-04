"""Environment family naming options: prefix and case through class metadata."""

from __future__ import annotations

import os
import re

import pytest

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings.plugin_api import family_entry_key
from advexp.settings.plugins.environment import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NESTED_DELIMITER,
    NameCase,
)
from advexp.settings.plugins.environment.variables import env_source, environment_variable_setting
from advexp.settings_base.environment_options import check_environment_options
from advexp.settings_base.sources import ENVIRONMENT_SOURCE_METADATA

_ENV_NAMES = (
    "TEST_EO_MODE",
    "TEST_EO_CACHE_TTL",
    "TEST_EO_DBHOST",
    "TEST_EO_EXTRA",
    "ENUM_MODE",
    "STR_MODE",
    "legacy_flag",
    "LEGACY_FLAG",
    "Legacy_Flag",
    "CHILD_mode",
    "RT_mode",
    "RT_BASE_mode",
    "RT_FOR_mode",
    "MIX_extra",
    "MIXIN_mode",
    "REMIX_mode",
    "mode",
    "MODE",
    "Mode",
    "MoDe",
)


class PrefixedSettings(
    Settings,
    options=env_source(name_prefix="TEST_EO_", name_case=NameCase.UPPER),
):
    mode: str = environment_variable_setting(default="production")  # TEST_EO_MODE
    cache_ttl: int = environment_variable_setting(default=300)  # TEST_EO_CACHE_TTL
    dbHost: str = environment_variable_setting(default="localhost")  # TEST_EO_DBHOST
    legacy: str = environment_variable_setting(name="legacy_flag", default="off")


class AnyCaseSettings(
    Settings,
    options=env_source(name_case=NameCase.ANY),
):
    mode: str = environment_variable_setting(default="production")
    legacy: str = environment_variable_setting(name="legacy_flag", default="off")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    yield


def test_import_registers_the_family_validator():
    validator = LibraryConfiguration._get_class_metadata_validator(ENVIRONMENT_METADATA_OPTIONS)
    assert validator is check_environment_options


def test_prefix_and_case_build_the_variable_name(monkeypatch):
    monkeypatch.setenv("TEST_EO_MODE", "staging")
    PrefixedSettings.load_settings()
    assert PrefixedSettings.mode == "staging"


def test_save_contains_and_delete_use_the_same_name():
    PrefixedSettings.cache_ttl = 120
    PrefixedSettings.save_settings()
    assert os.environ["TEST_EO_CACHE_TTL"] == "120"
    assert PrefixedSettings.contains_setting("cache_ttl") is True

    PrefixedSettings.delete_setting("cache_ttl")
    assert "TEST_EO_CACHE_TTL" not in os.environ
    assert PrefixedSettings.cache_ttl == 300  # back to the default


def test_case_touches_the_member_name_alone():
    # no camel-to-snake: dbHost under "upper" is DBHOST, the prefix keeps its spelling
    PrefixedSettings.dbHost = "db.example.com"
    PrefixedSettings.save_setting("dbHost")
    assert os.environ["TEST_EO_DBHOST"] == "db.example.com"


def test_explicit_name_is_the_full_address(monkeypatch):
    monkeypatch.setenv("legacy_flag", "on")
    PrefixedSettings.load_settings()
    assert PrefixedSettings.legacy == "on"

    PrefixedSettings.legacy = "maybe"
    PrefixedSettings.save_settings()
    assert os.environ["legacy_flag"] == "maybe"
    assert "TEST_EO_LEGACY" not in os.environ


def test_lower_case_option(monkeypatch):
    class LowerSettings(Settings):
        class_metadata = env_source(name_case=NameCase.LOWER)

        Mode: str = environment_variable_setting(default="x")

    monkeypatch.setenv("mode", "lowered")
    LowerSettings.load_settings()
    assert LowerSettings.Mode == "lowered"


def test_without_options_names_stay_as_written(monkeypatch):
    class PlainSettings(Settings):
        mode: str = environment_variable_setting(default="production")

    monkeypatch.setenv("mode", "dev")
    PlainSettings.load_settings()
    assert PlainSettings.mode == "dev"


def test_runtime_change_of_options_changes_names(monkeypatch):
    # the flat family key addresses the class's OWN entry; the subclass
    # declares its own member, whose variable the runtime entry builds
    class RuntimeSettings(PrefixedSettings):
        own: str = environment_variable_setting(default="x")

    RuntimeSettings.set_class_metadata(ENVIRONMENT_METADATA_OPTIONS, {NAME_PREFIX: "RT_"})
    # the stored entry is replaced wholesale: no case was set, so the
    # member name keeps its spelling
    monkeypatch.setenv("RT_own", "runtime")
    RuntimeSettings.load_settings()
    assert RuntimeSettings.own == "runtime"


def test_runtime_flat_set_of_a_subclass_touches_only_its_own_members(monkeypatch):
    class SubSettings(PrefixedSettings):
        extra: str = environment_variable_setting(default="e")

    SubSettings.set_class_metadata(ENVIRONMENT_METADATA_OPTIONS, {NAME_PREFIX: "SUB_"})
    # the subclass's own member resolves by the subclass's own entry
    monkeypatch.setenv("SUB_extra", "own")
    SubSettings.load_settings()
    assert SubSettings.extra == "own"
    # the inherited member keeps the base's variable: it was declared there
    monkeypatch.setenv("TEST_EO_MODE", "inherited")
    SubSettings.load_settings()
    assert SubSettings.mode == "inherited"


def test_runtime_invalid_options_rejected_before_storing():
    class GuardedSettings(PrefixedSettings):
        pass

    with pytest.raises(
        TypeError,
        match=rf"GuardedSettings\.class_metadata\['{ENVIRONMENT_METADATA_OPTIONS}\.",
    ):
        GuardedSettings.set_class_metadata(ENVIRONMENT_METADATA_OPTIONS, {NAME_CASE: "shout"})
    # the previous state stands
    assert GuardedSettings.get_class_metadata(ENVIRONMENT_METADATA_OPTIONS) == {
        NAME_PREFIX: "TEST_EO_",
        NAME_CASE: "upper",
        NESTED_DELIMITER: None,
    }


@pytest.mark.parametrize(
    "options",
    [
        {NAME_CASE: "shout"},
        {NAME_PREFIX: ""},
        {NAME_PREFIX: 7},
        {NAME_PREFIX: "APP_", "name_prefx": "typo"},
        {NESTED_DELIMITER: ""},
        {NESTED_DELIMITER: 7},
        "nope",
    ],
    ids=[
        "bad-case",
        "empty-prefix",
        "non-string-prefix",
        "unknown-option",
        "empty-delimiter",
        "non-string-delimiter",
        "non-mapping",
    ],
)
def test_invalid_declaration_fails_the_class_statement(options):
    with pytest.raises(
        TypeError, match=rf"Broken\.class_metadata\['{ENVIRONMENT_METADATA_OPTIONS}\."
    ):

        class Broken(Settings):
            class_metadata = {ENVIRONMENT_METADATA_OPTIONS: options}
            mode: str = environment_variable_setting(default="x")


def test_subclass_inherits_the_family_options(monkeypatch):
    class ChildSettings(PrefixedSettings):
        extra: str = environment_variable_setting(default="e")

    monkeypatch.setenv("TEST_EO_EXTRA", "child")
    ChildSettings.load_settings()
    assert ChildSettings.extra == "child"


def test_member_without_own_entry_takes_the_nearest_above(monkeypatch):
    # the resolution rule: a member of a class that declared no options of
    # its own resolves by the nearest entry above the declaring class
    class MiddleSettings(PrefixedSettings):
        port: int = environment_variable_setting(default=8080)

    class LeafSettings(
        MiddleSettings,
        options=env_source(name_prefix="LEAF_"),
    ):
        # "port" was declared in MiddleSettings — the base's entry governs it
        pass

    monkeypatch.setenv("TEST_EO_PORT", "9090")
    LeafSettings.load_settings()
    assert LeafSettings.port == 9090


def test_subclass_own_options_coexist_with_the_base_entry(monkeypatch):
    class ChildSettings(PrefixedSettings):
        class_metadata = env_source(name_prefix="CHILD_")
        extra: str = environment_variable_setting(default="e")

    # the subclass's own entry governs the subclass's own members
    monkeypatch.setenv("CHILD_extra", "own")
    ChildSettings.load_settings()
    assert ChildSettings.extra == "own"

    # the inherited member keeps the base's variable: it was declared there,
    # and the base's entry is not replaced by the subclass's own one
    monkeypatch.setenv("TEST_EO_MODE", "inherited")
    ChildSettings.load_settings()
    assert ChildSettings.mode == "inherited"

    # the base class keeps its own entry
    assert PrefixedSettings.get_class_metadata(ENVIRONMENT_METADATA_OPTIONS) == {
        NAME_PREFIX: "TEST_EO_",
        NAME_CASE: "upper",
        NESTED_DELIMITER: None,
    }


def test_runtime_retune_of_the_base_reaches_inherited_members(monkeypatch):
    # the chain resolves live: a runtime write into the base's own entry
    # rebuilds the inherited members' variables in every subclass
    class ChildSettings(PrefixedSettings):
        pass

    try:
        PrefixedSettings.set_class_metadata(ENVIRONMENT_METADATA_OPTIONS, {NAME_PREFIX: "RT_BASE_"})
        monkeypatch.setenv("RT_BASE_mode", "retuned")
        ChildSettings.load_settings()
        assert ChildSettings.mode == "retuned"
    finally:
        PrefixedSettings.set_class_metadata(
            ENVIRONMENT_METADATA_OPTIONS,
            env_source(name_prefix="TEST_EO_", name_case=NameCase.UPPER)[
                ENVIRONMENT_METADATA_OPTIONS
            ],
        )


def test_subclass_delete_of_its_own_family_entry_falls_back_to_the_base(monkeypatch):
    class ChildSettings(PrefixedSettings):
        extra: str = environment_variable_setting(default="e")

    ChildSettings.set_class_metadata(ENVIRONMENT_METADATA_OPTIONS, {NAME_PREFIX: "CHILD_"})
    ChildSettings.delete_class_metadata(ENVIRONMENT_METADATA_OPTIONS)

    # no own entry anymore: the base's entry builds the member's name again
    monkeypatch.setenv("TEST_EO_EXTRA", "fallback")
    ChildSettings.load_settings()
    assert ChildSettings.extra == "fallback"


def test_chain_snapshot_lists_both_family_entries():
    class ChildSettings(
        PrefixedSettings,
        options=env_source(name_prefix="CHILD_"),
    ):
        pass

    # the composite keys keep the base's entries and the subclass's apart
    # in the merged snapshot, the source seats among them
    snapshot = ChildSettings.get_class_all_metadata()
    assert snapshot[family_entry_key(ENVIRONMENT_METADATA_OPTIONS, PrefixedSettings)] == {
        NAME_PREFIX: "TEST_EO_",
        NAME_CASE: "upper",
        NESTED_DELIMITER: None,
    }
    assert snapshot[family_entry_key(ENVIRONMENT_METADATA_OPTIONS, ChildSettings)] == {
        NAME_PREFIX: "CHILD_",
        NAME_CASE: None,
        NESTED_DELIMITER: None,
    }
    assert family_entry_key(ENVIRONMENT_SOURCE_METADATA, ChildSettings) in snapshot


def test_the_builder_seats_the_link_beside_the_naming_dictionary():
    # no naming declared: the link alone, no dictionary entry
    assert set(dict(env_source())) == {ENVIRONMENT_SOURCE_METADATA}
    entry = dict(env_source(name_prefix="APP_", name_case=NameCase.UPPER))
    assert set(entry) == {ENVIRONMENT_SOURCE_METADATA, ENVIRONMENT_METADATA_OPTIONS}
    assert entry[ENVIRONMENT_METADATA_OPTIONS] == {
        NAME_PREFIX: "APP_",
        NAME_CASE: "upper",
        NESTED_DELIMITER: None,
    }


def test_helper_rejects_an_invalid_delimiter():
    with pytest.raises(TypeError, match=NESTED_DELIMITER):
        env_source(nested_delimiter="")


def test_enum_members_normalize_to_the_stored_string_form(monkeypatch):
    class EnumSpelledSettings(Settings):
        class_metadata = env_source(name_prefix="ENUM_", name_case=NameCase.UPPER)

        mode: str = environment_variable_setting(default="x")

    monkeypatch.setenv("ENUM_MODE", "enum")
    EnumSpelledSettings.load_settings()
    assert EnumSpelledSettings.mode == "enum"
    assert EnumSpelledSettings.get_class_metadata(ENVIRONMENT_METADATA_OPTIONS) == {
        NAME_PREFIX: "ENUM_",
        NAME_CASE: "upper",
        NESTED_DELIMITER: None,
    }

    # a hand-written runtime entry with a member passes the validator, and the
    # case option applies
    class RuntimeEnumSettings(Settings):
        mode: str = environment_variable_setting(default="x")

    RuntimeEnumSettings.set_class_metadata(
        ENVIRONMENT_METADATA_OPTIONS, {NAME_CASE: NameCase.LOWER}
    )
    monkeypatch.setenv("mode", "lowered")
    RuntimeEnumSettings.load_settings()
    assert RuntimeEnumSettings.mode == "lowered"


def test_the_plain_string_is_the_data_form_of_the_raw_channel(monkeypatch):
    # the helper takes the enum; the raw metadata channel takes data — a
    # hand-written entry with the stored string spelling works the same way
    class StringSpelledSettings(Settings):
        class_metadata = {ENVIRONMENT_METADATA_OPTIONS: {NAME_PREFIX: "STR_", NAME_CASE: "upper"}}

        mode: str = environment_variable_setting(default="x")

    monkeypatch.setenv("STR_MODE", "string")
    StringSpelledSettings.load_settings()
    assert StringSpelledSettings.mode == "string"


def test_options_helper_validates_eagerly():
    # the case is the enum's alone at the helper: a string is not accepted
    with pytest.raises(TypeError, match=f"{NAME_CASE} must be None or a NameCase member"):
        env_source(name_case="upper")
    with pytest.raises(TypeError, match=f"{NAME_CASE} must be None or a NameCase member"):
        env_source(name_case="shout")
    with pytest.raises(TypeError, match=NAME_PREFIX):
        env_source(name_prefix="")


# -- name_case=NameCase.ANY ------------------------------------------------


def test_any_keeps_the_stored_and_the_raw_channel_forms(monkeypatch):
    assert AnyCaseSettings.get_class_metadata(ENVIRONMENT_METADATA_OPTIONS) == {
        NAME_PREFIX: None,
        NAME_CASE: "any",
        NESTED_DELIMITER: None,
    }

    # a hand-written entry with the stored string spelling works the same way
    class StringAnySettings(Settings):
        class_metadata = {ENVIRONMENT_METADATA_OPTIONS: {NAME_CASE: "any"}}
        mode: str = environment_variable_setting(default="x")

    monkeypatch.setenv("MODE", "string")
    StringAnySettings.load_settings()
    assert StringAnySettings.mode == "string"


@pytest.mark.parametrize("spelling", ["MODE", "Mode", "MoDe"])
def test_any_loads_any_spelling_of_the_built_name(monkeypatch, spelling):
    monkeypatch.setenv(spelling, "any-case")
    AnyCaseSettings.load_settings()
    assert AnyCaseSettings.mode == "any-case"


def test_any_loads_any_spelling_of_an_explicit_name(monkeypatch):
    monkeypatch.setenv("LEGACY_FLAG", "on")
    AnyCaseSettings.load_settings()
    assert AnyCaseSettings.legacy == "on"


def test_any_without_a_spelling_is_a_plain_miss():
    AnyCaseSettings.load_settings()
    assert AnyCaseSettings.mode == "production"


def test_any_exact_spelling_wins_silently(monkeypatch):
    monkeypatch.setenv("mode", "exact")
    monkeypatch.setenv("MODE", "folded")
    AnyCaseSettings.load_settings()
    assert AnyCaseSettings.mode == "exact"


def test_any_two_folded_spellings_fail_the_load(monkeypatch):
    monkeypatch.setenv("MODE", "one")
    monkeypatch.setenv("Mode", "two")
    with pytest.raises(
        ValueError,
        match=re.escape(
            "the process environment holds two differently-cased spellings of "
            "the environment variable ('MODE' and 'Mode'); the lookup cannot "
            f"choose between them — remove one spelling or set {NAME_CASE} to "
            "the exact case"
        ),
    ):
        AnyCaseSettings.load_settings()


def test_any_save_and_delete_touch_the_found_spelling(monkeypatch):
    monkeypatch.setenv("MODE", "stale")
    AnyCaseSettings.mode = "staging"
    AnyCaseSettings.save_settings()
    assert os.environ["MODE"] == "staging"
    assert "mode" not in os.environ
    assert AnyCaseSettings.contains_setting("mode") is True

    AnyCaseSettings.delete_setting("mode")
    assert "MODE" not in os.environ


def test_any_save_of_a_new_variable_lands_under_the_built_name():
    # save_settings() writes into the real process environment: the autouse
    # fixture cleans variables only before the test, so the created spelling
    # is removed here, not left for the tests that run afterwards
    try:
        AnyCaseSettings.mode = "staging"
        AnyCaseSettings.save_settings()
        assert os.environ["mode"] == "staging"
    finally:
        del os.environ["mode"]
