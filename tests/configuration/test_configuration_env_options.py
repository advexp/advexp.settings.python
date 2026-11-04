"""Environment family naming options in the configuration source."""

from __future__ import annotations

import re

import pytest

from advexp.configuration import AggregateLoadError, Configuration
from advexp.configuration.plugins.environment import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NameCase,
)
from advexp.configuration.plugins.environment.variables import (
    env_source,
    environment_variable_setting,
)

_ENV_NAMES = (
    "TEST_ACP_HOST",
    "TEST_ACP_CACHE_TTL",
    "TEST_ACP_DBHOST",
    "legacy_flag",
    "LEGACY_FLAG",
    "Legacy_Flag",
    "mode",
    "Mode",
    "host",
    "HOST",
    "Host",
    "HoSt",
)


class PrefixedConfig(
    Configuration,
    options=env_source(name_prefix="TEST_ACP_", name_case=NameCase.UPPER),
):
    host: str = environment_variable_setting()  # TEST_ACP_HOST, required
    cache_ttl: int = environment_variable_setting(default=300)  # TEST_ACP_CACHE_TTL
    dbHost: str = environment_variable_setting(default="localhost")  # TEST_ACP_DBHOST
    legacy: str = environment_variable_setting(name="legacy_flag", default="off")


class AnyCaseConfig(
    Configuration,
    options=env_source(name_case=NameCase.ANY),
):
    host: str = environment_variable_setting()  # host, required
    legacy: str = environment_variable_setting(name="legacy_flag", default="off")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    yield


def test_prefix_and_case_build_the_variable_name(monkeypatch):
    monkeypatch.setenv("TEST_ACP_HOST", "db.example.com")
    PrefixedConfig.load_configuration()
    assert PrefixedConfig.host == "db.example.com"


def test_default_stands_in_when_the_variable_is_missing(monkeypatch):
    # host is required: the load needs its variable, the rest take defaults
    monkeypatch.setenv("TEST_ACP_HOST", "db.example.com")
    PrefixedConfig.load_configuration()
    assert PrefixedConfig.host == "db.example.com"
    assert PrefixedConfig.cache_ttl == 300


def test_case_touches_the_member_name_alone(monkeypatch):
    monkeypatch.setenv("TEST_ACP_HOST", "db.example.com")
    # no camel-to-snake: dbHost under "upper" is DBHOST, the prefix keeps its spelling
    monkeypatch.setenv("TEST_ACP_DBHOST", "db.example.com")
    PrefixedConfig.load_configuration()
    assert PrefixedConfig.dbHost == "db.example.com"


def test_explicit_name_is_the_full_address(monkeypatch):
    monkeypatch.setenv("TEST_ACP_HOST", "db.example.com")
    monkeypatch.setenv("legacy_flag", "on")
    PrefixedConfig.load_configuration()
    assert PrefixedConfig.legacy == "on"


def test_missing_required_variable_names_it_in_the_abort(monkeypatch):
    # host is required and its variable is built from the options: the abort
    # must say the variable's name, not the pattern-built storage name
    # (the module-qualified one), which the environment never reads
    with pytest.raises(AggregateLoadError) as info:
        PrefixedConfig.load_configuration()
    message = str(info.value)
    assert "environment variable 'TEST_ACP_HOST'" in message
    assert f"of '{PrefixedConfig.__name__}'" in message
    assert PrefixedConfig.__module__ not in message


def test_a_link_without_naming_keeps_names_as_written(monkeypatch):
    class PlainConfig(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(default="production")

    monkeypatch.setenv("mode", "dev")
    PlainConfig.load_configuration()
    assert PlainConfig.mode == "dev"


def test_same_options_same_names_as_the_settings_family(monkeypatch):
    # the vocabulary is the family's shared one: a settings class and a
    # configuration class with the same options read one variable
    from advexp.settings import Settings
    from advexp.settings.plugins.environment.variables import env_source
    from advexp.settings.plugins.environment.variables import (
        environment_variable_setting as setting,
    )

    class SameNamesSettings(Settings):
        class_metadata = env_source(name_prefix="TEST_ACP_", name_case=NameCase.UPPER)

        host: str = setting(default="fallback")

    monkeypatch.setenv("TEST_ACP_HOST", "shared.example.com")
    PrefixedConfig.load_configuration()
    SameNamesSettings.load_settings()
    assert PrefixedConfig.host == SameNamesSettings.host == "shared.example.com"


def test_lower_case_option(monkeypatch):
    class LowerConfig(
        Configuration,
        options=env_source(name_case=NameCase.LOWER),
    ):
        Mode: str = environment_variable_setting(default="x")

    monkeypatch.setenv("mode", "lowered")
    LowerConfig.load_configuration()
    assert LowerConfig.Mode == "lowered"


@pytest.mark.parametrize(
    "options",
    [
        {NAME_CASE: "shout"},
        {NAME_CASE: NameCase.UPPER, "name_prefx": "typo"},
        {NAME_PREFIX: ""},
    ],
    ids=["bad-case", "unknown-option", "empty-prefix"],
)
def test_invalid_naming_fails_the_runtime_channel(options):
    # the naming dictionary is the link's own declaration now; the raw
    # metadata channel still guards the stored form, and a bad value
    # fails the write naming the class and the key
    class Broken(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(default="x")

    with pytest.raises(
        TypeError, match=rf"Broken\.class_metadata\['{ENVIRONMENT_METADATA_OPTIONS}\."
    ):
        Broken.__settings_context__.set_class_metadata(ENVIRONMENT_METADATA_OPTIONS, options)


def test_subclass_own_options_leave_inherited_variables_alone(monkeypatch):
    # the per-class entries: the subclass's own entry governs its own
    # members, the inherited ones keep the base's variables
    class ChildConfig(
        PrefixedConfig,
        options=env_source(name_prefix="TEST_ACP_CHILD_", name_case=NameCase.UPPER),
    ):
        region: str = environment_variable_setting(default="eu")  # TEST_ACP_CHILD_REGION

    monkeypatch.setenv("TEST_ACP_HOST", "db.example.com")
    monkeypatch.setenv("TEST_ACP_CHILD_REGION", "us")
    ChildConfig.load_configuration()
    assert ChildConfig.host == "db.example.com"  # the base's variable, not renamed
    assert ChildConfig.region == "us"


def test_an_inherited_member_keeps_its_declarers_naming(monkeypatch):
    # the naming dictionary belongs to the class that declared the member:
    # a subclass's own chain replaces the links, and the inherited member's
    # variable still builds by its declarer's rules (the class options that
    # retuned an ancestor's entry are gone with them; redeclaring the member
    # in the subclass is the seat that naming has now)
    class ChildConfig(
        PrefixedConfig,
        options=env_source(name_prefix="TEST_ACP_CHILD_", name_case=NameCase.UPPER),
    ):
        pass

    monkeypatch.setenv("TEST_ACP_HOST", "db.example.com")
    monkeypatch.setenv("TEST_ACP_CHILD_HOST", "wrong.example.com")
    ChildConfig.load_configuration()
    assert ChildConfig.host == "db.example.com"


# -- name_case=NameCase.ANY ------------------------------------------------


@pytest.mark.parametrize("spelling", ["HOST", "Host", "HoSt"])
def test_any_loads_any_spelling_of_the_built_name(monkeypatch, spelling):
    monkeypatch.setenv(spelling, "any.example.com")
    AnyCaseConfig.load_configuration()
    assert AnyCaseConfig.host == "any.example.com"


def test_any_loads_any_spelling_of_an_explicit_name(monkeypatch):
    monkeypatch.setenv("HOST", "db.example.com")
    monkeypatch.setenv("LEGACY_FLAG", "on")
    AnyCaseConfig.load_configuration()
    assert AnyCaseConfig.legacy == "on"


def test_any_exact_spelling_wins_silently(monkeypatch):
    monkeypatch.setenv("host", "exact")
    monkeypatch.setenv("HOST", "folded")
    AnyCaseConfig.load_configuration()
    assert AnyCaseConfig.host == "exact"


def test_any_two_folded_spellings_fail_the_load(monkeypatch):
    monkeypatch.setenv("HOST", "one")
    monkeypatch.setenv("Host", "two")
    with pytest.raises(
        AggregateLoadError,
        match=re.escape(
            "the process environment holds two differently-cased spellings of "
            "the environment variable ('HOST' and 'Host'); the lookup cannot "
            f"choose between them — remove one spelling or set {NAME_CASE} to "
            "the exact case"
        ),
    ):
        AnyCaseConfig.load_configuration()
