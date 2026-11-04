# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Mapping storage: the dictionary of the class, which can be loaded and saved.

Importing this package enables the storage; no explicit registration
call is needed::

    import advexp.settings as adv_settings
    from advexp.settings.plugins.mapping_source import mapping_source

    BASE_DEFAULTS = {"token": "dev-token", "port": 8080}

    class AppSettings(
        adv_settings.Settings,
        options=mapping_source(BASE_DEFAULTS),
    ):
        token: str

``mapping_source(...)`` returns the result of the builder, which is meant
for the ``options=`` keyword of the ``class`` statement. No member factory
exists, because the dictionary uses member names, which plain declarations
already are. The dictionary is the storage of the class: a load reads it, a
save writes the member keys into it, and the resolver replaces it
completely between the passes::

    from advexp.settings.plugins.mapping_source import mapping_source_for

    mapping_source_for(AppSettings).set({"token": "runtime-token"})
    AppSettings.load_settings()
"""

from advexp.settings.plugins.mapping_source.link import MappingStorageLink
from advexp.settings.plugins.mapping_source.options import mapping_source
from advexp.settings.plugins.mapping_source.resolver import mapping_source_for
from advexp.settings.plugins.mapping_source.serializer import MappingStorageSerializer

__all__ = [
    "MappingStorageLink",
    "MappingStorageSerializer",
    "mapping_source",
    "mapping_source_for",
]
