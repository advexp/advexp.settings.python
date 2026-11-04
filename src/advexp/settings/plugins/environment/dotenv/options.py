# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The builders of the dotenv backend for this distribution.

The ``.env`` file is one seat of the namespace of the environment family.
The naming rules are the shared dictionary of the family (see
:func:`advexp.settings.plugins.environment.variables.env_source` for the
seat and its rules), and the file is the own parameter of the builders.
The source builder binds the class to the file storage. The file seat names
the file of the dotenv members of the class, when the builder of another
family holds the binding. Each entry that a builder creates carries the
name of the distribution, and the ``class`` statement of a class of another
distribution rejects it.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Sequence, Tuple, Union

from advexp.settings.plugin_api import PACKAGE_NAME
from advexp.settings.plugins.environment.dotenv.setting import DotenvSetting
from advexp.settings_base.dotenv_file import check_dotenv_file
from advexp.settings_base.dotenv_file import (
    dotenv_file as _dotenv_file,
)
from advexp.settings_base.env_parameter import (
    EnvParameter,
)
from advexp.settings_base.env_parameter import (
    link_parameters as _link_parameters,
)
from advexp.settings_base.environment import NameCase
from advexp.settings_base.environment_options import environment_options as _environment_options
from advexp.settings_base.family_boundaries import stamped_options
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.sources import (
    DOTENV_SOURCE_METADATA,
    LINK_FILE_PARAM,
    LINK_PARAMETERS_PARAM,
)


def dotenv_source(
    file: Optional[Union[str, os.PathLike]] = None,
    name_prefix: Optional[str] = None,
    name_case: Optional[NameCase] = None,
    nested_delimiter: Optional[str] = None,
    parameters: Union[EnvParameter, Sequence[EnvParameter], None] = None,
) -> Mapping[str, Any]:
    """Bind a settings class to a ``.env`` file, in the form used by this
    distribution.

    Pass the result of the builder to the ``options=`` keyword of the ``class``
    statement, either alone (for a class that reads nothing else) or next to
    the builders of other families in one ``options=`` sequence::

        class AppSettings(Settings, options=dotenv_source(
            file=".env", name_prefix="APP_", name_case=NameCase.UPPER,
        )):
            mode: str

    ``file`` names the file that the backend reads and writes. A builder
    without ``file`` uses the module default of the backend. An absent file
    behaves as an empty one: required members are reported, and defaults stand
    in. The name may contain template slots that are resolved through
    environment variables:
    ``dotenv_source(file=".env-{APP_ENV}", parameters=app_env)`` reads the file
    of the environment that ``APP_ENV`` names.

    The naming parameters ``name_prefix``, ``name_case``, and
    ``nested_delimiter`` declare the naming dictionary of the family for this
    class. A class has only one seat for these rules, and the process
    environment and this file share it. Declare the rules either on this
    builder or on ``env_source``, but only once per class: two declarations
    make the ``class`` statement fail, as for every metadata name that is
    declared twice. A class that declares no dictionary reads member names as
    written, with no prefix.

    The binding is a metadata entry of the class itself. A subclass without its
    own ``dotenv_source`` inherits the nearest one above it, and a subclass with
    its own ``dotenv_source`` switches to it for itself and its subclasses. The
    base class keeps reading its own file.
    """
    problem = check_dotenv_file(file) if file is not None else None
    if problem is not None:
        raise TypeError(f"invalid dotenv source file: {problem}")
    templates: Tuple[str, ...] = (os.fspath(file),) if file is not None else ()
    spelled = _link_parameters(parameters, templates, "dotenv_source")
    entry: dict = {
        DOTENV_SOURCE_METADATA: SourceLink(
            attribute_class=DotenvSetting,
            params={
                LINK_FILE_PARAM: file,
                LINK_PARAMETERS_PARAM: spelled,
            },
        )
    }
    if name_prefix is not None or name_case is not None or nested_delimiter is not None:
        entry.update(_environment_options(name_prefix, name_case, nested_delimiter))
    return stamped_options(entry, PACKAGE_NAME)


def dotenv_file(path: Union[str, os.PathLike]) -> Mapping[str, Any]:
    """Name the ``.env`` file of a settings class, in the form used by this
    distribution.

    The file seat is the file of the class for its ``dotenv_setting`` members,
    when the builder of another family holds the binding. The seat and its
    validation are part of the shared vocabulary of the family; see
    :func:`advexp.settings_base.dotenv_file.dotenv_file`. The stamp makes the
    ``class`` statement of a class of another distribution reject the entry.
    """
    return stamped_options(_dotenv_file(path), PACKAGE_NAME)
