# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The own value storage of snapshot instances.

A snapshot instance that ``Settings.to_object`` produces carries its values
in a dict under a reserved name in its ``__dict__``. This is separate from
the class storage that ordinary instances share. The helpers here read that
storage. They live in a module of their own, so that the descriptor and the
cross-validation pass can share them without an import cycle.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

INSTANCE_VALUES_ATTR = "__settings_instance_values__"
"""Own value storage of a snapshot instance created by ``Settings.to_object``."""


def instance_values(obj: Any) -> Optional[Dict[str, Any]]:
    """Own value storage of a snapshot instance, or ``None`` for any other object."""
    own: Optional[Dict[str, Any]] = getattr(obj, "__dict__", None)
    if own is None:
        return None
    return own.get(INSTANCE_VALUES_ATTR)
