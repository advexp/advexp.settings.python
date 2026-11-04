# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the mapping source.

The mapping is a dictionary that the application passes to the chain in
code: ``mapping_source(BASE_DEFAULTS)`` names a link whose storage is that
dictionary. The dictionary uses member names only. This is the same
vocabulary that every dictionary-based handle of the library uses
(``to_dict``, ``update_from_dict``, the load overrides). An explicit
``name=`` and declared ``aliases=`` therefore change nothing here: the
member name is the only key that the link looks up.

Keys that name no member of the class are not served by the link and are
dropped, with a debug record. Values go through the common conversion
pipeline, like the values of any source. The dictionary is isolated at both
edges: the builder copies what the call handed in, and every load serves a
fresh copy of the value that it found, so changes made on one side never
reach the other.

The source is read-only: it responds to ``load`` and ``contains``. The
write operations of the serializer contract refuse with an error (a
``UserFacingError`` around a ``NotImplementedError`` that names the
source), and the facade of the package never calls them.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Mapping, Optional, Tuple

from advexp.configuration.plugin_api import (
    NOT_FOUND,
    PACKAGE_NAME,
    ISettingAttribute,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.source_link_sink_interface import ISourceLinkSink

MAPPING_PARAM = "mapping"
"""The link parameter carrying the dictionary the mapping link reads."""


class MappingSourceSerializer(SettingsBaseSerializer, ISourceLinkSink):
    """Loads members from the dictionary that its link carries.

    The dictionary is the own copy of the link, made when the builder ran; the
    serializer holds no view of the caller's object. The value that a load
    finds is served as a deep copy, which gives the same isolation as the
    snapshots of the class.
    """

    def __init__(self) -> None:
        super().__init__()
        # name-mangled: the link's dictionary, dispatched through self,
        # kept out of a subclass's reach
        self.__values: Mapping[str, Any] = {}

    # -- ISourceLinkSink --------------------------------------------------------

    def set_source_link(self, link: SourceLink) -> None:
        """``ISourceLinkSink`` delivery: the link that this source reads.

        The mapping of the link is the storage itself. The serializer keeps the
        own copy of the link and serves deep copies of the values that it finds.
        """
        values = link.param(MAPPING_PARAM)
        self.__values = values if isinstance(values, Mapping) else {}

    # -- ISettingsSerializer ---------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        name = attr.bound_name if attr is not None else None
        if name is not None and name in self.__values:
            return copy.deepcopy(self.__values[name])
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """Refused with an error: a read-only source never writes.

        The facade of the package never calls this operation, so a caller that
        reaches it has mistaken the source for a storage backend. The refusal says
        so, instead of a silent no-op that would hide the bug.
        """
        raise UserFacingError(
            NotImplementedError(
                f"the mapping source is read-only: it loads and never writes ({PACKAGE_NAME})"
            )
        )

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """Refused with an error: a read-only source never deletes.

        The facade of the package never calls this operation, so a caller that
        reaches it has mistaken the source for a storage backend. The refusal says
        so, instead of a silent no-op that would hide the bug.
        """
        raise UserFacingError(
            NotImplementedError(
                f"the mapping source is read-only: it loads and never deletes ({PACKAGE_NAME})"
            )
        )

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        name = attr.bound_name if attr is not None else None
        return name is not None and name in self.__values

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
        """``("the mapping source", None)``: the dictionary that this link reads.
        It is not a file, so the designation carries no path.
        """
        return "the mapping source", None

    # -- ISerializerNotificationSink -------------------------------------------

    def on_start_load_settings(self) -> None:
        # the pass opened: name the dictionary's keys no member answers
        # to, once per pass — the reader debugging an empty load learns
        # the difference between a miss and a key the class never reads
        members: Dict[str, Any] = self.context.settings_class.__settings_members__
        for key in self.__values:
            if key not in members:
                self.context.logger.debug(
                    "the mapping source contains the key %r, which does not match any member of "
                    "'%s'; ignoring it",
                    key,
                    self.context.settings_class.__name__,
                )
