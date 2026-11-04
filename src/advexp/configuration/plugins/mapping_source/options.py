# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The builders of the mapping source.

The link that the builder returns is a dictionary that is carried into the
chain as a source of its own. The dictionary is either given in the
declaration, as in ``mapping_source(BASE_DEFAULTS)`` (a layer of defaults
that the code states), or it arrives at runtime. In the second case,
``mapping_source()`` called without a dictionary declares the live form:
an empty layer that the application fills through
:func:`~advexp.configuration.plugins.mapping_source.resolver.mapping_source_for`
before a load reads it.

The builder is the whole vocabulary of this family. A mapping link serves
no member factory (there is no ``mapping_setting``, because the dictionary
uses member names, which neutral members already are), so only the
builders live here.
"""

from __future__ import annotations

import collections
import copy
from typing import Any, Mapping, Optional

from advexp.configuration.plugin_api import PACKAGE_NAME
from advexp.configuration.plugins.mapping_source.link import MappingSourceLink
from advexp.configuration.plugins.mapping_source.serializer import (
    MAPPING_PARAM,
    MappingSourceSerializer,
)
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.source_link import SourceLink


def mapping_source(mapping: Optional[Mapping[str, Any]] = None) -> SourceBinding:
    """Declare a mapping link: a dictionary that is read as a source.

    Pass the result of the builder to the ``options=`` keyword of the ``class``
    statement. You can pass it alone (for a class whose members all come from
    the dictionary) or inside ``Sources(...)`` as the bottom layer of the
    chain, which is the last place a load looks before the declared defaults:

    ```python
        BASE_DEFAULTS = {"token": "dev-token", "port": 8080}

        class AppConfig(Configuration, options=Sources(
            env_source(name_prefix="APP_"),
            json_source(file="app.json"),
            mapping_source(BASE_DEFAULTS),
        )):
            token: str
    ```

    The dictionary that is passed in is copied at the call, so a later change
    to the caller's object never reaches the chain. A value that a load finds
    is served as a fresh copy in the same way. The dictionary uses member names
    only: an explicit ``name=`` or ``aliases=`` of a member changes nothing
    here, and a key that names no member is dropped, with a debug record. This
    form is not meant for a dictionary that the application changes between
    loads; the load overrides serve that purpose.

    If the builder is called without a dictionary, it declares the live form
    instead. The chain gets an empty mapping layer, and the application fills
    its dictionary at runtime through
    ``mapping_source_for(AppConfig).set({...})``. A load that runs before any
    ``set`` passes over the layer as a miss. In both forms the source works in
    the same way: it uses member names only, serves fresh copies of the values,
    and is never written back.
    """
    if mapping is None:
        return SourceBinding(link=MappingSourceLink(), family=PACKAGE_NAME)
    if isinstance(mapping, str) or not isinstance(mapping, collections.abc.Mapping):
        raise TypeError(
            f"mapping_source() expects a mapping of member names to values, "
            f"got {type(mapping).__name__}"
        )
    return SourceBinding(
        link=SourceLink(
            serializer_class=MappingSourceSerializer,
            params={MAPPING_PARAM: copy.deepcopy(dict(mapping))},
        ),
        family=PACKAGE_NAME,
    )
