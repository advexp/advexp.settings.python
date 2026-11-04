"""Declarative metadata: ``metadata=`` on attributes, ``class_metadata``."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from advexp.settings import LibraryConfiguration, Settings
from advexp.settings._internal.non_storage_setting import non_storage_setting
from advexp.settings.plugin_api import (
    NOT_FOUND,
    SettingsAttribute,
    SettingsBaseSerializer,
)
from advexp.settings.plugins.environment.variables import environment_variable_setting
from advexp.settings.plugins.json_settings import json_setting

# ---------------------------------------------------------------------------
# declared member and class metadata seed the runtime channel
# ---------------------------------------------------------------------------


class SeededSettings(Settings):
    class_metadata = {"config-version": 2, "origin": "seed"}

    mode: str = non_storage_setting(
        default="production", metadata={"ui-label": "Mode", "ui-order": 1}
    )
    api_token: Optional[str] = non_storage_setting(default=None, metadata={"secret": True})
    retries: int = non_storage_setting(default=3)


def test_declared_member_metadata_is_readable():
    assert SeededSettings.get_setting_metadata("mode", "ui-label") == "Mode"
    assert SeededSettings.get_setting_metadata("mode", "ui-order") == 1
    assert SeededSettings.get_setting_metadata("mode", "missing", "fallback") == "fallback"
    assert SeededSettings.get_setting_all_metadata("mode") == {"ui-label": "Mode", "ui-order": 1}
    assert SeededSettings.contains_setting_metadata("mode", "ui-label")
    assert not SeededSettings.contains_setting_metadata("mode", "missing")


def test_declared_none_is_a_value_like_any_other():
    class NoneMarkedSettings(Settings):
        flag: bool = non_storage_setting(default=False, metadata={"note": None})

    assert NoneMarkedSettings.contains_setting_metadata("flag", "note")
    assert NoneMarkedSettings.get_setting_metadata("flag", "note", "fallback") is None


def test_member_without_metadata_answers_empty():
    assert SeededSettings.get_setting_all_metadata("retries") == {}
    assert not SeededSettings.contains_setting_metadata("retries", "anything")
    assert SeededSettings.get_setting_metadata("retries", "anything") is None


def test_declared_class_metadata_is_readable():
    assert SeededSettings.get_class_metadata("config-version") == 2
    assert SeededSettings.get_class_metadata("origin") == "seed"
    assert SeededSettings.get_class_metadata("missing", "fallback") == "fallback"
    assert SeededSettings.get_class_all_metadata() == {"config-version": 2, "origin": "seed"}
    assert SeededSettings.contains_class_metadata("config-version")
    assert not SeededSettings.contains_class_metadata("missing")


def test_class_without_declaration_answers_empty():
    class BareSettings(Settings):
        flag: bool = non_storage_setting(default=False)

    assert BareSettings.get_class_all_metadata() == {}


# ---------------------------------------------------------------------------
# the class keyword: options= is the readable spelling of the declaration
# ---------------------------------------------------------------------------


def test_class_keyword_seeds_the_same_declared_channel():
    class KeywordSettings(
        Settings,
        options={"origin": "keyword"},
    ):
        flag: bool = non_storage_setting(default=False)

    assert KeywordSettings.get_class_all_metadata() == {"origin": "keyword"}
    # a declared entry's lifecycle: the runtime delete does not bring it back
    KeywordSettings.delete_class_metadata("origin")
    assert KeywordSettings.get_class_all_metadata() == {}
    KeywordSettings.set_class_metadata("runtime", 1)
    assert KeywordSettings.get_class_all_metadata() == {"runtime": 1}


def test_class_keyword_entry_inherits_along_the_mro():
    class BaseSettings(
        Settings,
        options={"origin": "keyword"},
    ):
        flag: bool = non_storage_setting(default=False)

    class ChildSettings(BaseSettings):
        pass

    assert ChildSettings.get_class_all_metadata() == {"origin": "keyword"}


def test_class_keyword_and_body_declaration_merge():
    class CombinedSettings(
        Settings,
        options={"origin": "keyword"},
    ):
        class_metadata = {"config-version": 2}
        flag: bool = non_storage_setting(default=False)

    # one channel, both spellings: the keyword's entry and the body's
    # free keys merge — the family key and the application's keys do not
    # meet (a family's key is its own long distinctive name)
    assert CombinedSettings.get_class_all_metadata() == {
        "origin": "keyword",
        "config-version": 2,
    }


def test_shared_name_fails_the_class_statement():
    with pytest.raises(TypeError, match="Declare each name only once"):

        class SharedSettings(
            Settings,
            options={"origin": "keyword"},
        ):
            class_metadata = {"origin": "body", "kept": True}
            flag: bool = non_storage_setting(default=False)


def test_shared_names_are_all_named_in_the_error():
    # every shared name lands in the message: the error points at the
    # whole overlap, not its first member
    with pytest.raises(TypeError, match=r"'another', 'origin'"):

        class SharedSettings(
            Settings,
            options={"origin": 1, "another": 2},
        ):
            class_metadata = {"origin": "body", "another": "body"}
            flag: bool = non_storage_setting(default=False)


# ---------------------------------------------------------------------------
# the keyword's sequence form: several option mappings in one options=
# ---------------------------------------------------------------------------


def test_sequence_form_combines_entries():
    class SequenceSettings(
        Settings,
        options=({"origin": "keyword"}, {"config-version": 2}),
    ):
        flag: bool = non_storage_setting(default=False)

    assert SequenceSettings.get_class_all_metadata() == {
        "origin": "keyword",
        "config-version": 2,
    }


def test_sequence_form_accepts_a_list_too():
    class ListSettings(
        Settings,
        options=[{"origin": "keyword"}, {"config-version": 2}],
    ):
        flag: bool = non_storage_setting(default=False)

    assert ListSettings.get_class_all_metadata() == {
        "origin": "keyword",
        "config-version": 2,
    }


def test_empty_sequence_declares_nothing():
    class EmptySequenceSettings(
        Settings,
        options=(),
    ):
        class_metadata = {"config-version": 2}
        flag: bool = non_storage_setting(default=False)

    assert EmptySequenceSettings.get_class_all_metadata() == {"config-version": 2}


def test_sequence_form_merges_with_the_body_declaration():
    class SequenceBodySettings(
        Settings,
        options=({"origin": "keyword"}, {"window": {"x": 10}}),
    ):
        class_metadata = {"config-version": 2}
        flag: bool = non_storage_setting(default=False)

    assert SequenceBodySettings.get_class_all_metadata() == {
        "origin": "keyword",
        "window": {"x": 10},
        "config-version": 2,
    }


def test_name_shared_by_two_entries_fails_the_class_statement():
    with pytest.raises(TypeError, match="more than once in options="):

        class SharedSettings(
            Settings,
            options=({"origin": 1}, {"origin": 2}),
        ):
            flag: bool = non_storage_setting(default=False)


def test_all_names_shared_across_entries_are_named_in_the_error():
    # the overlap is collected across every entry, not only the first pair
    with pytest.raises(TypeError, match=r"'another', 'origin'"):

        class SharedSettings(
            Settings,
            options=({"origin": 1, "another": 1}, {"origin": 2}, {"another": 2}),
        ):
            flag: bool = non_storage_setting(default=False)


def test_name_shared_by_an_entry_and_the_body_fails_the_class_statement():
    with pytest.raises(TypeError, match="in both class_metadata and options="):

        class SharedSettings(
            Settings,
            options=({"origin": "keyword"},),
        ):
            class_metadata = {"origin": "body"}
            flag: bool = non_storage_setting(default=False)


# ---------------------------------------------------------------------------
# the runtime layer works over the declarations
# ---------------------------------------------------------------------------


def test_runtime_set_overrides_and_extends_the_declaration():
    class MutableSettings(Settings):
        class_metadata = {"config-version": 2, "origin": "seed"}
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode", "ui-order": 1})

    MutableSettings.set_setting_metadata("mode", "ui-label", "Application mode")
    MutableSettings.set_setting_metadata("mode", "hint", "Runtime hint")
    assert MutableSettings.get_setting_all_metadata("mode") == {
        "ui-label": "Application mode",
        "ui-order": 1,
        "hint": "Runtime hint",
    }

    MutableSettings.set_class_metadata("origin", "runtime")
    MutableSettings.set_class_metadata("window", {"x": 10})
    assert MutableSettings.get_class_all_metadata() == {
        "config-version": 2,
        "origin": "runtime",
        "window": {"x": 10},
    }


def test_runtime_delete_removes_a_declared_entry():
    class DeletableSettings(Settings):
        class_metadata = {"origin": "seed"}
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode", "ui-order": 1})

    DeletableSettings.delete_setting_metadata("mode", "ui-label")
    assert not DeletableSettings.contains_setting_metadata("mode", "ui-label")
    assert DeletableSettings.get_setting_all_metadata("mode") == {"ui-order": 1}

    DeletableSettings.delete_class_metadata("origin")
    assert not DeletableSettings.contains_class_metadata("origin")
    assert DeletableSettings.get_class_all_metadata() == {}


def test_runtime_clear_takes_the_declarations_along():
    class ClearableSettings(Settings):
        class_metadata = {"origin": "seed"}
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode"})

    ClearableSettings.delete_class_all_metadata()
    assert ClearableSettings.get_class_all_metadata() == {}
    # the member side is untouched: the clear is the class-level storage's own
    assert ClearableSettings.get_setting_all_metadata("mode") == {"ui-label": "Mode"}


# ---------------------------------------------------------------------------
# inheritance
# ---------------------------------------------------------------------------


def test_member_metadata_follows_the_member_by_mro():
    class BaseSettings(Settings):
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode"})

    class ChildSettings(BaseSettings):
        pass

    assert ChildSettings.get_setting_all_metadata("mode") == {"ui-label": "Mode"}

    # runtime on the subclass adds keys on top of the inherited ones and
    # leaves the base alone
    ChildSettings.set_setting_metadata("mode", "child-only", True)
    assert ChildSettings.get_setting_all_metadata("mode") == {
        "ui-label": "Mode",
        "child-only": True,
    }
    assert BaseSettings.get_setting_all_metadata("mode") == {"ui-label": "Mode"}


def test_member_redeclaration_replaces_metadata_wholesale():
    class BaseSettings(Settings):
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode", "ui-order": 1})

    class ChildSettings(BaseSettings):
        mode: str = non_storage_setting(default="dev", metadata={"ui-label": "Child mode"})

    # no per-key merge: the redeclaration's metadata is the whole state
    assert ChildSettings.get_setting_all_metadata("mode") == {"ui-label": "Child mode"}
    # the base class keeps its own view
    assert BaseSettings.get_setting_all_metadata("mode") == {"ui-label": "Mode", "ui-order": 1}
    # a base runtime write on the old declaration never leaks into the
    # redeclared member: its chain ends at the subclass
    BaseSettings.set_setting_metadata("mode", "ui-order", 9)
    assert ChildSettings.get_setting_all_metadata("mode") == {"ui-label": "Child mode"}


# ---------------------------------------------------------------------------
# member metadata resolves the chain like class metadata: a write into a
# base reaches the subclasses, a subclass's write never touches its bases
# ---------------------------------------------------------------------------


def test_member_runtime_write_on_the_base_reaches_the_subclasses():
    class BaseSettings(Settings):
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode"})

    class ChildSettings(BaseSettings):
        other: bool = non_storage_setting(default=False)

    BaseSettings.set_setting_metadata("mode", "ui-label", "Runtime mode")
    BaseSettings.set_setting_metadata("mode", "hint", "Runtime hint")
    assert ChildSettings.get_setting_metadata("mode", "ui-label") == "Runtime mode"
    assert ChildSettings.get_setting_metadata("mode", "hint") == "Runtime hint"
    assert ChildSettings.contains_setting_metadata("mode", "hint")
    assert ChildSettings.get_setting_all_metadata("mode") == {
        "ui-label": "Runtime mode",
        "hint": "Runtime hint",
    }

    # a subclass created after the write sees it too
    class LateChildSettings(BaseSettings):
        pass

    assert LateChildSettings.get_setting_metadata("mode", "hint") == "Runtime hint"


def test_member_runtime_write_on_a_subclass_stays_local():
    class BaseSettings(Settings):
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode"})

    class ChildSettings(BaseSettings):
        pass

    ChildSettings.set_setting_metadata("mode", "ui-label", "Child mode")
    assert ChildSettings.get_setting_metadata("mode", "ui-label") == "Child mode"
    assert BaseSettings.get_setting_metadata("mode", "ui-label") == "Mode"


def test_member_delete_removes_only_the_own_entry_and_answers():
    class BaseSettings(Settings):
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode"})

    class ChildSettings(BaseSettings):
        pass

    # no own entry: the delete answers False, the base's declaration stays
    assert ChildSettings.delete_setting_metadata("mode", "ui-label") is False
    assert ChildSettings.get_setting_metadata("mode", "ui-label") == "Mode"

    # an own entry (a runtime write): gone, the base's takes over again
    ChildSettings.set_setting_metadata("mode", "ui-label", "Child mode")
    assert ChildSettings.delete_setting_metadata("mode", "ui-label") is True
    assert ChildSettings.get_setting_metadata("mode", "ui-label") == "Mode"

    # the declarer's own delete is the one that removes the entry everywhere
    assert BaseSettings.delete_setting_metadata("mode", "ui-label") is True
    assert BaseSettings.get_setting_metadata("mode", "ui-label") is None
    assert ChildSettings.get_setting_metadata("mode", "ui-label") is None


def test_class_delete_answers_whether_an_own_entry_went():
    class BaseSettings(Settings):
        class_metadata = {"origin": "base"}

    class ChildSettings(BaseSettings):
        pass

    # no own entry: False, and the ancestor's entry stays visible
    assert ChildSettings.delete_class_metadata("origin") is False
    assert ChildSettings.get_class_metadata("origin") == "base"

    ChildSettings.set_class_metadata("origin", "child")
    assert ChildSettings.delete_class_metadata("origin") is True
    assert ChildSettings.get_class_metadata("origin") == "base"

    assert BaseSettings.delete_class_metadata("origin") is True
    assert BaseSettings.get_class_metadata("origin") is None


def test_member_chain_stops_at_the_redeclaring_class():
    # a member redeclared in the middle of a chain: the classes above the
    # redeclarer hold a different declaration of the same name, and it
    # never leaks down
    class GrandSettings(Settings):
        mode: str = non_storage_setting(default="g", metadata={"ui-label": "Grand"})

    class MiddleSettings(GrandSettings):
        mode: str = non_storage_setting(default="m", metadata={"ui-label": "Middle"})

    class LeafSettings(MiddleSettings):
        pass

    assert LeafSettings.get_setting_all_metadata("mode") == {"ui-label": "Middle"}
    GrandSettings.set_setting_metadata("mode", "hint", "grand hint")
    assert LeafSettings.get_setting_metadata("mode", "hint") is None
    assert GrandSettings.get_setting_metadata("mode", "hint") == "grand hint"


def test_class_metadata_merges_along_the_mro():
    class GrandSettings(Settings):
        class_metadata = {"config-version": 1, "origin": "grand", "scope": "root"}

    class MiddleSettings(GrandSettings):
        class_metadata = {"config-version": 2, "origin": "middle"}

    class LeafSettings(MiddleSettings):
        class_metadata = {"origin": "leaf"}

    # per key the most derived declaration wins, the rest carry over
    assert GrandSettings.get_class_all_metadata() == {
        "config-version": 1,
        "origin": "grand",
        "scope": "root",
    }
    assert MiddleSettings.get_class_all_metadata() == {
        "config-version": 2,
        "origin": "middle",
        "scope": "root",
    }
    assert LeafSettings.get_class_all_metadata() == {
        "config-version": 2,
        "origin": "leaf",
        "scope": "root",
    }


def test_subclass_without_own_declaration_inherits_the_base_one():
    class BaseSettings(Settings):
        class_metadata = {"origin": "base"}

    class ChildSettings(BaseSettings):
        other: bool = non_storage_setting(default=False)

    assert ChildSettings.get_class_all_metadata() == {"origin": "base"}
    ChildSettings.set_class_metadata("extra", 1)
    assert BaseSettings.get_class_all_metadata() == {"origin": "base"}


# ---------------------------------------------------------------------------
# the runtime channel resolves the chain live: a write into a base reaches
# the subclasses, a subclass's write never touches its bases
# ---------------------------------------------------------------------------


def test_runtime_write_on_the_base_reaches_the_subclasses():
    class BaseSettings(Settings):
        class_metadata = {"origin": "base"}
        flag: bool = non_storage_setting(default=False)

    class ChildSettings(BaseSettings):
        pass

    BaseSettings.set_class_metadata("origin", "runtime")
    BaseSettings.set_class_metadata("extra", 1)
    assert ChildSettings.get_class_metadata("origin") == "runtime"
    assert ChildSettings.get_class_metadata("extra") == 1
    assert ChildSettings.get_class_all_metadata() == {"origin": "runtime", "extra": 1}
    assert BaseSettings.get_class_all_metadata() == {"origin": "runtime", "extra": 1}


def test_subclass_created_after_a_runtime_write_sees_it():
    class BaseSettings(Settings):
        class_metadata = {"origin": "base"}
        flag: bool = non_storage_setting(default=False)

    BaseSettings.set_class_metadata("origin", "runtime")

    class LateChildSettings(BaseSettings):
        pass

    assert LateChildSettings.get_class_metadata("origin") == "runtime"


def test_runtime_write_on_a_subclass_stays_local():
    class BaseSettings(Settings):
        class_metadata = {"origin": "base"}

    class ChildSettings(BaseSettings):
        pass

    ChildSettings.set_class_metadata("origin", "child")
    assert ChildSettings.get_class_metadata("origin") == "child"
    assert BaseSettings.get_class_metadata("origin") == "base"


def test_subclass_delete_removes_only_the_own_entry():
    class BaseSettings(Settings):
        class_metadata = {"origin": "base"}

    class ChildSettings(BaseSettings):
        pass

    # no own entry: the delete is a no-op, the base's stays visible
    ChildSettings.delete_class_metadata("origin")
    assert ChildSettings.get_class_metadata("origin") == "base"

    # an own entry (a runtime write): gone, the base's takes over again
    ChildSettings.set_class_metadata("origin", "child")
    ChildSettings.delete_class_metadata("origin")
    assert ChildSettings.get_class_metadata("origin") == "base"

    # the base's own delete is the one that removes the entry everywhere below
    BaseSettings.delete_class_metadata("origin")
    assert BaseSettings.get_class_metadata("origin") is None
    assert ChildSettings.get_class_metadata("origin") is None


def test_clear_takes_only_the_own_entries_along():
    class BaseSettings(Settings):
        class_metadata = {"origin": "base"}

    class ChildSettings(BaseSettings):
        class_metadata = {"child-key": 1}

    ChildSettings.set_class_metadata("runtime-key", 2)
    ChildSettings.delete_class_all_metadata()
    # the child's own entries are gone; the base's stay visible through the chain
    assert ChildSettings.get_class_all_metadata() == {"origin": "base"}
    assert BaseSettings.get_class_all_metadata() == {"origin": "base"}


def test_plain_base_class_contributes_its_declaration():
    # a non-settings mixin in the MRO is a declaration point like any other
    class Mixin:
        class_metadata = {"origin": "mixin"}

    class MixedSettings(Mixin, Settings):
        flag: bool = non_storage_setting(default=False)

    assert MixedSettings.get_class_all_metadata() == {"origin": "mixin"}


# ---------------------------------------------------------------------------
# isolation
# ---------------------------------------------------------------------------


def test_declaration_mutation_after_class_creation_stays_out():
    declared_member = {"ui-label": "Mode", "nested": {"items": [1]}}
    declared_class = {"window": {"x": 10}}

    class IsolatedSettings(Settings):
        class_metadata = declared_class
        mode: str = non_storage_setting(default="x", metadata=declared_member)

    # a subclass created before any mutation reads the same declaration
    class SiblingSettings(IsolatedSettings):
        pass

    declared_member["ui-label"] = "MUTATED"
    declared_member["nested"]["items"].append(2)
    declared_class["window"]["x"] = 999

    assert IsolatedSettings.get_setting_all_metadata("mode") == {
        "ui-label": "Mode",
        "nested": {"items": [1]},
    }
    assert IsolatedSettings.get_class_all_metadata() == {"window": {"x": 10}}
    assert SiblingSettings.get_setting_all_metadata("mode") == {
        "ui-label": "Mode",
        "nested": {"items": [1]},
    }

    # the declared dict is a seed taken once; a later mutation of it never
    # reaches the storage — live changes go through the runtime channel
    IsolatedSettings.set_setting_metadata("mode", "ui-label", "runtime")
    assert SiblingSettings.get_setting_metadata("mode", "ui-label") == "runtime"
    assert declared_member["ui-label"] == "MUTATED"  # the caller's dict untouched too


def test_getters_return_copies():
    class SnapshotSettings(Settings):
        mode: str = non_storage_setting(default="x", metadata={"ui-label": "Mode"})

    snapshot = SnapshotSettings.get_setting_all_metadata("mode")
    snapshot["ui-label"] = "MUTATED"
    assert SnapshotSettings.get_setting_metadata("mode", "ui-label") == "Mode"


def test_attribute_metadata_property_serves_isolated_copies():
    attribute = SettingsAttribute(default=1, metadata={"k": {"deep": [1]}})

    first = attribute.metadata
    first["k"]["deep"].append(2)
    assert attribute.metadata == {"k": {"deep": [1]}}
    assert attribute.metadata is not attribute.metadata

    # nothing declared: an empty dict, not None
    assert SettingsAttribute(default=1).metadata == {}


# ---------------------------------------------------------------------------
# the bundled factories carry the parameter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [non_storage_setting, json_setting, environment_variable_setting],
    ids=["non_storage_setting", "json_setting", "environment_variable_setting"],
)
def test_factories_pass_metadata_through(factory):
    assert factory(default=1, metadata={"ui-label": "Label"}).metadata == {"ui-label": "Label"}
    assert factory(default=1).metadata == {}


def test_attribute_class_construction_passes_metadata_through():
    from advexp.settings.plugins.environment.variables import EnvironmentVariableSetting
    from advexp.settings.plugins.json_settings import JSONSetting

    assert JSONSetting(default=1, path="/net", metadata={"m": 1}).metadata == {"m": 1}
    assert EnvironmentVariableSetting(default=1, metadata={"m": 1}).metadata == {"m": 1}


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_non_mapping_metadata_rejected_at_construction():
    with pytest.raises(TypeError, match="metadata must be a mapping"):
        non_storage_setting(default=1, metadata=[("ui-label", "Label")])
    with pytest.raises(TypeError, match="metadata must be a mapping"):
        json_setting(default=1, metadata="ui-label")


def test_non_mapping_class_declaration_rejected_at_class_creation():
    with pytest.raises(
        TypeError,
        match="Broken.class_metadata is reserved for the class's own",
    ):

        class Broken(Settings):
            class_metadata = [("origin", "seed")]


def test_non_mapping_options_rejected_at_class_creation():
    with pytest.raises(
        TypeError,
        match="Broken.class_metadata is reserved for the class's own",
    ):

        class Broken(
            Settings,
            options="origin",
        ):
            class_metadata = {"config-version": 2}
            flag: bool = non_storage_setting(default=False)


def test_non_mapping_sequence_entry_rejected_at_class_creation():
    # a list of key-value pairs is the sequence form with a non-mapping
    # entry: the error names options= and the entry's type
    with pytest.raises(TypeError, match="Broken: every options= entry must be a mapping"):

        class Broken(
            Settings,
            options=(("origin", "seed"),),
        ):
            flag: bool = non_storage_setting(default=False)


# ---------------------------------------------------------------------------
# registered validators check the declared and the runtime channel alike
# ---------------------------------------------------------------------------


def test_registered_validator_checks_declaration_and_runtime():
    def check(value):
        if value != "ok":
            return f"must be 'ok', got {value!r}"
        return None

    LibraryConfiguration.register_class_metadata_validator("test-declarative-family", check)
    try:
        # the flat family key lands under the per-class key, so the error
        # names it: 'test-declarative-family.<module>.<class>'
        with pytest.raises(
            TypeError,
            match=r"Broken\.class_metadata\['test-declarative-family\..*'\]: must be 'ok'",
        ):

            class Broken(Settings):
                class_metadata = {"test-declarative-family": "bad"}
                flag: bool = non_storage_setting(default=False)

        class Fine(Settings):
            class_metadata = {"test-declarative-family": "ok"}
            flag: bool = non_storage_setting(default=False)

        assert Fine.get_class_metadata("test-declarative-family") == "ok"

        with pytest.raises(TypeError, match="must be 'ok'"):
            Fine.set_class_metadata("test-declarative-family", "bad")
        Fine.set_class_metadata("test-declarative-family", "ok")
        assert Fine.get_class_metadata("test-declarative-family") == "ok"

        # keys with no validator stay the open channel's business alone
        Fine.set_class_metadata("anything-else", {"free": "form"})
    finally:
        LibraryConfiguration._class_metadata_validators.pop("test-declarative-family", None)


def test_reregistering_the_same_validator_is_a_noop():
    def check(value):
        return None

    LibraryConfiguration.register_class_metadata_validator("test-declarative-same", check)
    try:
        LibraryConfiguration.register_class_metadata_validator("test-declarative-same", check)
        assert LibraryConfiguration._get_class_metadata_validator("test-declarative-same") is check
    finally:
        LibraryConfiguration._class_metadata_validators.pop("test-declarative-same", None)


def test_registering_a_second_validator_for_a_key_conflicts():
    LibraryConfiguration.register_class_metadata_validator(
        "test-declarative-conflict", lambda value: None
    )
    try:
        with pytest.raises(ValueError, match="already registered"):
            LibraryConfiguration.register_class_metadata_validator(
                "test-declarative-conflict", lambda value: "problem"
            )
    finally:
        LibraryConfiguration._class_metadata_validators.pop("test-declarative-conflict", None)


# ---------------------------------------------------------------------------
# the declarations reach the backend through the same context as the runtime
# channel
# ---------------------------------------------------------------------------


def test_serializer_reads_declared_metadata_through_the_context():
    storage: Dict[str, Any] = {}

    class RedactingAttribute(SettingsAttribute):
        pass

    class RedactingSerializer(SettingsBaseSerializer):
        def load(self, setting_name, attr):
            return storage.get(setting_name, NOT_FOUND)

        def save(self, setting_name, attr, value):
            member = attr.bound_name
            if self.context.get_setting_metadata(member, "redact-on-save"):
                value = "***"
            storage[setting_name] = value

        def delete(self, setting_name, attr):
            storage.pop(setting_name, None)

        def contains(self, setting_name, attr):
            return setting_name in storage

        def synchronize(self):
            pass

    LibraryConfiguration.register_settings_attribute(RedactingAttribute, RedactingSerializer)

    class SecretSettings(Settings):
        api_token: str = RedactingAttribute(default="s3cr3t", metadata={"redact-on-save": True})
        plain: str = RedactingAttribute(default="visible")

    try:
        SecretSettings.save_settings()
        full_token = f"{SecretSettings.__module__}.SecretSettings.api_token"
        full_plain = f"{SecretSettings.__module__}.SecretSettings.plain"
        assert storage[full_token] == "***"  # the declaration reached the backend
        assert storage[full_plain] == "visible"

        # the runtime channel flips the declared switch the same way
        SecretSettings.set_setting_metadata("plain", "redact-on-save", True)
        SecretSettings.save_settings()
        assert storage[full_plain] == "***"
    finally:
        LibraryConfiguration._attribute_serializers.pop(RedactingAttribute, None)
