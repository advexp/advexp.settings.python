# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The registry entry describing one declared setting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from advexp.settings_base.library_configuration import member_term
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.setting_descriptor import SettingDescriptor

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.settings_meta import SettingsMeta


def resolve_member(settings_class: SettingsMeta, setting_name: str) -> SettingMember:
    """Return the registry entry of the setting declared under the name.

    Raises ``KeyError`` when the class declares no such member, naming the
    available members — the shared unknown-name check that everything
    addressing one member of a class goes through. The word for the member
    is the distribution's own (``setting`` or ``member``), so the message
    speaks the class's package vocabulary.
    """
    members: Dict[str, SettingMember] = settings_class.__settings_members__
    member = members.get(setting_name)
    if member is None:
        available = ", ".join(sorted(members)) or "<none>"
        term = member_term(settings_class)
        raise KeyError(
            f"'{setting_name}' is not a {term} of {settings_class.__name__}; "
            f"available {term}s: {available}"
        )
    return member


class SettingMember:
    """Registry entry for one declared setting (built by the settings metaclass)."""

    __slots__ = ("name", "attribute", "descriptor", "annotation")

    def __init__(
        self,
        name: str,
        attribute: ISettingAttribute,
        descriptor: SettingDescriptor,
        annotation: Any = None,
    ) -> None:
        self.name = name
        self.attribute = attribute
        self.descriptor = descriptor
        self.annotation = annotation
