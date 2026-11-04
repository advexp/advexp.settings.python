# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Mandatory storage backend contract."""

from __future__ import annotations

import abc
from typing import Any, Optional

from advexp.settings_base.setting_attribute_interface import ISettingAttribute


class ISettingsSerializer(abc.ABC):
    """Mandatory storage operations.

    The four operations every storage backend provides — load, save,
    delete, contains — plus ``synchronize`` at the end of a pass. A
    backend implementing this contract alone is valid: the pipeline
    asks for nothing more, and the optional parts — the name wishes,
    the context injection, the notification bracket — live in their own
    contracts, which ``SettingsBaseSerializer`` fills with defaults.

    The ``attr`` argument of the operations is the setting's attribute
    instance, or ``None`` for a dynamic-settings entry: dynamic settings
    have no attribute instance, only the plugin's pinned
    ``attribute_class``. Backends read their own parameters off the attribute
    through
    :meth:`~advexp.settings_base.settings_base_serializer.SettingsBaseSerializer.attribute_of`.
    """

    @abc.abstractmethod
    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        """Return the stored value for the setting, or :data:`NOT_FOUND`."""

    @abc.abstractmethod
    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """Store the value; ``None`` is a legitimate value.

        A storage that can represent it (a document storage, say) keeps it
        as its null form; a string-only storage that has none removes the
        entry instead — for such a storage ``None`` and absence coincide.
        Removing a setting outright is :meth:`delete`'s job.

        ``value`` is the caller's current object, handed over by reference.
        Backends that keep it in memory (rather than serializing right away)
        must copy mutable values themselves — the class storage must not share
        mutable state with the backend's.
        """

    @abc.abstractmethod
    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """Remove the setting from storage (missing setting is not an error)."""

    @abc.abstractmethod
    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        """Whether the storage currently holds a value for the setting."""

    @abc.abstractmethod
    def synchronize(self) -> None:
        """Flush pending changes.

        Runs after the save/delete member loop and before the end
        notifications — inside the ``on_start/end_serializer_action`` bracket.
        Conditions that must reach the user follow the storage operations'
        rule: wrap the original error in
        :class:`~advexp.settings_base.user_facing_error.UserFacingError`.
        """
