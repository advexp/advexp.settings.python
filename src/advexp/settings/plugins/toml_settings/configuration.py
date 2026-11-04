# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The TOML backend configuration."""

from __future__ import annotations

import os
from typing import Optional

from advexp.settings_base.module_default import register_module_default
from advexp.settings_base.module_default_meta import ModuleDefaultMeta
from advexp.settings_base.toml_file import check_toml_file


class TOMLSettingsConfiguration(metaclass=ModuleDefaultMeta):
    """TOML backend configuration (class-level state)."""

    file_path: Optional[os.PathLike] = None
    """Default settings file location (``str`` or ``os.PathLike``).

    It applies to settings classes without a ``toml_file(...)`` binding.
    When neither is set, the first storage access raises.

    A settings module can keep its file to itself — declare it at the
    module's top level, with ``for_this_module`` from the package
    root:

    ```python
        TOMLSettingsConfiguration.file_path = for_this_module(
            Path("app-settings.toml")
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
    TOMLSettingsConfiguration,
    lambda configuration: configuration.file_path,
    check_toml_file,
)
