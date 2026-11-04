# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The link builder of the TOML source for this distribution.

The parameters of the link (the file, the subtree and the key pattern) are
the own vocabulary of the TOML family and are spelled on the link itself.
The builder here is the chain spelling of that vocabulary for the classes
of this distribution. The link that it returns carries the name of the
distribution, and the ``class`` statement of a class of another
distribution rejects it.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Sequence, Union

from advexp.configuration.plugin_api import PACKAGE_NAME
from advexp.configuration.plugins.toml_settings.setting import TOMLSetting
from advexp.settings_base.dynamic_document import (
    TOML_DYNAMIC_GROUP_METADATA,
    check_dynamic_settings_group,
)
from advexp.settings_base.env_parameter import (
    EnvParameter,
)
from advexp.settings_base.env_parameter import (
    link_parameters as _link_parameters,
)
from advexp.settings_base.pointer import pointer_steps
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.sources import (
    LINK_FILE_PARAM,
    LINK_NAME_PATTERN_PARAM,
    LINK_PARAMETERS_PARAM,
    LINK_PATH_PARAM,
)
from advexp.settings_base.toml_file import TOML_DYNAMIC_FILE_METADATA, check_toml_file


def toml_source(
    file: Union[str, os.PathLike],
    path: Optional[str] = None,
    name_pattern: Optional[str] = None,
    dynamic_file: Optional[Union[str, os.PathLike]] = None,
    dynamic_of: Optional[str] = None,
    parameters: Union[EnvParameter, Sequence[EnvParameter], None] = None,
) -> SourceBinding:
    """Declare a TOML file link, in the form used by this distribution.

    Pass the result of the builder to the ``options=`` keyword of the ``class``
    statement, either alone (for a class that reads nothing else) or inside
    ``Sources(...)`` as one link of the chain:

    ```python
        class AppConfig(Configuration, options=Sources(
            env_source(name_prefix="APP_"),
            toml_source(file="app.toml"),
        )):
    ```

    ``file`` names the file that the link reads. It may contain template slots
    that are resolved through environment variables:
    ``toml_source(file="settings-{APP_ENV}.toml", parameters=app_env)`` reads
    the file of the environment that ``APP_ENV`` names.

    ``path`` anchors every key of the link inside a subtree of the document, as
    a JSON Pointer (RFC 6901). The ``path=`` of a member locates its key within
    the subtree, and the path of the link is added in front of it.

    ``name_pattern`` sets the pattern that builds the keys. If it is omitted,
    the full ``{module}.{class}.{member}`` pattern is used, and its dots are the
    table levels through which the address is nested. The link belongs to the
    class that declares it: the own chain of a subclass replaces it for that
    subclass only, and the base class keeps reading its own file.

    The dynamic side reads the group of a writer. ``dynamic_of`` names the
    group key of the writing class, which is the name under which its dynamic
    entries are stored in the document (``"app.LocalSettings"`` for a writer
    class with the default name). Without it, the class reads no dynamic
    entries. By default, the entries are in the file of the link (one document
    for both sides). ``dynamic_file`` gives them a file of their own, which is
    resolved through the same ``parameters`` if it contains template slots. The
    class reaches the collection through the TOML dynamic plugin of
    ``advexp.configuration.plugins.toml_dynamic_settings``.
    """
    problem = check_toml_file(file)
    if problem is not None:
        raise TypeError(f"invalid TOML source file: {problem}")
    if dynamic_file is not None:
        dynamic_problem = check_toml_file(dynamic_file)
        if dynamic_problem is not None:
            raise TypeError(f"invalid TOML dynamic file: {dynamic_problem}")
    if dynamic_of is not None:
        group_problem = check_dynamic_settings_group(dynamic_of)
        if group_problem is not None:
            raise TypeError(f"invalid TOML dynamic writer group: {group_problem}")
    if path is not None:
        # fail at the builder call, not at the first load pass
        pointer_steps(path)
    templates: tuple = (os.fspath(file),)
    if dynamic_file is not None:
        templates = (os.fspath(file), os.fspath(dynamic_file))
    spelled = _link_parameters(parameters, templates, "toml_source")
    extras: Mapping[str, Any] = {}
    if dynamic_file is not None or dynamic_of is not None:
        extras = {
            key: value
            for key, value in (
                (TOML_DYNAMIC_FILE_METADATA, dynamic_file),
                (TOML_DYNAMIC_GROUP_METADATA, dynamic_of),
            )
            if value is not None
        }
    return SourceBinding(
        link=SourceLink(
            attribute_class=TOMLSetting,
            params={
                LINK_FILE_PARAM: file,
                LINK_PATH_PARAM: path,
                LINK_NAME_PATTERN_PARAM: name_pattern,
                LINK_PARAMETERS_PARAM: spelled,
            },
        ),
        extras=extras or None,
        family=PACKAGE_NAME,
    )
