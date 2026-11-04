"""Tests of the serializer base class helpers."""

from __future__ import annotations

from typing import Any, Optional

import pytest

from advexp.settings import Settings
from advexp.settings.plugin_api import (
    NO_DEFAULT,
    SettingsAttribute,
    SettingsBaseSerializer,
)


class PathSetting(SettingsAttribute):
    """An attribute with a backend-specific parameter (the ``path=`` pattern)."""

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = NO_DEFAULT,
        path: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, default=default)
        self.path: Optional[str] = path


def path_setting(
    *,
    name: Optional[str] = None,
    default: Any = NO_DEFAULT,
    path: Optional[str] = None,
) -> Any:
    return PathSetting(name=name, default=default, path=path)


class SubPathSetting(PathSetting):
    """A user subclass of the attribute class."""


class ParameterlessSetting(SettingsAttribute):
    """A foreign attribute class without that parameter."""


class Serializer(SettingsBaseSerializer):
    """Minimal concrete backend: the inherited helpers are the subject here."""

    def load(self, setting_name: str, attr: Any) -> Any:
        raise NotImplementedError

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        raise NotImplementedError

    def delete(self, setting_name: str, attr: Any) -> None:
        raise NotImplementedError

    def contains(self, setting_name: str, attr: Any) -> bool:
        raise NotImplementedError


def test_attribute_of_returns_the_attribute_narrowed():
    attr = PathSetting(name="host", path="net")

    setting = Serializer().attribute_of(attr, PathSetting)

    assert setting is attr
    assert setting is not None
    assert setting.path == "net"  # the typed view: the parameter is plain to read


def test_attribute_of_accepts_attribute_subclasses():
    attr = SubPathSetting(path="net")

    setting = Serializer().attribute_of(attr, PathSetting)

    assert setting is attr


def test_attribute_of_returns_none_for_dynamic_entries():
    # dynamic settings call the serializer with attr=None
    assert Serializer().attribute_of(None, PathSetting) is None


def test_attribute_of_returns_none_for_foreign_attribute_classes():
    # a serializer installed as the global override receives attributes of
    # foreign classes: the backend's parameters are simply absent
    assert Serializer().attribute_of(ParameterlessSetting(), PathSetting) is None


class ContextProbeSettings(Settings):
    host: str = path_setting(name="host", default="localhost")


def test_context_arrives_with_set_serializer_params():
    # the base keeps the delivered context: backends read it through the
    # property instead of overriding set_serializer_params with their own
    # field. Before any delivery — a serializer instance outside a pass —
    # the context does not exist; the value-form helpers and the name
    # wishes stay usable without it
    serializer = Serializer()
    with pytest.raises(RuntimeError, match="not bound to a pass"):
        _ = serializer.context

    serializer.set_serializer_params(ContextProbeSettings.__settings_context__)

    context = serializer.context
    assert context is ContextProbeSettings.__settings_context__
    assert context.settings_class is ContextProbeSettings
