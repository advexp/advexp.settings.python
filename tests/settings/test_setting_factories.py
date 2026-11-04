"""Declaration factories: the type-checker-friendly spelling of the attribute
classes.

The factories must build exactly what their attribute classes build: the same
type, the same keyword parameters, and the same sentinel semantics for
``default=``. A settings class that is declared through them must behave like
any other.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from advexp.settings import Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment.variables import (
    EnvironmentVariableSetting,
    environment_variable_setting,
)
from advexp.settings.plugins.json_settings import (
    JSONSetting,
    JSONSettingsConfiguration,
    json_setting,
)


def test_json_setting_builds_the_class_attribute() -> None:
    attribute = json_setting(
        name="host", default="localhost", path="/net", metadata={"ui-label": "Host"}
    )
    assert isinstance(attribute, JSONSetting)
    assert attribute.name == "host"
    assert attribute.default == "localhost"
    assert attribute.path == "/net"
    assert attribute.metadata == {"ui-label": "Host"}


def test_json_setting_matches_the_class_construction() -> None:
    via_factory = json_setting(name="port", default=8080)
    via_class = JSONSetting(name="port", default=8080)
    assert type(via_factory) is type(via_class)
    assert via_factory.name == via_class.name
    assert via_factory.default == via_class.default
    assert via_factory.path == via_class.path
    assert via_factory.metadata == via_class.metadata == {}


def test_json_setting_default_sentinel_semantics() -> None:
    omitted = json_setting()
    assert omitted.name is None
    assert omitted.path is None
    assert omitted.default is NO_DEFAULT
    assert omitted.default_in_use is False

    explicit_sentinel = json_setting(default=NO_DEFAULT)
    assert explicit_sentinel.default is NO_DEFAULT
    assert explicit_sentinel.default_in_use is False

    none_value = json_setting(default=None)
    assert none_value.default is None
    assert none_value.default_in_use is True


def test_json_setting_takes_no_positional_arguments() -> None:
    with pytest.raises(TypeError):
        json_setting("host")  # type: ignore[misc]


def test_environment_variable_setting_builds_the_class_attribute() -> None:
    attribute = environment_variable_setting(name="APP_MODE", default="production")
    assert isinstance(attribute, EnvironmentVariableSetting)
    assert attribute.name == "APP_MODE"
    assert attribute.default == "production"


def test_environment_variable_setting_matches_the_class_construction() -> None:
    via_factory = environment_variable_setting(name="APP_PORT", default=8080)
    via_class = EnvironmentVariableSetting(name="APP_PORT", default=8080)
    assert type(via_factory) is type(via_class)
    assert via_factory.name == via_class.name
    assert via_factory.default == via_class.default
    assert via_factory.metadata == via_class.metadata == {}


def test_environment_variable_setting_default_sentinel_semantics() -> None:
    omitted = environment_variable_setting()
    assert omitted.name is None
    assert omitted.default is NO_DEFAULT
    assert omitted.default_in_use is False

    none_value = environment_variable_setting(default=None)
    assert none_value.default is None
    assert none_value.default_in_use is True


def test_environment_variable_setting_takes_no_positional_arguments() -> None:
    with pytest.raises(TypeError):
        environment_variable_setting("APP_MODE")  # type: ignore[misc]


class FactoryDeclaredSettings(Settings):
    host: str = json_setting(name="host", default="localhost")
    port: int = json_setting(default=9000)
    mode: str = environment_variable_setting(name="TEST_ASV_FACTORY_MODE", default="production")


@pytest.fixture(autouse=True)
def configured_file(tmp_path, monkeypatch) -> Iterator[Path]:
    path = tmp_path / "settings.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", path)
    yield path


def test_settings_declared_through_factories_round_trip(monkeypatch) -> None:
    assert FactoryDeclaredSettings.port == 9000

    monkeypatch.setenv("TEST_ASV_FACTORY_MODE", "staging")
    FactoryDeclaredSettings.load_settings()
    assert FactoryDeclaredSettings.mode == "staging"
    assert FactoryDeclaredSettings.host == "localhost"  # no file yet -> default

    FactoryDeclaredSettings.host = "example.com"
    FactoryDeclaredSettings.port = 8080
    FactoryDeclaredSettings.save_settings()

    monkeypatch.setenv("TEST_ASV_FACTORY_MODE", "production")
    FactoryDeclaredSettings.load_settings()
    assert FactoryDeclaredSettings.host == "example.com"  # back from the file
    assert FactoryDeclaredSettings.port == 8080
    assert FactoryDeclaredSettings.mode == "production"
