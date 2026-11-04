# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Per-settings-class context.

The context is what serializers and plugins receive. It carries the
reference to the settings class, the metadata storages, and the cache of
plugin instances.

Every storage keeps only the *own* entries of the class: the declarations of
the class body, plus the runtime writes into this class. The reading
operations resolve the inheritance chain live, key by key, and the nearest
entry wins. A write into a base class reaches its subclasses, and a write
into a subclass never touches its base classes. This is the rule of a
:class:`collections.ChainMap` built along the MRO, and of class attribute
lookup itself.
"""

from __future__ import annotations

import collections.abc
import copy
import inspect
import logging
import os
import threading
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

from advexp.settings_base.getter import SettingRef, resolve_setting_name
from advexp.settings_base.library_configuration import (
    FAMILY_ENTRY_SEPARATOR,
    LibraryConfiguration,
    family_entry_key,
    logger_for,
)
from advexp.settings_base.names import (
    get_dynamic_setting_full_name,
    get_dynamic_setting_name,
)
from advexp.settings_base.setting_member import resolve_member
from advexp.settings_base.settings_base_plugin import PluginT
from advexp.settings_base.settings_plugin_interface import ISettingsPlugin
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.settings_meta import SettingsMeta

CLASS_METADATA_NAME = "class_metadata"
"""Reserved member name a settings class body declares class metadata under."""

SETTINGS_CONTEXT_ATTR = "__settings_context__"
"""Attribute the settings metaclass stores each class's context under. Every
settings class holds its own; the chain-resolving reads of the class
metadata reach the ancestors' storages through it."""


def _declared_entries(klass: type) -> Dict[str, Any]:
    """The ``class_metadata`` declaration of the body of one class, as it is stored.

    A flat key of a family (the entry of ``options=`` that a helper built) is the
    own entry of the *declaring* class: it is stored under the per-class key of
    the family for that class. The values are deep-copied, so a later change to
    the declared mapping never reaches the storage. A declaration that is not a
    mapping makes the ``class`` statement fail with a ``TypeError`` that names
    the offending declaration.
    """
    declared = vars(klass).get(CLASS_METADATA_NAME)
    if declared is None:
        return {}
    if not isinstance(declared, collections.abc.Mapping):
        raise TypeError(
            f"{klass.__name__}.{CLASS_METADATA_NAME} is reserved for "
            "the class's own metadata and must be a mapping of "
            f"metadata names to values, got {type(declared).__name__}"
        )
    entries: Dict[str, Any] = {}
    for metadata_name, metadata_value in declared.items():
        key = metadata_name
        if LibraryConfiguration._is_family_metadata_key(metadata_name):
            key = family_entry_key(metadata_name, klass)
        entries[key] = copy.deepcopy(metadata_value)
    return entries


def _absorbed_base_classes(settings_class: SettingsMeta) -> List[type]:
    """The MRO bases whose declarations the class absorbs into its own storage.

    A plain mixin has no runtime channel of its own, because the metaclass never
    built a context for it. The nearest settings class below the mixin therefore
    carries the declaration of the mixin as its own. The walk stops at the first
    base that has a context: that base already absorbed everything above it when
    it was created.
    """
    absorbed: List[type] = []
    for klass in inspect.getmro(settings_class)[1:]:
        if vars(klass).get(SETTINGS_CONTEXT_ATTR) is not None:
            break
        absorbed.append(klass)
    return absorbed


def _check_class_metadata(
    settings_class: "SettingsMeta", metadata_name: str, metadata_value: Any
) -> None:
    """Run the validator that is registered for the metadata key over one value.

    An invalid value raises :class:`TypeError` that names the settings class and
    the key. A key with no registered validator belongs only to the open channel
    and stores whatever it was given.
    """
    validator = LibraryConfiguration._get_class_metadata_validator(metadata_name)
    if validator is None:
        return
    problem = validator(metadata_value)
    if problem is not None:
        raise TypeError(
            f"{settings_class.__name__}.{CLASS_METADATA_NAME}[{metadata_name!r}]: {problem}"
        )


def _check_family_entry_addressee(settings_class: "SettingsMeta", metadata_name: str) -> None:
    """Reject a per-class entry of a family that addresses a class outside the
    chain.

    The resolution of the entries of a family walks the MRO of the settings
    class. An entry that is keyed by a class that is not one of its bases would
    therefore sit dead in the storage: a mistyped ancestor class would retune
    nothing, with no indication of the failure. The addressee is checked by its
    spelling. The per-class keys of the whole MRO are the legitimate ones, and a
    key that matches none of them names a class that the chain never held.
    """
    family_key = LibraryConfiguration._family_key_of_entry(metadata_name)
    if family_key is None:
        return
    for klass in inspect.getmro(settings_class):
        if metadata_name == family_entry_key(family_key, klass):
            return
    ancestor = metadata_name[len(family_key) + len(FAMILY_ENTRY_SEPARATOR) :]
    raise TypeError(
        f"{settings_class.__name__}.{CLASS_METADATA_NAME}[{metadata_name!r}]: "
        f"the entry addresses {ancestor}, which is not an ancestor of "
        f"{settings_class.__name__}. A family's per-class entry must address "
        f"the declaring class or one of its bases"
    )


def _declared_settings_metadata(settings_class: SettingsMeta) -> Dict[str, Dict[str, Any]]:
    """The member metadata with which the own storage of this class starts.

    The ``metadata=`` declaration of a member is stored in the storage of the
    class that declared the member. Every class in the chain of a member is
    built by the metaclass, so a declaring class always has a storage of its
    own. A member that a subclass redeclares seeds only the storage of this
    subclass. An inherited member keeps its declaration in the storage of its
    declaring class, and it reaches the readers through the chain. The
    ``metadata`` property of the attribute serves isolated copies, so the
    buckets stored here share nothing with the declarations.
    """
    declared: Dict[str, Dict[str, Any]] = {}
    for name, member in settings_class.__settings_members__.items():
        declaring = getattr(member.attribute, "declaring_class", None)
        if declaring is not settings_class:
            continue
        metadata = getattr(member.attribute, "metadata", None)
        if metadata:
            declared[name] = metadata
    return declared


class SettingsContext:
    """One instance per settings class, created by the settings metaclass.

    Every storage holds the *own* entries of the class: the declarations of the
    class body, plus the runtime writes into this class. The declarations of a
    plain mixin are absorbed here too, because a mixin has no runtime channel of
    its own. The reading operations resolve the inheritance chain live, key by
    key, and the most derived entry wins.

    The chain of a member ends at the class that declared it: the classes above
    it never held the member, and a redeclared member reads only the metadata of
    the redeclaration.
    """

    def __init__(self, settings_class: SettingsMeta) -> None:
        self._settings_class = settings_class
        self._logger = logger_for(settings_class)
        self._lock = threading.RLock()
        # the class's own entries alone; declarations of plain bases come
        # first, the class's own declaration wins — the chain above is
        # resolved live at read time, so no snapshot grows stale
        self._class_metadata: Dict[str, Any] = {}
        for klass in reversed(_absorbed_base_classes(settings_class)):
            self._class_metadata.update(_declared_entries(klass))
        self._class_metadata.update(_declared_entries(settings_class))
        # a key with a registered validator carries a plugin family's
        # options; an invalid declaration — a broken value, an entry keyed
        # by a class outside the chain — fails the class statement itself
        for metadata_name, metadata_value in self._class_metadata.items():
            _check_family_entry_addressee(settings_class, metadata_name)
            _check_class_metadata(settings_class, metadata_name, metadata_value)
        # keyed by member name -> metadata name -> value; opens with the
        # metadata= declarations of the members this class declared (and
        # absorbed from plain bases) — inherited ones stay in their
        # declarers' storages and come through the chain reads
        self._settings_metadata: Dict[str, Dict[str, Any]] = _declared_settings_metadata(
            settings_class
        )
        self._plugins: Dict[type, ISettingsPlugin] = {}
        # keyed by a backend's anchor key (its family metadata key) ->
        # (configured spelling, anchored absolute path): the file addresses
        # this class has resolved; a changed spelling reanchors on read
        self._file_anchors: Dict[Any, Tuple[str, Path]] = {}
        # the open parameter-value scopes of the passes running on this
        # class, innermost last: a pass resolves each environment-seated
        # path parameter once and reuses the value for the rest of the
        # pass, and every pass resolves anew — nothing survives a pass
        self._parameter_passes: List[Dict[str, str]] = []
        # the values the passes so far resolved, keyed by variable name:
        # a load rereads its variables every pass and refreshes the
        # memory, while a write pass seeds its scope from the memory, so
        # a save lands in the file of the environment the load read —
        # the values always return to the storage they came from
        self._remembered_parameters: Dict[str, str] = {}

    @property
    def settings_class(self) -> SettingsMeta:
        return self._settings_class

    @property
    def logger(self) -> logging.Logger:
        """The logging channel of the distribution that drives the settings class.

        There is one logger per distribution, not per settings class: the contexts
        of all classes under the same root declaration hold the same logger object.
        """
        return self._logger

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    # -- class metadata -----------------------------------------------------

    def _chain_metadata(self) -> Dict[str, Any]:
        """The live chain view: the own entries of every class, with the most derived
        entry for each key.

        The contexts along the MRO are read as they are, so a runtime write into
        any class of the chain (for example, a base entry that is retuned after its
        subclasses exist) is what the readers see. Classes without a context (plain
        mixins) are not included: their declarations were absorbed by the settings
        class below them.
        """
        merged: Dict[str, Any] = {}
        for klass in reversed(inspect.getmro(self._settings_class)):
            context = vars(klass).get(SETTINGS_CONTEXT_ATTR)
            if context is not None:
                merged.update(context._class_metadata)
        return merged

    def get_family_options(self, family_key: str, declaring_class: type) -> Optional[Any]:
        """Return the options entry of the family that governs a member of
        ``declaring_class``.

        This is the resolution rule of the per-class entries of a family: the
        nearest entry at or above the class that *declared* the member. It is the
        own entry of the declaring class if that class has one, and otherwise the
        entry of the closest ancestor. The lookup runs over the live storages of the
        chain. An override that a reading subclass declares or retunes at runtime
        therefore applies, and so does a runtime retune of the own entry of an
        ancestor; the classes above the declaring class never see either of them.
        The result is ``None`` if no class of the chain declared the options of the
        family.
        """
        merged = self._chain_metadata()
        for klass in inspect.getmro(declaring_class):
            key = family_entry_key(family_key, klass)
            if key in merged:
                return copy.deepcopy(merged[key])
        return None

    def _own_family_key(self, metadata_name: str) -> str:
        # the flat family spelling at runtime addresses the class's own entry
        return family_entry_key(metadata_name, self._settings_class)

    def set_class_metadata(self, metadata_name: str, metadata_value: Any) -> None:
        """Store a class-level metadata entry on this class; ``None`` is a value.

        A key with a registered validator is checked before it is stored. This is
        the same check that the declaration of a class body goes through, so data
        that the backends rely on cannot break after startup.

        A flat key of a family stores the own entry of the class (the per-class
        key). The entry of an ancestor is addressed by its per-class key, which the
        helpers of the family build from the class itself. The addressee must be the
        class itself or one of its bases, which is the same chain rule that the
        ``class`` statement enforces.

        The value is deep-copied, so the stored metadata never shares mutable state
        with the object of the caller. The entry is stored in the own storage of
        this class, and the readers of the chain (this class and its subclasses)
        resolve it live, so the write reaches every subclass at once. Removing an
        entry is the job of :meth:`delete_class_metadata`.
        """
        if LibraryConfiguration._is_family_metadata_key(metadata_name):
            metadata_name = self._own_family_key(metadata_name)
        _check_family_entry_addressee(self._settings_class, metadata_name)
        _check_class_metadata(self._settings_class, metadata_name, metadata_value)
        self._class_metadata[metadata_name] = copy.deepcopy(metadata_value)

    def get_class_metadata(self, metadata_name: str, default: Any = None) -> Any:
        """Read a class-level metadata entry; the nearest entry wins.

        The rule is the same as for class attribute lookup: the own storage of this
        class first, then the storages of the bases, with the most derived entry for
        each key. Declarations and runtime writes are resolved alike, and live. A
        flat key of a family reads the nearest entry, which is the one that governs
        the own members of this class.
        """
        merged = self._chain_metadata()
        if LibraryConfiguration._is_family_metadata_key(metadata_name):
            for klass in inspect.getmro(self._settings_class):
                key = family_entry_key(metadata_name, klass)
                if key in merged:
                    return copy.deepcopy(merged[key])
            return default
        if metadata_name not in merged:
            return default
        return copy.deepcopy(merged[metadata_name])

    def get_class_all_metadata(self) -> Dict[str, Any]:
        """Return every class-level metadata entry, keyed by metadata name.

        This is the enumeration that the single-key getter cannot give: the entries
        that are visible to the class (its own entries and those of the chain) in
        one dict of deep copies. Changing the snapshot never affects the stored
        metadata. The per-class entries of a family keep their distinct composite
        keys, so the snapshot of a subclass lists its own entry next to the entry of
        the base. A class with nothing stored anywhere in its chain returns an empty
        dict.
        """
        return copy.deepcopy(self._chain_metadata())

    def contains_class_metadata(self, metadata_name: str) -> bool:
        """Return whether the chain holds the name, counting the nearest own entry.

        This is the unambiguous form of :meth:`get_class_metadata`. ``get`` returns
        its default both for a missing entry and for a stored ``None``, while
        ``contains`` tells the two cases apart. It checks the whole chain, with the
        same resolution that ``get`` applies.
        """
        merged = self._chain_metadata()
        if LibraryConfiguration._is_family_metadata_key(metadata_name):
            for klass in inspect.getmro(self._settings_class):
                if family_entry_key(metadata_name, klass) in merged:
                    return True
            return False
        return metadata_name in merged

    def delete_class_metadata(self, metadata_name: str) -> bool:
        """Remove the own class-level metadata entry of the class; a missing entry is
        not an error.

        Only what this class itself declared or stored is removed. An entry of an
        ancestor stays visible to the readers of the chain, in the same way that
        deleting an attribute of a subclass makes the lookup fall back to the
        attribute of the base class. A flat key of a family removes the own entry of
        the family of the class. The method returns whether an own entry existed and
        was removed. An entry that was seeded by the declaration in the class body
        is removed in the same way: the declaration seeds the storage only once, and
        the entry does not come back.
        """
        if LibraryConfiguration._is_family_metadata_key(metadata_name):
            metadata_name = self._own_family_key(metadata_name)
        if metadata_name not in self._class_metadata:
            return False
        del self._class_metadata[metadata_name]
        return True

    def delete_class_all_metadata(self) -> None:
        """Remove every own class-level metadata entry of the class.

        Only the own storage of the class is cleared. The entries of the ancestors
        stay visible to the readers of the chain: clearing a subclass does not clear
        its bases. The iteration order of a dynamic plugin and the entries that were
        seeded by the declaration in the class body are own entries, and they are
        removed with the rest.
        """
        self._class_metadata.clear()

    # -- file anchors --------------------------------------------------------

    def anchored_file_path(self, anchor_key: Any, configured: Union[str, os.PathLike]) -> Path:
        """The absolute path that the class has anchored for one file configuration.

        A file backend passes in the configured spelling (the binding of its class
        or the module default, resolved by its own chain) and receives the absolute
        path that the class anchors for it. The first access anchors the file, and
        every pass during the life of the class (reads, diagnostics, and writes)
        keeps using that file, even if the working directory changes.

        Reconfiguration re-anchors the file: a spelling that differs from the
        anchored one is anchored anew, against the working directory of that moment,
        so a changed ``file_path`` takes effect on the next access. ``anchor_key``
        tells the anchors apart inside one class: a backend with two files anchors
        each of them under its own key.
        """
        spelling = os.fspath(configured)
        anchor = self._file_anchors.get(anchor_key)
        if anchor is not None and anchor[0] == spelling:
            return anchor[1]
        path = Path(os.path.abspath(spelling))
        self._file_anchors[anchor_key] = (spelling, path)
        return path

    # -- pass parameter values ----------------------------------------------

    def open_parameter_pass(self, initial: Optional[Mapping[str, str]] = None) -> None:
        """Open the scope of one pass for resolved path-parameter values.

        The load pass opens a scope before it walks the members and closes it
        afterwards. Every resolution that the pass makes, whichever link of the
        chain it serves, therefore shares one reading of each variable.

        Scopes nest: a pass that is opened inside another one resolves its own
        values, because the values of the outer pass belong to the outer pass.
        ``initial`` seeds the scope with values that the pass must not read again.
        The write directions pass the remembered values of the last load here, so a
        save expands its template with the environment that the class actually
        loaded from.
        """
        self._parameter_passes.append(dict(initial) if initial else {})

    def close_parameter_pass(self) -> None:
        """Close the innermost open scope of resolved path-parameter values."""
        self._parameter_passes.pop()

    def remembered_parameter_values(self) -> Dict[str, str]:
        """The path-parameter values that the passes have resolved so far.

        The values are keyed by variable name. The result is a copy, so the mapping
        of the caller never shares state with the memory. A load refreshes an entry
        each time it reads the variable again. A write pass that finds no entry
        resolves the variable live, and its answer is stored here in the same way.
        As a result, a process that saves before its first load keeps one
        environment for every pass that follows.
        """
        return dict(self._remembered_parameters)

    def pass_parameter_value(self, variable: str, resolve: Callable[[], str]) -> str:
        """Return the value of one variable for the innermost open pass.

        The first request for a variable runs the ``resolve`` call and remembers its
        answer for the rest of the pass. Later requests read the remembered value. A
        fresh resolution that is made inside a pass is also stored in the remembered
        values of the class, which is the memory from which a write pass seeds its
        scope. Outside any open scope (a probe outside a pass), every request
        resolves anew, because nothing is cached where no pass owns the value.
        """
        if not self._parameter_passes:
            return resolve()
        values = self._parameter_passes[-1]
        if variable not in values:
            value = resolve()
            values[variable] = value
            self._remembered_parameters[variable] = value
        return values[variable]

    # -- setting metadata ----------------------------------------------------

    def _member_chain(self, declaring: Optional[type]) -> List[type]:
        """The classes through which one read of member metadata resolves.

        The chain runs from this class down the MRO to the class that *declared* the
        member, inclusive: the classes above the declaring class never held the
        member. If no declaration record names the member, the chain is the whole
        MRO. This is a permissive fallback and never the fast path.
        """
        mro = inspect.getmro(self._settings_class)
        if declaring is not None:
            try:
                return list(mro[: mro.index(declaring) + 1])
            except ValueError:
                pass
        return list(mro)

    def _declared_member(self, setting_name: SettingRef) -> Tuple[str, Optional[type]]:
        """Resolve a reference to a member that the settings class declares.

        The result is the member name and its declaring class. A name (or a getter
        that names one) that the class does not declare raises ``KeyError``. No
        backend would ever read such an entry back, because backends iterate over
        the declared members, so storing it could only hide a typo.
        """
        name = resolve_setting_name(setting_name)
        member = resolve_member(self._settings_class, name)
        declaring = getattr(member.attribute, "declaring_class", None)
        return name, declaring

    def set_setting_metadata(
        self, setting_name: SettingRef, metadata_name: str, metadata_value: Any
    ) -> None:
        """Store metadata for one setting on this class; ``None`` is a value.

        The entry is stored in the own storage of this class, and the readers of the
        chain resolve it live. The readers are this class and its subclasses, but
        never a class above the declarer of the member.

        ``setting_name`` is the member name or a getter lambda for it. A member that
        the settings class does not declare raises ``KeyError``; this is the same
        check that every setting-metadata operation here applies. The value is
        deep-copied, so the stored metadata never shares mutable state with the
        object of the caller. Removing an entry is the job of
        :meth:`delete_setting_metadata`.
        """
        name, _ = self._declared_member(setting_name)
        bucket = self._settings_metadata.setdefault(name, {})
        bucket[metadata_name] = copy.deepcopy(metadata_value)

    def get_setting_metadata(
        self, setting_name: SettingRef, metadata_name: str, default: Any = None
    ) -> Any:
        """Read one metadata entry of a setting; the nearest entry wins.

        The ChainMap rule applies along the chain of the member (from this class
        down to the declaring class): the most derived entry that holds the key
        wins, whichever side declared or wrote it.
        """
        name, declaring = self._declared_member(setting_name)
        for klass in self._member_chain(declaring):
            context = vars(klass).get(SETTINGS_CONTEXT_ATTR)
            if context is None:
                continue
            bucket = context._settings_metadata.get(name)
            if bucket is not None and metadata_name in bucket:
                return copy.deepcopy(bucket[metadata_name])
        return default

    def get_setting_all_metadata(self, setting_name: SettingRef) -> Dict[str, Any]:
        """Return every metadata entry of one setting, keyed by metadata name.

        This is the enumeration that the single-key getter cannot give: the entries
        that are visible to the class along the chain of the member. For each key,
        the most derived entry wins. A runtime write adds keys on top of the
        inherited ones without removing them. The dict and its values are deep
        copies, so changing the snapshot never affects the stored metadata. A
        setting with nothing stored anywhere in its chain returns an empty dict. A
        member that a subclass redeclares reads only the metadata of the
        redeclaration, because its chain ends at the subclass.
        """
        name, declaring = self._declared_member(setting_name)
        merged: Dict[str, Any] = {}
        for klass in reversed(self._member_chain(declaring)):
            context = vars(klass).get(SETTINGS_CONTEXT_ATTR)
            if context is not None:
                bucket = context._settings_metadata.get(name)
                if bucket:
                    merged.update(bucket)
        return copy.deepcopy(merged)

    def contains_setting_metadata(self, setting_name: SettingRef, metadata_name: str) -> bool:
        """Return whether the chain of the member holds the key, counting the nearest
        entry.

        This is the unambiguous form of :meth:`get_setting_metadata`. ``get``
        returns its default both for a missing entry and for a stored ``None``,
        while ``contains`` tells the two cases apart. It checks the whole chain,
        with the same resolution that ``get`` applies.
        """
        name, declaring = self._declared_member(setting_name)
        for klass in self._member_chain(declaring):
            context = vars(klass).get(SETTINGS_CONTEXT_ATTR)
            if context is None:
                continue
            bucket = context._settings_metadata.get(name)
            if bucket is not None and metadata_name in bucket:
                return True
        return False

    def delete_setting_metadata(self, setting_name: SettingRef, metadata_name: str) -> bool:
        """Remove the own entry of the class for one setting; a missing entry is not an
        error.

        Only what this class itself declared or stored is removed. An entry of the
        declaring class, or of another reader of the chain, stays visible, in the
        same way that deleting an attribute of a subclass makes the lookup fall back
        to the attribute of the base class. The method returns whether an own entry
        existed and was removed. An entry that was seeded by the ``metadata=``
        declaration of the member is removed in the same way: the declaration seeds
        the storage only once, and the entry does not come back.
        """
        name, _ = self._declared_member(setting_name)
        bucket = self._settings_metadata.get(name)
        if bucket is None or metadata_name not in bucket:
            return False
        bucket.pop(metadata_name, None)
        if not bucket:
            del self._settings_metadata[name]
        return True

    # -- dynamic names -----------------------------------------------------

    def get_dynamic_setting_full_name(
        self, setting_name: str, serializer: Optional[ISettingsSerializer] = None
    ) -> str:
        """Return the full storage name of one dynamic entry of this settings class.

        This is the counterpart of :meth:`get_dynamic_setting_name`. It takes the
        plain name by which the settings know the entry, and expands it to the name
        that the storage sees: the dynamic marker and the class part of the pattern
        are put in front. Backends that lay out dynamic entries in structures of
        their own use it to build the names that they later enumerate. The
        ``serializer`` argument carries the delimiter wish of the serializer. The
        serializer in which the call runs usually passes itself.
        """
        return get_dynamic_setting_full_name(setting_name, self._settings_class, serializer)

    def get_dynamic_setting_name(
        self, full_name: str, serializer: Optional[ISettingsSerializer] = None
    ) -> Optional[str]:
        """Return the plain setting name for a dynamic full name of this settings
        class.

        This is the inverse of :meth:`get_dynamic_setting_full_name`. It removes the
        dynamic marker and the class part of the pattern, and leaves the name by
        which the settings know the entry. The result is ``None`` if the name is not
        a dynamic entry of this class: a static name, a dynamic entry of another
        class, or foreign data.

        The ``serializer`` argument carries the delimiter wish of the serializer.
        The serializer in which the call runs usually passes itself. A backend that
        serves dynamic entries reaches the metadata of their plugin in this way,
        because that metadata is keyed by the plain name.
        """
        return get_dynamic_setting_name(full_name, self._settings_class, serializer)

    # -- plugins -------------------------------------------------------------

    def get_plugin(self, plugin_class: Type[PluginT]) -> PluginT:
        """Return the cached plugin instance for this settings class."""
        with self._lock:
            # (the cast is for mypy: it has no narrowing for invariant dict values)
            # noinspection PyUnnecessaryCast
            plugin = cast(Optional[PluginT], self._plugins.get(plugin_class))
            if plugin is None:
                resolved_class = LibraryConfiguration._resolve_plugin_class(plugin_class)
                plugin = resolved_class()
                plugin.bind_context(self)
                self._plugins[plugin_class] = plugin
            return plugin
