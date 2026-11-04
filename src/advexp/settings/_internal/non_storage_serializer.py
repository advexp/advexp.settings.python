# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of a member without a storage.

A member declared with no storage behind it is served by this pair: the
value lives in memory alone, the declared default or the last assignment.
The storage passes leave it alone: a load finds nothing in the storage,
a save and a delete have nowhere to go, and the membership probe reports
an empty storage.
"""

from typing import Any, Optional

from advexp.settings_base.not_found import NOT_FOUND
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.settings_base_serializer import SettingsBaseSerializer


class NonStorageSerializer(SettingsBaseSerializer):
    """The storage operations of a member without a storage."""

    # -- ISettingsSerializer ----------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        return None

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        return None

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        return False
