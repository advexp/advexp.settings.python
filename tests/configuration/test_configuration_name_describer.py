# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The bundled sources of the package implement the name describer.

This is the structural counterpart of the check of the settings package. A
walk over the plugins tree collects every serializer class that the sources
of the package define. A source that is added later therefore joins the
check without a test edit, and a backend that is built on the raw
``ISettingsSerializer`` contract cannot quietly stay outside the load
diagnostics of the family.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import List, Set

import pytest

import advexp.configuration.plugins
from advexp.configuration import AggregateLoadError, Configuration, MissingValueError
from advexp.configuration.plugin_api import (
    REQUIRED,
    ISettingNameDescriber,
    ISettingsSerializer,
    ISourceDescriber,
)
from advexp.configuration.plugins.environment.variables import (
    env_source,
    environment_variable_setting,
)

_PLUGINS_PREFIX = "advexp.configuration.plugins."


def _bundled_serializers() -> List[type]:
    """Return every serializer class that the plugin modules of the package
    define.

    The walk is the point: a source that is added later joins the checks without
    a test edit. Only classes that are defined under the ``plugins`` tree of the
    package count. A module that re-exports the class of a sibling source adds
    nothing new.
    """
    found: Set[type] = set()
    for info in pkgutil.walk_packages(advexp.configuration.plugins.__path__, _PLUGINS_PREFIX):
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
    assert issubclass(serializer_class, ISettingNameDescriber)
    assert issubclass(serializer_class, ISourceDescriber)


def test_abort_lists_the_aliases_beside_the_primary_address(monkeypatch):
    # a miss spells every address the pass checked: the reader of the
    # abort sees the old names too, not only the primary one
    class TokenConfiguration(
        Configuration,
        options=env_source(),
    ):
        token: str = environment_variable_setting(
            name="APP_TOKEN", aliases=["APP_TOKEN_OLD"], default=REQUIRED
        )

    for name in ("APP_TOKEN", "APP_TOKEN_OLD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(AggregateLoadError) as info:
        TokenConfiguration.load_configuration()

    assert "(environment variable 'APP_TOKEN' (aliases: 'APP_TOKEN_OLD'))" in str(
        info.value.errors[0]
    )
    assert isinstance(info.value.errors[0], MissingValueError)
