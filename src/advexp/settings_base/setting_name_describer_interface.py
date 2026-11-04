# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Setting name describer."""

from __future__ import annotations

import abc
from typing import Optional

from advexp.settings_base.setting_attribute_interface import ISettingAttribute


class ISettingNameDescriber(abc.ABC):
    """Spell the storage address of a setting for messages that a human reads.

    This is a serializer capability that the load diagnostics quote. By
    default, a pass names a setting by its pattern-built storage name
    (``namespace.Class.member``, or the explicit ``name=`` of the member). The
    storage that a backend reads may address the setting differently, however.
    For example, the environment family builds each variable name from the
    naming options of the class, so the pattern name is a string that the
    storage never sees.

    A backend of that kind spells its own address instead. The word for the
    member is the own term of the distribution (here, ``member``). The
    designation of the source of a file backend is added next to the address,
    and it names the file that the address alone cannot name:

    ```python
    member 'host' (environment variable 'DEMO_APP_HOST') of 'AppConfig'
    member 'port' (key 'port' in the TOML file /etc/app.toml) of ...
    ```

    :class:`~advexp.settings_base.settings_base_serializer.SettingsBaseSerializer`
    implements this interface with a ``None`` default, which means the
    pattern-built name. A backend that derives from it overrides only this one
    method. The interface itself is the contract for a backend that is built on
    :class:`~advexp.settings_base.settings_serializer_interface.ISettingsSerializer`
    alone, and it is probed through ``isinstance``.
    """

    @abc.abstractmethod
    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """Return the storage address of the setting, in the own spelling of this
        backend.

        A pass calls this method when it builds a message about the setting, for
        example the abort of a required member, or a fallback warning.
        ``setting_name`` is the pattern-built storage name (the explicit ``name=``
        if the member declares one). ``attr`` is the attribute of the member, or
        ``None`` for a dynamic-settings entry. These are the inputs from which a
        backend spells its address: ``name=``, the bound member name, and the class
        metadata through the context.

        The result is a short phrase that names the entry of the storage. It is the
        address alone (``environment variable 'APP_MODE'``, ``key 'port'``). The
        caller adds the designation of the source next to it if that designation
        adds the file, so the message names the exact file only once. ``None`` says
        that the backend has no spelling of its own, and the caller prints
        ``setting_name`` instead.
        """
