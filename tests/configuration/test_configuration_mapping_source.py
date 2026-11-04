"""MappingSource tests: the static dictionary link and its live form.

The S rows of the usage matrix walk through the behavior of the chain. This
module pins the own contract of the plugin: the two forms of the builder,
the handle of the resolver, and the vocabulary that the live dictionary
uses.
"""

from __future__ import annotations

import logging

import pytest

from advexp.configuration import Configuration, Sources, chain_setting
from advexp.configuration.plugins.mapping_source import (
    MappingSourceLink,
    mapping_source,
    mapping_source_for,
)


def test_the_builder_refuses_a_non_mapping():
    with pytest.raises(TypeError, match="mapping_source\\(\\) expects a mapping"):
        mapping_source("token=dev-token")


def test_the_no_dictionary_call_declares_the_live_form():
    binding = mapping_source()
    assert isinstance(binding.link, MappingSourceLink)


def test_the_resolver_hands_the_same_link_every_call():
    class C(
        Configuration,
        options=Sources(mapping_source()),
    ):
        token: str = "fallback"

    assert mapping_source_for(C) is mapping_source_for(C)


def test_set_refuses_a_non_mapping():
    class C(
        Configuration,
        options=Sources(mapping_source()),
    ):
        token: str = "fallback"

    with pytest.raises(TypeError, match="expects a mapping of member names to values, got str"):
        mapping_source_for(C).set("token=dev-token")

    with pytest.raises(TypeError, match="expects a mapping of member names to values, got int"):
        mapping_source_for(C).set(8080)


def test_the_live_dictionary_speaks_member_names_alone(caplog):
    # the live form rides the mapping serializer: an explicit name= and
    # declared aliases change nothing for it, and a key naming no member
    # drops out with a debug record — the static form's vocabulary, held
    # by the dictionary that arrives at runtime
    class C(
        Configuration,
        options=Sources(mapping_source()),
    ):
        host: str = chain_setting(name="HOST", aliases=["OLD_HOST"], default="fallback")

    mapping_source_for(C).set({"host": "map-host", "foreign": 42})
    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        C.load_configuration()
    assert C.host == "map-host"
    assert any("does not match any member" in record.getMessage() for record in caplog.records)


def test_the_static_link_still_serves_beside_the_live_one():
    # the two forms are two links of one chain: the static one answers
    # from its own dictionary, the live one from whatever set() last
    # left, and the chain's order decides between them
    class C(
        Configuration,
        options=Sources(mapping_source({"port": 8080}), mapping_source()),
    ):
        port: int = 0
        token: str = "fallback"

    mapping_source_for(C).set({"port": 9000, "token": "dev-token"})
    C.load_configuration()
    assert C.port == 8080  # the static link sits above and answers first
    assert C.token == "dev-token"  # only the live link holds the key
