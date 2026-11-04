# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The dotenv backend configuration."""

from __future__ import annotations

import os
from typing import Union

from advexp.settings_base.dotenv_file import check_dotenv_file
from advexp.settings_base.module_default import register_module_default
from advexp.settings_base.module_default_meta import ModuleDefaultMeta


class DotenvConfiguration(metaclass=ModuleDefaultMeta):
    """Dotenv backend configuration (class-level state)."""

    file_path: Union[str, os.PathLike] = ".env"
    """Default file location (``str`` or ``os.PathLike``).

    A relative path resolves against the working directory of the running
    process. It applies to settings classes without a ``dotenv_file(...)``
    binding; an absent file behaves as an empty one — the declared defaults
    stand in. The default is the ecosystem's conventional file, so the
    backend works with no configuration at all.

    A settings module can keep its file to itself — declare it at the
    module's top level, with ``for_this_module`` from the package
    root:

    ```python
        DotenvConfiguration.file_path = for_this_module(Path("app.env"))
    ```

    The declaration holds for the classes of the module it is written
    in and wins over this attribute; every other module keeps reading
    the attribute — the process-wide default above.
    """


register_module_default(
    DotenvConfiguration,
    lambda configuration: configuration.file_path,
    check_dotenv_file,
)
