# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The settings plugin contract: the storage backend plugin kind."""

from __future__ import annotations

from advexp.settings_base.plugin_interface import IPlugin


class ISettingsPlugin(IPlugin):
    """The contract of the storage backend plugin kind.

    A plugin of this kind bundles a storage backend: it registers its
    setting attributes and serializers (conventionally from a ``setup()``
    class method that is called at registration), and it exposes
    plugin-specific operations that user code reaches through
    ``Settings.get_plugin(...)``.

    The members of the contract live on the common :class:`IPlugin` root:
    a plugin of either kind is a name plus the bound context of one
    settings class.
    """
