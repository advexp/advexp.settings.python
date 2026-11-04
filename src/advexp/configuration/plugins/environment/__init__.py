# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The environment family of sources: one namespace with shared naming
options.

The process environment and ``.env`` files address a single variable
space. Therefore, every source of the family builds names by the rules
that are declared on the environment link of the chain:
``env_source(name_prefix=..., name_case=...)`` or
``dotenv_source(file=..., name_prefix=...)``, with one seat per class::

    import advexp.configuration.plugins.environment.variables as env
    import advexp.configuration as adv_config

    class AppConfig(adv_config.Configuration, options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER,
    )):
        # APP_SESSION_TTL, required
        session_ttl: timedelta = env.environment_variable_setting(default="0:30:00")

    # APP_SESSION_TTL=1:30:00 in the environment
    AppConfig.load_configuration()

    # datetime.timedelta(seconds=5400) — parsed, not a string
    print(repr(AppConfig.session_ttl))

This package is the vocabulary of the family. Importing it registers the
options validator and brings in the naming options and their constants.
The vocabulary itself lives in the foundation of the family,
``advexp.settings_base.environment_options``: the namespace spans several
distributions, so the settings backends and the read-only configuration
sources build names by the same rules. Importing this package enables no
source. Each source is enabled by importing its own module, which contains
everything the source needs, including its chain builder: ``variables``
(the process environment) and ``dotenv`` (a ``.env`` file parsed by
python-dotenv, which comes with the ``dotenv`` extra of the distribution).
"""

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
    "NameCase",
]
