"""The vocabulary of path parameters: slots, declarations, and per-pass values.

The foundation module ``advexp.settings_base.env_parameter`` carries the
mechanics that both distributions share:

- the slot spelling that a templated file uses;
- the ``env_parameter`` declaration, with its whitelist;
- the per-pass resolution that the load pass scopes.

The tests here hold the own rules of the vocabulary. The configuration
behavior that is built on them (the chain, the loud failures, and the file
families) lives in the usage-matrix section of the package.
"""

from __future__ import annotations

import logging
import os

import pytest

from advexp.configuration import Configuration
from advexp.settings_base.env_parameter import (
    SLOT_SPELLING,
    EnvParameter,
    env_parameter,
    resolve_templated_path,
    template_slots,
)


def test_slots_are_identifiers_in_braces_each_listed_once():
    # the order of first appearance is the order the resolver walks
    assert template_slots("settings-{APP_ENV}.json") == ("APP_ENV",)
    assert template_slots("{A}-{B}-{A}.json") == ("A", "B")
    assert template_slots("app.json") == ()


def test_braces_that_spell_no_identifier_stay_literal():
    # {}, {1} and {a b} name no variable, so they are the file name's
    # own text — no escaping syntax exists or is needed
    assert template_slots("curly-{}.json") == ()
    assert template_slots("set{1}.json") == ()
    assert template_slots("a{b c}.json") == ()
    assert template_slots("{APP_ENV}-{OTHER_X}.json") == ("APP_ENV", "OTHER_X")
    assert SLOT_SPELLING.fullmatch("{valid_name_1}") is not None


def test_the_declaration_carries_its_whitelist_and_slot():
    # the slot is the variable's own name unless slot= renames it, and
    # the whitelist stores as the tuple the link reads
    plain = env_parameter("APP_ENV", choices=["dev", "prod"])
    assert plain.variable == "APP_ENV"
    assert plain.choices == ("dev", "prod")
    assert plain.slot_name == "APP_ENV"
    assert plain.default is None
    assert isinstance(plain, EnvParameter)

    renamed = env_parameter("APP_ENV", choices=["dev"], slot="env")
    assert renamed.slot_name == "env"
    assert renamed.variable == "APP_ENV"


def test_the_declaration_refuses_an_unusable_shape():
    # a variable is a name, a whitelist is non-empty unique strings, a
    # default is one of them, a slot is an identifier
    with pytest.raises(TypeError, match="non-empty variable name"):
        env_parameter("", choices=("dev",))
    with pytest.raises(TypeError, match="expects a sequence"):
        env_parameter("APP_ENV", choices="dev")
    with pytest.raises(TypeError, match="non-empty strings"):
        env_parameter("APP_ENV", choices=("dev", ""))
    with pytest.raises(TypeError, match="expects a string or None"):
        env_parameter("APP_ENV", choices=("dev",), default=1)
    with pytest.raises(TypeError, match="not one of the declared choices"):
        env_parameter("APP_ENV", choices=("dev",), default="test")


def test_the_resolver_unfolds_a_templated_spelling(monkeypatch):
    # the unfolded spelling is the file the link reads this pass
    monkeypatch.setenv("APP_ENV", "dev")
    parameter = env_parameter("APP_ENV", choices=("dev", "prod"))
    context = _context_of_declaration()

    unfolded = resolve_templated_path(
        context, "settings-{APP_ENV}.json", (parameter,), "the test source"
    )
    assert unfolded == "settings-dev.json"


def test_the_resolver_passes_a_bare_spelling_through():
    # no parameters, no resolution: the plain path every unparameterized
    # link spells comes back as given
    context = _context_of_declaration()
    assert resolve_templated_path(context, "app.json", None, "the test source") == "app.json"


def test_one_pass_resolves_a_variable_once_and_the_next_anew(monkeypatch, caplog):
    # the scope is the pass: inside one, the second question reads the
    # remembered value; a later pass reads the environment again, and a
    # resolution outside any scope reads fresh every time
    context = _context_of_declaration()
    parameter = env_parameter("APP_ENV", choices=("dev", "prod"))
    reads: list = []

    real_get = os.environ.get

    def counting_get(name, default=None):
        reads.append(name)
        return real_get(name, default)

    monkeypatch.setenv("APP_ENV", "dev")
    # installed after the setenv: pytest's own undo bookkeeping probes the
    # old value through environ.get and owes no read to the machinery
    monkeypatch.setattr("advexp.settings_base.env_parameter.os.environ.get", counting_get)

    with caplog.at_level(logging.DEBUG):
        context.open_parameter_pass()
        try:
            first = resolve_templated_path(
                context, "a-{APP_ENV}.json", (parameter,), "the test source"
            )
            second = resolve_templated_path(
                context, "b-{APP_ENV}.json", (parameter,), "the test source"
            )
        finally:
            context.close_parameter_pass()
        outside = resolve_templated_path(
            context, "c-{APP_ENV}.json", (parameter,), "the test source"
        )
    assert (first, second, outside) == ("a-dev.json", "b-dev.json", "c-dev.json")
    # one read for the pass — the second question of a pass reads the
    # remembered value — and one more for the probe outside any scope
    assert reads == ["APP_ENV", "APP_ENV"]

    monkeypatch.setenv("APP_ENV", "prod")
    reads.clear()
    with caplog.at_level(logging.DEBUG):
        context.open_parameter_pass()
        try:
            third = resolve_templated_path(
                context, "a-{APP_ENV}.json", (parameter,), "the test source"
            )
        finally:
            context.close_parameter_pass()
    assert third == "a-prod.json"
    assert reads == ["APP_ENV"], "every pass resolves anew, one read a pass"

    # the debug records name the variable, its value and the file
    messages = [record.getMessage() for record in caplog.records]
    assert any("APP_ENV" in m and "'dev'" in m and "a-dev.json" in m for m in messages)
    assert any("APP_ENV" in m and "'prod'" in m and "a-prod.json" in m for m in messages)


def _context_of_declaration():
    """The context of one configuration class, the resolver's seat.

    The resolver needs a context for its pass scope and its logger; any
    settings class of the family carries one.
    """

    class Skeleton(Configuration):
        pass

    return Skeleton.__settings_context__
