# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The declaration base mechanics: the marker and the pour itself.

The usage-matrix sections (Z of settings, W of configuration) walk the same
machinery through whole classes; this module drives the pieces directly,
without a settings class, the way the pour sees them.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from advexp.settings import Settings
from advexp.settings.plugins.environment.variables import env_source
from advexp.settings_base import SettingDeclarations, setting
from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.setting_declarations import expand_base_declarations


class ThirdPartyAttribute(BaseAttribute):
    """An attribute printed with a family of its own, as a plugin author's
    backend attribute is."""

    FAMILY_NAME = "advexp.settings"


def _third_party() -> ThirdPartyAttribute:
    return ThirdPartyAttribute(
        name=None,
        default=None,
        metadata=None,
        aliases=None,
        gt=None,
        ge=None,
        lt=None,
        le=None,
        eq=None,
        ne=None,
        min_length=None,
        max_length=None,
        regex=None,
        validator=None,
    )


def test_the_marker_beside_a_settings_base_makes_a_settings_class():
    # the metaclass of the settings base wins: such a class is a settings
    # class from the start, and the marker adds nothing to it
    class Direct(
        SettingDeclarations,
        Settings,
        options=env_source(),
    ):
        answer: int = 1

    assert "answer" in Direct.__settings_members__


def test_marker_refuses_a_printed_attribute():
    with pytest.raises(
        TypeError,
        match="Blueprint.token is an advexp.settings attribute in a declaration base",
    ):

        class Blueprint(SettingDeclarations):
            token = _third_party()


def test_unmarked_plain_base_stays_silent():
    class Plain:
        answer: int = 1

    namespace: dict = {}
    expand_base_declarations(namespace, (Plain, object), "S")
    assert namespace == {}


def test_pour_wraps_plain_and_factory_declarations():
    class Blueprint(SettingDeclarations):
        retries: int = 3
        bare: str
        limit: ClassVar[int] = 9
        low = setting(default=0)
        high = setting(default=10, ge=low)

    namespace: dict = {"body_member": setting(default=1, ge=Blueprint.low)}
    expand_base_declarations(namespace, (Blueprint, object), "S")

    assert sorted(namespace) == ["bare", "body_member", "high", "low", "retries"]
    assert namespace["retries"].default == 3
    assert namespace["bare"].default is REQUIRED
    assert "limit" not in namespace  # a ClassVar is no declaration

    # one copy pass with one shared memo: the references land on the copies
    assert namespace["high"].constraint_member_rules[0].reference is namespace["low"]
    # the body's reference onto the base's declaration turns onto the copy
    assert namespace["body_member"].constraint_member_rules[0].reference is namespace["low"]
    # the originals stay untouched: the blueprint is inert after the pour
    assert Blueprint.high.constraint_member_rules[0].reference is Blueprint.low
    assert Blueprint.low is not namespace["low"]


def test_mutable_defaults_are_copied_not_shared():
    class Blueprint(SettingDeclarations):
        plain: list = [1]
        rich = setting(default=[2])

    first: dict = {}
    second: dict = {}
    expand_base_declarations(first, (Blueprint, object), "B")
    expand_base_declarations(second, (Blueprint, object), "C")

    assert first["plain"].default is not second["plain"].default
    assert first["plain"].default == second["plain"].default == [1]
    assert first["rich"].default is not second["rich"].default


def test_body_wins_and_the_lost_reference_is_named():
    class Blueprint(SettingDeclarations):
        low = setting(default=0)
        high = setting(default=10, ge=low)

    namespace = {"low": setting(default=5)}
    with pytest.raises(
        TypeError,
        match="S.high references 'low' in ge=, but the body of S overrides 'low'",
    ):
        expand_base_declarations(namespace, (Blueprint, object), "S")


def test_body_reference_to_an_overridden_name_is_refused():
    class Blueprint(SettingDeclarations):
        low = setting(default=0)
        other = setting(default=7)

    namespace = {
        "x": setting(default=1, ge=Blueprint.low),
        "low": setting(default=5),
    }
    with pytest.raises(
        TypeError,
        match="S.x references 'low' in ge=, but the body of S overrides 'low'",
    ):
        expand_base_declarations(namespace, (Blueprint, object), "S")


def test_more_derived_base_wins():
    class Base(SettingDeclarations):
        answer: int = 1

    class Derived(Base):
        answer: int = 2

    namespace: dict = {}
    expand_base_declarations(namespace, (Derived, object), "S")
    assert namespace["answer"].default == 2


def test_a_printed_attribute_of_an_unmarked_chain_class_is_refused():
    # the marker guards its own body; an unmarked mixin between the base and
    # the settings class meets the same refusal at the pour
    class Carrier:
        token = _third_party()

    class Marked(SettingDeclarations):
        pass

    with pytest.raises(TypeError, match="S inherits Carrier.token, an advexp.settings attribute"):
        expand_base_declarations({}, (Carrier, Marked, object), "S")


def test_a_when_condition_pours_and_redirects_like_a_rule():
    class Blueprint(SettingDeclarations):
        flag = setting(default=False)
        gated = setting(default=1, when=flag)

    namespace = {"body_gated": setting(default=2, when=Blueprint.flag)}
    expand_base_declarations(namespace, (Blueprint, object), "S")
    assert namespace["gated"].constraint_condition is namespace["flag"]
    assert namespace["body_gated"].constraint_condition is namespace["flag"]
