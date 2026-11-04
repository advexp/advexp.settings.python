"""Secret value wrappers: masking, conversion, constraints, storage form."""

from __future__ import annotations

import logging
import os
from typing import Optional

import pytest

from advexp.settings import SecretBytes, SecretStr, Settings, SettingValidationError
from advexp.settings.plugins.environment.variables import environment_variable_setting
from advexp.settings_base.conversion import (
    correct_type,
    is_secret_type,
    to_json_value,
    to_storage_string,
    unwrap_secret,
)

# ---------------------------------------------------------------------------
# the wrappers themselves
# ---------------------------------------------------------------------------


def test_repr_and_str_answer_the_mask():
    text = SecretStr("hunter2")
    assert "hunter2" not in repr(text)
    assert "hunter2" not in str(text)
    assert repr(text) == "SecretStr('**********')"
    assert str(text) == "**********"

    payload = SecretBytes(b"\x00\x01raw")
    assert "raw" not in repr(payload)
    assert repr(payload) == "SecretBytes(b'**********')"
    assert str(payload) == "**********"


def test_get_secret_value_is_the_one_way():
    assert SecretStr("hunter2").get_secret_value() == "hunter2"
    assert SecretBytes(b"raw").get_secret_value() == b"raw"


def test_equality_and_hash_look_inside():
    assert SecretStr("a") == SecretStr("a")
    assert SecretStr("a") != SecretStr("b")
    assert hash(SecretStr("a")) == hash(SecretStr("a"))
    assert SecretStr("a") != "a"  # no accidental comparison with the payload
    assert SecretBytes(b"x") == SecretBytes(b"x")


# ---------------------------------------------------------------------------
# conversion and storage forms
# ---------------------------------------------------------------------------


def test_conversion_wraps_plain_payloads():
    assert correct_type("hunter2", SecretStr) == SecretStr("hunter2")
    assert correct_type(b"raw", SecretBytes) == SecretBytes(b"raw")
    # a string encodes as UTF-8 for the bytes wrapper, the way bytes convert
    assert correct_type("raw", SecretBytes) == SecretBytes(b"raw")
    # an already wrapped value keeps as is
    wrapped = SecretStr("hunter2")
    assert correct_type(wrapped, SecretStr) is wrapped


def test_conversion_failure_masks_the_payload():
    with pytest.raises(ValueError, match="cannot convert the <secret> value to SecretStr"):
        correct_type(42, SecretStr)


def test_secret_type_detection_and_unwrapping():
    assert is_secret_type(SecretStr)
    assert is_secret_type(SecretBytes)
    assert is_secret_type(Optional[SecretStr])
    assert not is_secret_type(str)
    assert unwrap_secret(SecretStr("x")) == "x"
    assert unwrap_secret(SecretBytes(b"x")) == b"x"
    assert unwrap_secret("plain") == "plain"


def test_storage_forms_are_plain_payloads():
    assert to_storage_string(SecretStr("hunter2")) == "hunter2"
    assert to_json_value(SecretBytes(b"raw")) == "raw"
    # the recursion carries the unwrap into containers and dataclass fields
    assert to_json_value([SecretStr("a"), SecretBytes(b"b")]) == ["a", "b"]


# ---------------------------------------------------------------------------
# the settings flow
# ---------------------------------------------------------------------------


class Credentials(Settings):
    api_key: SecretStr = environment_variable_setting(name="TEST_SVK_KEY", default="fallback-key")
    token: Optional[SecretBytes] = environment_variable_setting(name="TEST_SVK_TOKEN", default=None)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("TEST_SVK_KEY", "TEST_SVK_TOKEN", "TEST_SVK_KEY2"):
        monkeypatch.delenv(name, raising=False)
    yield


def test_declared_default_wraps_at_class_creation():
    Credentials.load_settings()
    assert Credentials.api_key == SecretStr("fallback-key")
    assert Credentials.token is None


def test_load_wraps_the_source_payload(monkeypatch):
    monkeypatch.setenv("TEST_SVK_KEY", "from-env")
    Credentials.load_settings()
    assert Credentials.api_key == SecretStr("from-env")
    assert isinstance(Credentials.api_key, SecretStr)


def test_save_stores_the_plain_payload(monkeypatch):
    Credentials.api_key = SecretStr("assigned-secret")
    Credentials.save_settings()
    assert os.environ["TEST_SVK_KEY"] == "assigned-secret"
    # and loading wraps it back
    Credentials.load_settings()
    assert Credentials.api_key == SecretStr("assigned-secret")


def test_constraint_check_sees_inside_and_masks(caplog, monkeypatch):
    class Keyed(Settings):
        api_key: SecretStr = environment_variable_setting(name="TEST_SVK_KEY2", min_length=8)

    monkeypatch.setenv("TEST_SVK_KEY2", "short")
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        Keyed.load_settings()
    assert Keyed.api_key is None  # the violation fell back to the (absent) default
    messages = [record.getMessage() for record in caplog.records]
    assert any("violates its constraints" in message for message in messages)
    assert all("short" not in message for message in messages)


def test_assignment_violation_masks_the_value():
    # regex= is the constraint whose message names the value: exactly where
    # the mask has to stand in
    class Keyed(Settings):
        api_key: SecretStr = environment_variable_setting(name="TEST_SVK_KEY2", regex="^tok-")

    with pytest.raises(SettingValidationError) as info:
        Keyed.api_key = SecretStr("short")
    assert "short" not in str(info.value)
    assert "**********" in str(info.value)


def test_update_from_dict_secret_failure_is_masked():
    with pytest.raises(ValueError, match="cannot convert the <secret> value"):
        Credentials.update_from_dict({"api_key": 42})
