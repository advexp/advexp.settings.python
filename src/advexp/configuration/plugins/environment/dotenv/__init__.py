# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Dotenv file configuration source.

Importing this package enables the source; no explicit registration call
is needed. The module contains everything that the source needs: the
naming rules of the family arrive through the environment link of the
chain, and the ``dotenv_source`` builder names the file::

    import advexp.configuration.plugins.environment.dotenv as env
    import advexp.configuration as adv_config

    class AppConfig(adv_config.Configuration, options=env.dotenv_source(
        file="app.env", name_prefix="APP_", name_case=env.NameCase.UPPER,
    )):
        # APP_SESSION_TTL in app.env
        session_ttl: timedelta = env.dotenv_setting(default="0:30:00")

    # APP_SESSION_TTL=1:30:00 in the file
    AppConfig.load_configuration()

    # datetime.timedelta(seconds=5400) — parsed, not a string
    print(repr(AppConfig.session_ttl))

Names are built by the shared rules of the environment family. The prefix
and the case that are declared on the environment link of the chain apply,
an explicit ``name=`` is the full address, and the nested delimiter of the
family addresses the fields of a dataclass member. As a result, a variable
that this source reads resolves in exactly the same way in the process
environment source. The source depends on the python-dotenv package:
install it with the extra of the distribution
(``pip install "advexp-configuration[dotenv]"``).

Declare members through the ``dotenv_setting`` factory so that the
assignments pass type checking. Assigning a ``DotenvSetting`` instance does
the same thing at runtime, but type checkers report a type mismatch for it
(see ``dotenv_setting``).

This module contains the whole source (the builder, the factory and the
serializer), and importing it enables only this source: the sibling source
for the process environment is not enabled until its own module is
imported. The root of the family, ``advexp.configuration.plugins.environment``,
contains only the naming vocabulary and enables no source.
"""

from advexp.configuration.plugins.environment.dotenv.options import dotenv_source
from advexp.configuration.plugins.environment.dotenv.plugin import DotenvPlugin
from advexp.configuration.plugins.environment.dotenv.serializer import DotenvSerializer
from advexp.configuration.plugins.environment.dotenv.setting import DotenvSetting, dotenv_setting
from advexp.settings_base.environment import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NESTED_DELIMITER,
    NameCase,
)

__all__ = [
    "ENVIRONMENT_METADATA_OPTIONS",
    "NAME_CASE",
    "NAME_PREFIX",
    "NESTED_DELIMITER",
    "DotenvPlugin",
    "DotenvSerializer",
    "DotenvSetting",
    "NameCase",
    "dotenv_setting",
    "dotenv_source",
]
