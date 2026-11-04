# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The live mapping link: the dictionary arrives at runtime.

In the static form, the dictionary is known when the class is declared. In
the live form, it is not. The builder called without a dictionary,
``mapping_source()``, puts this link in the chain instead, and from then
on the dictionary is the own state of the link. It is empty until the
application fills it through
:func:`~advexp.configuration.plugins.mapping_source.resolver.mapping_source_for`,
and every later load of the class reads it. One link holds one dictionary,
and ``set`` replaces it completely: the link is a layer of the chain, not
a target for merging.
"""

from __future__ import annotations

import collections
import copy
from typing import Any, Dict, Mapping

from advexp.configuration.plugins.mapping_source.serializer import (
    MAPPING_PARAM,
    MappingSourceSerializer,
)
from advexp.settings_base.source_link import SourceLink


class MappingSourceLink(SourceLink):
    """The link of the live mapping source: a dictionary that is filled at
    runtime.

    The link carries the serializer of the mapping source and its dictionary
    as the own parameter of the link. This is the same place where the
    dictionary of the static form sits, and it is served in the same way: by
    member names only, with every value returned as a fresh copy. The
    dictionary starts empty, and ``set(mapping)`` is the only way to write to
    it; nothing else changes it.
    """

    def __init__(self) -> None:
        # name-mangled: the link's dictionary, replaced in place by set(),
        # kept out of a subclass's reach
        self.__values: Dict[str, Any] = {}
        super().__init__(
            serializer_class=MappingSourceSerializer,
            params={MAPPING_PARAM: self.__values},
        )

    def set(self, mapping: Mapping[str, Any]) -> None:
        """Replace the dictionary with ``mapping``. The link stores a copy, not a view.

        The replacement is complete: keys that the new dictionary does not contain
        are removed, whatever the previous dictionary held. The dictionary is
        deep-copied on the way in, so afterwards the caller's object and the state
        of the link share nothing. In the same way, a load serves every value that
        it finds as a fresh copy. A load reads the dictionary once, at its start,
        so a replacement made while a load is running takes effect from the next
        load.
        """
        if isinstance(mapping, str) or not isinstance(mapping, collections.abc.Mapping):
            raise TypeError(
                "set() on the live mapping source expects a mapping of member names "
                f"to values, got {type(mapping).__name__}"
            )
        replacement = copy.deepcopy(dict(mapping))
        self.__values.clear()
        self.__values.update(replacement)
