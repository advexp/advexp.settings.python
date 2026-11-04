# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the TOML file backend.

Importing the package (which imports this module) enables the backend, so no
explicit registration call is needed. See the package docstring for a usage
example.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Union

from advexp.settings.plugin_api import (
    AttributeSerializerBinding,
    LibraryConfiguration,
    SettingsBasePlugin,
    SourceLink,
)
from advexp.settings.plugins.toml_settings.serializer import TOMLSettingsSerializer
from advexp.settings.plugins.toml_settings.setting import TOMLSetting
from advexp.settings_base.sources import (
    LINK_FILE_PARAM,
    TOML_SOURCE_METADATA,
)
from advexp.settings_base.toml_file import TOML_FILE_METADATA, check_toml_file


class TOMLSettingsPlugin(SettingsBasePlugin):
    """Plugin object for the TOML file backend.

    The binding of a class to its file is the source seat of the family,
    :data:`~advexp.settings_base.sources.TOML_SOURCE_METADATA`. It is declared
    with ``options=toml_source(file=...)``. The :attr:`file_path` property is
    the imperative spelling over the file of the same seat; there is nothing
    separate next to it.
    """

    # the declarative binding; the plugin base setup() registers
    # it at import of this package
    binding = AttributeSerializerBinding(TOMLSetting, TOMLSettingsSerializer)

    @property
    def plugin_name(self) -> str:
        return "TOMLSettings"

    def __source_link(self) -> Optional[SourceLink]:
        """The TOML source seat in the class's chain; ``None`` when unbound."""
        link: Any = self.context.get_class_metadata(TOML_SOURCE_METADATA)
        return link if isinstance(link, SourceLink) else None

    @property
    def file_path(self) -> Optional[Union[str, os.PathLike]]:
        """The file binding of the settings class; ``None`` when the module default
        governs.

        Reading resolves along the class chain: the own binding of the class, or
        otherwise the binding of the nearest ancestor. Assigning re-binds the class
        itself: the value is validated and stored on the own source link of the
        class. The declarative ``options=toml_source(file=...)`` binding and an
        assignment here are therefore the same channel.
        """
        link = self.__source_link()
        if link is not None:
            return link.param(LINK_FILE_PARAM)
        return self.context.get_class_metadata(TOML_FILE_METADATA)

    @file_path.setter
    def file_path(self, value: Union[str, os.PathLike]) -> None:
        problem = check_toml_file(value)
        if problem is not None:
            raise TypeError(f"invalid TOML source file: {problem}")
        link = self.__source_link()
        if link is None:
            self.context.set_class_metadata(TOML_FILE_METADATA, value)
            return
        self.context.set_class_metadata(
            TOML_SOURCE_METADATA,
            SourceLink(
                attribute_class=link.attribute_class,
                params={**link.params, LINK_FILE_PARAM: value},
            ),
        )


LibraryConfiguration.register_settings_plugin(TOMLSettingsPlugin)
