"""MappingSource storage tests: the binding, the seat, and the resolver.

The S rows of the usage matrix walk through the behavior of the storage.
This module pins the own contract of the plugin: the two spellings of the
builder, the refusals of the resolver, and the validation in ``set()``.
"""

from __future__ import annotations

import pytest

from advexp.settings import Settings
from advexp.settings.plugins.environment.variables import env_source
from advexp.settings.plugins.mapping_source import (
    MappingStorageLink,
    mapping_source,
    mapping_source_for,
)
from advexp.settings.plugins.mapping_source.serializer import MAPPING_SOURCE_METADATA


def test_the_builder_refuses_a_non_mapping():
    with pytest.raises(TypeError, match="mapping_source\\(\\) expects a mapping"):
        mapping_source("token=dev-token")


def test_the_builder_binds_the_seat_key():
    entry = mapping_source()
    assert set(entry) == {MAPPING_SOURCE_METADATA}
    assert isinstance(entry[MAPPING_SOURCE_METADATA], MappingStorageLink)


def test_the_resolver_refuses_a_class_the_family_never_built():
    class Plain:
        pass

    with pytest.raises(TypeError, match="Plain is not a settings class"):
        mapping_source_for(Plain)


def test_the_resolver_refuses_a_class_without_the_binding():
    class S(
        Settings,
        options=env_source(name_prefix="MSX_"),
    ):
        token: str = "t"

    with pytest.raises(TypeError, match="S declares no mapping storage"):
        mapping_source_for(S)


def test_set_refuses_a_non_mapping():
    class S(
        Settings,
        options=mapping_source(),
    ):
        token: str = "t"

    with pytest.raises(TypeError, match="expects a mapping of member names to values, got str"):
        mapping_source_for(S).set("token=dev-token")

    with pytest.raises(TypeError, match="expects a mapping of member names to values, got int"):
        mapping_source_for(S).set(8080)
