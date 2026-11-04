"""EnvironmentVariables plugin tests (process environment via monkeypatch)."""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
import textwrap
from datetime import datetime
from typing import Optional

import pytest

from advexp.settings import LibraryConfiguration, Settings

# noinspection PyProtectedMember
from advexp.settings._internal.non_storage_setting import non_storage_setting
from advexp.settings.plugins.environment.variables import (
    EnvironmentVariableSetting,
    EnvironmentVariablesPlugin,
    environment_variable_setting,
)

_ENV_NAMES = (
    "TEST_ASV_TEXT",
    "TEST_ASV_FLAG",
    "TEST_ASV_COUNT",
    "TEST_ASV_WHEN",
    "TEST_ASV_PROXY",
    "plain",
)


class EnvSettings(Settings):
    # Optional[str]: this storage has no null form, so None (unset) is a
    # regular value of the member
    text: Optional[str] = environment_variable_setting(name="TEST_ASV_TEXT", default="default-text")
    flag: bool = environment_variable_setting(name="TEST_ASV_FLAG", default=False)
    count: int = environment_variable_setting(name="TEST_ASV_COUNT", default=0)
    when: Optional[datetime] = environment_variable_setting(name="TEST_ASV_WHEN", default=None)
    plain: str = environment_variable_setting()  # falls back to the member name


@dataclasses.dataclass
class Proxy:
    host: str
    port: int = 3128


class ProxySettings(Settings):
    proxy: Optional[Proxy] = environment_variable_setting(name="TEST_ASV_PROXY", default=None)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    yield


def test_import_enables_plugin():
    from advexp.settings_base.base_attribute import BaseAttribute

    factory = LibraryConfiguration._get_serializer_factory(EnvironmentVariableSetting)
    assert factory is not None
    # the base attribute class itself stays unregistered
    assert LibraryConfiguration._get_serializer_factory(BaseAttribute) is None


def test_variables_module_is_self_sufficient():
    """The backend's own module carries the naming options beside its factory."""
    script = textwrap.dedent(
        """
        import os
        import sys

        import advexp.settings.plugins.environment.variables as variables
        from advexp.settings import Settings

        os.environ["TEST_ASV_TEXT"] = "from-module"


        class SelfSufficientSettings(
            Settings,
            options=variables.env_source(
                "TEST_ASV_", variables.NameCase.UPPER
            ),
        ):
            # TEST_ASV_TEXT, built by the imported options
            text: str = variables.environment_variable_setting(default="default")


        SelfSufficientSettings.load_settings()
        assert SelfSufficientSettings.text == "from-module"

        # the backend came in alone: the dotenv sibling never loaded
        assert not any("environment.dotenv" in name for name in sys.modules)
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_load_missing_variables_apply_defaults():
    EnvSettings.load_settings()
    assert EnvSettings.text == "default-text"
    assert EnvSettings.flag is False
    assert EnvSettings.count == 0
    assert EnvSettings.when is None


def test_load_string_value(monkeypatch):
    monkeypatch.setenv("TEST_ASV_TEXT", "from-env")
    EnvSettings.load_settings()
    assert EnvSettings.text == "from-env"


def test_load_converts_bool_int_and_datetime(monkeypatch):
    monkeypatch.setenv("TEST_ASV_FLAG", "True")
    monkeypatch.setenv("TEST_ASV_COUNT", "42")
    monkeypatch.setenv("TEST_ASV_WHEN", "2026-09-03T10:15:30")
    EnvSettings.load_settings()
    assert EnvSettings.flag is True
    assert EnvSettings.count == 42
    assert EnvSettings.when == datetime(2026, 9, 3, 10, 15, 30)


def test_unconvertible_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("TEST_ASV_COUNT", "not-a-number")
    EnvSettings.load_settings()
    assert EnvSettings.count == 0


def test_save_writes_environment(monkeypatch):
    EnvSettings.flag = True
    EnvSettings.count = 7
    EnvSettings.save_settings()
    assert os.environ["TEST_ASV_FLAG"] == "True"
    assert os.environ["TEST_ASV_COUNT"] == "7"


def test_save_none_unsets_variable(monkeypatch):
    # this storage has no null form: None and absence coincide
    monkeypatch.setenv("TEST_ASV_TEXT", "stale")
    EnvSettings.text = None
    EnvSettings.save_setting("text")
    assert "TEST_ASV_TEXT" not in os.environ


def test_member_name_fallback(monkeypatch):
    monkeypatch.setenv("plain", "plain-value")
    EnvSettings.load_settings()
    assert EnvSettings.plain == "plain-value"


# ---------------------------------------------------------------------------
# aliases: several addresses of one member, first found wins
# ---------------------------------------------------------------------------

_ALIAS_ENV_NAMES = ("TEST_ASV_PRIMARY", "TEST_ASV_FIRST", "TEST_ASV_SECOND")


@pytest.fixture
def clean_alias_env(monkeypatch):
    for name in _ALIAS_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


class AliasSettings(Settings):
    ttl: str = environment_variable_setting(
        name="TEST_ASV_PRIMARY",
        aliases=["TEST_ASV_FIRST", "TEST_ASV_SECOND"],
        default="default-ttl",
    )


def test_alias_loads_when_primary_is_missing(monkeypatch, clean_alias_env):
    # the migration seat: the old name keeps serving the member
    monkeypatch.setenv("TEST_ASV_SECOND", "from-old-name")
    AliasSettings.load_settings()
    assert AliasSettings.ttl == "from-old-name"


def test_alias_order_primary_then_declaration_order(monkeypatch, clean_alias_env):
    # both aliases set: the first declared alias wins
    monkeypatch.setenv("TEST_ASV_FIRST", "first")
    monkeypatch.setenv("TEST_ASV_SECOND", "second")
    AliasSettings.load_settings()
    assert AliasSettings.ttl == "first"

    # the primary address outranks every alias
    monkeypatch.setenv("TEST_ASV_PRIMARY", "primary")
    AliasSettings.load_settings()
    assert AliasSettings.ttl == "primary"


def test_alias_contains_matches_any_address(monkeypatch, clean_alias_env):
    assert AliasSettings.contains_setting("ttl") is False
    monkeypatch.setenv("TEST_ASV_SECOND", "kept")
    assert AliasSettings.contains_setting("ttl") is True


def test_alias_save_writes_the_primary_address_alone(monkeypatch, clean_alias_env):
    monkeypatch.setenv("TEST_ASV_SECOND", "old-value")
    AliasSettings.load_settings()

    AliasSettings.ttl = "saved"
    AliasSettings.save_settings()
    assert os.environ["TEST_ASV_PRIMARY"] == "saved"
    assert os.environ["TEST_ASV_SECOND"] == "old-value"  # aliases are read addresses


def test_alias_delete_clears_every_address(monkeypatch, clean_alias_env):
    for name in _ALIAS_ENV_NAMES:
        monkeypatch.setenv(name, "value")
    AliasSettings.load_settings()

    AliasSettings.delete_setting("ttl")
    # an alias left behind would resurrect the value at the next load
    assert all(name not in os.environ for name in _ALIAS_ENV_NAMES)
    assert AliasSettings.ttl == "default-ttl"


def test_contains_setting(monkeypatch):
    assert EnvSettings.contains_setting("text") is False
    monkeypatch.setenv("TEST_ASV_TEXT", "here")
    assert EnvSettings.contains_setting("text") is True


def test_delete_setting(monkeypatch):
    monkeypatch.setenv("TEST_ASV_TEXT", "value")
    EnvSettings.load_settings()
    assert EnvSettings.text == "value"

    EnvSettings.delete_setting("text")
    assert "TEST_ASV_TEXT" not in os.environ
    assert EnvSettings.text == "default-text"  # reset to default


def test_round_trip_save_then_load(monkeypatch):
    EnvSettings.flag = True
    EnvSettings.count = 99
    EnvSettings.text = "saved"
    EnvSettings.save_settings()

    EnvSettings.reset_settings()
    assert EnvSettings.flag is False

    EnvSettings.load_settings()
    assert EnvSettings.flag is True
    assert EnvSettings.count == 99
    assert EnvSettings.text == "saved"


def test_dataclass_round_trip_through_environment(monkeypatch):
    ProxySettings.reset_settings()
    ProxySettings.proxy = Proxy("proxy.example", 8080)
    ProxySettings.save_settings()
    # a dataclass is one JSON-encoded variable
    assert os.environ["TEST_ASV_PROXY"] == '{"host":"proxy.example","port":8080}'

    ProxySettings.reset_settings()
    assert ProxySettings.proxy is None
    ProxySettings.load_settings()
    assert ProxySettings.proxy == Proxy("proxy.example", 8080)
    assert isinstance(ProxySettings.proxy, Proxy)

    # an externally set variable is parsed the same way; a field default fills the gap
    monkeypatch.setenv("TEST_ASV_PROXY", '{"host": "other.example"}')
    ProxySettings.load_settings()
    assert ProxySettings.proxy == Proxy("other.example", 3128)


def test_single_setting_save_and_load(monkeypatch):
    monkeypatch.setenv("TEST_ASV_TEXT", "old")
    EnvSettings.text = "new"
    EnvSettings.save_setting("text")
    assert os.environ["TEST_ASV_TEXT"] == "new"

    EnvSettings.text = "ignored"
    EnvSettings.load_setting("text")
    assert EnvSettings.text == "new"


def test_get_plugin_bound_to_class():
    plugin = EnvSettings.get_plugin(EnvironmentVariablesPlugin)
    assert plugin.plugin_name == "EnvironmentVariables"
    assert plugin.context.settings_class is EnvSettings


def test_mixed_attributes_use_their_own_serializers():
    # each member is served by its own attribute's pair: the environment
    # member reads its variable, the in-memory member re-declares its default
    class Mixed(Settings):
        text: str = environment_variable_setting(name="TEST_ASV_TEXT", default="env-default")
        local_only: bool = non_storage_setting(default=False)

    Mixed.local_only = True
    Mixed.load_settings()
    assert Mixed.text == "env-default"
    assert Mixed.local_only is False  # the load re-declared the default

    Mixed.local_only = True
    Mixed.save_settings()  # the memory member's save is a no-op
    assert Mixed.local_only is True
