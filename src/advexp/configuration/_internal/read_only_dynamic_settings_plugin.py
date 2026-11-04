# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Read-only dynamic collections: the reading side of a written group.

A dynamic collection of this package reads a group of entries that a
writing class of the settings distribution stored. The writer's group key
names the group, and the file and section parameters place it. The
collection offers only the reading half of the collection's interface.
Everything that modifies the storage or the collection's metadata is
refused with a ``TypeError``, the same guard that this package applies to
its members: this package loads, and never writes.
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Optional

from advexp.settings_base.document_dynamic_settings_plugin import (
    DocumentDynamicSettingsPlugin,
)
from advexp.settings_base.dynamic_document import (
    dynamic_flat_prefix,
    dynamic_writer_group,
)
from advexp.settings_base.dynamic_settings_info_interface import IDynamicSettingsInfo
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.user_facing_error import UserFacingError


class ReadOnlyDocumentDynamicSettingsPlugin(DocumentDynamicSettingsPlugin):
    """Base class for the dynamic plugins of this package: a read-only collection.

    The collection reads the group of dynamic entries that a writing class
    stored. The writer's group key, which is declared next to the reading
    class's source binding (``json_source(dynamic_of=...)`` and its TOML
    counterpart), names the group in the document. The file levels and the
    section parameters place the group exactly as the writer laid it out.

    The reading interface is the runtime half of the collection.
    :meth:`load_configuration` re-reads the group (it must be called
    explicitly: the class's load pass never touches the dynamic side).
    :meth:`get_setting` converts the value to the type of the default.
    :meth:`to_dict` returns a snapshot. Iteration follows the order in the
    class metadata, like the writer's own collection. The writing half and the
    metadata API are refused with a ``TypeError``, because the entries belong
    to the writer, and the sources of this package are read-only.
    """

    WRITER_GROUP_METADATA: ClassVar[str]
    """The class metadata key holding the writing class's group key this
    collection reads; each document family's plugin names its own key."""

    # -- the writer's group ------------------------------------------------------

    def _writer_group(self) -> Optional[str]:
        """The group key of the writing class; ``None`` if the class declared none.

        The single underscore is deliberate: this is a contract between modules,
        not an interface for subclasses. The serializer of the family reads the
        same binding through the shared helper, so the two sides agree by
        construction.
        """
        return dynamic_writer_group(self.context, self.WRITER_GROUP_METADATA)

    def __require_writer_group(self) -> str:
        group = self._writer_group()
        if group is None:
            # the plain error, not the UserFacingError wrapper: the wrapper
            # serves the passes the pipeline drives, and a collection method
            # called directly must hear the error itself
            raise ValueError(
                f"{self.context.settings_class.__name__} reads no dynamic group: "
                "its options= do not name the writer's group key. Name the "
                "writing class's group next to the source binding, for example "
                'json_source(dynamic_of="app.LocalSettings") or its TOML '
                "equivalent. The group is the key under which the writer's "
                "entries are stored in the document"
            )
        return group

    # -- names --------------------------------------------------------------------

    def _dynamic_full_name(self, simple_name: str, serializer: ISettingsSerializer) -> str:
        """The storage name of one entry: the ``D`` marker followed by the writer's
        key.

        The naming of the reading class never enters this name, because the
        entries belong to the writer's group, and the group's key is the address
        that the class declared. The single underscore is deliberate: this method
        overrides a base-class hook as a contract between modules, and it is not
        an interface for subclasses.
        """
        return dynamic_flat_prefix(serializer, self.__require_writer_group()) + simple_name

    def _dynamic_stored_names(self, serializer: ISettingsSerializer) -> List[str]:
        """Plain names of the writer group's entries that are currently in storage.

        The enumeration goes through the serializer, like the base class's, but
        it keeps the names of the writer's group (those under the group's
        ``D``-prefixed key), not those of the reading class. The single underscore
        is deliberate: this method overrides a base-class hook as a contract
        between modules, and it is not an interface for subclasses.
        """
        if not isinstance(serializer, IDynamicSettingsInfo):
            raise TypeError(
                f"{type(serializer).__name__} cannot enumerate stored dynamic settings: "
                "this operation requires the serializer to implement "
                "IDynamicSettingsInfo (get_dynamic_settings_names)"
            )
        prefix = dynamic_flat_prefix(serializer, self.__require_writer_group())
        try:
            full_names = list(serializer.get_dynamic_settings_names())
        except UserFacingError as user_error:
            raise user_error.inner from user_error
        return [name[len(prefix) :] for name in full_names if name.startswith(prefix)]

    # -- the load pass -----------------------------------------------------------

    def load_configuration(self) -> None:
        """Rebuild the collection from the writer's group in the storage.

        This is the package's own name for the collection's load, so that one verb
        serves both the class and the plugin handle. It must be called explicitly:
        the class's load pass never touches the dynamic side.
        """
        self.load_settings()

    # -- refused: the writing side --------------------------------------------------

    def save_settings(self) -> None:
        """Refused with an error: this package never writes to its sources.

        The dynamic entries belong to the writing distribution. A reader that
        needs them stored must write them through its own settings class.
        """
        raise TypeError(
            f"the {self.plugin_name} collection is read-only: it only loads "
            "entries and never writes to the storage. Writing is done by the "
            "dynamic plugin of the settings distribution"
        )

    def save_setting(self, setting_name: str) -> None:
        """Refused with an error: this package never writes to its sources.

        The dynamic entries belong to the writing distribution. A reader that
        needs them stored must write them through its own settings class.
        """
        raise TypeError(
            f"the {self.plugin_name} collection is read-only: it only loads "
            "entries and never writes to the storage. Writing is done by the "
            "dynamic plugin of the settings distribution"
        )

    def delete_settings(self) -> None:
        """Refused with an error: this package never deletes from its sources."""
        raise TypeError(
            f"the {self.plugin_name} collection is read-only: it only loads "
            "entries and never deletes anything from the storage. Writing is "
            "done by the dynamic plugin of the settings distribution"
        )

    def delete_setting(self, setting_name: str) -> None:
        """Refused with an error: this package never deletes from its sources."""
        raise TypeError(
            f"the {self.plugin_name} collection is read-only: it only loads "
            "entries and never deletes anything from the storage. Writing is "
            "done by the dynamic plugin of the settings distribution"
        )

    def set_setting(self, setting_name: str, value: Any) -> None:
        """Refused with an error: values come from the storage only.

        A read-only collection holds what its writer stored. To refresh it, call
        :meth:`load_configuration`.
        """
        raise TypeError(
            f"the {self.plugin_name} collection is read-only: its values come "
            "only from the storage. Call load_configuration() to refresh them"
        )

    def update_from_dict(self, data: Any) -> None:
        """Refused with an error: values come from the storage only.

        A read-only collection holds what its writer stored. To refresh it, call
        :meth:`load_configuration`.
        """
        raise TypeError(
            f"the {self.plugin_name} collection is read-only: its values come "
            "only from the storage. Call load_configuration() to refresh them"
        )

    def load_setting(self, setting_name: str) -> None:
        """Refused: the only reading operation is the load of the whole group.

        Refreshing a single entry is a live-update feature, which this reader does
        not provide. :meth:`load_configuration` re-reads every entry of the group.
        """
        raise TypeError(
            "the read-only collection does not support loading a single entry. "
            "Call load_configuration(), which refreshes every entry of the group"
        )

    # -- refused: the metadata API ----------------------------------------------------

    def set_setting_metadata(
        self, setting_name: str, metadata_name: str, metadata_value: Any
    ) -> None:
        """Refused with an error: a read-only collection carries no metadata.

        The storage holds none (the writer's metadata is its runtime state and is
        never stored), so the reader has nothing to restore it from.
        """
        raise TypeError(
            f"the {self.plugin_name} collection has no setting metadata: "
            "the storage holds none, and a reader never writes any"
        )

    def get_setting_metadata(
        self, setting_name: str, metadata_name: str, default: Any = None
    ) -> Any:
        """Refused with an error: a read-only collection carries no metadata.

        The storage holds none (the writer's metadata is its runtime state and is
        never stored), so the reader has nothing to restore it from.
        """
        raise TypeError(
            f"the {self.plugin_name} collection has no setting metadata: "
            "the storage holds none, and a reader never writes any"
        )

    def get_setting_all_metadata(self, setting_name: str) -> Any:
        """Refused with an error: a read-only collection carries no metadata.

        The storage holds none (the writer's metadata is its runtime state and is
        never stored), so the reader has nothing to restore it from.
        """
        raise TypeError(
            f"the {self.plugin_name} collection has no setting metadata: "
            "the storage holds none, and a reader never writes any"
        )

    def contains_setting_metadata(self, setting_name: str, metadata_name: str) -> bool:
        """Refused with an error: a read-only collection carries no metadata.

        The storage holds none (the writer's metadata is its runtime state and is
        never stored), so the reader has nothing to restore it from.
        """
        raise TypeError(
            f"the {self.plugin_name} collection has no setting metadata: "
            "the storage holds none, and a reader never writes any"
        )

    def delete_setting_metadata(self, setting_name: str, metadata_name: str) -> None:
        """Refused with an error: a read-only collection carries no metadata.

        The storage holds none (the writer's metadata is its runtime state and is
        never stored), so the reader has nothing to restore it from.
        """
        raise TypeError(
            f"the {self.plugin_name} collection has no setting metadata: "
            "the storage holds none, and a reader never writes any"
        )

    def delete_setting_all_metadata(self, setting_name: str) -> None:
        """Refused with an error: a read-only collection carries no metadata.

        The storage holds none (the writer's metadata is its runtime state and is
        never stored), so the reader has nothing to restore it from.
        """
        raise TypeError(
            f"the {self.plugin_name} collection has no setting metadata: "
            "the storage holds none, and a reader never writes any"
        )
