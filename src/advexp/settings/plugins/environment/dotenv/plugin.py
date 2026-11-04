# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The plugin object of the dotenv file backend.

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
from advexp.settings.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.settings.plugins.environment.dotenv.setting import DotenvSetting
from advexp.settings_base.dotenv_file import DOTENV_FILE_METADATA, check_dotenv_file
from advexp.settings_base.sources import (
    DOTENV_SOURCE_METADATA,
    LINK_FILE_PARAM,
)


class DotenvPlugin(SettingsBasePlugin):
    """Plugin object for the dotenv file backend.

    The binding of a class to its file is class metadata, stored under the
    family key of the source seat of the family,
    :data:`~advexp.settings_base.sources.DOTENV_SOURCE_METADATA`. It is
    declared with ``options=dotenv_source(file=...)``. The :attr:`file_path`
    property is the imperative spelling over the file of the same seat; there
    is nothing separate next to it.
    """

    # the declarative binding; the plugin base setup() registers
    # it at import of this package
    binding = AttributeSerializerBinding(DotenvSetting, DotenvSerializer)

    @property
    def plugin_name(self) -> str:
        return "Dotenv"

    @property
    def file_path(self) -> Optional[Union[str, os.PathLike]]:
        """The file binding of the settings class; ``None`` when the module default
        governs.

        Reading resolves along the class chain: the own binding of the class, or
        otherwise the binding of the nearest ancestor. Assigning re-binds the class
        itself: the value is validated and stored on the own source link of the
        class. The declarative ``options=dotenv_source(file=...)`` binding and an
        assignment here are therefore the same channel.
        """
        link: Any = self.context.get_class_metadata(DOTENV_SOURCE_METADATA)
        if isinstance(link, SourceLink):
            return link.param(LINK_FILE_PARAM)
        return self.context.get_class_metadata(DOTENV_FILE_METADATA)

    @file_path.setter
    def file_path(self, value: Union[str, os.PathLike]) -> None:
        problem = check_dotenv_file(value)
        if problem is not None:
            raise TypeError(f"invalid dotenv source file: {problem}")
        link: Any = self.context.get_class_metadata(DOTENV_SOURCE_METADATA)
        if not isinstance(link, SourceLink):
            self.context.set_class_metadata(DOTENV_FILE_METADATA, value)
            return
        self.context.set_class_metadata(
            DOTENV_SOURCE_METADATA,
            SourceLink(
                attribute_class=link.attribute_class,
                params={**link.params, LINK_FILE_PARAM: value},
            ),
        )


LibraryConfiguration.register_settings_plugin(DotenvPlugin)
