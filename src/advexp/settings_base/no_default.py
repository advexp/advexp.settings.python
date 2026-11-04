# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The ``NO_DEFAULT`` sentinel of setting attribute defaults."""

from __future__ import annotations


class _NoDefault:
    """Sentinel: distinguishes "no default given" from ``default=None``."""

    def __repr__(self) -> str:
        return "NO_DEFAULT"


NO_DEFAULT = _NoDefault()
"""Sentinel for absent default values (allows ``default=False``/``default=None``).

A member declared with it serves ``None`` while no value has arrived, and
that stand-in faces the member's own constraints at class creation: a
member whose constraints reject ``None`` — ``eq=``, a ``validator``
returning false — fails the ``class`` statement, for without an assignment
it could never hold a valid value; :data:`~advexp.settings_base.required.REQUIRED`
is the honest spelling for such a member.
"""
