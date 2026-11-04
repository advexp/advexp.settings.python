# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The resolver of the mapping storage.

The application never holds the link that the builder returned: the
``class`` statement stores its own copy, and calling ``set`` on another copy
would reach nothing. The resolver therefore starts from the class:
``mapping_source_for(AppSettings)`` returns the mapping storage of the
binding of that class. This is the object whose ``set`` and ``get`` the
application calls, and whose dictionary the loads and saves of the class
work on. The name follows the ``_for`` pattern of the family
(:func:`~advexp.settings_base.library_configuration.logger_for`,
:func:`~advexp.settings_base.module_default.module_default_for`): the
mapping storage *for* a class.
"""

from __future__ import annotations

from advexp.settings.plugin_api import SETTINGS_CONTEXT_ATTR
from advexp.settings.plugins.mapping_source.link import MappingStorageLink
from advexp.settings.plugins.mapping_source.serializer import stored_mapping_link


def mapping_source_for(cls: type) -> MappingStorageLink:
    """The mapping storage of ``cls``: the link of the binding, with ``set`` and
    ``get``.

    Bind the storage with ``mapping_source(...)`` in the ``class`` statement,
    and reach it from the class:

    ```python
    mapping_source_for(AppSettings).set({"token": "dev-token"})
    AppSettings.load_settings()
    ```

    The resolver reads the nearest binding. A subclass without its own
    ``mapping_source`` shares the storage of its base class: one dictionary, one
    ``set``, one ``get``. The resolver raises an error that names the class if
    the class was not built by the family, or if the class has no mapping
    binding.
    """
    if getattr(cls, SETTINGS_CONTEXT_ATTR, None) is None:
        raise TypeError(
            f"{cls.__name__} is not a settings class: "
            "mapping_source_for() reads the storage binding of a settings class"
        )
    link = stored_mapping_link(cls)
    if not isinstance(link, MappingStorageLink):
        raise TypeError(
            f"{cls.__name__} declares no mapping storage. Bind one in the class "
            "statement (options=mapping_source(...))"
        )
    return link
