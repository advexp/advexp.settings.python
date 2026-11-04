# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the mapping storage, and the seat that it reads.

The storage is a dictionary that the class owns. It is seeded by the
``mapping_source(...)`` binding, replaced completely through the ``set`` of
the resolver, and written by the saves of the class. The dictionary uses
member names only. This is the same vocabulary that every dictionary-based
handle of the library uses (``to_dict``, ``update_from_dict``, the load
overrides). An explicit ``name=`` and declared ``aliases=`` therefore change
nothing here: the member name is the only key that the storage looks up and
the only key that it writes.

Keys that name no member of the class are not served by the storage and are
dropped, with a debug record. A save touches only the keys of the members of
the class and leaves the rest of the dictionary as it is. This is the same
rule that the file storages follow for a shared document. The dictionary is
isolated at both edges: every value that is served and every value that is
stored is a deep copy, so changes made on one side never reach the other.

This module is the leaf of the family: it names the key of the seat and the
link parameter, and the walk that reaches the stored link. The resolver and
the link build on it.
"""

from __future__ import annotations

import copy
import inspect
from typing import Any, Dict, Optional, Tuple

from advexp.settings.plugin_api import (
    NOT_FOUND,
    SETTINGS_CONTEXT_ATTR,
    ISettingAttribute,
    SettingsBaseSerializer,
    family_entry_key,
)
from advexp.settings_base.source_link import SourceLink

MAPPING_SOURCE_METADATA = "__MappingSource"
"""The metadata key of the mapping storage's seat. The value is the
family's :class:`~advexp.settings.plugins.mapping_source.link.MappingStorageLink`
— the storage's dictionary among its parameters — built by the
``mapping_source(...)`` builder."""

MAPPING_PARAM = "mapping"
"""The link parameter carrying the dictionary the mapping storage reads."""


def stored_mapping_link(cls: type) -> Optional[SourceLink]:
    """The stored link of the mapping seat that a class reads: its own, otherwise
    the nearest one above it.

    The walk follows the seat resolution rule for the per-class key of the seat:
    the stored values of the MRO are merged, and the most derived declaring
    class wins. It reads the stored entry as it stands. The public metadata
    reads return deep copies, and calling ``set`` on a copy would change nothing
    that the class keeps. The serializer and the resolver both reach the stored
    link through this walk, so the loads, the saves, and the handles all work
    on one dictionary.
    """
    merged: dict = {}
    for klass in reversed(inspect.getmro(cls)):
        context = vars(klass).get(SETTINGS_CONTEXT_ATTR)
        if context is not None:
            merged.update(context._class_metadata)
    for klass in inspect.getmro(cls):
        link = merged.get(family_entry_key(MAPPING_SOURCE_METADATA, klass))
        if link is not None:
            return link
    return None


class MappingStorageSerializer(SettingsBaseSerializer):
    """Loads, saves, and deletes members in the dictionary of the class.

    The dictionary is the own dictionary of the stored binding, and it is
    reached live at every call. The load passes work over copies of the
    binding, so a write that landed in a copy would change nothing that the
    class keeps. The values keep their Python form: the storage is a dictionary
    in memory, not a text format. The conversion pipeline takes the values back
    in the same way as it takes any Python value.
    """

    def __values(self) -> Dict[str, Any]:
        # name-mangled: dispatched through self, kept out of a
        # subclass's reach; an entry the seat holds without the
        # dictionary parameter serves nothing — a stand-in, not a
        # mapping_source() binding
        link = stored_mapping_link(self.context.settings_class)
        if link is None:
            return {}
        values = link.param(MAPPING_PARAM)
        return values if isinstance(values, dict) else {}

    # -- ISettingsSerializer ---------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        name = attr.bound_name if attr is not None else None
        values = self.__values()
        if name is not None and name in values:
            return copy.deepcopy(values[name])
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        # the member's key alone: the rest of the dictionary is not the
        # class's to touch, and a foreign key survives the save as it
        # stands — the shared-document rule of the file storages
        name = attr.bound_name if attr is not None else None
        if name is None:
            return
        self.__values()[name] = copy.deepcopy(value)

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        name = attr.bound_name if attr is not None else None
        if name is not None:
            self.__values().pop(name, None)

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        name = attr.bound_name if attr is not None else None
        return name is not None and name in self.__values()

    # -- ISettingNameDescriber ----------------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """``member name '<name>'``: the only address that this storage has.

        The dictionary knows member names and nothing else, so the phrase names
        the key in the same way, whatever the declarations of the member say
        elsewhere.
        """
        if attr is None:
            return None
        return f"member name '{attr.bound_name}'"

    # -- ISourceDescriber ------------------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """``("the mapping storage", None)``: the dictionary of the class. It is not a
        file, so the designation carries no path.
        """
        return "the mapping storage", None

    # -- ISerializerNotificationSink -------------------------------------------

    def on_start_load_settings(self) -> None:
        # the pass opened: name the dictionary's keys no member answers
        # to, once per pass — the reader debugging an empty load learns
        # the difference between a miss and a key the class never reads
        members = self.context.settings_class.__settings_members__
        for key in self.__values():
            if key not in members:
                self.context.logger.debug(
                    "the mapping storage contains the key %r, which does not match any member "
                    "of '%s'; ignoring it",
                    key,
                    self.context.settings_class.__name__,
                )
