# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The metadata channel of the configuration facade: declarations and runtime."""

from __future__ import annotations

import pytest

from advexp.configuration import Configuration, sourceless_setting
from advexp.configuration.plugins.environment.variables import env_source
from advexp.settings_base.environment_variable_setting import environment_variable_setting
from advexp.settings_base.sources import SOURCE_CHAIN_METADATA

# ---------------------------------------------------------------------------
# the declared channel reads through the facade
# ---------------------------------------------------------------------------


class SeededConfiguration(Configuration):
    class_metadata = {"config-version": 2, "origin": "seed"}

    mode: str = sourceless_setting(default="production", metadata={"ui-label": "Mode"})
    retries: int = sourceless_setting(default=3)


def test_declared_member_metadata_is_readable():
    assert SeededConfiguration.get_setting_metadata("mode", "ui-label") == "Mode"
    assert SeededConfiguration.get_setting_metadata("mode", "missing", "fallback") == "fallback"
    assert SeededConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Mode"}
    assert SeededConfiguration.contains_setting_metadata("mode", "ui-label")
    assert not SeededConfiguration.contains_setting_metadata("mode", "missing")


def test_member_without_metadata_answers_empty():
    assert SeededConfiguration.get_setting_all_metadata("retries") == {}
    assert not SeededConfiguration.contains_setting_metadata("retries", "anything")
    # the dictionary rule: no default= for a missing entry, KeyError answers
    with pytest.raises(KeyError, match="not a metadata entry of the member 'retries'"):
        SeededConfiguration.get_setting_metadata("retries", "anything")
    assert SeededConfiguration.get_setting_metadata("retries", "anything", "fallback") == "fallback"
    assert SeededConfiguration.get_setting_metadata("retries", "anything", default=None) is None


def test_declared_class_metadata_is_readable():
    assert SeededConfiguration.get_class_metadata("config-version") == 2
    assert SeededConfiguration.get_class_metadata("origin") == "seed"
    assert SeededConfiguration.get_class_metadata("missing", "fallback") == "fallback"
    assert SeededConfiguration.get_class_all_metadata() == {"config-version": 2, "origin": "seed"}
    assert SeededConfiguration.contains_class_metadata("config-version")
    assert not SeededConfiguration.contains_class_metadata("missing")


def test_class_keyword_seeds_the_same_declared_channel():
    class KeywordConfiguration(
        Configuration,
        options={"origin": "keyword"},
    ):
        flag: bool = sourceless_setting(default=False)

    assert KeywordConfiguration.get_class_all_metadata() == {"origin": "keyword"}
    # a declared entry's lifecycle: the runtime delete does not bring it back
    KeywordConfiguration.delete_class_metadata("origin")
    assert KeywordConfiguration.get_class_all_metadata() == {}
    KeywordConfiguration.set_class_metadata("runtime", 1)
    assert KeywordConfiguration.get_class_all_metadata() == {"runtime": 1}


def test_class_with_a_chain_hides_it_from_the_listing():
    class ChainedConfiguration(
        Configuration,
        options=env_source(),
    ):
        class_metadata = {"origin": "seed"}
        mode: str = environment_variable_setting(default="x")

    # the listing carries the open channel alone: the source chain stays in
    # the storage under its reserved key, hidden from the snapshot but
    # addressable by its flat name
    assert ChainedConfiguration.get_class_all_metadata() == {"origin": "seed"}
    assert ChainedConfiguration.contains_class_metadata(SOURCE_CHAIN_METADATA)


# ---------------------------------------------------------------------------
# the runtime layer works over the declarations
# ---------------------------------------------------------------------------


def test_runtime_set_overrides_and_extends_the_declaration():
    class MutableConfiguration(Configuration):
        class_metadata = {"config-version": 2, "origin": "seed"}
        mode: str = sourceless_setting(default="x", metadata={"ui-label": "Mode", "ui-order": 1})

    MutableConfiguration.set_setting_metadata("mode", "ui-label", "Application mode")
    MutableConfiguration.set_setting_metadata("mode", "hint", "Runtime hint")
    assert MutableConfiguration.get_setting_all_metadata("mode") == {
        "ui-label": "Application mode",
        "ui-order": 1,
        "hint": "Runtime hint",
    }

    MutableConfiguration.set_class_metadata("origin", "runtime")
    MutableConfiguration.set_class_metadata("window", {"x": 10})
    assert MutableConfiguration.get_class_all_metadata() == {
        "config-version": 2,
        "origin": "runtime",
        "window": {"x": 10},
    }


def test_runtime_delete_removes_a_declared_entry():
    class DeletableConfiguration(Configuration):
        mode: str = sourceless_setting(default="x", metadata={"ui-label": "Mode"})

    assert DeletableConfiguration.delete_setting_metadata("mode", "ui-label") is True
    assert not DeletableConfiguration.contains_setting_metadata("mode", "ui-label")
    assert DeletableConfiguration.get_setting_all_metadata("mode") == {}

    # no own entry to remove: the delete answers False and is not an error
    assert DeletableConfiguration.delete_setting_metadata("mode", "ui-label") is False


def test_delete_of_the_declaration_attribute_is_rejected():
    class GuardedConfiguration(Configuration):
        class_metadata = {"origin": "seed"}
        mode: str = sourceless_setting(default="x")

    # the same guard of the shared metaclass: the declaration attribute is
    # not the runtime channel, and the del names the channel methods
    with pytest.raises(
        TypeError,
        match=r"delete_class_metadata\('name'\).*delete_class_all_metadata",
    ):
        del GuardedConfiguration.class_metadata
    assert "class_metadata" in vars(GuardedConfiguration)
    assert GuardedConfiguration.get_class_all_metadata() == {"origin": "seed"}


def test_runtime_delete_all_drops_the_whole_bucket():
    class ClearableConfiguration(Configuration):
        mode: str = sourceless_setting(default="x")

    ClearableConfiguration.set_setting_metadata("mode", "ui-label", "Mode")
    ClearableConfiguration.set_setting_metadata("mode", "ui-order", 1)
    result = ClearableConfiguration.delete_setting_all_metadata("mode")
    assert result is None
    assert ClearableConfiguration.get_setting_all_metadata("mode") == {}

    # a bucket with nothing stored: not an error
    ClearableConfiguration.delete_setting_all_metadata("mode")


def test_class_level_clear_keeps_the_member_channel():
    class MixedConfiguration(Configuration):
        class_metadata = {"origin": "seed"}
        mode: str = sourceless_setting(default="x")

    MixedConfiguration.set_setting_metadata("mode", "ui-label", "Mode")
    MixedConfiguration.delete_class_all_metadata()
    with pytest.raises(KeyError):
        MixedConfiguration.get_class_metadata("origin")
    # the member channel is the clear's own business alone
    assert MixedConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Mode"}


def test_undeclared_name_is_refused():
    class CheckedConfiguration(Configuration):
        mode: str = sourceless_setting(default="x")

    with pytest.raises(KeyError):
        CheckedConfiguration.set_setting_metadata("nope", "k", 1)
    with pytest.raises(KeyError):
        CheckedConfiguration.get_setting_all_metadata("nope")
    with pytest.raises(KeyError):
        CheckedConfiguration.delete_setting_all_metadata("nope")


def test_getter_lambda_names_the_member():
    class GetterConfiguration(Configuration):
        mode: str = sourceless_setting(default="x")

    GetterConfiguration.set_setting_metadata(lambda cls: cls.mode, "hint", "via getter")
    assert GetterConfiguration.get_setting_metadata(lambda cls: cls.mode, "hint") == "via getter"
    GetterConfiguration.delete_setting_all_metadata(lambda cls: cls.mode)
    assert GetterConfiguration.get_setting_all_metadata("mode") == {}


# ---------------------------------------------------------------------------
# the channel stands apart from the values and the sources
# ---------------------------------------------------------------------------


def test_runtime_metadata_survives_a_load(monkeypatch):
    class LoadedConfiguration(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(default="x", metadata={"ui-label": "Mode"})

    monkeypatch.setenv("mode", "from-env")
    LoadedConfiguration.set_setting_metadata("mode", "hint", "Runtime hint")
    LoadedConfiguration.set_class_metadata("origin", "runtime")

    LoadedConfiguration.load_configuration()

    assert LoadedConfiguration.mode == "from-env"
    assert LoadedConfiguration.get_setting_all_metadata("mode") == {
        "ui-label": "Mode",
        "hint": "Runtime hint",
    }
    assert LoadedConfiguration.get_class_metadata("origin") == "runtime"


def test_load_does_not_resurrect_deleted_entries(monkeypatch):
    class LoadedConfiguration(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(default="x", metadata={"ui-label": "Mode"})

    monkeypatch.setenv("mode", "from-env")
    LoadedConfiguration.delete_setting_all_metadata("mode")
    LoadedConfiguration.load_configuration()
    # the declaration seeds the storage once, at the class statement: the
    # load reloads values, not metadata
    assert LoadedConfiguration.get_setting_all_metadata("mode") == {}


# ---------------------------------------------------------------------------
# inheritance
# ---------------------------------------------------------------------------


def test_member_metadata_follows_the_member_by_mro():
    class BaseConfiguration(Configuration):
        mode: str = sourceless_setting(default="x", metadata={"ui-label": "Mode"})

    class ChildConfiguration(BaseConfiguration):
        pass

    assert ChildConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Mode"}

    # runtime on the subclass adds keys on top of the inherited ones and
    # leaves the base alone
    ChildConfiguration.set_setting_metadata("mode", "child-only", True)
    assert ChildConfiguration.get_setting_all_metadata("mode") == {
        "ui-label": "Mode",
        "child-only": True,
    }
    assert BaseConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Mode"}


def test_member_redeclaration_replaces_metadata_wholesale():
    class BaseConfiguration(Configuration):
        mode: str = sourceless_setting(default="x", metadata={"ui-label": "Mode", "ui-order": 1})

    class ChildConfiguration(BaseConfiguration):
        mode: str = sourceless_setting(default="dev", metadata={"ui-label": "Child mode"})

    # no per-key merge: the redeclaration's metadata is the whole state
    assert ChildConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Child mode"}
    # a base runtime write on the old declaration never leaks into the
    # redeclared member: its chain ends at the subclass
    BaseConfiguration.set_setting_metadata("mode", "ui-order", 9)
    assert ChildConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Child mode"}


def test_member_delete_all_removes_only_the_own_entries():
    class BaseConfiguration(Configuration):
        mode: str = sourceless_setting(default="x", metadata={"ui-label": "Mode"})

    class ChildConfiguration(BaseConfiguration):
        pass

    # the child's bucket holds nothing of its own: the delete is a no-op, and
    # the base's declaration stays visible
    ChildConfiguration.delete_setting_all_metadata("mode")
    assert ChildConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Mode"}

    # an own runtime entry: gone with the bucket, the base's takes over again
    ChildConfiguration.set_setting_metadata("mode", "hint", "child hint")
    ChildConfiguration.delete_setting_all_metadata("mode")
    assert ChildConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Mode"}

    # the declarer's own delete is the one that clears the entry everywhere
    BaseConfiguration.delete_setting_all_metadata("mode")
    assert BaseConfiguration.get_setting_all_metadata("mode") == {}
    assert ChildConfiguration.get_setting_all_metadata("mode") == {}


def test_class_metadata_merges_along_the_mro():
    class GrandConfiguration(Configuration):
        class_metadata = {"config-version": 1, "origin": "grand", "scope": "root"}

    class MiddleConfiguration(GrandConfiguration):
        class_metadata = {"config-version": 2, "origin": "middle"}

    class LeafConfiguration(MiddleConfiguration):
        class_metadata = {"origin": "leaf"}

    # per key the most derived declaration wins, the rest carry over
    assert GrandConfiguration.get_class_all_metadata() == {
        "config-version": 1,
        "origin": "grand",
        "scope": "root",
    }
    assert MiddleConfiguration.get_class_all_metadata() == {
        "config-version": 2,
        "origin": "middle",
        "scope": "root",
    }
    assert LeafConfiguration.get_class_all_metadata() == {
        "config-version": 2,
        "origin": "leaf",
        "scope": "root",
    }


def test_subclass_delete_removes_only_the_own_entry():
    class BaseConfiguration(Configuration):
        class_metadata = {"origin": "base"}

    class ChildConfiguration(BaseConfiguration):
        pass

    # no own entry: False, and the ancestor's entry stays visible
    assert ChildConfiguration.delete_class_metadata("origin") is False
    assert ChildConfiguration.get_class_metadata("origin") == "base"

    ChildConfiguration.set_class_metadata("origin", "child")
    assert ChildConfiguration.delete_class_metadata("origin") is True
    assert ChildConfiguration.get_class_metadata("origin") == "base"

    assert BaseConfiguration.delete_class_metadata("origin") is True
    with pytest.raises(KeyError):
        BaseConfiguration.get_class_metadata("origin")
    with pytest.raises(KeyError):
        ChildConfiguration.get_class_metadata("origin")


def test_clear_takes_only_the_own_entries_along():
    class BaseConfiguration(Configuration):
        class_metadata = {"origin": "base"}

    class ChildConfiguration(BaseConfiguration):
        class_metadata = {"child-key": 1}

    ChildConfiguration.set_class_metadata("runtime-key", 2)
    ChildConfiguration.delete_class_all_metadata()
    # the child's own entries are gone; the base's stay visible
    assert ChildConfiguration.get_class_all_metadata() == {"origin": "base"}
    assert BaseConfiguration.get_class_all_metadata() == {"origin": "base"}


# ---------------------------------------------------------------------------
# the reset forms restore the declared state
# ---------------------------------------------------------------------------


def test_reset_restores_the_declarations_of_both_channels():
    class ResettableConfiguration(
        Configuration,
        options=env_source(),
    ):
        class_metadata = {"config-version": 2, "origin": "seed"}
        mode: str = environment_variable_setting(default="x", metadata={"ui-label": "Mode"})

    ResettableConfiguration.delete_setting_metadata("mode", "ui-label")
    ResettableConfiguration.set_setting_metadata("mode", "hint", "Runtime hint")
    ResettableConfiguration.set_class_metadata("origin", "Overridden")
    ResettableConfiguration.set_class_metadata("runtime-key", 1)

    ResettableConfiguration.reset_all_settings_metadata()
    ResettableConfiguration.reset_class_all_metadata()

    assert ResettableConfiguration.get_setting_all_metadata("mode") == {"ui-label": "Mode"}
    assert ResettableConfiguration.get_class_all_metadata() == {
        "config-version": 2,
        "origin": "seed",
    }


def test_class_reset_brings_the_source_chain_back():
    # the cross with #98: the service entry of the chain is declared state,
    # so a clear that took it is undone by the reset
    class ChainedConfiguration(
        Configuration,
        options=env_source(),
    ):
        class_metadata = {"origin": "seed"}
        mode: str = environment_variable_setting(default="x")

    ChainedConfiguration.delete_class_all_metadata()
    assert not ChainedConfiguration.contains_class_metadata(SOURCE_CHAIN_METADATA)

    ChainedConfiguration.reset_class_all_metadata()

    assert ChainedConfiguration.contains_class_metadata(SOURCE_CHAIN_METADATA)
    assert ChainedConfiguration.get_class_all_metadata() == {"origin": "seed"}
    # the chain works again: a load runs through it
    ChainedConfiguration.load_configuration()
    assert ChainedConfiguration.mode == "x"


def test_reset_of_an_undeclared_name_is_refused():
    class CheckedConfiguration(
        Configuration,
        options=env_source(),
    ):
        mode: str = environment_variable_setting(default="x")

    with pytest.raises(KeyError):
        CheckedConfiguration.reset_setting_all_metadata("nope")


# ---------------------------------------------------------------------------
# isolation
# ---------------------------------------------------------------------------


def test_declaration_mutation_after_class_creation_stays_out():
    declared_member = {"ui-label": "Mode", "nested": {"items": [1]}}
    declared_class = {"window": {"x": 10}}

    class IsolatedConfiguration(Configuration):
        class_metadata = declared_class
        mode: str = sourceless_setting(default="x", metadata=declared_member)

    declared_member["ui-label"] = "MUTATED"
    declared_member["nested"]["items"].append(2)
    declared_class["window"]["x"] = 999

    assert IsolatedConfiguration.get_setting_all_metadata("mode") == {
        "ui-label": "Mode",
        "nested": {"items": [1]},
    }
    assert IsolatedConfiguration.get_class_metadata("window") == {"x": 10}


def test_getters_return_copies():
    class SnapshotConfiguration(Configuration):
        mode: str = sourceless_setting(default="x", metadata={"ui-label": "Mode"})

    snapshot = SnapshotConfiguration.get_setting_all_metadata("mode")
    snapshot["ui-label"] = "MUTATED"
    assert SnapshotConfiguration.get_setting_metadata("mode", "ui-label") == "Mode"

    class_snapshot = SnapshotConfiguration.get_class_all_metadata()
    class_snapshot["runtime-key"] = "MUTATED"
    assert not SnapshotConfiguration.contains_class_metadata("runtime-key")
