# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The ``NOT_FOUND`` sentinel of storage backends."""

from __future__ import annotations


class _NotFound:
    """Sentinel returned by serializers when a setting has no stored value."""

    def __repr__(self) -> str:
        return "NOT_FOUND"


NOT_FOUND = _NotFound()
"""Returned by ``ISettingsSerializer.load`` when the storage holds no value.

A ``None`` return is a *valid* stored value; absence of a value is always
expressed with this sentinel.
"""
