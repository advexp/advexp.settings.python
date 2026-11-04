# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The source builder of the process environment for this distribution.

The variable namespace spans several distributions: a settings backend and
a read-only configuration source that read the same variables must resolve
them in the same way. For this reason, the naming rules are the shared
vocabulary of the family in ``advexp.settings_base.environment_options``,
with one dictionary per declaring class. The builder here is the binding of
that vocabulary for the classes of this distribution: the entry that it
builds carries the name of the distribution, and the ``class`` statement of
a class of another distribution rejects it.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from advexp.settings.plugin_api import PACKAGE_NAME
from advexp.settings.plugins.environment.variables.setting import (
    EnvironmentVariableSetting,
)
from advexp.settings_base.environment import NameCase
from advexp.settings_base.environment_options import environment_options as _environment_options
from advexp.settings_base.family_boundaries import stamped_options
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.sources import (
    ENVIRONMENT_SOURCE_METADATA,
)


def env_source(
    name_prefix: Optional[str] = None,
    name_case: Optional[NameCase] = None,
    nested_delimiter: Optional[str] = None,
) -> Mapping[str, Any]:
    """Bind a settings class to the process environment, in the form used by this
    distribution.

    Pass the result of the builder to the ``options=`` keyword of the ``class``
    statement, either alone (for a class that reads nothing else) or next to
    the builders of other families in one ``options=`` sequence::

        class AppSettings(Settings, options=env.env_source(
            name_prefix="APP_", name_case=env.NameCase.UPPER,
        )):
            mode: str

    The naming parameters ``name_prefix``, ``name_case``, and
    ``nested_delimiter`` declare the naming dictionary of the family for this
    class. A class has only one seat for these rules, and the process
    environment and a ``.env`` file share it, because they are one variable
    namespace. Declare the dictionary either on this builder or on
    ``dotenv_source``, but only once per class: two declarations make the
    ``class`` statement fail, as for every metadata name that is declared
    twice. A class that declares no dictionary reads member names as written,
    with no prefix.

    The binding is a metadata entry of the class itself. A subclass without its
    own environment binding inherits the nearest one above it, and a subclass
    with its own binding switches to it for itself and its subclasses. The base
    class keeps reading its own variables.
    """
    entry: dict = {
        ENVIRONMENT_SOURCE_METADATA: SourceLink(attribute_class=EnvironmentVariableSetting)
    }
    if name_prefix is not None or name_case is not None or nested_delimiter is not None:
        entry.update(_environment_options(name_prefix, name_case, nested_delimiter))
    return stamped_options(entry, PACKAGE_NAME)
