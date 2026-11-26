"""The chain probe of configuration classes: contains_member.

The probe asks the source chain whether any link holds a value for one
member, the way a load would walk it: the first link that holds a value
answers, and a chain where no link holds one answers False. The probe
builds no state — the values of the class stand as they were.
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional

import pytest

from advexp.configuration import (
    Configuration,
    ConversionError,
    Sources,
    sourceless_setting,
)
from advexp.configuration.plugin_api import (
    AttributeSerializerBinding,
    ConfigurationAttribute,
    ISettingAttribute,
    LibraryConfiguration,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    SourceBinding,
    SourceLink,
)
from advexp.configuration.plugins.environment.variables import env_source
from advexp.configuration.plugins.json_settings import json_source
from advexp.configuration.plugins.mapping_source import mapping_source
from advexp.configuration.plugins.mapping_source.resolver import mapping_source_for
from advexp.settings_base.environment_variable_setting import (
    environment_variable_setting,
)
from advexp.settings_base.json_setting import json_setting
from advexp.settings_base.not_found import NOT_FOUND
from advexp.settings_base.user_facing_error import UserFacingError

# plain members read the environment by their member name, so the fixture
# keeps the handful of names these tests use out of the real environment
_PLAIN_MEMBER_VARS = ("token", "port", "mode", "endpoint")


@pytest.fixture(autouse=True)
def clean_member_env(monkeypatch):
    for name in _PLAIN_MEMBER_VARS:
        monkeypatch.delenv(name, raising=False)
    yield


class _FailingProbeAttribute(ConfigurationAttribute):
    """A test source family: the contains probe fails on demand."""


class _FailingProbeSerializer(SettingsBaseSerializer):
    """Raises on ``contains`` in the way the enclosing test picks.

    ``kind_contains`` chooses what the probe meets: ``"plain"`` raises a
    runtime error, ``"facing"`` raises a user-facing wrapper, and ``None``
    answers quietly.
    """

    kind_contains: ClassVar[Optional[str]] = None

    @staticmethod
    def _raise(kind: Optional[str]) -> None:
        if kind == "plain":
            raise RuntimeError("contains boom")
        if kind == "facing":
            raise UserFacingError(ValueError("contains inner"))

    def load(self, setting_name: str, attr: Any) -> Any:
        return NOT_FOUND

    def save(self, setting_name: str, attr: Any, value: Any) -> None:
        """No-op: a test source never writes."""

    def delete(self, setting_name: str, attr: Any) -> None:
        """No-op: a test source never deletes."""

    def contains(self, setting_name: str, attr: Any) -> bool:
        self._raise(self.kind_contains)
        return False


class _FailingProbePlugin(SettingsBasePlugin):
    binding = AttributeSerializerBinding(_FailingProbeAttribute, _FailingProbeSerializer)

    @property
    def plugin_name(self) -> str:
        return "FailingProbe"


LibraryConfiguration.register_settings_plugin(_FailingProbePlugin)


def _failing_probe_source() -> Any:
    # the third-party source's own chain spelling: a link of its family
    return SourceBinding(SourceLink(attribute_class=_FailingProbeAttribute))


def _failing_probe_setting(**kwargs: Any) -> Any:
    return _FailingProbeAttribute(**kwargs)


def test_a_miss_across_the_whole_chain_answers_false():
    class ChainConfig(
        Configuration,
        options=Sources(env_source(), mapping_source({})),
    ):
        token: str = "fallback"

    assert ChainConfig.contains_member("token") is False


def test_a_value_in_the_first_link_answers_true(monkeypatch):
    monkeypatch.setenv("token", "env-token")

    class ChainConfig(
        Configuration,
        options=Sources(env_source(), mapping_source({})),
    ):
        token: str = "fallback"

    assert ChainConfig.contains_member("token") is True


def test_a_value_in_the_second_link_answers_true():
    class ChainConfig(
        Configuration,
        options=Sources(env_source(), mapping_source({"token": "map-token"})),
    ):
        token: str = "fallback"

    assert ChainConfig.contains_member("token") is True


def test_the_probe_builds_no_state_the_values_stand_as_they_were():
    class ChainConfig(
        Configuration,
        options=Sources(env_source(), mapping_source({"port": 9000})),
    ):
        port: int = 8080

    assert ChainConfig.contains_member("port") is True
    assert ChainConfig.port == 8080  # the probe loaded nothing
    assert ChainConfig.load_configuration() == ()
    assert ChainConfig.port == 9000  # the load, not the probe, brought the value


def test_a_family_member_is_asked_only_at_its_family_links(tmp_path, monkeypatch):
    file = tmp_path / "app.json"
    file.write_text("{}")
    monkeypatch.setenv("mode", "dev")
    monkeypatch.setenv("endpoint", "https://env.example")

    class ChainConfig(
        Configuration,
        options=Sources(json_source(file=file), env_source()),
    ):
        endpoint: str = json_setting(default="https://default.example")
        mode: str = "dev-default"

    # the plain member is asked at every link, and the env link holds it
    assert ChainConfig.contains_member("mode") is True
    # the json family member is asked only at the json link; the env link
    # holds a variable of that name, but the probe never reads it there
    assert ChainConfig.contains_member("endpoint") is False


def test_an_environment_alias_variable_counts(monkeypatch):
    monkeypatch.delenv("TEST_CM_HOST", raising=False)
    monkeypatch.setenv("TEST_CM_HOST_ALIAS", "web-1")

    class ChainConfig(
        Configuration,
        options=env_source(),
    ):
        host: str = environment_variable_setting(
            name="TEST_CM_HOST", aliases=["TEST_CM_HOST_ALIAS"], default="localhost"
        )

    assert ChainConfig.contains_member("host") is True


def test_a_json_alias_under_the_link_path_counts(tmp_path):
    file = tmp_path / "app.json"
    file.write_text('{"server": {"host-name": "web-1"}}')

    class ChainConfig(
        Configuration,
        options=json_source(file=file, path="/server"),
    ):
        host: str = json_setting(aliases=["host-name"], default="localhost")

    assert ChainConfig.contains_member("host") is True


def test_presence_only_the_stored_value_needs_no_conversion():
    class ChainConfig(
        Configuration,
        options=mapping_source({"port": "not-a-number"}),
    ):
        port: int = 8080

    # the link holds a value, so the probe answers True; whether the value
    # survives a load is the load's own question
    assert ChainConfig.contains_member("port") is True
    report = ChainConfig.load_configuration()
    assert len(report) == 1
    assert isinstance(report[0], ConversionError)
    assert ChainConfig.port == 8080


def test_a_live_mapping_source_answers_as_the_dictionary_changes():
    class ChainConfig(
        Configuration,
        options=mapping_source(),
    ):
        token: str = "fallback"

    assert ChainConfig.contains_member("token") is False
    mapping_source_for(ChainConfig).set({"token": "dev-token"})
    assert ChainConfig.contains_member("token") is True


def test_a_sourceless_member_answers_false():
    class ChainConfig(
        Configuration,
        options=mapping_source(),
    ):
        note: str = sourceless_setting(default="v2")

    assert ChainConfig.contains_member("note") is False


def test_a_getter_lambda_selects_the_member():
    class ChainConfig(
        Configuration,
        options=mapping_source({"token": "map-token"}),
    ):
        token: str = "fallback"

    assert ChainConfig.contains_member(lambda m: m.token) is True


def test_an_unknown_member_names_the_available_members():
    class ChainConfig(
        Configuration,
        options=mapping_source(),
    ):
        token: str = "fallback"

    with pytest.raises(KeyError, match="'nope' is not a member of ChainConfig"):
        ChainConfig.contains_member("nope")


def test_a_plain_source_error_leaves_as_is(monkeypatch):
    monkeypatch.setattr(_FailingProbeSerializer, "kind_contains", "plain")

    class ChainConfig(
        Configuration,
        options=Sources(_failing_probe_source(), env_source()),
    ):
        member: str = _failing_probe_setting(default="stored-value")

    with pytest.raises(RuntimeError, match="contains boom"):
        ChainConfig.contains_member("member")


def test_a_user_facing_source_error_arrives_unwrapped(monkeypatch):
    monkeypatch.setattr(_FailingProbeSerializer, "kind_contains", "facing")

    class ChainConfig(
        Configuration,
        options=Sources(_failing_probe_source(), env_source()),
    ):
        member: str = _failing_probe_setting(default="stored-value")

    with pytest.raises(ValueError, match="contains inner") as info:
        ChainConfig.contains_member("member")

    assert isinstance(info.value.__cause__, UserFacingError)


def test_the_probe_fires_the_contains_bracket_and_builds_no_state():
    events: list = []

    class SinkAttribute(ConfigurationAttribute):
        """A test source family served by the recording serializer."""

    class SinkSerializer(SettingsBaseSerializer):
        """Records the notification hooks the machinery fires around a pass."""

        def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
            return NOT_FOUND

        def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
            """No-op: a test source never writes."""

        def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
            """No-op: a test source never deletes."""

        def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
            return False

        def on_start_serializer_action(self) -> None:
            events.append(("start-action",))

        def on_start_contains_settings(self) -> None:
            events.append(("start-contains",))

        def on_end_contains_settings(self) -> None:
            events.append(("end-contains",))

        def on_end_serializer_action(self) -> None:
            events.append(("end-action",))

    def sink_source() -> Any:
        return SourceBinding(
            SourceLink(attribute_class=SinkAttribute, serializer_class=SinkSerializer)
        )

    class ProbeConfig(
        Configuration,
        options=sink_source(),
    ):
        value: int = 5

    assert ProbeConfig.contains_member("value") is False
    # the contains bracket fires, and nothing else does: no synchronize, no
    # state built — the read-only probe touches the source alone
    assert events == [
        ("start-action",),
        ("start-contains",),
        ("end-contains",),
        ("end-action",),
    ]
