# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The settings base class.

Subclass :class:`Settings` and declare members through plain annotations
(the source binding of the class reads them) or through the factory of a
backend. Then use the class-level API; the values are stored per class::

    class LocalSettings(Settings, options=js.json_source("local.json")):
        width: int = 800
        airplane_mode: bool = setting(name="airplaneMode", default=False)

    LocalSettings.load_settings()
    LocalSettings.airplane_mode = True
    LocalSettings.save_settings()
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Mapping, Optional, Tuple, Type, TypeVar, cast

from advexp.settings._internal import pipeline
from advexp.settings._internal.package_name import PACKAGE_NAME
from advexp.settings._internal.plain_settings_meta import PlainSettingsMeta
from advexp.settings._internal.settings_attribute import SettingsAttribute
from advexp.settings_base.context import SettingsContext
from advexp.settings_base.conversion import correct_type
from advexp.settings_base.cross_validation import (
    collect_settings_problems,
    effective_values,
    format_problems,
)
from advexp.settings_base.getter import SettingRef, resolve_setting_name
from advexp.settings_base.instance_values import INSTANCE_VALUES_ATTR, instance_values
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.setting_validation_error import SettingValidationError
from advexp.settings_base.settings_base_plugin import PluginT

_T = TypeVar("_T", bound="Settings")


class Settings(metaclass=PlainSettingsMeta):
    """Base class for typed application settings.

    All operations are class-level: the settings class itself is the singleton.
    Instances are supported for reads and writes, but they share the class
    storage. :meth:`to_object` and :meth:`update_from_object` copy values out
    to a detached instance of the class and back from it, and :meth:`to_dict`
    and :meth:`update_from_dict` do the same with a plain dict.

    Every method that addresses one setting by name (the single-setting passes
    and the setting-metadata methods) also accepts a getter lambda that selects
    the member: ``save_setting(lambda s: s.port)``. The lambda is inspected,
    never called.
    """

    # Injected by the settings metaclass at class creation (annotations only:
    # they hold no values, keeping every settings class on its own storage).
    # The types resolve at runtime on purpose: they end up in the class
    # __annotations__, which typing.get_type_hints evaluates for subclasses.
    __settings_members__: Dict[str, SettingMember]
    __settings_values__: Dict[str, Any]
    __settings_context__: SettingsContext

    # the machinery's records for this distribution's classes are carried
    # by the import-name channel: the base routes them by this declaration,
    # every subclass inherits it (all classes of the distribution share the
    # one logger), and a sibling distribution declares its own root the
    # same way
    __logger_name__ = PACKAGE_NAME

    # the distribution boundary: members are declared through this base,
    # and the class statement refuses a member declared with another
    # distribution's attribute — the bases spell different defaults, so a
    # misplaced attribute would silently change what the member means
    __attribute_base__ = SettingsAttribute

    # the word the machinery's diagnostics call this distribution's
    # members by, beside the other declarations of the root
    __member_term__ = "setting"

    # -- logging ---------------------------------------------------------------

    @classmethod
    def logger(cls) -> logging.Logger:
        """Return this distribution's logging channel, ready to be configured.

        There is one channel per distribution: the one that ``__logger_name__``
        declares and that every class of the package shares. A subclass inherits
        the method and returns the same channel. Unlike
        :meth:`~advexp.settings.LibraryConfiguration.logger`, which returns the
        channel of the whole family, this channel addresses only the records of
        this package: a level set here overrides the family's level for this
        package, and a handler added here receives only this package's records.
        The propagation rule is the same as for the family channel: a handler added
        here, next to the application's ``logging.basicConfig()``, duplicates every
        record unless propagation of this channel is turned off.
        """
        return logging.getLogger(cls.__logger_name__)

    # -- class-level passes --------------------------------------------------

    @classmethod
    def load_settings(cls) -> Tuple[MemberLoadError, ...]:
        """Load all declared settings from their storages and report the fallbacks.

        The behavior matches
        :meth:`advexp.configuration.Configuration.load_configuration`: both use the
        one load pass of the family.

        Every member is loaded, whatever happened to the previous one. A member
        declared :data:`~advexp.settings.REQUIRED` whose storage provides nothing
        usable records an error. The error names the cause (no value, a value that
        cannot be converted, a constraint violation, or a failed storage), the
        member, its setting, and the class. An optional member (one declared with a
        value, with ``NO_DEFAULT``, or without ``default=``) records the same
        error, but it stands at its default instead.

        A plain miss is not an error. For an optional member, a miss is the normal
        way in which the default gets used, so it is not reported at the usual log
        levels; a debug record names the address that came up empty. When the pass
        aborts, the optional misses are attached to the abort in the aggregate's
        ``misses``, so the reader of the failure can see which optional members
        stood at their defaults.

        At the end, one abort reports every required failure at once. It is always
        :class:`~advexp.settings.AggregateLoadError`, however many members failed.
        Its ``errors`` tuple holds each member's own error, and its ``fallbacks``
        tuple holds the optional fallbacks of the same run. If there is no
        required failure, there is no abort: the method returns the fallbacks as
        its report (an empty tuple when every member loaded cleanly), so a caller
        can learn what fell back without parsing logs. A user-facing storage
        condition (a corrupt or inaccessible storage) does not wait for the end:
        if the failing member has a default that would mask it, the condition
        propagates and aborts the whole pass immediately.

        The pass builds the class state from scratch and applies it in one step. A
        completed load fully determines the state: every member takes either the
        value that its storages produced or its declared default. A value from an
        earlier load therefore never survives when the current storages hold
        nothing for that member, so one class can be reused across loads, and each
        pass stands on its own. A pass that ends in the aggregate abort, or in a
        propagating storage condition, leaves the class exactly as the call found
        it: no values are partly applied, and no defaults are served by the failed
        run. So if a reload fails, the process keeps the configuration that it is
        already running with.
        """
        return pipeline.load_settings(cls.__settings_context__)

    @classmethod
    def save_settings(cls) -> None:
        """Save the current values of all declared settings.

        Ordinary backend errors are logged and skipped. A user-facing error (a
        broken storage) propagates and aborts the whole pass, so the settings
        declared after the failing one (including those of other backends) stay
        unsaved.
        """
        pipeline.save_settings(cls.__settings_context__)

    @classmethod
    def delete_settings(cls) -> None:
        """Delete all declared settings from their storages and reset them to their
        defaults.

        Ordinary backend errors are logged and skipped. A user-facing error
        propagates and aborts the whole pass (other backends included). A member
        declared :data:`~advexp.settings.REQUIRED` has no default to reset to:
        once its storage entries are gone, the member is unset, and reading it
        raises an error, as before any load.
        """
        pipeline.delete_settings(cls.__settings_context__)

    @classmethod
    def reset_settings(cls) -> None:
        """Reset all declared settings to their defaults (no storage access).

        A member declared :data:`~advexp.settings.REQUIRED` has no default to
        serve, so the pass clears its current value instead. This leaves the
        member in the never-loaded state, in which reading it raises an error:
        the state that a fresh declaration has before any load. The other members
        are reset in the normal way, whatever the position of the required member
        in the declaration order.
        """
        pipeline.reset_settings(cls.__settings_context__)

    @classmethod
    def validate_settings(cls) -> None:
        """Check every declared setting against all its constraints.

        This is the strict manual check, in the same family as the load and save
        passes. In one pass, it checks the field constraints (with their ``when=``
        conditions resolved against the current values), the cross-member rules (a
        comparison bound that references another member), and the ``__validate__``
        hook. Every violation of every member is collected into one
        :class:`~advexp.settings_base.setting_validation_error.SettingValidationError`,
        which carries the per-member report in its ``problems`` attribute. A CLI or
        a test can read this report as data. Nothing changes: values and storages
        stay exactly as they were. If everything passes, nothing is raised::

            LocalSettings.validate_settings()
        """
        pipeline.validate_settings(cls.__settings_context__)

    # -- single-setting passes -----------------------------------------------
    # Every ``setting_name`` below also accepts a getter lambda in place of the
    # name string: ``save_setting(lambda s: s.port)``. The lambda is inspected,
    # never called.

    @classmethod
    def load_setting(cls, setting_name: SettingRef) -> Optional[MemberLoadError]:
        """Load one setting from its storage and report the fallback of the member.

        ``setting_name`` is the member's name or a getter lambda that selects it:
        ``load_setting(lambda s: s.port)``.

        The return value is the row of this member in the report that
        :meth:`load_settings` returns:

        - ``None``, if the member got its value, or got its default in the normal
          way (the storage held nothing for it).
        - A :class:`~advexp.settings.MemberLoadError`
          (:class:`~advexp.settings.SourceLoadError`,
          :class:`~advexp.settings.ConversionError`, or
          :class:`~advexp.settings.ConstraintViolationError`), if a member with a
          default fell back to it. This is the same entry that the report of the
          class pass would carry.

        A member declared :data:`~advexp.settings.REQUIRED` raises an error
        instead. There is no aggregate for a single member, so the caller sees the
        own error of the member (for example, a failed source, or a read of a
        never-loaded member). A user-facing storage condition is raised unwrapped,
        as in the class pass.
        """
        return pipeline.load_setting(cls.__settings_context__, resolve_setting_name(setting_name))

    @classmethod
    def save_setting(cls, setting_name: SettingRef) -> None:
        """Save the current value of one setting.

        ``setting_name`` is the member's name or a getter lambda selecting
        it: ``save_setting(lambda s: s.port)``.
        """
        pipeline.save_setting(cls.__settings_context__, resolve_setting_name(setting_name))

    @classmethod
    def delete_setting(cls, setting_name: SettingRef) -> None:
        """Delete one setting from its storage and reset it to its default.

        ``setting_name`` is the member's name or a getter lambda that selects it:
        ``delete_setting(lambda s: s.port)``. A member declared
        :data:`~advexp.settings.REQUIRED` is left unset after the delete: it has no
        default to stand at, so reading it raises an error, as before any load.
        """
        pipeline.delete_setting(cls.__settings_context__, resolve_setting_name(setting_name))

    @classmethod
    def reset_setting(cls, setting_name: SettingRef) -> None:
        """Reset one setting to its default (no storage access).

        ``setting_name`` is the member's name or a getter lambda that selects it:
        ``reset_setting(lambda s: s.port)``. A member declared
        :data:`~advexp.settings.REQUIRED` is cleared instead: it has no default to
        stand at, so reading it raises an error, as before any load.
        """
        pipeline.reset_setting(cls.__settings_context__, resolve_setting_name(setting_name))

    @classmethod
    def contains_setting(cls, setting_name: SettingRef) -> bool:
        """Return whether the setting's storage holds a value.

        ``setting_name`` is the member's name or a getter lambda selecting
        it: ``contains_setting(lambda s: s.port)``.
        """
        return pipeline.contains_setting(
            cls.__settings_context__, resolve_setting_name(setting_name)
        )

    # -- snapshot (in-memory) -------------------------------------------------
    #
    # The settings class is the singleton storage, so a "copy" must be a
    # different object: a plain dict (``SimpleNamespace(**d)``) or a detached
    # instance of the class itself. Applying a snapshot back touches only the
    # in-memory values; persisting stays explicit.

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Return a snapshot of all declared settings, keyed by member name.

        Values are deep-copied, so changing the snapshot never affects the class
        (and vice versa). Members that were never assigned or loaded report their
        effective default. Secure settings are included as they are, so treat the
        snapshot accordingly::

            snapshot = LocalSettings.to_dict()
        """
        with cls.__settings_context__.lock:
            return {name: copy.deepcopy(getattr(cls, name)) for name in cls.__settings_members__}

    @classmethod
    def update_from_dict(cls, data: Mapping[str, Any], *, ignore_unknown: bool = False) -> None:
        """Set declared settings from a mapping keyed by member name.

        Values are converted to the annotated types exactly as on load
        (``"8080"`` for an ``int`` member becomes ``8080``). Then the whole update
        is checked against every declared constraint over the merged state (the
        new values together with the current ones): the own constraints of each
        member with its ``when=`` condition, the cross-member rules, and the
        ``__validate__`` hook. If there is a violation, every finding is collected
        into one :class:`SettingValidationError` and nothing is applied. The values
        that are passed are deep-copied, so the class storage never shares mutable
        state with the mapping.

        Keys that are not declared settings raise ``KeyError``. The update is a
        mutator, and a mistyped name should fail loudly, instead of hiding in a
        partial update. For a dictionary from elsewhere (for example, the
        ``model_dump()`` of another model that has fields this class never
        declared), pass ``ignore_unknown=True`` instead: the unknown keys are
        skipped, with a debug record, and the declared ones are applied.

        Storages are not written. Call :meth:`save_settings` to persist the
        values::

            LocalSettings.update_from_dict({'airplane_mode': True})
            LocalSettings.save_settings()
        """
        cls._apply_snapshot(data, ignore_unknown=ignore_unknown)

    @classmethod
    def to_object(cls: Type[_T]) -> _T:
        """Return a snapshot of all declared settings as a detached instance.

        The returned instance is of the settings class itself, so its fields carry
        the declared names and annotations. If you rename a setting, every stale
        field access on a snapshot becomes a type-checker error (and an
        ``AttributeError`` at runtime). The instance holds its own deep-copied
        values: reading or writing them never affects the class, and vice versa.
        Members that were never assigned or loaded report their effective default.
        Secure settings are included as they are, so treat the snapshot
        accordingly. Apply the snapshot back with :meth:`update_from_object`::

            snapshot = LocalSettings.to_object()
        """
        with cls.__settings_context__.lock:
            # object.__new__ is the detached-instance construction (the class
            # __new__ belongs to the metaclass); the cast states the result type
            snapshot = object.__new__(cls)
            # a plain attribute write into the fresh instance's own value
            # storage, which the descriptors read (vars() would go through a
            # proxy the stubs type as read-only)
            object.__setattr__(
                snapshot,
                INSTANCE_VALUES_ATTR,
                {name: copy.deepcopy(getattr(cls, name)) for name in cls.__settings_members__},
            )
        return cast(_T, snapshot)

    @classmethod
    def update_from_object(cls, obj: object, *, ignore_unknown: bool = False) -> None:
        """Set declared settings from the fields of an object.

        The object is usually a snapshot from :meth:`to_object`. Any object with a
        plain attribute namespace also works (for example,
        ``SimpleNamespace(**to_dict())`` or a dataclass instance), and the field
        names are the member names. Values are converted to the annotated types,
        and the whole update is checked over the merged state, exactly as in
        :meth:`update_from_dict`. The values are then deep-copied.

        Field names that are not declared settings raise ``KeyError``.
        ``ignore_unknown=True`` skips them in the same way, with a debug record;
        use it for an object from elsewhere whose namespace has fields that this
        class never declared. A failed conversion or check applies nothing.

        Storages are not written. Call :meth:`save_settings` to persist the
        values::

            LocalSettings.update_from_object(snapshot)
            LocalSettings.save_settings()
        """
        own = instance_values(obj)
        if own is not None:
            cls._apply_snapshot(own, ignore_unknown=ignore_unknown)
            return
        namespace: Optional[Dict[str, Any]] = getattr(obj, "__dict__", None)
        if namespace is None:
            raise TypeError(
                f"cannot read settings from {type(obj).__name__!r}: it has no attribute namespace"
            )
        cls._apply_snapshot(namespace, ignore_unknown=ignore_unknown)

    @classmethod
    def _apply_snapshot(cls, data: Mapping[str, Any], *, ignore_unknown: bool = False) -> None:
        members = cls.__settings_members__
        unknown = sorted(set(data) - set(members))
        if unknown:
            if not ignore_unknown:
                listing = ", ".join(repr(name) for name in unknown)
                raise KeyError(
                    f"{listing} not a setting of {cls.__name__}; "
                    f"available settings: {', '.join(sorted(members))}"
                )
            # the same record the load overrides and the mapping storage
            # write: a foreign key is not this class's to read, and the
            # reader debugging a partial apply learns where it went
            logger = cls.__settings_context__.logger
            for name in unknown:
                logger.debug(
                    "the update entry %r does not match any setting of '%s'; ignoring it",
                    name,
                    cls.__name__,
                )

        with cls.__settings_context__.lock:
            # conversion first, then the checks over the merged state — the
            # new values beside the current ones — so a cross-member rule
            # or a __validate__ finding rejects the whole update before
            # anything is written
            converted_all = {
                name: correct_type(value, members[name].annotation)
                for name, value in data.items()
                if name in members
            }
            merged = effective_values(cls)
            merged.update(converted_all)
            report = collect_settings_problems(cls, merged)
            if report:
                raise SettingValidationError(format_problems(cls, report), problems=report)
            values = cls.__settings_values__
            values.update({name: copy.deepcopy(value) for name, value in converted_all.items()})

    # -- plugins -----------------------------------------------------------

    @classmethod
    def get_plugin(cls, plugin_class: Type[PluginT]) -> PluginT:
        """Return the plugin instance bound to this settings class (cached)."""
        return cls.__settings_context__.get_plugin(plugin_class)

    # -- metadata -------------------------------------------------------------
    # Like the single-setting operations above, ``setting_name`` here also
    # accepts a getter lambda in place of the name string. The storages
    # start with the class body's declarations — ``metadata=`` on the
    # members, ``class_metadata`` on the class; the methods below are the
    # runtime layer over that state.

    @classmethod
    def set_setting_metadata(
        cls, setting_name: SettingRef, metadata_name: str, metadata_value: Any
    ) -> None:
        """Store metadata for a setting on this class, keyed by member name.

        ``None`` is a value like any other; removing an entry is the job of
        :meth:`delete_setting_metadata`. The entry is stored in the own storage of
        this class, and the readers along the chain (this class and its
        subclasses) resolve it live. A setting reference that the class does not
        declare raises ``KeyError``; every setting-metadata operation applies the
        same check. Values are deep-copied in both directions, so the stored
        metadata and the objects of the caller never share mutable state.
        """
        cls.__settings_context__.set_setting_metadata(setting_name, metadata_name, metadata_value)

    @classmethod
    def get_setting_metadata(
        cls, setting_name: SettingRef, metadata_name: str, default: Any = None
    ) -> Any:
        """Read one metadata entry of a setting; the nearest entry wins.

        The ChainMap rule applies along the inheritance chain of the member (from
        this class down to the class that declared the member): the most derived
        entry that holds the key wins, whichever side declared or wrote it.
        """
        return cls.__settings_context__.get_setting_metadata(setting_name, metadata_name, default)

    @classmethod
    def get_setting_all_metadata(cls, setting_name: SettingRef) -> Dict[str, Any]:
        """Return every metadata entry of one setting, keyed by metadata name.

        This is the snapshot form of :meth:`get_setting_metadata`, and the way to
        enumerate everything that the setting carries along its chain. For each
        key, the most derived entry wins. A runtime write adds keys on top of the
        inherited ones without removing them. A member that is redeclared in a
        subclass carries only the metadata of the redeclaration, because its chain
        ends at the subclass. The dict and its values are deep-copied. A setting
        with nothing stored anywhere in its chain returns an empty dict.

        ``setting_name`` accepts a getter in place of the name string. A member
        that the class does not declare raises ``KeyError``, the same check that
        every setting-metadata operation applies.
        """
        return cls.__settings_context__.get_setting_all_metadata(setting_name)

    @classmethod
    def contains_setting_metadata(cls, setting_name: SettingRef, metadata_name: str) -> bool:
        """Return whether a metadata entry of the setting is stored under the name.

        This is the unambiguous form of :meth:`get_setting_metadata`. ``get``
        returns its default both for a missing entry and for a stored ``None``,
        while ``contains`` tells the two cases apart. It checks the whole chain,
        with the same resolution that ``get`` applies. ``setting_name`` accepts a
        getter in place of the name string, like the other setting operations.
        """
        return cls.__settings_context__.contains_setting_metadata(setting_name, metadata_name)

    @classmethod
    def delete_setting_metadata(cls, setting_name: SettingRef, metadata_name: str) -> bool:
        """Remove the own entry of the class for a setting; a missing entry is not an
        error.

        Only what this class itself declared or stored is removed. An entry of the
        declaring class or of another class in the chain stays visible, in the same
        way that deleting an attribute of a subclass makes the lookup fall back to
        the attribute of the base class. The method returns whether the class had
        an entry of its own to remove. An entry that was seeded by the ``metadata=``
        declaration of the member is removed in the same way: the declaration seeds
        the storage only once, and the entry does not come back.
        """
        return cls.__settings_context__.delete_setting_metadata(setting_name, metadata_name)

    @classmethod
    def set_class_metadata(cls, metadata_name: str, metadata_value: Any) -> None:
        """Store class-level metadata on this class; ``None`` is a value like any
        other.

        The entry is stored in the own storage of this class, and the readers along
        the inheritance chain (this class and its subclasses) resolve it live. The
        write reaches every subclass at once, while the base classes are never
        touched. Removing an entry is the job of :meth:`delete_class_metadata`.
        Values are deep-copied in both directions, so the stored metadata and the
        objects of the caller never share mutable state.
        """
        cls.__settings_context__.set_class_metadata(metadata_name, metadata_value)

    @classmethod
    def get_class_metadata(cls, metadata_name: str, default: Any = None) -> Any:
        """Read a class-level metadata entry; the nearest entry wins.

        The rule is the same as for class attribute lookup: the own storage of this
        class first, then the storages of the base classes. Declarations and
        runtime writes are resolved alike, and they are resolved live, so a runtime
        write into a base class is what a subclass reads.
        """
        return cls.__settings_context__.get_class_metadata(metadata_name, default)

    @classmethod
    def get_class_all_metadata(cls) -> Dict[str, Any]:
        """Return every class-level metadata entry, keyed by metadata name.

        This is the snapshot form of :meth:`get_class_metadata`, and the way to
        enumerate everything that the class carries: its own entries and those of
        its chain, in one dict of deep-copied values. A class with nothing stored
        anywhere in its chain returns an empty dict.
        """
        return cls.__settings_context__.get_class_all_metadata()

    @classmethod
    def contains_class_metadata(cls, metadata_name: str) -> bool:
        """Return whether a class-level metadata entry is stored under the name.

        This is the unambiguous form of :meth:`get_class_metadata`. ``get`` returns
        its default both for a missing entry and for a stored ``None``, while
        ``contains`` tells the two cases apart. It checks the whole inheritance
        chain, with the same resolution that ``get`` applies.
        """
        return cls.__settings_context__.contains_class_metadata(metadata_name)

    @classmethod
    def delete_class_metadata(cls, metadata_name: str) -> bool:
        """Remove the own class-level metadata entry of the class; a missing entry is
        not an error.

        Only what this class itself declared or stored is removed. An entry of an
        ancestor stays visible, in the same way that deleting an attribute of a
        subclass makes the lookup fall back to the attribute of the base class. The
        method returns whether the class had an entry of its own to remove. An
        entry that was seeded by the declaration in the class body is removed in
        the same way: the declaration seeds the storage only once, and the entry
        does not come back.
        """
        return cls.__settings_context__.delete_class_metadata(metadata_name)

    @classmethod
    def delete_class_all_metadata(cls) -> None:
        """Remove every own class-level metadata entry of the class.

        Only the own storage of the class is cleared. The entries of the ancestors
        stay visible to the readers of the chain: clearing a subclass does not clear
        its base classes. The iteration order of a dynamic plugin and the entries
        that were seeded by the declaration in the class body are own entries of the
        class, and they are removed with the rest.
        """
        cls.__settings_context__.delete_class_all_metadata()
