# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The error raised for setting attributes without a registered serializer."""

from __future__ import annotations


class PluginNotEnabledError(KeyError):
    """A setting attribute has no registered serializer (plugin not imported)."""
