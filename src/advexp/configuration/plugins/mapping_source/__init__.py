# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Mapping source: a dictionary read as a chain link.

Importing this package enables the source; no explicit registration
call is needed::

    import advexp.configuration as adv_config
    from advexp.configuration.plugins.mapping_source import mapping_source

    BASE_DEFAULTS = {"token": "dev-token", "port": 8080}

    class AppConfig(adv_config.Configuration, options=Sources(
        env_source(name_prefix="APP_"),
        mapping_source(BASE_DEFAULTS),
    )):
        token: str

``mapping_source(...)`` returns the result of the builder, which is meant
for the ``options=`` keyword of the ``class`` statement. Assigning the
underlying attribute instance is not the way to use this family, and no
member factory exists, because the dictionary uses member names, which
plain declarations already are. As a source, the dictionary is read-only:
it is never written back.

If the builder is called without a dictionary, it declares the live form:
the chain holds an empty mapping layer, and the application fills its
dictionary at runtime through the resolver::

    from advexp.configuration.plugins.mapping_source import (
        mapping_source,
        mapping_source_for,
    )

    class AppConfig(adv_config.Configuration, options=Sources(
        env_source(name_prefix="APP_"),
        mapping_source(),
    )):
        token: str

    mapping_source_for(AppConfig).set({"token": "dev-token"})
    AppConfig.load_configuration()

The resolver is the only handle of the live form. The class declares the
link, and ``mapping_source_for(cls)`` returns the one link of its chain.
It returns the same object on every call, whichever load passes read it.
"""

from advexp.configuration.plugins.mapping_source.link import MappingSourceLink
from advexp.configuration.plugins.mapping_source.options import mapping_source
from advexp.configuration.plugins.mapping_source.resolver import mapping_source_for
from advexp.configuration.plugins.mapping_source.serializer import MappingSourceSerializer

__all__ = [
    "MappingSourceLink",
    "MappingSourceSerializer",
    "mapping_source",
    "mapping_source_for",
]
