# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The environment family of backends: one namespace with shared naming rules.

The process environment and ``.env`` files address a single variable
space. Therefore, every backend of the family builds names by the rules
that are declared per settings class: the naming parameters of the source
builder (``env_source(...)``, ``dotenv_source(...)``). Each class has its
own dictionary of rules (the declaration of a subclass never changes the
variables of inherited members), and a member is resolved by the dictionary
of the class that declared it::

    import advexp.settings as adv_settings
    import advexp.settings.plugins.environment.variables as env

    class AppSettings(adv_settings.Settings, options=env.env_source(
        name_prefix="APP_", name_case=env.NameCase.UPPER,
    )):
        # APP_SESSION_TTL
        session_ttl: timedelta = timedelta(minutes=30)

    # APP_SESSION_TTL=1:30:00 in the environment
    AppSettings.load_settings()

    # datetime.timedelta(seconds=5400) — parsed, not a string
    print(repr(AppSettings.session_ttl))

This package is the vocabulary of the family. Importing it registers the
options validator and brings in the naming constants. The vocabulary itself
lives in the foundation of the family,
``advexp.settings_base.environment_options``: the namespace spans several
distributions, so the settings backends and the read-only configuration
sources build names by the same rules. Importing this package enables no
backend. Each backend is enabled by importing its own module, which
contains everything the backend needs, including its source builder, so
importing that module alone is enough: ``variables`` (the process
environment) and ``dotenv`` (a ``.env`` file parsed by python-dotenv, which
comes with the ``dotenv`` extra of the distribution).
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
