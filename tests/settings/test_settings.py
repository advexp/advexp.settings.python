"""Smoke tests: the package and all plugin subpackages import cleanly."""

import importlib
import subprocess
import sys
import textwrap

import advexp.settings
import advexp.settings.plugin_api

PLUGIN_MODULES = [
    "advexp.settings.plugins.json_settings",
    "advexp.settings.plugins.environment.variables",
]


def test_version_is_exposed():
    assert advexp.settings.__version__


def test_no_default_is_plugin_api_only():
    # the application spelling of "no default" is an omitted ``default=``;
    # the sentinel itself stays with the backend authors' plugin_api
    assert not hasattr(advexp.settings, "NO_DEFAULT")
    assert hasattr(advexp.settings.plugin_api, "NO_DEFAULT")


def test_required_is_shared_with_plugin_api():
    # both audiences read the marker: applications declare a required
    # member with it, backend authors meet it as a declared default
    assert hasattr(advexp.settings, "REQUIRED")
    assert hasattr(advexp.settings.plugin_api, "REQUIRED")


def test_plugins_importable():
    for module_name in PLUGIN_MODULES:
        module = importlib.import_module(module_name)
        assert module.__doc__, f"{module_name} is missing a docstring"


def test_the_core_import_is_self_sufficient():
    """The facade alone declares a working class: setting lives in memory."""
    script = textwrap.dedent(
        """
        from datetime import timedelta

        from advexp.settings import (
            SettingValidationError,
            Settings,
            non_storage_setting,
        )


        class Limits(Settings):
            timeout: timedelta = non_storage_setting(default="0:30:00")
            retries: int = non_storage_setting(default=3, ge=0)


        # the declared defaults, converted
        assert repr(Limits.timeout) == "datetime.timedelta(seconds=1800)"
        assert Limits.retries == 3

        # the passes of a storage-backed class run clean on a memory class
        Limits.load_settings()
        Limits.save_settings()
        assert Limits.retries == 3

        # assignment, constraints, bulk update, snapshot
        Limits.retries = 5
        assert Limits.to_dict() == {
            "timeout": timedelta(seconds=1800), "retries": 5
        }
        Limits.update_from_dict({"retries": 7})
        assert Limits.retries == 7
        try:
            Limits.retries = -1
            raise SystemExit("the constraint did not fire")
        except SettingValidationError:
            pass
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
