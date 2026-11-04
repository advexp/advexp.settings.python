# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The bundled backends implement the name describer, and the diagnostics stay
detailed.

The base serializer carries :class:`ISettingNameDescriber` with a ``None``
default, so every backend of the package implements the interface by
construction. The structural check below walks the plugins tree and collects
the serializer classes that it finds, so a backend that is added later joins
the check without a test edit.

The environment family goes further. It spells its names (the variable that
is built from the naming options of the class, and the dotenv spelling with
the file that it reads) in every channel of the load diagnostics: the abort
entries of required members and the report entries of fallbacks.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import List, Set

import pytest

import advexp.settings.plugins
from advexp.settings import (
    REQUIRED,
    AggregateLoadError,
    ConversionError,
    MissingValueError,
    Settings,
)
from advexp.settings.plugin_api import (
    ISettingNameDescriber,
    ISettingsSerializer,
    ISourceDescriber,
)
from advexp.settings.plugins.environment import NameCase
from advexp.settings.plugins.environment.dotenv import dotenv_setting, dotenv_source
from advexp.settings.plugins.environment.variables import env_source, environment_variable_setting
from advexp.settings.plugins.json_settings import (
    JSONSettingsConfiguration,
    json_setting,
)
from advexp.settings.plugins.json_settings.serializer import JSONSettingsSerializer

_PLUGINS_PREFIX = "advexp.settings.plugins."


def _bundled_serializers() -> List[type]:
    """Return every serializer class that the plugin modules of the package
    define.

    The walk is the point: a plugin that is added later joins the checks
    without a test edit. Only classes that are defined under the ``plugins``
    tree of the package count. A module that re-exports the class of a sibling
    backend adds nothing new.
    """
    found: Set[type] = set()
    for info in pkgutil.walk_packages(advexp.settings.plugins.__path__, _PLUGINS_PREFIX):
        module = importlib.import_module(info.name)
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, ISettingsSerializer)
                and value.__module__.startswith(_PLUGINS_PREFIX)
            ):
                found.add(value)
    return sorted(found, key=lambda cls: cls.__name__)


_KNOWN_BACKENDS = {
    "DotenvSerializer",
    "EnvironmentVariablesSerializer",
    "JSONSettingsSerializer",
}


def test_discovery_finds_the_bundled_backends():
    # the walk itself is guarded: a discovery that finds nothing would
    # parametrize no cases and pass vacuously — the floor of known names
    # catches that (and follows a rename, the only edit it ever needs)
    assert _KNOWN_BACKENDS <= {cls.__name__ for cls in _bundled_serializers()}


@pytest.mark.parametrize(
    "serializer_class",
    _bundled_serializers(),
    ids=lambda cls: cls.__name__,
)
def test_every_bundled_serializer_implements_the_describer(serializer_class):
    # every backend the package ships spells its names — or keeps the
    # pattern-built one through the base's default; a backend built on the
    # raw ISettingsSerializer contract joins the family's diagnostics the
    # same way, and this is where forgetting is caught
    assert issubclass(serializer_class, ISettingNameDescriber)
    assert issubclass(serializer_class, ISourceDescriber)


def test_env_abort_names_the_variable_of_an_explicitly_named_member(monkeypatch):
    class TokenSettings(Settings):
        token: str = environment_variable_setting(name="APP_TOKEN", default=REQUIRED)

    monkeypatch.delenv("APP_TOKEN", raising=False)
    with pytest.raises(AggregateLoadError) as info:
        TokenSettings.load_settings()

    assert "(environment variable 'APP_TOKEN')" in str(info.value.errors[0])
    assert isinstance(info.value.errors[0], MissingValueError)


def test_diagnostics_list_the_aliases_beside_the_primary_address(monkeypatch):
    # a miss spells every address the pass checked: the reader of the
    # abort sees the old names too, not only the primary one
    class TokenSettings(Settings):
        token: str = environment_variable_setting(
            name="APP_TOKEN", aliases=["APP_TOKEN_OLD", "TOKEN"], default=REQUIRED
        )

    for name in ("APP_TOKEN", "APP_TOKEN_OLD", "TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(AggregateLoadError) as info:
        TokenSettings.load_settings()

    assert "(environment variable 'APP_TOKEN' (aliases: 'APP_TOKEN_OLD', 'TOKEN'))" in str(
        info.value.errors[0]
    )


def test_dotenv_diagnostics_name_the_variable_and_the_file(tmp_path):
    # both channels of one run: a required member the file does not carry,
    # and an optional one holding an unconvertible value — each entry
    # names the variable built from the options and the file to provide
    # it in, the storage's own words for a reader who never saw the class
    env_file = tmp_path / "app.env"
    env_file.write_text("APP_RETRIES = many\n", encoding="utf-8")

    class FileSettings(
        Settings,
        options=(
            env_source(name_prefix="APP_", name_case=NameCase.UPPER),
            dotenv_source(file=env_file),
        ),
    ):
        token: str = dotenv_setting(default=REQUIRED)
        retries: int = dotenv_setting(default=3)

    with pytest.raises(AggregateLoadError) as info:
        FileSettings.load_settings()

    spelling = f"environment variable 'APP_TOKEN' in the dotenv file {env_file}"
    assert f"({spelling})" in str(info.value.errors[0])
    assert isinstance(info.value.errors[0], MissingValueError)
    # the cause names the storage; the address above already named the
    # file, and the message quotes it exactly once
    assert "is required: the dotenv file provided no value" in str(info.value.errors[0])
    assert str(info.value.errors[0]).count(str(env_file)) == 1

    fallback_spelling = f"environment variable 'APP_RETRIES' in the dotenv file {env_file}"
    assert f"({fallback_spelling})" in str(info.value.fallbacks[0])
    assert isinstance(info.value.fallbacks[0], ConversionError)


def test_json_diagnostics_name_the_file_the_source_raised_from(tmp_path, monkeypatch):
    # a corrupt document is the source's own condition: the entry says
    # which file broke, not just "its source raised"
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", config_file)
    config_file.write_text("{not json", encoding="utf-8")

    class FileSettings(Settings):
        entry: str = json_setting(name="entry", default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        FileSettings.load_settings()

    message = str(info.value.errors[0])
    assert "is required: the JSON file raised" in message
    assert "cannot parse the JSON settings file" in message


def test_dotenv_diagnostics_name_the_full_path_of_a_relative_file(tmp_path, monkeypatch):
    # a relative binding addresses the working directory; quoting the full
    # path names the exact file on disk, where the bare name would leave
    # the place to guess
    monkeypatch.chdir(tmp_path)

    class FileSettings(
        Settings,
        options=dotenv_source(file=Path("app.env")),
    ):
        token: str = dotenv_setting(default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        FileSettings.load_settings()

    full_path = tmp_path / "app.env"
    message = str(info.value.errors[0])
    assert f"environment variable 'token' in the dotenv file {full_path}" in message
    assert "is required: the dotenv file provided no value" in message
    # the file shows up once: the address carries it, the cause does not repeat it
    assert message.count(str(full_path)) == 1


def test_json_diagnostics_name_the_full_path_of_a_relative_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", Path("config.json"))

    class FileSettings(Settings):
        entry: str = json_setting(name="entry", default=REQUIRED)

    with pytest.raises(AggregateLoadError) as info:
        FileSettings.load_settings()

    message = str(info.value.errors[0])
    assert "is required: the JSON file provided no value" in message
    assert f"key 'entry' in the JSON file {tmp_path / 'config.json'}" in message


def test_json_backend_has_no_spelling_of_its_own():
    # the JSON storage key is the pattern-built name itself: the backend
    # implements the interface through the base and keeps the default, so
    # its diagnostics quote the key unchanged
    serializer = JSONSettingsSerializer()

    assert serializer.describe_setting_name("some.storage.key", None) is None
