# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The resolver of the live mapping link.

The application never holds the link that the builder returned: the
``class`` statement stores its own copy, and calling ``set`` on another
copy would reach nothing. The resolver therefore starts from the class:
``mapping_source_for(AppConfig)`` returns the mapping source of the chain
of that class, which is the object whose ``set`` the next load reads. The
name follows the ``_for`` pattern of the family
(:func:`~advexp.settings_base.library_configuration.logger_for`,
:func:`~advexp.settings_base.module_default.module_default_for`): the
mapping source *for* a class.
"""

from __future__ import annotations

import inspect
from typing import List, Optional

from advexp.configuration.plugin_api import (
    SETTINGS_CONTEXT_ATTR,
    SOURCE_CHAIN_METADATA,
    family_entry_key,
)
from advexp.configuration.plugins.mapping_source.link import MappingSourceLink
from advexp.settings_base.sources import Sources


def mapping_source_for(cls: type) -> MappingSourceLink:
    """The live mapping source of ``cls``: the chain link that ``set()`` fills.

    Declare the link with ``mapping_source()`` (the builder called without a
    dictionary), and then reach it from the class::

        mapping_source_for(AppConfig).set({"token": "dev-token"})
        AppConfig.load_configuration()

    The resolver reads the nearest chain. A subclass without a chain of its
    own shares the mapping source of its base class: one dictionary, one
    ``set``. The resolver raises an error that names the class in these cases:
    the class was not built by the family, the class has no chain, the chain
    has no live link (the form that takes a dictionary has no handle for
    filling it), or the chain has more than one live link.
    """
    if getattr(cls, SETTINGS_CONTEXT_ATTR, None) is None:
        raise TypeError(
            f"{cls.__name__} is not a configuration class: "
            "mapping_source_for() reads the source chain of a configuration class"
        )
    chain = _nearest_chain(cls)
    if chain is None:
        raise TypeError(
            f"{cls.__name__} declares no source chain, but the live mapping source "
            "must be part of one. Declare mapping_source() (called without a "
            "dictionary) in the class's options="
        )
    live: List[MappingSourceLink] = [link for link in chain if isinstance(link, MappingSourceLink)]
    if not live:
        raise TypeError(
            f"the source chain of {cls.__name__} contains no mapping source to fill. "
            "Declare mapping_source() (called without a dictionary) in the "
            "class's options=. The form that takes a dictionary has no fill handle"
        )
    if len(live) > 1:
        raise TypeError(
            f"the source chain of {cls.__name__} contains {len(live)} mapping sources "
            "to fill, but a chain may contain only one. Declare mapping_source() once"
        )
    return live[0]


def _nearest_chain(cls: type) -> Optional[Sources]:
    """The chain that the class reads: its own, otherwise the nearest one above
    it.

    The lookup follows the metadata resolution rule for the per-class key of
    the chain: the stored values of the MRO are merged, and the most derived
    declaring class wins. It reads the stored entry as it stands. The public
    metadata reads return deep copies, and calling ``set()`` on a copy would
    change nothing that the class loads.
    """
    merged: dict = {}
    for klass in reversed(inspect.getmro(cls)):
        context = vars(klass).get(SETTINGS_CONTEXT_ATTR)
        if context is not None:
            merged.update(context._class_metadata)
    for klass in inspect.getmro(cls):
        chain = merged.get(family_entry_key(SOURCE_CHAIN_METADATA, klass))
        if chain is not None:
            return chain
    return None
