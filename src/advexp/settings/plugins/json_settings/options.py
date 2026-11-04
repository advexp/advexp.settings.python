# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The builders of the JSON backend for this distribution.

The shared vocabulary of the backend (the file bindings and the naming
options) lives in :mod:`advexp.settings_base.json_file` and
:mod:`advexp.settings_base.json_options`, and it serves the two
distributions that read and write the same files. The builders here are the
spellings of that vocabulary for the classes of this distribution.

The source builder binds the class to its JSON storage: the file, the file
of the dynamic entries, and the key pattern. The file seat names the file of
the JSON members of the class, when the builder of another family holds the
binding. Each entry that a builder creates carries the name of the
distribution, so the ``class`` statement of a class of another distribution
rejects it. Import the builders from the package of the backend, as
applications have always done.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Sequence, Tuple, Union

from advexp.settings.plugin_api import PACKAGE_NAME
from advexp.settings.plugins.json_settings.setting import JSONSetting
from advexp.settings_base.env_parameter import (
    EnvParameter,
)
from advexp.settings_base.env_parameter import (
    link_parameters as _link_parameters,
)
from advexp.settings_base.family_boundaries import stamped_options
from advexp.settings_base.json_file import (
    JSON_DYNAMIC_FILE_METADATA,
    check_json_file,
)
from advexp.settings_base.json_file import (
    json_file as _json_file,
)
from advexp.settings_base.json_options import (
    NAME_PATTERN,
    check_json_options,
)
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.sources import (
    JSON_SOURCE_METADATA,
    LINK_FILE_PARAM,
    LINK_NAME_PATTERN_PARAM,
    LINK_PARAMETERS_PARAM,
)


def json_source(
    file: Optional[Union[str, os.PathLike]] = None,
    name_pattern: Optional[str] = None,
    dynamic_file: Optional[Union[str, os.PathLike]] = None,
    parameters: Union[EnvParameter, Sequence[EnvParameter], None] = None,
) -> Mapping[str, Any]:
    """Bind a settings class to its JSON file storage, in the form used by this
    distribution.

    Pass the result of the builder to the ``options=`` keyword of the ``class``
    statement, either alone (for a class that keeps everything in one JSON file)
    or next to the builders of other families in one ``options=`` sequence:

    ```python
    class AppSettings(Settings, options=js.json_source(file="app-settings.json")):
        token: str
    ```

    ``file`` names the file of the declared members of the class. A builder
    without ``file`` uses the module default of the backend. The name may
    contain template slots that are resolved through environment variables:
    ``json_source(file="settings-{APP_ENV}.json", parameters=app_env)`` reads
    the file of the environment that ``APP_ENV`` names. The parameters are
    declared once next to the binding and are shared by every templated path of
    the class.

    ``name_pattern`` sets the pattern that builds the keys. If it is omitted,
    the full ``{module}.{class}.{member}`` pattern is used. The explicit
    ``name=`` of a member is the full address in the document and never passes
    through the pattern.

    ``dynamic_file`` moves the dynamic entries of the class (the settings with
    names given at runtime) into a JSON file of their own. A class without it
    keeps them in the static file. The name may contain template slots in the
    same way as ``file``, filled from the same ``parameters``.

    The binding is a metadata entry of the class itself. A subclass without its
    own ``json_source`` inherits the nearest one above it, and a subclass with
    its own ``json_source`` switches to it for itself and its subclasses. The
    base class keeps reading its own file. Two ``json_source`` builders in one
    ``options=`` make the ``class`` statement fail, as for every metadata name
    that is declared twice.
    """
    problem = check_json_file(file) if file is not None else None
    if problem is not None:
        raise TypeError(f"invalid JSON source file: {problem}")
    if dynamic_file is not None:
        dynamic_problem = check_json_file(dynamic_file)
        if dynamic_problem is not None:
            raise TypeError(f"invalid JSON dynamic file: {dynamic_problem}")
    pattern_problem = check_json_options({NAME_PATTERN: name_pattern})
    if pattern_problem is not None:
        raise TypeError(f"invalid JSON source {NAME_PATTERN}: {pattern_problem}")
    templates: Tuple[str, ...] = ()
    if file is not None:
        templates = (os.fspath(file),)
        if dynamic_file is not None:
            templates = (os.fspath(file), os.fspath(dynamic_file))
    spelled = _link_parameters(parameters, templates, "json_source")
    entry: dict = {
        JSON_SOURCE_METADATA: SourceLink(
            attribute_class=JSONSetting,
            params={
                LINK_FILE_PARAM: file,
                LINK_NAME_PATTERN_PARAM: name_pattern,
                LINK_PARAMETERS_PARAM: spelled,
            },
        )
    }
    if dynamic_file is not None:
        entry[JSON_DYNAMIC_FILE_METADATA] = dynamic_file
    return stamped_options(entry, PACKAGE_NAME)


def json_file(path: Union[str, os.PathLike]) -> Mapping[str, Any]:
    """Name the JSON file of a settings class, in the form used by this
    distribution.

    The file seat is the file of the class for its ``json_setting`` members,
    when the builder of another family holds the binding. The seat and its
    validation are part of the shared vocabulary of the backend; see
    :func:`advexp.settings_base.json_file.json_file`. The stamp makes the
    ``class`` statement of a class of another distribution reject the entry.
    """
    return stamped_options(_json_file(path), PACKAGE_NAME)
