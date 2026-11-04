# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The default base class for storage backends.

It derives from all the backend contracts and provides the default
implementations. The optional interfaces are capabilities that the pipeline
probes for, not requirements. A backend that implements only
:class:`~advexp.settings_base.settings_serializer_interface.ISettingsSerializer`
is valid (it gets no injection of parameters, default names, and no
notifications). Deriving from this class is the way to get the optional
parts and to override only what a backend cares about.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Optional, Tuple, Type

from advexp.settings_base import conversion
from advexp.settings_base.base_attribute import AttributeT
from advexp.settings_base.serializer_notification_sink_interface import (
    ISerializerNotificationSink,
)
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.setting_name_describer_interface import ISettingNameDescriber
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.settings_serializer_wishes_interface import (
    ISettingsSerializerWishes,
)
from advexp.settings_base.source_describer_interface import ISourceDescriber

if TYPE_CHECKING:  # pragma: no cover - typing only
    from advexp.settings_base.context import SettingsContext


class SettingsBaseSerializer(
    ISettingsSerializer,
    ISettingsSerializerWishes,
    ISettingNameDescriber,
    ISerializerNotificationSink,
    ISourceDescriber,
    metaclass=abc.ABCMeta,
):
    """Base class for storage backends: the class from which plugin serializers
    derive.

    Everything except the four storage operations has a default:

    - ``synchronize`` and the notifications are no-ops.
    - The delimiter wish is ``'.'``.
    - Name fragments pass through unsanitized.
    - The name of a setting in messages keeps the pattern-built spelling.
    - The delivered context is kept for the ``context`` property.

    The base declares every optional interface, so the pipeline always delivers
    parameters, wishes, name spellings, and notifications to subclasses. It is
    enough to override only the ones that a backend cares about.

    The pipeline creates instances per serializer class, and an instance may be
    reused across the settings of one pass. The context of the pass arrives
    through ``set_serializer_params`` and is read back through the ``context``
    property.

    The value-form helpers ``to_json_value``, ``to_toml_value``, and
    ``to_storage_string`` render a value into the storage forms that the
    round-trip types of the library support. Override them to extend the set of
    storable types. The narrowing helper ``attribute_of`` turns the ``attr`` of
    the interface methods into the own attribute class of the backend, for
    reading backend-specific parameters.
    """

    def __init__(self) -> None:
        # name-mangled: the base's own state dispatched through self, immune
        # to a subclass's same-named attribute
        self.__context: Optional[SettingsContext] = None

    # -- ISettingsSerializer ---------------------------------------------------

    @abc.abstractmethod
    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        """``ISettingsSerializer`` storage operation: return the stored
        value for ``setting_name``, or :data:`NOT_FOUND`.
        """

    @abc.abstractmethod
    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """``ISettingsSerializer`` storage operation: store ``value``. This includes
        ``None``, which is stored in the null form of the storage if it has one (a
        storage without a null form removes the entry).
        """

    @abc.abstractmethod
    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """``ISettingsSerializer`` storage operation: remove the setting
        from storage (a missing setting is not an error).
        """

    @abc.abstractmethod
    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        """``ISettingsSerializer`` storage operation: whether the storage
        currently holds a value for the setting.
        """

    def synchronize(self) -> None:
        """``ISettingsSerializer`` storage operation: flush pending
        changes. The default is nothing to flush.
        """

    # -- ISettingNameDescriber ---------------------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """Default: ``None``. Messages name the setting by its pattern-built storage
        name.

        Override this method when the storage addresses the setting differently
        from the pattern (for example, the environment family builds each variable
        name from the naming options of the class). The returned phrase is the
        address alone: the caller adds the designation of the source next to it, so
        the message names the exact file only once.
        """
        return None

    # -- ISourceDescriber ------------------------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Default: ``None``. The load diagnostics say just ``its source``.

        Override this method to name the backend in them. The designation that it
        returns replaces ``its source`` in the causes, for example ``the process
        environment provided no value``, or ``the JSON file /etc/app.json raised
        ...``.
        """
        return None

    # -- attribute views --------------------------------------------------------

    @staticmethod
    def attribute_of(
        attr: Optional[ISettingAttribute], attribute_class: Type[AttributeT]
    ) -> Optional[AttributeT]:
        """The own helper of the base: return ``attr`` narrowed to
        ``attribute_class``, or ``None`` if the narrowing does not apply.

        The serializer contracts type ``attr`` as ``Optional[ISettingAttribute]``,
        because dynamic entries call with ``attr=None``. This helper is the only way
        to turn ``attr`` into the typed view from which a backend reads its own
        parameters (``path=`` and similar ones). ``None`` covers the case in which
        the view does not apply:

        ```python
                setting = self.attribute_of(attr, JSONSetting)
                path = setting.path if setting is not None else None
        ```

        """
        return attr if isinstance(attr, attribute_class) else None

    # -- value forms -------------------------------------------------------------

    @staticmethod
    def to_storage_string(value: Any) -> str:
        """The own helper of the base: render ``value`` for a string-oriented storage
        (environment variables and similar storages).

        Booleans are rendered as ``True``/``False``, dates and times in ISO format,
        enums by member name, and collections and dataclasses in JSON-encoded form.
        The result round-trips with the conversion on the load side. Override the
        method to support further types.
        """
        return conversion.to_storage_string(value)

    @staticmethod
    def to_json_value(value: Any) -> Any:
        """The own helper of the base: render ``value`` for a JSON document (the
        storage form of a JSON backend).

        Enums are rendered by member name, dates and times in ISO format, and
        collections and dataclasses in a JSON-friendly form. The result round-trips
        with the conversion on the load side. Override the method to support further
        types.
        """
        return conversion.to_json_value(value)

    @staticmethod
    def to_toml_value(value: Any) -> Any:
        """The own helper of the base: render ``value`` for a TOML document (the
        storage form of a TOML backend).

        Enums are rendered by member name, timedeltas in their ``str()`` form,
        collections and dataclasses as arrays and tables, and datetimes in native
        form. ``None`` and text that is not UTF-8 raise an error, because TOML has
        neither a null nor a string that is not UTF-8. The result round-trips with
        the conversion on the load side. Override the method to support further
        types.
        """
        return conversion.to_toml_value(value)

    @staticmethod
    def to_yaml_value(value: Any) -> Any:
        """The own helper of the base: render ``value`` for a YAML document (the
        storage form of a YAML backend).

        Enums are rendered by member name, timedeltas in their ``str()`` form,
        collections and dataclasses as sequences and mappings, and datetimes and
        dates in native form. ``None`` is kept as the null of the document. Text
        that is not UTF-8 raises an error, because every YAML string is UTF-8. The
        result round-trips with the conversion on the load side. Override the method
        to support further types.
        """
        return conversion.to_yaml_value(value)

    # -- ISettingsSerializerWishes ---------------------------------------------

    def delimiter(self) -> str:
        """``ISettingsSerializerWishes`` wish: the separator the machinery
        uses between the name parts of an automatic storage name. The
        default is ``'.'``.
        """
        return "."

    def remove_inappropriate_symbols(self, text: str) -> str:
        """``ISettingsSerializerWishes`` wish: sanitize a name fragment
        before it is used in a storage name. The default leaves ``text``
        unchanged.
        """
        return text

    def set_serializer_params(self, context: SettingsContext) -> None:
        """``ISettingsSerializerWishes`` delivery: the pipeline calls this
        once after construction with the settings context of the pass;
        the base stores it, and ``context`` reads it back.
        """
        self.__context = context

    @property
    def context(self) -> SettingsContext:
        """The read side of the context injection of ``ISettingsSerializerWishes``:
        the settings context of the pass that is being run.

        The pipeline delivers the context through :meth:`set_serializer_params`
        before the first storage call. Reading it on an instance outside a pass
        (before any delivery) is an error. The value-form helpers
        (``to_json_value``, ``to_storage_string``) and the name wishes do not need
        the context, so an instance that is constructed directly stays usable for
        them. This property mirrors the ``context`` property of the plugin side.
        """
        context = self.__context
        if context is None:
            raise RuntimeError(
                f"serializer {type(self).__name__} is not bound to a pass yet. "
                "The pipeline provides the context before the first storage call"
            )
        return context

    # -- ISerializerNotificationSink --------------------------------------------
    #
    # The notification bracket of the notification-sink contract: every
    # hook's default is a no-op, and a backend overrides the ones it cares
    # about (the dotenv backend, for one, drops its cached file view when
    # a bracket ends).

    def on_start_serializer_action(self) -> None:
        """``ISerializerNotificationSink`` hook: a load, save or delete pass
        is about to use this serializer. The default is a no-op.
        """

    def on_end_serializer_action(self) -> None:
        """``ISerializerNotificationSink`` hook: the pass using this
        serializer has finished. The default is a no-op.
        """

    def on_start_load_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a load pass starts. The
        default is a no-op.
        """

    def on_end_load_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a load pass ends. The
        default is a no-op.
        """

    def on_start_save_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a save pass starts. The
        default is a no-op.
        """

    def on_end_save_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a save pass ends. The
        default is a no-op.
        """

    def on_start_delete_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a delete pass starts. The
        default is a no-op.
        """

    def on_end_delete_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a delete pass ends. The
        default is a no-op.
        """

    def on_start_contains_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a contains probe starts.
        The default is a no-op.
        """

    def on_end_contains_settings(self) -> None:
        """``ISerializerNotificationSink`` hook: a contains probe ends. The
        default is a no-op.
        """
