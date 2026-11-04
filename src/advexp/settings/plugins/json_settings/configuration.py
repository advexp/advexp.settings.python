# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The JSON backend configuration."""

from __future__ import annotations

import os
from typing import Optional

from advexp.settings_base.json_file import check_json_file
from advexp.settings_base.module_default import register_module_default
from advexp.settings_base.module_default_meta import ModuleDefaultMeta


class JSONSettingsConfiguration(metaclass=ModuleDefaultMeta):
    """JSON backend configuration (class-level state)."""

    file_path: Optional[os.PathLike] = None
    """Default settings file location (``str`` or ``os.PathLike``).

    It applies to settings classes without a ``json_file(...)`` binding.
    When neither is set, the first storage access raises.

    A settings module can keep its file to itself — declare it at the
    module's top level, with ``for_this_module`` from the package
    root:

    ```python
    JSONSettingsConfiguration.file_path = for_this_module(
        Path("app-settings.json")
    )
    ```

    The declaration holds for the classes of the module it is written
    in and wins over this attribute; every other module keeps reading
    the attribute, which stays the process-wide channel — set it once
    at startup for the whole application. The declaration is an
    ordinary module-level statement: it takes effect during the
    module's import, so a tool that imports the settings modules
    collects it without running the application.
    """


register_module_default(
    JSONSettingsConfiguration,
    lambda configuration: configuration.file_path,
    check_json_file,
)
