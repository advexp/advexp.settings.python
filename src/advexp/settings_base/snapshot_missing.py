# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The ``missing=`` modes of ``to_dict``: what a required member without a
value becomes in the snapshot.

A snapshot reads every member, and reading a required member that never got
a value raises — the default mode keeps that honesty. The other two modes
soften it for a class in such a state (never loaded, a failed load, or a
reset that cleared the member): ``MISSING_NONE`` stands ``None`` in for
every such member, and ``MISSING_SKIP`` leaves the member out of the
snapshot entirely.
"""

from __future__ import annotations

from typing import Any

MISSING_RAISE = "raise"
"""The default mode: a required member without a value fails the snapshot
with the read error of that member."""

MISSING_NONE = "none"
"""A required member without a value is exported as ``None``: the snapshot
keeps every member name, and a model with optional fields accepts it."""

MISSING_SKIP = "skip"
"""A required member without a value is left out: the snapshot holds only
the members that have a value."""

_MISSING_MODES = (MISSING_RAISE, MISSING_NONE, MISSING_SKIP)


def validate_missing_mode(value: Any) -> None:
    """Raise ``ValueError`` unless ``value`` is one of the ``missing=`` modes.

    The error message lists every accepted mode, so a typo names its own
    correction.
    """
    if value not in _MISSING_MODES:
        listing = ", ".join(repr(mode) for mode in _MISSING_MODES)
        raise ValueError(f"missing={value!r} is not one of: {listing}")
