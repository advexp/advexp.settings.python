# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The metaclass that turns holder assignments into module declarations."""

from __future__ import annotations

from typing import Any

from advexp.settings_base.module_default import ModuleDefault, store_module_default


class ModuleDefaultMeta(type):
    """The metaclass of the configuration holders of the backends: the classes whose
    class-level attributes carry the process-wide defaults.

    Assigning a
    :class:`~advexp.settings_base.module_default.ModuleDefault` to one of the
    parameters of a holder declares the value for the module in which the
    assignment is written. The metaclass validates the value and stores the
    declaration in the registry of module declarations. The attribute of the
    holder keeps the process-wide value that it held: reading the parameter after
    a declaration still shows the fallback that every other module resolves
    through.

    Any other assignment reaches the class untouched, and it is the plain
    process-wide channel, exactly as before.
    """

    def __setattr__(cls, name: str, value: Any) -> None:
        if isinstance(value, ModuleDefault):
            store_module_default(cls, name, value)
            return
        super().__setattr__(name, value)
