"""Getter-lambda form of the single-setting API."""

from __future__ import annotations

import operator
import os

import pytest

from advexp.settings import Settings
from advexp.settings.plugins.environment.variables import environment_variable_setting

_ENV_NAMES = ("TEST_GETTER_HOST", "TEST_GETTER_PORT")


class GetterSettings(Settings):
    host: str = environment_variable_setting(name="TEST_GETTER_HOST", default="localhost")
    port: int = environment_variable_setting(name="TEST_GETTER_PORT", default=8080)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    GetterSettings.reset_settings()
    yield
    GetterSettings.reset_settings()


def test_save_setting_accepts_getter():
    GetterSettings.port = 5432
    GetterSettings.save_setting(lambda s: s.port)
    assert os.environ["TEST_GETTER_PORT"] == "5432"


def test_string_form_still_works():
    GetterSettings.port = 5432
    GetterSettings.save_setting("port")
    assert os.environ["TEST_GETTER_PORT"] == "5432"


def test_load_setting_accepts_getter(monkeypatch):
    monkeypatch.setenv("TEST_GETTER_HOST", "db.example.com")
    GetterSettings.load_setting(lambda s: s.host)
    assert GetterSettings.host == "db.example.com"


def test_delete_setting_accepts_getter():
    GetterSettings.port = 5432
    GetterSettings.delete_setting(lambda s: s.port)
    assert "TEST_GETTER_PORT" not in os.environ
    assert GetterSettings.port == 8080


def test_contains_setting_accepts_getter():
    assert GetterSettings.contains_setting(lambda s: s.port) is False
    GetterSettings.save_setting(lambda s: s.port)
    assert GetterSettings.contains_setting(lambda s: s.port) is True


def test_reset_setting_resets_only_that_member():
    GetterSettings.host = "changed"
    GetterSettings.port = 5432
    GetterSettings.reset_setting(lambda s: s.port)
    assert GetterSettings.port == 8080
    assert GetterSettings.host == "changed"


def test_metadata_accepts_getter():
    GetterSettings.set_setting_metadata(lambda s: s.host, "parameter", "value")
    assert GetterSettings.get_setting_metadata(lambda s: s.host, "parameter") == "value"


def test_metadata_ref_forms_are_interchangeable():
    GetterSettings.set_setting_metadata(lambda s: s.host, "parameter", "value")
    # written via lambda, read back via the member-name string
    assert GetterSettings.get_setting_metadata("host", "parameter") == "value"


def test_metadata_contains_accepts_getter():
    GetterSettings.set_setting_metadata(lambda s: s.host, "have", "value")
    # asked via lambda, answered via the member-name string and back
    assert GetterSettings.contains_setting_metadata(lambda s: s.host, "have")
    assert GetterSettings.contains_setting_metadata("host", "have")
    assert not GetterSettings.contains_setting_metadata(lambda s: s.port, "have")


def test_getter_for_undeclared_member_raises():
    with pytest.raises(KeyError, match="nope"):
        GetterSettings.save_setting(lambda s: s.nope)


def make_closure_getter():
    name = "port"
    return lambda s: getattr(s, name)  # noqa: E731


@pytest.mark.parametrize(
    "bad_ref",
    [
        5432,  # a value: ServerSettings.save_setting(ServerSettings.port)
        operator.attrgetter("port"),  # callable without bytecode
        lambda: 8080,
        lambda s: 8080,
        lambda s: s,
        lambda s, t: s.port,
        lambda s, *args: s.port,
        lambda s, **kwargs: s.port,
        lambda s: s.port + 1,
        lambda s: s.host.upper(),
        lambda s: s.host.port,  # nested attribute
        make_closure_getter(),
    ],
)
def test_bad_references_are_rejected(bad_ref):
    with pytest.raises(TypeError, match="lambda s: s.<member>"):
        GetterSettings.save_setting(bad_ref)
