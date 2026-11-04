"""EnvironmentVariables source tests (process environment via monkeypatch)."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import textwrap
from datetime import datetime
from typing import Optional

import pytest

from advexp.configuration import Configuration, LibraryConfiguration
from advexp.configuration.plugins.environment.variables import (
    EnvironmentVariableSetting,
    EnvironmentVariablesPlugin,
    env_source,
    environment_variable_setting,
)

_ENV_NAMES = (
    "TEST_ACF_TEXT",
    "TEST_ACF_FLAG",
    "TEST_ACF_COUNT",
    "TEST_ACF_WHEN",
    "TEST_ACF_PROXY",
    "plain",
)


class EnvConfiguration(
    Configuration,
    options=env_source(),
):
    # Optional[str]: this source has no null form, so None (unset) is a
    # regular value of the member
    text: Optional[str] = environment_variable_setting(name="TEST_ACF_TEXT", default="default-text")
    flag: bool = environment_variable_setting(name="TEST_ACF_FLAG", default=False)
    count: int = environment_variable_setting(name="TEST_ACF_COUNT", default=0)
    when: Optional[datetime] = environment_variable_setting(name="TEST_ACF_WHEN", default=None)
    plain: str = environment_variable_setting(default="plain-default")  # name = member name


@dataclasses.dataclass
class Proxy:
    host: str
    port: int = 3128


class ProxyConfiguration(
    Configuration,
    options=env_source(),
):
    proxy: Optional[Proxy] = environment_variable_setting(name="TEST_ACF_PROXY", default=None)


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
    """The source's own module carries the naming options beside its factory."""
    script = textwrap.dedent(
        """
        import os
        import sys

        import advexp.configuration.plugins.environment.variables as variables
        from advexp.configuration import Configuration

        os.environ["TEST_ACF_TEXT"] = "from-module"


        class SelfSufficientConfig(
            Configuration,
            options=variables.env_source(
                "TEST_ACF_", variables.NameCase.UPPER
            ),
        ):
            # TEST_ACF_TEXT, built by the imported options
            text: str = variables.environment_variable_setting(default="default")


        SelfSufficientConfig.load_configuration()
        assert SelfSufficientConfig.text == "from-module"

        # the source came in alone: the dotenv sibling never loaded
        assert not any("environment.dotenv" in name for name in sys.modules)
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_load_missing_variables_apply_defaults():
    EnvConfiguration.load_configuration()
    assert EnvConfiguration.text == "default-text"
    assert EnvConfiguration.flag is False
    assert EnvConfiguration.count == 0
    assert EnvConfiguration.when is None
    assert EnvConfiguration.plain == "plain-default"


def test_load_string_value(monkeypatch):
    monkeypatch.setenv("TEST_ACF_TEXT", "from-env")
    EnvConfiguration.load_configuration()
    assert EnvConfiguration.text == "from-env"


def test_load_converts_bool_int_and_datetime(monkeypatch):
    monkeypatch.setenv("TEST_ACF_FLAG", "True")
    monkeypatch.setenv("TEST_ACF_COUNT", "42")
    monkeypatch.setenv("TEST_ACF_WHEN", "2026-09-03T10:15:30")
    EnvConfiguration.load_configuration()
    assert EnvConfiguration.flag is True
    assert EnvConfiguration.count == 42
    assert EnvConfiguration.when == datetime(2026, 9, 3, 10, 15, 30)


def test_unconvertible_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("TEST_ACF_COUNT", "not-a-number")
    EnvConfiguration.load_configuration()
    assert EnvConfiguration.count == 0


def test_constraint_violating_value_falls_back_to_default(monkeypatch):
    class BoundedConfiguration(
        Configuration,
        options=env_source(),
    ):
        count: int = environment_variable_setting(name="TEST_ACF_COUNT", default=10, ge=10)

    monkeypatch.setenv("TEST_ACF_COUNT", "5")
    BoundedConfiguration.load_configuration()
    assert BoundedConfiguration.count == 10


def test_member_name_fallback(monkeypatch):
    monkeypatch.setenv("plain", "plain-value")
    EnvConfiguration.load_configuration()
    assert EnvConfiguration.plain == "plain-value"


def test_dataclass_parses_from_environment(monkeypatch):
    # a dataclass is one JSON-encoded variable; a field default fills the gap
    monkeypatch.setenv("TEST_ACF_PROXY", '{"host": "other.example"}')
    ProxyConfiguration.load_configuration()
    assert ProxyConfiguration.proxy == Proxy("other.example", 3128)
    assert isinstance(ProxyConfiguration.proxy, Proxy)


def test_get_plugin_bound_to_class():
    plugin = EnvConfiguration.get_plugin(EnvironmentVariablesPlugin)
    assert plugin.plugin_name == "EnvironmentVariables"
    assert plugin.context.settings_class is EnvConfiguration


# ---------------------------------------------------------------------------
# aliases: several addresses of one member, first found wins
# ---------------------------------------------------------------------------

_ALIAS_ENV_NAMES = ("TEST_ACF_PRIMARY", "TEST_ACF_FIRST", "TEST_ACF_SECOND")


@pytest.fixture
def clean_alias_env(monkeypatch):
    for name in _ALIAS_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


class AliasConfiguration(
    Configuration,
    options=env_source(),
):
    ttl: str = environment_variable_setting(
        name="TEST_ACF_PRIMARY",
        aliases=["TEST_ACF_FIRST", "TEST_ACF_SECOND"],
        default="default-ttl",
    )


def test_alias_loads_when_primary_is_missing(monkeypatch, clean_alias_env):
    # the migration seat: the old name keeps serving the member
    monkeypatch.setenv("TEST_ACF_SECOND", "from-old-name")
    AliasConfiguration.load_configuration()
    assert AliasConfiguration.ttl == "from-old-name"


def test_alias_order_primary_then_declaration_order(monkeypatch, clean_alias_env):
    monkeypatch.setenv("TEST_ACF_FIRST", "first")
    monkeypatch.setenv("TEST_ACF_SECOND", "second")
    AliasConfiguration.load_configuration()
    assert AliasConfiguration.ttl == "first"

    monkeypatch.setenv("TEST_ACF_PRIMARY", "primary")
    AliasConfiguration.load_configuration()
    assert AliasConfiguration.ttl == "primary"
