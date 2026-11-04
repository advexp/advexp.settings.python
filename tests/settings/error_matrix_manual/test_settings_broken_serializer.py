"""A broken serializer: the source itself fails.

The test replaces the ``load`` of the backend serializer with a function
that raises an error, so the storage behind the class is never read at all.

The family keeps its log-and-continue policy:

- The exception is logged for each member at the error level. In the full
  fallback shape, the message names the place of the member and the source
  that raised, and its tail announces the fallback of an optional member.
- The required members collect their source errors into the aggregate.
- The optional members stand at their defaults, with one report entry each.
"""

import logging

import pytest
from settings_serializer_classes import (
    BROKEN_SERIALIZER_DOTENV_FILE,
    BROKEN_SERIALIZER_JSON_FILE,
    BROKEN_SERIALIZER_TOML_FILE,
    BrokenSerializerDotenvSettings,
    BrokenSerializerEnvSettings,
    BrokenSerializerJsonSettings,
    BrokenSerializerTomlSettings,
)

from advexp.settings import AggregateLoadError, SourceLoadError
from advexp.settings.plugins.environment.dotenv import DotenvSerializer
from advexp.settings.plugins.environment.variables import EnvironmentVariablesSerializer
from advexp.settings.plugins.json_settings import JSONSettingsSerializer
from advexp.settings.plugins.toml_settings import TOMLSettingsSerializer


def exploding_load(self, setting_name, attr):
    """A serializer ``load`` that breaks: the stand-in for a failing source."""
    raise RuntimeError("serializer exploded")


def test_broken_serializer_env(monkeypatch, caplog):
    """The environment serializer's read breaks."""
    monkeypatch.setattr(EnvironmentVariablesSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerEnvSettings.load_settings()

    # the exception is logged per member in the full fallback shape: the
    # member's place, the source that raised, and the fallback tail an
    # optional member earns
    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        "setting 'answer' (environment variable 'EMX_ANSWER') "
        "of 'BrokenSerializerEnvSettings': "
        "the process environment raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        "setting 'plain' (environment variable 'EMX_PLAIN') "
        "of 'BrokenSerializerEnvSettings': "
        "the process environment raised RuntimeError (serializer exploded); "
        "using the default value"
    ) in error_messages

    # the required members collected their source errors
    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        "setting 'answer' (environment variable 'EMX_ANSWER') "
        "of 'BrokenSerializerEnvSettings' is required: "
        "the process environment raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)
    assert isinstance(error.__cause__, RuntimeError)

    # the optional members stood at their defaults with a report entry each
    assert [str(fallback) for fallback in info.value.fallbacks] == [
        "setting 'plain' (environment variable 'EMX_PLAIN') "
        "of 'BrokenSerializerEnvSettings' fell back to its default: "
        "the process environment raised RuntimeError (serializer exploded)",
        "setting 'known' (environment variable 'EMX_KNOWN') "
        "of 'BrokenSerializerEnvSettings' fell back to its default: "
        "the process environment raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerEnvSettings.plain is None
    assert BrokenSerializerEnvSettings.known == 7


def test_broken_serializer_dotenv(monkeypatch, caplog):
    """The dotenv serializer's read breaks."""
    monkeypatch.setattr(DotenvSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerDotenvSettings.load_settings()

    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvSettings': "
        "the dotenv file raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        f"setting 'plain' (environment variable 'EMX_PLAIN' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvSettings': "
        "the dotenv file raised RuntimeError (serializer exploded); using the default value"
    ) in error_messages

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvSettings' "
        "is required: the dotenv file raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)

    assert [str(fallback) for fallback in info.value.fallbacks] == [
        f"setting 'plain' (environment variable 'EMX_PLAIN' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvSettings' "
        "fell back to its default: "
        "the dotenv file raised RuntimeError (serializer exploded)",
        f"setting 'known' (environment variable 'EMX_KNOWN' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvSettings' "
        "fell back to its default: "
        "the dotenv file raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerDotenvSettings.plain is None
    assert BrokenSerializerDotenvSettings.known == 7


def test_broken_serializer_json(monkeypatch, caplog):
    """The JSON serializer's read breaks."""
    monkeypatch.setattr(JSONSettingsSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerJsonSettings.load_settings()

    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        f"setting 'answer' (key 'answer' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonSettings': "
        "the JSON file raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        f"setting 'plain' (key 'plain' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonSettings': "
        "the JSON file raised RuntimeError (serializer exploded); using the default value"
    ) in error_messages

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonSettings' is required: "
        "the JSON file raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)

    assert [str(fallback) for fallback in info.value.fallbacks] == [
        f"setting 'plain' (key 'plain' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonSettings' fell back to its default: "
        "the JSON file raised RuntimeError (serializer exploded)",
        f"setting 'known' (key 'known' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonSettings' fell back to its default: "
        "the JSON file raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerJsonSettings.plain is None
    assert BrokenSerializerJsonSettings.known == 7


def test_broken_serializer_toml(monkeypatch, caplog):
    """The TOML serializer's read breaks."""
    monkeypatch.setattr(TOMLSettingsSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerTomlSettings.load_settings()

    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        f"setting 'answer' (key 'answer' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlSettings': "
        "the TOML file raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        f"setting 'plain' (key 'plain' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlSettings': "
        "the TOML file raised RuntimeError (serializer exploded); using the default value"
    ) in error_messages

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlSettings' is required: "
        "the TOML file raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)

    assert [str(fallback) for fallback in info.value.fallbacks] == [
        f"setting 'plain' (key 'plain' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlSettings' fell back to its default: "
        "the TOML file raised RuntimeError (serializer exploded)",
        f"setting 'known' (key 'known' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlSettings' fell back to its default: "
        "the TOML file raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerTomlSettings.plain is None
    assert BrokenSerializerTomlSettings.known == 7
