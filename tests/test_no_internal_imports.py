"""Import boundaries of the source tree: private internals and layering.

Three rules live here.

1. ``advexp.settings._internal`` and ``advexp.configuration._internal`` are
   private API. The supported import sites are the root of each package
   (``advexp.settings`` and ``advexp.configuration``, the application API)
   and its ``plugin_api`` (for backend authors). The internals are
   refactored freely, and only the library itself and its unit tests may
   touch them.
2. The base package is a layer below the settings package.
   ``advexp.settings_base`` has no reference to ``advexp.settings`` at all:
   not an import (not even in ``if TYPE_CHECKING`` blocks), and not a
   mention in a docstring or a string. A consumer that has only
   ``advexp-settings-base`` installed can therefore be type-checked at full
   precision, and the layering reads honestly from the own sources of the
   base.
3. The configuration package is a sibling, not a client.
   ``advexp.configuration`` builds on the base alone and imports nothing
   from ``advexp.settings``. A user who has only ``advexp-configuration``
   installed must find every import resolvable.

Python cannot enforce any of these lines at runtime, so they are held here,
and also by the ruff ``TID251`` ban on both ``_internal`` packages (see
pyproject.toml).
"""

import ast
import pathlib
import re

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# source trees only: build/ and dist/ hold stale copies of older revisions
_CODE_DIRS = [
    _REPO_ROOT / "src" / "advexp" / "settings" / "plugins",
    _REPO_ROOT / "src" / "advexp" / "configuration" / "plugins",
    _REPO_ROOT / "samples",
]

_BASE_DIR = _REPO_ROOT / "src" / "advexp" / "settings_base"

_CONFIGURATION_DIR = _REPO_ROOT / "src" / "advexp" / "configuration"

# the private implementation subpackages; each package's root and plugin_api
# are their only supported import sites
_PRIVATE_PACKAGES = (
    "advexp.settings._internal",
    "advexp.configuration._internal",
)


def _python_files(*directories):
    for directory in directories:
        yield from sorted(directory.rglob("*.py"))


def _imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield node.module
                if node.module == "advexp":
                    # `from advexp import settings` spells the same dependency
                    yield from (f"advexp.{alias.name}" for alias in node.names)


def _is_private_module(name):
    return any(name == package or name.startswith(package + ".") for package in _PRIVATE_PACKAGES)


@pytest.mark.parametrize(
    "path", list(_python_files(*_CODE_DIRS)), ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_no_internal_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = sorted(name for name in _imported_modules(tree) if _is_private_module(name))
    assert not offenders, (
        f"{path.relative_to(_REPO_ROOT)} imports the private package {offenders}; "
        "use the package root (advexp.settings, advexp.configuration — the "
        "application API) or its plugin_api (advexp.settings.plugin_api, "
        "advexp.configuration.plugin_api)"
    )


@pytest.mark.parametrize(
    "path", list(_python_files(_BASE_DIR)), ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_base_does_not_import_settings(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = sorted(
        name
        for name in _imported_modules(tree)
        if name == "advexp.settings" or name.startswith("advexp.settings.")
    )
    assert not offenders, (
        f"{path.relative_to(_REPO_ROOT)} imports {offenders} from the package built "
        "on top of the base; the base must stay self-contained (type the settings "
        "class as SettingsMeta, not as Settings)"
    )


@pytest.mark.parametrize(
    "path", list(_python_files(_CONFIGURATION_DIR)), ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_configuration_does_not_import_settings(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = sorted(
        name
        for name in _imported_modules(tree)
        if name == "advexp.settings" or name.startswith("advexp.settings.")
    )
    assert not offenders, (
        f"{path.relative_to(_REPO_ROOT)} imports {offenders} from the settings "
        "package; advexp-configuration depends on advexp-settings-base alone — "
        "import the base's own modules or advexp.configuration.plugin_api"
    )


@pytest.mark.parametrize(
    "path", list(_python_files(_BASE_DIR)), ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_base_mentions_no_settings_package(path):
    text = path.read_text(encoding="utf-8")
    # `advexp.settings_base` is the base's own spelling and does not count;
    # anything else — an import, a docstring cross-reference, a channel name —
    # is a reference to the package built on top of the base
    assert not re.findall(r"advexp\.settings(?![_a-zA-Z0-9])", text), (
        f"{path.relative_to(_REPO_ROOT)} mentions the settings package; the base "
        "is a layer below it — reference the base's own names or phrase the "
        "prose without the settings spelling"
    )
