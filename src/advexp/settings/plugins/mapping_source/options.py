# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The builder and the seat of the mapping storage.

The builder binds a settings class to its dictionary storage. The storage is
either empty, to be filled at runtime, or seeded by the dictionary of the
call (a layer of defaults that the code states). The link that the binding
stores carries the dictionary. The resolver
:func:`~advexp.settings.plugins.mapping_source.resolver.mapping_source_for`
returns it with ``set`` and ``get``, and the loads, saves, and deletes of
the class work on the same dictionary.

The storage serves the neutral members (plain declarations and
``setting(...)``), and only them. It cannot be used next to another source
binding, because there is no order between the bindings that a plain member
could follow. The own seats of a family (the file seat of a family, or a
factory member of a family) can be used next to it without restrictions.
"""

from __future__ import annotations

import collections
from typing import Any, Mapping, Optional

from advexp.settings.plugin_api import PACKAGE_NAME
from advexp.settings.plugins.mapping_source.link import MappingStorageLink
from advexp.settings.plugins.mapping_source.serializer import MAPPING_SOURCE_METADATA
from advexp.settings_base.family_boundaries import stamped_options
from advexp.settings_base.sources import (
    register_exclusive_source_seat,
    register_source_link_key,
)


def mapping_source(mapping: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
    """Bind a settings class to its dictionary storage.

    Pass the result of the builder to the ``options=`` keyword of the ``class``
    statement:

    ```python
    class AppSettings(Settings, options=mapping_source(BASE_DEFAULTS)):
        token: str
    ```

    ``mapping`` seeds the storage. The dictionary is copied at the call, so a
    later change to the object of the caller never reaches the storage, and
    every value that a load finds is served as a fresh copy in the same way. If
    the builder is called without a dictionary, it binds an empty storage. The
    application fills it at runtime through
    ``mapping_source_for(AppSettings).set({...})``, and a load that runs before
    any ``set`` passes over the storage as a miss.

    The storage uses member names only: an explicit ``name=`` or ``aliases=`` of
    a member changes nothing here, and a key that names no member is dropped,
    with a debug record. A save writes only the member keys and leaves the rest
    of the dictionary as it is. A delete removes the key of its member in the
    same way.

    The storage is the only source binding of the class. If a class declares it
    next to another source builder, the ``class`` statement fails. The own seats
    of a family (``json_file(...)``, or a factory member of a family) can be
    used next to it without restrictions.
    """
    if mapping is not None and (
        isinstance(mapping, str) or not isinstance(mapping, collections.abc.Mapping)
    ):
        raise TypeError(
            f"mapping_source() expects a mapping of member names to values, "
            f"got {type(mapping).__name__}"
        )
    return stamped_options(
        {MAPPING_SOURCE_METADATA: MappingStorageLink(mapping)},
        PACKAGE_NAME,
    )


# the import alone seats the family: the storage's seat joins the
# source-link keys, exclusive of every other source seat
register_source_link_key(MAPPING_SOURCE_METADATA)
register_exclusive_source_seat(MAPPING_SOURCE_METADATA)
