"""The distribution boundaries of the settings family.

Two mixes are possible, and both are refused:

- A settings attribute that is placed in a configuration class changes what
  the member means. The attribute bases of the two distributions spell
  different defaults for ``default=``, so a required member would silently
  become an optional one.
- A source builder of one distribution that is placed in a class of the
  other distribution retunes the sources of the wrong class.

Both mixes make the ``class`` statement fail with one line that names the
class, the member (where there is one), and both distributions.

Unstamped spellings pass in any class: the own builders of the family
foundation, and a hand-written mapping. The open channel carries no stamp,
and the skeletons of the foundation belong to no distribution.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import advexp.configuration as adv_config
import advexp.configuration.plugins.json_settings as cjs
import advexp.settings as adv_settings
import advexp.settings.plugins.environment.dotenv as sdot
import advexp.settings.plugins.json_settings as sjs
from advexp.configuration.plugins.environment.variables import env_source as cenv_source
from advexp.settings.plugins.environment.variables import env_source as senv_source
from advexp.settings_base.environment_options import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NESTED_DELIMITER,
)
from advexp.settings_base.environment_options import (
    environment_options as base_options,
)
from advexp.settings_base.sources import ENVIRONMENT_SOURCE_METADATA


def test_settings_attribute_in_configuration_class_fails():
    # the regression of the silent mix: a configuration member declared
    # with the settings package's attribute used to fall back to defaults
    # instead of aborting the load
    with pytest.raises(
        TypeError,
        match="BadConfig.session_ttl is an advexp.settings attribute "
        "in an advexp.configuration class",
    ):

        class BadConfig(adv_config.Configuration):
            session_ttl: timedelta = sjs.json_setting()


def test_configuration_attribute_in_settings_class_fails():
    with pytest.raises(
        TypeError,
        match="BadSettings.session_ttl is an advexp.configuration attribute "
        "in an advexp.settings class",
    ):

        class BadSettings(adv_settings.Settings):
            session_ttl: timedelta = cjs.json_setting()


def test_own_attributes_create_cleanly():
    class AppSettings(adv_settings.Settings):
        session_ttl: timedelta = sjs.json_setting(default=10)

    class AppConfig(
        adv_config.Configuration,
        options=cjs.json_source(file="app.json"),
    ):
        session_ttl: timedelta = cjs.json_setting(default=10)

    assert AppSettings.__settings_members__["session_ttl"] is not None
    assert AppConfig.__settings_members__["session_ttl"] is not None


def test_inherited_members_stay_checked_at_their_declarer():
    # the subclass adds a member of its own distribution beside the
    # inherited one; only the class's own declarations are re-checked
    class Base(adv_settings.Settings):
        session_ttl: timedelta = sjs.json_setting(default=10)

    class Sub(Base):
        timeout: timedelta = sjs.json_setting(default=30)

    assert set(Sub.__settings_members__) == {"session_ttl", "timeout"}


def test_settings_options_in_configuration_class_fail():
    with pytest.raises(
        TypeError,
        match="BadOptions declares advexp.settings options in an advexp.configuration class",
    ):

        class BadOptions(
            adv_config.Configuration,
            options=sjs.json_source(file="x.json"),
        ):
            pass

    with pytest.raises(
        TypeError,
        match="BadSeat declares advexp.settings options in an advexp.configuration class",
    ):
        # the file seat carries the same stamp as the source builder
        class BadSeat(
            adv_config.Configuration,
            options=sjs.json_file("x.json"),
        ):
            pass

    with pytest.raises(
        TypeError,
        match="BadDotenvSeat declares advexp.settings options in an advexp.configuration class",
    ):
        # every family's seat carries the stamp
        class BadDotenvSeat(
            adv_config.Configuration,
            options=sdot.dotenv_file("x.env"),
        ):
            pass


def test_configuration_source_in_settings_class_fails():
    with pytest.raises(
        TypeError,
        match="BadSettings: source chains are provided by advexp.configuration and are not "
        "supported here. Declare this class's sources one builder at a time",
    ):

        class BadSettings(
            adv_settings.Settings,
            options=cenv_source(name_prefix="DEMO_"),
        ):
            pass


def test_source_builder_inside_an_options_sequence_fails():
    with pytest.raises(
        TypeError,
        match="SeqBad: a source builder was passed inside the options= sequence. "
        r"The chain counts as a single entry: pass Sources\(\.\.\.\) "
        "containing the builders to options= instead",
    ):

        class SeqBad(
            adv_config.Configuration,
            options=(cenv_source(name_prefix="DEMO_"), {"app": 1}),
        ):
            pass


def test_body_class_metadata_declaration_is_settled_too():
    with pytest.raises(
        TypeError,
        match="BodyBad declares advexp.settings options in an advexp.configuration class",
    ):

        class BodyBad(adv_config.Configuration):
            class_metadata = senv_source(name_prefix="DEMO_")


def test_own_options_store_the_plain_mapping():
    class AppSettings(
        adv_settings.Settings,
        options=senv_source(name_prefix="APP_"),
    ):
        pass

    stored = vars(AppSettings)["class_metadata"]
    assert type(stored) is dict
    assert set(stored) == {ENVIRONMENT_SOURCE_METADATA, ENVIRONMENT_METADATA_OPTIONS}
    assert stored[ENVIRONMENT_METADATA_OPTIONS] == {
        NAME_PREFIX: "APP_",
        NAME_CASE: None,
        NESTED_DELIMITER: None,
    }


def test_unstamped_options_pass_in_any_class():
    # the foundation's own builder carries no stamp: the open spelling of
    # the shared vocabulary serves both distributions
    class AppSettings(
        adv_settings.Settings,
        options=base_options(name_prefix="APP_"),
    ):
        pass

    class AppConfig(
        adv_config.Configuration,
        options=base_options(name_prefix="APP_"),
    ):
        pass

    expected = {NAME_PREFIX: "APP_", NAME_CASE: None, NESTED_DELIMITER: None}
    assert AppSettings.get_class_metadata(ENVIRONMENT_METADATA_OPTIONS) == expected
    assert vars(AppConfig)["class_metadata"] == {ENVIRONMENT_METADATA_OPTIONS: expected}


def test_roots_of_two_families_cannot_build_one_class():
    with pytest.raises(TypeError, match="metaclass conflict"):
        # the class statement itself is the refusal under test; the
        # checker flags the very mixing the runtime must reject. The
        # roots carry sibling metaclasses — each distribution expands the
        # shared base with its own declarations — so Python's own conflict
        # is the mix's first refusal, before any family check runs
        class Mixed(  # type: ignore[metaclass, misc]
            adv_settings.Settings, adv_config.Configuration
        ):
            pass
