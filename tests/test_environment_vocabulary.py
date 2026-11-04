"""The vocabulary of the environment family is gathered in one import.

The foundation module ``advexp.settings_base.environment`` collects the
naming options and the constants. The ``plugins.environment`` packages of
both distributions re-export the shared objects of the vocabulary from it:
one import line for each package, and a one-line import for the whole family
next to them.

The entry builder of the naming dictionary is the shared vocabulary itself.
The source builders of both distributions (``env_source(...)`` and
``dotenv_source(...)``) put it into their links. Each of them is stamped
with the name of its distribution, so a class of one distribution refuses
the builder of the other at the ``class`` statement.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

import advexp.configuration.plugins.environment as configuration_family
import advexp.settings.plugins.environment as settings_family
from advexp.settings_base import environment as family
from advexp.settings_base.environment_options import environment_options
from advexp.settings_base.name_case import NameCase
from advexp.settings_base.sources import ENVIRONMENT_SOURCE_METADATA


def test_the_module_gathers_the_vocabulary():
    # the gathered names are the defining objects, not copies
    assert family.NameCase is NameCase
    assert family.environment_options is environment_options
    for name in (
        "DOTENV_FILE_METADATA",
        "ENVIRONMENT_METADATA_OPTIONS",
        "NAME_PREFIX",
        "NAME_CASE",
        "NESTED_DELIMITER",
        "apply_environment_case",
        "build_environment_name",
    ):
        assert hasattr(family, name)


def test_both_distributions_reexport_the_shared_vocabulary():
    for package in (settings_family, configuration_family):
        assert package.NameCase is NameCase


def test_both_distributions_source_builders_declare_the_same_naming():
    # the distributions' environment builders declare the one naming
    # dictionary: the same foundation entry beside each package's own link
    import advexp.configuration.plugins.environment.variables as cenv
    import advexp.settings.plugins.environment.variables as senv

    assert dict(cenv.env_source(name_prefix="APP_").extras) == {
        name: value
        for name, value in dict(senv.env_source(name_prefix="APP_")).items()
        if name != ENVIRONMENT_SOURCE_METADATA
    }
    # no naming declared: the link alone, no dictionary entry
    assert dict(cenv.env_source().extras) == {}
    assert set(dict(senv.env_source())) == {ENVIRONMENT_SOURCE_METADATA}


def test_settings_dotenv_builder_declares_the_shared_naming():
    # the dotenv builder seats its link beside the naming dictionary the
    # family shares: the dictionary entry is the foundation's own form
    import advexp.settings.plugins.environment.dotenv as denv
    from advexp.settings_base.environment_options import ENVIRONMENT_METADATA_OPTIONS
    from advexp.settings_base.sources import DOTENV_SOURCE_METADATA

    entry = dict(denv.dotenv_source(file="shared.env", name_prefix="APP_"))
    assert set(entry) == {DOTENV_SOURCE_METADATA, ENVIRONMENT_METADATA_OPTIONS}
    assert (
        entry[ENVIRONMENT_METADATA_OPTIONS]
        == dict(environment_options(name_prefix="APP_"))[ENVIRONMENT_METADATA_OPTIONS]
    )


@pytest.mark.parametrize(
    ("family_module", "facade_module"),
    [
        ("advexp.settings.plugins.environment", "advexp.settings"),
        ("advexp.configuration.plugins.environment", "advexp.configuration"),
    ],
)
def test_the_family_root_enables_no_backend(family_module, facade_module):
    """The root carries the naming vocabulary alone: no backend comes in."""
    script = textwrap.dedent(
        """
        import sys

        import {family_module} as family
        from {facade_module} import LibraryConfiguration

        # no backend module of the family loaded, none registered
        assert not any(
            "environment.variables" in name or "environment.dotenv" in name
            for name in sys.modules
        )
        enabled = {{plugin.__name__ for plugin in LibraryConfiguration._plugin_classes}}
        assert "EnvironmentVariablesPlugin" not in enabled
        assert "DotenvPlugin" not in enabled
        assert not hasattr(family, "environment_variable_setting")
        assert not hasattr(family, "dotenv_setting")
        """
    ).format(family_module=family_module, facade_module=facade_module)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
