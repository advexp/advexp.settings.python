# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The link builder of the dotenv source for this distribution.

The ``.env`` file is one seat of the namespace of the environment family.
The naming rules are the shared dictionary of the family (see
:mod:`advexp.configuration.plugins.environment.variables` for the seat and
its rules), and the file is the link's own parameter. The builder here is
the chain spelling of the file binding for the classes of this
distribution: the link that it returns carries the name of this
distribution, and the ``class`` statement of a class from another
distribution rejects it.
"""

from __future__ import annotations

import os
from typing import Optional, Sequence, Union

from advexp.configuration.plugin_api import PACKAGE_NAME
from advexp.configuration.plugins.environment.dotenv.setting import DotenvSetting
from advexp.settings_base.dotenv_file import check_dotenv_file
from advexp.settings_base.env_parameter import (
    EnvParameter,
)
from advexp.settings_base.env_parameter import (
    link_parameters as _link_parameters,
)
from advexp.settings_base.environment import NameCase
from advexp.settings_base.environment_options import environment_options as _environment_options
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.sources import LINK_FILE_PARAM, LINK_PARAMETERS_PARAM


def dotenv_source(
    file: Union[str, os.PathLike],
    name_prefix: Optional[str] = None,
    name_case: Optional[NameCase] = None,
    nested_delimiter: Optional[str] = None,
    parameters: Union[EnvParameter, Sequence[EnvParameter], None] = None,
) -> SourceBinding:
    """Declare a ``.env`` file link, in the form used by this distribution.

    Pass the result of the builder to the ``options=`` keyword of the
    ``class`` statement, either alone (for a class that reads nothing else) or
    inside ``Sources(...)`` as one link of the chain::

        class AppConfig(Configuration, options=Sources(
            env_source(name_prefix="APP_", name_case=NameCase.UPPER),
            dotenv_source(file="app.env"),
        )):

    ``file`` names the file that the link reads. A missing file behaves as an
    empty one: required members are reported, and defaults stand in. The name
    may contain template slots that are filled in from environment variables:
    ``dotenv_source(file=".env-{APP_ENV}", parameters=app_env)`` reads the file
    of the environment that ``APP_ENV`` names. The naming parameters
    ``name_prefix``, ``name_case``, and ``nested_delimiter`` declare the naming
    dictionary of the family for this class, which has only one seat for these
    rules; see
    :func:`advexp.configuration.plugins.environment.variables.env_source` for
    the rules of the seat. The link belongs to the class that declares it: a
    subclass's own chain replaces it for that subclass only, and the base class
    keeps reading its own file.
    """
    problem = check_dotenv_file(file)
    if problem is not None:
        raise TypeError(f"invalid dotenv source file: {problem}")
    extras = {}
    if name_prefix is not None or name_case is not None or nested_delimiter is not None:
        extras = _environment_options(name_prefix, name_case, nested_delimiter)
    spelled = _link_parameters(parameters, (os.fspath(file),), "dotenv_source")
    return SourceBinding(
        link=SourceLink(
            attribute_class=DotenvSetting,
            params={
                LINK_FILE_PARAM: file,
                LINK_PARAMETERS_PARAM: spelled,
            },
        ),
        extras=extras,
        family=PACKAGE_NAME,
    )
