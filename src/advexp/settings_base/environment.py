# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The vocabulary of the environment family in one import.

Both backends of the family, the process environment and a ``.env`` file,
address one variable space. Everything that governs the addressing lives in
the foundation of the family: the naming options (``name_prefix``,
``name_case``, ``nested_delimiter``) and the dotenv file binding. This
module gathers it, so one import gives the whole vocabulary:

```python
from advexp.settings_base.environment import (
    NameCase,
    environment_options,
)
```

The setting factories stay with their backends: a factory binds a member to
a plugin, and plugins live in the distributions, above the base. The
backends import the names of this module next to their own. The loading
distributions re-export the vocabulary from here through their own
environment plugin packages.
"""

from __future__ import annotations

from advexp.settings_base.dotenv_file import DOTENV_FILE_METADATA
from advexp.settings_base.environment_options import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NESTED_DELIMITER,
    apply_environment_case,
    build_environment_name,
    environment_options,
)
from advexp.settings_base.name_case import NameCase

__all__ = [
    "DOTENV_FILE_METADATA",
    "ENVIRONMENT_METADATA_OPTIONS",
    "NAME_CASE",
    "NAME_PREFIX",
    "NESTED_DELIMITER",
    "NameCase",
    "apply_environment_case",
    "build_environment_name",
    "environment_options",
]
