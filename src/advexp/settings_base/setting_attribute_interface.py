# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The setting attribute contract."""

from __future__ import annotations

import abc
from typing import Any, Optional, Tuple


class ISettingAttribute(abc.ABC):
    """The setting attribute contract: it marks a class member as a setting.

    The settings metaclass detects (by this interface) an instance that is
    assigned in the body of a settings class, and replaces it with a value
    descriptor. The serializer that serves the setting is the one that is
    registered for the class of the attribute.

    The contract consists of five data fields with fixed semantics:

    - ``name``: the override of the storage name (``None`` expands the name
      pattern).
    - ``default``: the declared default, or the
      :data:`~advexp.settings_base.no_default.NO_DEFAULT` sentinel when there is
      none. ``None`` is a legitimate default value, so absence has its own
      marker.
    - ``aliases``: additional full storage addresses that a load tries after the
      primary one.
    - ``bound_name``: the member to which the instance is bound. The library
      writes it when it binds the instance.
    - ``declaring_class``: the settings class whose body declared the member. The
      library writes it at the same moment.

    Everything beyond the contract belongs to the attribute class itself. These
    are optional parameters that backends read through
    :meth:`~advexp.settings_base.settings_base_serializer.SettingsBaseSerializer.attribute_of`
    (``path``, and so on).

    The fields are declared as abstract properties: an attribute class that is
    missing any of them fails at instantiation with a :class:`TypeError`. An
    implementation satisfies them with properties over per-instance storage, as
    :class:`~advexp.settings_base.base_attribute.BaseAttribute` does.

    An ABCMeta in the MRO of an attribute can confuse the matching of
    constructor arguments in PyCharm (weak warnings on ``name=`` and
    ``default=``). The enforced contract is worth that noise.
    """

    @property
    @abc.abstractmethod
    def name(self) -> Optional[str]:
        """Storage name override from the attribute constructor.

        ``None`` expands the configured name pattern, with the member name
        in the ``{FieldName}`` slot.
        """

    @property
    @abc.abstractmethod
    def default(self) -> Any:
        """The declared default value.

        If no default was given, the value is the
        :data:`~advexp.settings_base.no_default.NO_DEFAULT` sentinel. ``None`` is a
        legitimate default, so absence has its own marker. The
        :data:`~advexp.settings_base.required.REQUIRED` sentinel declares a member
        that must get its value from a source.
        """

    @property
    @abc.abstractmethod
    def aliases(self) -> Tuple[str, ...]:
        """Additional storage addresses of the setting, tried after the primary one.

        The value is an empty tuple for an attribute that is declared without
        ``aliases=``. Each alias is a full address in the storage and has the same
        status as an explicit ``name=``: the naming options of the family never
        change it. A load looks up the primary address first, then the aliases in
        their declared order, and the first address found wins. The write direction
        keeps serving the primary address.
        """

    @property
    @abc.abstractmethod
    def bound_name(self) -> Optional[str]:
        """Name of the class member this instance is assigned to.

        Not set by user code: the library writes it at class creation, and
        backends read it as the member-name fallback when ``name`` is unset
        (env vars and similar backends). Stays ``None`` for attributes
        bound to no member (dynamic settings).
        """

    @bound_name.setter
    @abc.abstractmethod
    def bound_name(self, value: Optional[str]) -> None:
        """The library's write side of the binding; it is read-only for user
        code."""

    @property
    @abc.abstractmethod
    def declaring_class(self) -> Optional[type]:
        """The settings class whose body declared this member.

        It is not set by user code: the library writes it at class creation,
        together with ``bound_name``. Only the creation of the declaring class
        writes it; a subclass that inherits the member does not. Backends read it as
        the anchor for the per-class options of the family: the storage name of a
        member is built with the entry of the class that declared it. It stays
        ``None`` for attributes that are bound to no member (dynamic settings).
        """

    @declaring_class.setter
    @abc.abstractmethod
    def declaring_class(self, value: Optional[type]) -> None:
        """The library's write side of the declaration record; it is
        read-only for user code."""
