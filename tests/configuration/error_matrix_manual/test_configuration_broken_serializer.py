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
from configuration_serializer_classes import (
    BROKEN_SERIALIZER_DOTENV_FILE,
    BROKEN_SERIALIZER_JSON_FILE,
    BROKEN_SERIALIZER_TOML_FILE,
    BrokenSerializerDotenvConfiguration,
    BrokenSerializerEnvConfiguration,
    BrokenSerializerJsonConfiguration,
    BrokenSerializerTomlConfiguration,
)

from advexp.configuration import AggregateLoadError, SourceLoadError
from advexp.configuration.plugins.environment.dotenv import DotenvSerializer
from advexp.configuration.plugins.environment.variables import (
    EnvironmentVariablesSerializer,
)
from advexp.configuration.plugins.json_settings import JSONSettingsSerializer
from advexp.configuration.plugins.toml_settings import TOMLSettingsSerializer


def exploding_load(self, setting_name, attr):
    """A serializer ``load`` that breaks: the stand-in for a failing source."""
    raise RuntimeError("serializer exploded")


def test_broken_serializer_env(monkeypatch, caplog):
    """The environment serializer's read breaks."""
    monkeypatch.setattr(EnvironmentVariablesSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerEnvConfiguration.load_configuration()

    # the exception is logged per member in the full fallback shape: the
    # member's place, the source that raised, and the fallback tail an
    # optional member earns
    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        "member 'answer' (environment variable 'EMC_ANSWER') "
        "of 'BrokenSerializerEnvConfiguration': "
        "the process environment raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        "member 'plain' (environment variable 'EMC_PLAIN') "
        "of 'BrokenSerializerEnvConfiguration': "
        "the process environment raised RuntimeError (serializer exploded); "
        "using the default value"
    ) in error_messages

    # the required members collected their source errors
    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        "member 'answer' (environment variable 'EMC_ANSWER') "
        "of 'BrokenSerializerEnvConfiguration' is required: "
        "the process environment raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)

    # the optional members stood at their defaults with a report entry each
    assert [str(fallback) for fallback in info.value.fallbacks] == [
        "member 'plain' (environment variable 'EMC_PLAIN') "
        "of 'BrokenSerializerEnvConfiguration' fell back to its default: "
        "the process environment raised RuntimeError (serializer exploded)",
        "member 'known' (environment variable 'EMC_KNOWN') "
        "of 'BrokenSerializerEnvConfiguration' fell back to its default: "
        "the process environment raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerEnvConfiguration.plain is None
    assert BrokenSerializerEnvConfiguration.known == 7


def test_broken_serializer_dotenv(monkeypatch, caplog):
    """The dotenv serializer's read breaks."""
    monkeypatch.setattr(DotenvSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerDotenvConfiguration.load_configuration()

    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvConfiguration': "
        "the dotenv file raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        f"member 'plain' (environment variable 'EMC_PLAIN' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvConfiguration': "
        "the dotenv file raised RuntimeError (serializer exploded); using the default value"
    ) in error_messages

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvConfiguration' "
        "is required: the dotenv file raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)

    assert [str(fallback) for fallback in info.value.fallbacks] == [
        f"member 'plain' (environment variable 'EMC_PLAIN' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvConfiguration' "
        "fell back to its default: "
        "the dotenv file raised RuntimeError (serializer exploded)",
        f"member 'known' (environment variable 'EMC_KNOWN' in the dotenv file "
        f"{BROKEN_SERIALIZER_DOTENV_FILE}) of 'BrokenSerializerDotenvConfiguration' "
        "fell back to its default: "
        "the dotenv file raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerDotenvConfiguration.plain is None
    assert BrokenSerializerDotenvConfiguration.known == 7


def test_broken_serializer_json(monkeypatch, caplog):
    """The JSON serializer's read breaks."""
    monkeypatch.setattr(JSONSettingsSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerJsonConfiguration.load_configuration()

    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        f"member 'answer' (key 'answer' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonConfiguration': "
        "the JSON file raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        f"member 'plain' (key 'plain' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonConfiguration': "
        "the JSON file raised RuntimeError (serializer exploded); using the default value"
    ) in error_messages

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonConfiguration' is required: "
        "the JSON file raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)

    assert [str(fallback) for fallback in info.value.fallbacks] == [
        f"member 'plain' (key 'plain' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonConfiguration' fell back to its default: "
        "the JSON file raised RuntimeError (serializer exploded)",
        f"member 'known' (key 'known' in the JSON file {BROKEN_SERIALIZER_JSON_FILE}) "
        "of 'BrokenSerializerJsonConfiguration' fell back to its default: "
        "the JSON file raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerJsonConfiguration.plain is None
    assert BrokenSerializerJsonConfiguration.known == 7


def test_broken_serializer_toml(monkeypatch, caplog):
    """The TOML serializer's read breaks."""
    monkeypatch.setattr(TOMLSettingsSerializer, "load", exploding_load)

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenSerializerTomlConfiguration.load_configuration()

    error_messages = [
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    ]
    assert (
        f"member 'answer' (key 'answer' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlConfiguration': "
        "the TOML file raised RuntimeError (serializer exploded)"
    ) in error_messages
    assert (
        f"member 'plain' (key 'plain' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlConfiguration': "
        "the TOML file raised RuntimeError (serializer exploded); using the default value"
    ) in error_messages

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlConfiguration' is required: "
        "the TOML file raised RuntimeError (serializer exploded)"
    )
    assert isinstance(error.__cause__, RuntimeError)

    assert [str(fallback) for fallback in info.value.fallbacks] == [
        f"member 'plain' (key 'plain' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlConfiguration' fell back to its default: "
        "the TOML file raised RuntimeError (serializer exploded)",
        f"member 'known' (key 'known' in the TOML file {BROKEN_SERIALIZER_TOML_FILE}) "
        "of 'BrokenSerializerTomlConfiguration' fell back to its default: "
        "the TOML file raised RuntimeError (serializer exploded)",
    ]
    assert BrokenSerializerTomlConfiguration.plain is None
    assert BrokenSerializerTomlConfiguration.known == 7
