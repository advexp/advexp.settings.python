# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Optional serializer capability: enumerating the stored dynamic settings.

A storage that can list the dynamic entries that it holds implements this
interface. Dynamic-settings plugins probe the serializer for it, in the same
way as the pipeline probes the optional wishes. Backends that cannot
enumerate (a write-only secrets store, for example) simply do not implement
it, and their dynamic plugins work with the names that user code sets
explicitly.
"""

from __future__ import annotations

import abc
from typing import Iterable


class IDynamicSettingsInfo(abc.ABC):
    """Optional capability: the storage can enumerate its dynamic entries."""

    @abc.abstractmethod
    def get_dynamic_settings_names(self) -> Iterable[str]:
        """Return the full storage names of the dynamic entries that the storage holds.

        The names serve the settings class to which the pass of the serializer is
        bound. They are built through
        :meth:`SettingsContext.get_dynamic_setting_full_name`, and they are returned
        in the own order of the storage. The plugin filters them down to its class,
        so the names of other classes, where a storage returns them, have no effect.
        """
