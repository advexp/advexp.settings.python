# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The link of the mapping storage: the dictionary of the class, held by the
binding.

The link that the ``mapping_source(...)`` binding puts in the seat of the
class carries the dictionary of the storage as its own parameter. The
dictionary is seeded by the call of the builder, and it is empty if the call
gave none. From then on, the dictionary is the state of the link: ``set``
replaces it completely, ``get`` returns a copy, and the loads, saves, and
deletes of the class read and write the same dictionary through the
serializer of the storage.

One link holds one dictionary. A subclass without a binding of its own
shares the link of its base class: one dictionary, one ``set``, one
``get``.
"""

from __future__ import annotations

import collections
import copy
from typing import Any, Dict, Mapping, Optional

from advexp.settings.plugins.mapping_source.serializer import (
    MAPPING_PARAM,
    MappingStorageSerializer,
)
from advexp.settings_base.source_link import SourceLink


class MappingStorageLink(SourceLink):
    """The link of the binding: the dictionary of the mapping storage, with the two
    handles of the resolver on it.

    The link carries the serializer of the storage and its dictionary, which is
    the seat that the whole family reads. ``set(mapping)`` and ``get()`` are the
    channel of the application. The loads and saves of the class are the other
    channel, and both channels work on the same dictionary.
    """

    def __init__(self, mapping: Optional[Mapping[str, Any]] = None) -> None:
        # name-mangled: the storage's dictionary, replaced in place by
        # set(), written by the class's saves, kept out of a subclass's
        # reach
        self.__values: Dict[str, Any] = copy.deepcopy(dict(mapping)) if mapping else {}
        super().__init__(
            serializer_class=MappingStorageSerializer,
            params={MAPPING_PARAM: self.__values},
        )

    def set(self, mapping: Mapping[str, Any]) -> None:
        """Replace the dictionary of the storage with ``mapping``. The link stores a
        copy, not a view.

        The replacement is complete: keys that the new dictionary does not contain
        are removed, whatever the previous dictionary held. This includes the keys
        that the saves of the class wrote. The save channel and this channel are
        two separate channels, and a save never brings back what a ``set`` has
        removed. The dictionary is deep-copied on the way in, and ``get`` returns a
        copy, so the object of the caller and the state of the storage share
        nothing.
        """
        if isinstance(mapping, str) or not isinstance(mapping, collections.abc.Mapping):
            raise TypeError(
                "set() on the mapping storage expects a mapping of member names "
                f"to values, got {type(mapping).__name__}"
            )
        replacement = copy.deepcopy(dict(mapping))
        self.__values.clear()
        self.__values.update(replacement)

    def get(self) -> Dict[str, Any]:
        """Return the dictionary of the storage as it stands now: a deep copy, so
        changes that the caller makes never reach the storage.

        The dictionary holds the last ``set`` and the saves of the class together,
        keyed by member name. A foreign key that the application stored keeps its
        place among them.
        """
        return copy.deepcopy(self.__values)
