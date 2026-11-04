# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Base class for dynamic-settings plugins.

Dynamic settings are name-value pairs without a declared class member: the
names appear at runtime and the collection lives in the plugin instance bound
to the settings class. A settings class may mix both kinds — declared members
plus a dynamic collection reached through the plugin.
"""

from __future__ import annotations

import copy
import inspect
from contextlib import contextmanager
from typing import Any, ClassVar, Dict, Iterator, List, Mapping, Type

from advexp.settings_base.attribute_serializer_binding import AttributeSerializerBinding
from advexp.settings_base.conversion import correct_type
from advexp.settings_base.dynamic_settings_info_interface import IDynamicSettingsInfo
from advexp.settings_base.names import (
    DEFAULT_SETTINGS_NAME_PATTERN,
    DYNAMIC_SETTING_NAME_PREFIX,
    SettingNameMode,
    get_dynamic_settings_class_prefix,
    get_full_setting_name,
    get_setting_name_delimiter,
)
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.not_found import NOT_FOUND
from advexp.settings_base.serializer_cache import SerializerCache
from advexp.settings_base.serializer_notification_sink_interface import (
    ISerializerNotificationSink,
)
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.settings_base_plugin import SettingsBasePlugin
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.type_display import type_display
from advexp.settings_base.user_facing_error import UserFacingError


# (plugin_name stays abstract: a dynamic backend always names itself in a
# concrete subclass)
# noinspection PyAbstractClass
class DynamicSettingsBasePlugin(SettingsBasePlugin):
    """Base class for plugins that serve dynamic settings.

    A dynamic settings plugin reuses a static backend. The mandatory
    :attr:`binding` pins the setting attribute whose serializer also serves the
    dynamic entries. The values then live in the same storage as the static
    settings of the class, under dynamic names (the ``D`` prefix keeps the two
    apart).

    The recommended pin is the namespaced form ``DynamicSettingAttribute[Attr]``.
    It has its own registry slot, so the ``setup()`` of the base, which registers
    the binding, never touches the registration of ``Attr`` by the static
    plugin. The serializer must tolerate ``None`` in its ``attr`` argument. For
    :meth:`load_settings`, it must also implement
    :class:`~advexp.settings_base.dynamic_settings_info_interface.IDynamicSettingsInfo`.

    The values are held in the plugin instance (one per settings class), keyed by
    the plain setting name. Nothing touches the storage until one of the storage
    methods runs. The conversion follows the value contract of the static side:
    saving renders the values into the storage form of the backend, and
    :meth:`get_setting` converts them back to the type of the given default.

    The iteration order of the collection comes from the class metadata key
    :attr:`ITERATION_ORDER_METADATA`. The names that it lists come first, in
    that order, and the names that it does not list follow in the order in which
    they were added.
    """

    ITERATION_ORDER_METADATA = "dynamic_settings_order"
    """Class metadata key holding the canonical iteration order of the names."""

    binding: ClassVar[AttributeSerializerBinding]
    """Mandatory on every dynamic plugin (validated at class definition).

    The binding the base :meth:`setup` registers; the attribute class is
    the collection's pin. The namespaced form
    ``DynamicSettingAttribute[Attr]``
    (:class:`~advexp.settings_base.dynamic_setting_attribute.\
DynamicSettingAttribute`) is the
    recommended pin: it is its own slot in the serializer registry — the
    serializer bound to it serves the dynamic entries alone and never
    touches the registration of the attribute class the pin namespaces. A
    bare attribute class pins that attribute directly, sharing the slot
    with the static side.
    """

    @property
    def attribute_class(self) -> Type[ISettingAttribute]:
        """The collection's pin: the binding's attribute class."""
        return self.binding.attribute_class

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # an intermediate base — a layer over this class serving no backend of
        # its own, its ``plugin_name`` still abstract — brings no binding: the
        # concrete plugin below it declares one
        plugin_name = getattr(cls, "plugin_name", None)
        if getattr(plugin_name, "__isabstractmethod__", False):
            return
        # fail at class definition, not at the first storage operation
        # (inspect.getmro rather than __mro__: the same linearization, and a
        # plain function the checker resolves without descriptor quirks)
        for klass in inspect.getmro(cls):
            if klass is DynamicSettingsBasePlugin:
                break
            declared = vars(klass).get("binding")
            if declared is not None:
                if not isinstance(declared, AttributeSerializerBinding):
                    raise TypeError(
                        f"{cls.__name__}.binding must be an "
                        "AttributeSerializerBinding, whose fields are an "
                        "ISettingAttribute implementation and an "
                        "ISettingsSerializer implementation"
                    )
                attribute_class, serializer_class = declared
                if not (
                    isinstance(attribute_class, type)
                    and issubclass(attribute_class, ISettingAttribute)
                ):
                    raise TypeError(
                        f"{cls.__name__}.binding must bind an ISettingAttribute "
                        f"implementation as the attribute class, "
                        f"got {type_display(attribute_class)!r}"
                    )
                if not (
                    isinstance(serializer_class, type)
                    and issubclass(serializer_class, ISettingsSerializer)
                ):
                    raise TypeError(
                        f"{cls.__name__}.binding must bind an ISettingsSerializer "
                        f"implementation as the serializer class, "
                        f"got {type_display(serializer_class)!r}"
                    )
                return
        raise TypeError(
            f"{cls.__name__} must declare 'binding': a required "
            "AttributeSerializerBinding that pairs the pin attribute class "
            "with the serializer that serves its dynamic settings"
        )

    def __init__(self) -> None:
        super().__init__()
        # plain setting name -> value (insertion order = the order added)
        self.__values: Dict[str, Any] = {}
        # plain setting name -> metadata name -> value (runtime annotation,
        # not storage state: the deletes and the loads clear it)
        self.__metadata: Dict[str, Dict[str, Any]] = {}

    # -- serializer and names ------------------------------------------------
    # (the machinery below is name-mangled: dispatched through self on a
    # class users subclass, it must stay immune to a subclass's own
    # same-named helper or attribute)

    def __serializer(self, cache: SerializerCache) -> ISettingsSerializer:
        return cache.get_for_attribute_class(self.attribute_class)

    def _dynamic_name_pattern(self) -> str:
        """Return the name pattern from which the storage names of the dynamic entries
        are built; the default is the full pattern of the name builder.

        The single underscore is deliberate: this is a contract between modules, not
        an interface for subclasses. A backend whose storage names have a form of
        their own overrides this hook (for example, the JSON dynamic backend, whose
        configuration holds a name-pattern parameter). Every name that this base
        builds or parses follows the hook.
        """
        return DEFAULT_SETTINGS_NAME_PATTERN

    def _dynamic_full_name(self, simple_name: str, serializer: ISettingsSerializer) -> str:
        """Return the storage name of one entry of the collection.

        The default is the full dynamic pattern of the name builder, applied to the
        settings class. The single underscore is deliberate: this is a contract
        between modules, not an interface for subclasses. A collection whose storage
        names have a form of their own overrides the hook. For example, the
        read-only reader of the group of another class spells its names from the
        declared key of the writer, without the own naming of the reading class.
        Every pass of this base (loads, saves, and deletes) follows the hook.
        """
        return get_full_setting_name(
            simple_name,
            None,
            self.context.settings_class,
            serializer,
            mode=SettingNameMode.DYNAMIC,
            pattern=self._dynamic_name_pattern(),
        )

    def _dynamic_stored_names(self, serializer: ISettingsSerializer) -> List[str]:
        """Return the plain names of the entries of this collection that are currently
        in storage.

        The enumeration may itself hit a user-facing condition (a corrupt file, for
        example). Such a condition propagates in the same way as those that the
        entry operations raise.

        The prefix is built up front, not per name. A name pattern with no
        ``{FieldName}`` slot is a configuration error, and it fails the pass here
        even if the storage holds nothing to strip. (The per-name inverse, for
        backend authors, is ``get_dynamic_setting_name``.)

        A collection that reads the group of another class overrides the hook with
        its own rule. The single underscore is deliberate: this is a contract
        between modules, not an interface for subclasses.
        """
        info = self.__enumeration(serializer)
        prefix = (
            DYNAMIC_SETTING_NAME_PREFIX
            + get_setting_name_delimiter(serializer, self.context.settings_class)
            + get_dynamic_settings_class_prefix(
                self.context.settings_class, serializer, self._dynamic_name_pattern()
            )
        )
        try:
            full_names = list(info.get_dynamic_settings_names())
        except UserFacingError as user_error:
            raise user_error.inner from user_error
        return [name[len(prefix) :] for name in full_names if name.startswith(prefix)]

    @staticmethod
    def __enumeration(serializer: ISettingsSerializer) -> IDynamicSettingsInfo:
        if not isinstance(serializer, IDynamicSettingsInfo):
            raise TypeError(
                f"{type(serializer).__name__} cannot enumerate stored dynamic settings: "
                "this operation requires the serializer to implement "
                "IDynamicSettingsInfo (get_dynamic_settings_names)"
            )
        return serializer

    @staticmethod
    @contextmanager
    def __serializer_action(serializer: ISettingsSerializer, mode: str) -> Iterator[None]:
        """The serializer notification bracket around a dynamic pass.

        The dynamic passes drive their serializer directly, without the class
        pipeline. The bracket keeps the contract that the pipeline honors. For
        example, the JSON backend releases its shared document view when the
        brackets close: a pass without them would leave the entry of the file held
        and never re-read.
        """
        sink = serializer if isinstance(serializer, ISerializerNotificationSink) else None
        if sink is not None:
            sink.on_start_serializer_action()
            getattr(sink, f"on_start_{mode}_settings")()
        try:
            yield
        finally:
            if sink is not None:
                getattr(sink, f"on_end_{mode}_settings")()
                sink.on_end_serializer_action()

    def __ordered_names(self) -> List[str]:
        """Names in the effective order: metadata order first, then the rest."""
        declared = self.context.get_class_metadata(self.ITERATION_ORDER_METADATA) or []
        ordered: List[str] = []
        listed = set()
        for name in declared:
            if name in self.__values and name not in listed:
                ordered.append(name)
                listed.add(name)
        ordered.extend(name for name in self.__values if name not in listed)
        return ordered

    # -- class-level passes ----------------------------------------------------

    def load_settings(self) -> None:
        """Rebuild the collection from the storage.

        Every dynamic entry of this settings class that is found in the storage
        replaces the current collection. Ordinary backend errors are logged, and the
        entry is skipped. A user-facing error propagates and aborts the pass (the
        entries before the failing one stay loaded). The metadata is cleared with
        the rebuild: a load brings values, and the storage holds no metadata to
        bring.
        """
        with self.context.lock:
            cache = SerializerCache(self.context)
            serializer = self.__serializer(cache)
            with self.__serializer_action(serializer, "load"):
                values: Dict[str, Any] = {}
                for simple_name in self._dynamic_stored_names(serializer):
                    try:
                        raw_value = serializer.load(
                            self._dynamic_full_name(simple_name, serializer), None
                        )
                    except UserFacingError as user_error:
                        raise user_error.inner from user_error
                    except Exception as exc:  # noqa: BLE001 - load errors are logged, not raised
                        self.context.logger.error(
                            "load exception for dynamic setting '%s': %s", simple_name, exc
                        )
                        continue
                    if raw_value is not NOT_FOUND:
                        values[simple_name] = raw_value
                self.__metadata.clear()
                self.__values = values

    def save_settings(self) -> None:
        """Save every value, drop the storage entries that the collection no longer
        has, and flush.

        Ordinary backend errors are logged, and the value is skipped. A user-facing
        error propagates and aborts the pass. Saving ``None`` follows the storage
        contract: a backend with a null form keeps the entry, and a backend without
        one drops it.
        """
        with self.context.lock:
            cache = SerializerCache(self.context)
            serializer = self.__serializer(cache)
            with self.__serializer_action(serializer, "save"):
                for simple_name, value in list(self.__values.items()):
                    try:
                        serializer.save(
                            self._dynamic_full_name(simple_name, serializer), None, value
                        )
                    except UserFacingError as user_error:
                        raise user_error.inner from user_error
                    except Exception as exc:  # noqa: BLE001 - save errors logged, not raised
                        self.context.logger.error(
                            "save exception for dynamic setting '%s': %s", simple_name, exc
                        )
                if isinstance(serializer, IDynamicSettingsInfo):
                    for simple_name in self._dynamic_stored_names(serializer):
                        if simple_name not in self.__values:
                            self.__delete_from_storage(serializer, simple_name)
                self.__synchronize(serializer)

    def delete_settings(self) -> None:
        """Delete every dynamic entry of this class from the storage, and clear the
        collection.

        Ordinary backend errors are logged, and the entry is skipped. A user-facing
        error propagates and aborts the pass. The metadata of the collection is
        cleared with it.
        """
        with self.context.lock:
            cache = SerializerCache(self.context)
            serializer = self.__serializer(cache)
            with self.__serializer_action(serializer, "delete"):
                names = list(self.__values)
                if isinstance(serializer, IDynamicSettingsInfo):
                    # entries the collection lost without a save are deleted too
                    names.extend(
                        name
                        for name in self._dynamic_stored_names(serializer)
                        if name not in self.__values
                    )
                for simple_name in names:
                    self.__delete_from_storage(serializer, simple_name)
                self.__synchronize(serializer)
                self.__values.clear()
                self.__metadata.clear()

    # -- single-setting passes ---------------------------------------------------

    def load_setting(self, setting_name: str) -> None:
        """Load one entry from the storage into the collection.

        If the storage no longer holds the entry, it is dropped from the collection
        (the storage is the source of truth). A name that never held a value is
        dropped in the same way. In both cases, the metadata of the name is dropped
        too: a load brings the value, and the storage holds no metadata to bring.
        """
        with self.context.lock:
            cache = SerializerCache(self.context)
            serializer = self.__serializer(cache)
            with self.__serializer_action(serializer, "load"):
                try:
                    raw_value = serializer.load(
                        self._dynamic_full_name(setting_name, serializer), None
                    )
                except UserFacingError as user_error:
                    raise user_error.inner from user_error
                if raw_value is NOT_FOUND:
                    self.__values.pop(setting_name, None)
                else:
                    self.__values[setting_name] = raw_value
                self.__metadata.pop(setting_name, None)

    def save_setting(self, setting_name: str) -> None:
        """Save one value to the storage, and flush.

        The name must be in the collection (call :meth:`set_setting` first),
        because there is nothing to save otherwise. Saving ``None`` stores it like
        any other value, as the storage contract says.
        """
        with self.context.lock:
            if setting_name not in self.__values:
                raise KeyError(
                    f"dynamic setting '{setting_name}' has no value to save. "
                    "Set it first with set_setting"
                )
            cache = SerializerCache(self.context)
            serializer = self.__serializer(cache)
            with self.__serializer_action(serializer, "save"):
                try:
                    serializer.save(
                        self._dynamic_full_name(setting_name, serializer),
                        None,
                        self.__values[setting_name],
                    )
                    self.__synchronize(serializer)
                except UserFacingError as user_error:
                    raise user_error.inner from user_error

    def delete_setting(self, setting_name: str) -> None:
        """Delete one entry from the storage, and drop it from the collection.

        Deleting a name that the storage does not hold is not an error. The
        metadata of the name is removed with it, while
        :meth:`delete_setting_metadata` removes only the metadata.
        """
        with self.context.lock:
            cache = SerializerCache(self.context)
            serializer = self.__serializer(cache)
            with self.__serializer_action(serializer, "delete"):
                try:
                    serializer.delete(self._dynamic_full_name(setting_name, serializer), None)
                    self.__synchronize(serializer)
                except UserFacingError as user_error:
                    raise user_error.inner from user_error
                self.__values.pop(setting_name, None)
                self.__metadata.pop(setting_name, None)

    # -- values ------------------------------------------------------------------

    def get_setting(self, setting_name: str, default: Any = NO_DEFAULT) -> Any:
        """Return the value of a dynamic setting.

        Without ``default``, the raw storage form is returned, and a missing name
        raises ``KeyError``. With ``default``, the stored value is converted to the
        type of the default (like the annotated conversion of declared settings). If
        the value fails to convert, or if the name is missing, a deep copy of the
        default is returned.
        """
        with self.context.lock:
            if setting_name not in self.__values:
                if default is NO_DEFAULT:
                    raise KeyError(f"there is no dynamic setting '{setting_name}'")
                return copy.deepcopy(default)
            value = self.__values[setting_name]
            if default is NO_DEFAULT:
                return value
            try:
                return correct_type(value, type(default))
            except (ValueError, TypeError) as exc:
                self.context.logger.warning(
                    "cannot convert the value of dynamic setting '%s' to the type of its "
                    "default (%s); using the default value",
                    setting_name,
                    exc,
                )
                return copy.deepcopy(default)

    def set_setting(self, setting_name: str, value: Any) -> None:
        """Set a value in the collection (a plain assignment; nothing is stored).

        The value is kept as given, with the usual reference semantics of an
        assignment. The storage is written by :meth:`save_setting` and
        :meth:`save_settings`. Deleting a stored entry is the job of
        :meth:`delete_setting`.
        """
        with self.context.lock:
            self.__values[setting_name] = value

    # -- setting metadata -------------------------------------------------------

    def __require_name(self, setting_name: str) -> None:
        """Fail on a name that the collection does not hold.

        A dynamic setting exists exactly while it holds a value, so metadata for
        anything else could never be read back and could only hide a typo. Every
        metadata operation applies this check. The error names the collection, like
        the unknown-member error of the declared side.
        """
        if setting_name not in self.__values:
            available = ", ".join(sorted(self.__values)) or "<none>"
            raise KeyError(
                f"'{setting_name}' is not a dynamic setting of "
                f"{self.context.settings_class.__name__}; "
                f"available dynamic settings: {available}"
            )

    def set_setting_metadata(
        self, setting_name: str, metadata_name: str, metadata_value: Any
    ) -> None:
        """Store metadata for one dynamic setting; ``None`` is a value like any other.

        The metadata lives with the collection of this plugin, keyed by the plain
        dynamic name. The two storages therefore stay apart, even when a declared
        member has the same name (that metadata belongs to the own channel of the
        declared side, ``SettingsContext.set_setting_metadata``).

        A dynamic setting exists exactly while it holds a value. Every metadata
        operation therefore requires the name to be one that the collection holds. A
        miss raises ``KeyError`` that names the collection.

        The metadata is a runtime state of the collection, not a stored one: the
        deletes remove it too, and the loads clear it (see :meth:`delete_setting`
        and :meth:`load_settings`). Removing entries alone is the job of
        :meth:`delete_setting_metadata` and :meth:`delete_setting_all_metadata`. The
        value is deep-copied, so the stored metadata never shares mutable state with
        the object of the caller.
        """
        with self.context.lock:
            self.__require_name(setting_name)
            bucket = self.__metadata.setdefault(setting_name, {})
            bucket[metadata_name] = copy.deepcopy(metadata_value)

    def get_setting_metadata(
        self, setting_name: str, metadata_name: str, default: Any = None
    ) -> Any:
        with self.context.lock:
            self.__require_name(setting_name)
            bucket = self.__metadata.get(setting_name)
            if bucket is None or metadata_name not in bucket:
                return default
            return copy.deepcopy(bucket[metadata_name])

    def get_setting_all_metadata(self, setting_name: str) -> Dict[str, Any]:
        """Return every metadata entry of one dynamic setting, keyed by metadata name.

        This is the snapshot form of :meth:`get_setting_metadata`, and the way to
        enumerate everything that the name carries. The dict and its values are
        deep-copied. A setting with nothing stored returns an empty dict. As with
        every metadata operation, the name must be one that the collection holds.
        """
        with self.context.lock:
            self.__require_name(setting_name)
            return copy.deepcopy(self.__metadata.get(setting_name, {}))

    def contains_setting_metadata(self, setting_name: str, metadata_name: str) -> bool:
        """Return whether a metadata entry of the dynamic setting is stored under the
        name.

        This is the unambiguous form of :meth:`get_setting_metadata`. ``get``
        returns its default both for a missing entry and for a stored ``None``,
        while ``contains`` tells the two cases apart. As with every metadata
        operation, the name must be one that the collection holds.
        """
        with self.context.lock:
            self.__require_name(setting_name)
            bucket = self.__metadata.get(setting_name)
            return bucket is not None and metadata_name in bucket

    def delete_setting_metadata(self, setting_name: str, metadata_name: str) -> None:
        """Remove one metadata entry of a dynamic setting; a missing entry is not an
        error.

        As with every metadata operation, the name must be one that the collection
        holds. This method removes only the metadata, and the setting stays as it
        is. Deleting the setting itself (:meth:`delete_setting`) removes its
        metadata together with it.
        """
        with self.context.lock:
            self.__require_name(setting_name)
            bucket = self.__metadata.get(setting_name)
            if bucket is not None:
                bucket.pop(metadata_name, None)
                if not bucket:
                    del self.__metadata[setting_name]

    def delete_setting_all_metadata(self, setting_name: str) -> None:
        """Remove every metadata entry of one dynamic setting at once.

        The per-entry form is :meth:`delete_setting_metadata`. As with every
        metadata operation, the name must be one that the collection holds. A
        setting with no stored metadata is not an error.
        """
        with self.context.lock:
            self.__require_name(setting_name)
            self.__metadata.pop(setting_name, None)

    # -- snapshot ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a snapshot of the collection, keyed by setting name.

        The values are deep-copied, and the keys follow the effective iteration
        order (first the order that is declared in the metadata, then the order in
        which the names were added).
        """
        with self.context.lock:
            return {name: copy.deepcopy(self.__values[name]) for name in self.__ordered_names()}

    def update_from_dict(self, data: Mapping[str, Any]) -> None:
        """Set many values at once; unknown names become new settings.

        The point of a dynamic collection is its open set of names. Unlike the bulk
        update of the declared side, this method therefore rejects no key. The
        values are deep-copied before anything is applied, and the storage is not
        written: saving stays explicit.
        """
        with self.context.lock:
            self.__values.update({name: copy.deepcopy(value) for name, value in data.items()})

    # -- collection protocol ---------------------------------------------------------

    def __iter__(self) -> Iterator[str]:
        with self.context.lock:
            return iter(self.__ordered_names())

    def __len__(self) -> int:
        with self.context.lock:
            return len(self.__values)

    def __contains__(self, setting_name: object) -> bool:
        with self.context.lock:
            return setting_name in self.__values

    # -- helpers ---------------------------------------------------------------------

    def __delete_from_storage(self, serializer: ISettingsSerializer, simple_name: str) -> None:
        try:
            serializer.delete(self._dynamic_full_name(simple_name, serializer), None)
        except UserFacingError as user_error:
            raise user_error.inner from user_error
        except Exception as exc:  # noqa: BLE001 - delete errors are logged, not raised
            self.context.logger.error(
                "delete exception for dynamic setting '%s': %s", simple_name, exc
            )

    def __synchronize(self, serializer: ISettingsSerializer) -> None:
        try:
            serializer.synchronize()
        except UserFacingError as user_error:
            raise user_error.inner from user_error
        except Exception as exc:  # noqa: BLE001 - sync errors are logged and skipped by design
            self.context.logger.error(
                "synchronization failed for %s: %s", type(serializer).__name__, exc
            )
