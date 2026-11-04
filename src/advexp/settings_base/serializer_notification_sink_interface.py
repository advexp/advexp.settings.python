# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Serializer notification sink."""

from __future__ import annotations

import abc


class ISerializerNotificationSink(abc.ABC):
    """Pass notifications.

    A separate contract that
    :class:`~advexp.settings_base.settings_base_serializer.SettingsBaseSerializer`
    fills with no-op defaults.

    ``contains_setting`` fires the same notification bracket as the other
    passes.
    """

    @abc.abstractmethod
    def on_start_serializer_action(self) -> None:
        """Notification: a load/save/delete pass is about to use this serializer."""

    @abc.abstractmethod
    def on_end_serializer_action(self) -> None:
        """Notification: the pass using this serializer has finished."""

    @abc.abstractmethod
    def on_start_load_settings(self) -> None:
        """Notification: start of a load pass."""

    @abc.abstractmethod
    def on_end_load_settings(self) -> None:
        """Notification: end of a load pass."""

    @abc.abstractmethod
    def on_start_save_settings(self) -> None:
        """Notification: start of a save pass."""

    @abc.abstractmethod
    def on_end_save_settings(self) -> None:
        """Notification: end of a save pass."""

    @abc.abstractmethod
    def on_start_delete_settings(self) -> None:
        """Notification: start of a delete pass."""

    @abc.abstractmethod
    def on_end_delete_settings(self) -> None:
        """Notification: end of a delete pass."""

    @abc.abstractmethod
    def on_start_contains_settings(self) -> None:
        """Notification: start of a contains probe."""

    @abc.abstractmethod
    def on_end_contains_settings(self) -> None:
        """Notification: end of a contains probe."""
