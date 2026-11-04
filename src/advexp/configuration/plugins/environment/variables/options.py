# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The source builder of the environment family for this distribution.

The variable namespace spans several distributions: a settings backend and
a read-only configuration source that read the same variables must resolve
them in the same way. For this reason, the naming rules are the shared
vocabulary of the family in ``advexp.settings_base.environment_options``,
with one dictionary per declaring class. The builder here is the chain
spelling of that vocabulary for the classes of this distribution: the link
that it returns carries the name of the distribution, and the ``class``
statement of a class of another distribution rejects it.
"""

from __future__ import annotations

from typing import Optional

from advexp.configuration.plugin_api import PACKAGE_NAME
from advexp.configuration.plugins.environment.variables.setting import (
    EnvironmentVariableSetting,
)
from advexp.settings_base.environment import NameCase
from advexp.settings_base.environment_options import environment_options as _environment_options
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.source_link import SourceLink


def env_source(
    name_prefix: Optional[str] = None,
    name_case: Optional[NameCase] = None,
    nested_delimiter: Optional[str] = None,
) -> SourceBinding:
    """Declare a process-environment link, in the form used by this distribution.

    Pass the result of the builder to the ``options=`` keyword of the ``class``
    statement, either alone (for a class that reads nothing else) or inside
    ``Sources(...)`` as one link of the chain:

    ```python
        class AppConfig(Configuration, options=Sources(
            env_source(name_prefix="APP_", name_case=NameCase.UPPER),
            json_source(file="app.json"),
        )):
    ```

    The naming parameters ``name_prefix``, ``name_case`` and
    ``nested_delimiter`` declare the naming dictionary of the family for this
    class. A class has only one seat for these rules, and every environment
    link of the chain shares it (the process environment and a ``.env`` file
    form one namespace). Declaring the parameters on two environment links in
    one ``options=`` makes the ``class`` statement fail, because two records of
    one dictionary could drift apart through a typo. A link without naming
    parameters reads the dictionary that the nearest environment link above it
    declared. If there is none, member names are used as written, with no
    prefix. The dictionary belongs to the class that declares it: a subclass's
    own link with naming parameters adds a dictionary of its own, and the
    members of the base class keep theirs.
    """
    extras = {}
    if name_prefix is not None or name_case is not None or nested_delimiter is not None:
        extras = _environment_options(name_prefix, name_case, nested_delimiter)
    return SourceBinding(
        link=SourceLink(attribute_class=EnvironmentVariableSetting),
        extras=extras,
        family=PACKAGE_NAME,
    )
