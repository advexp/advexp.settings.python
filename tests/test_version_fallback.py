"""The version fallback of a source checkout must track the version of the
distribution.

Each package resolves ``__version__`` from the metadata of the installed
distribution. If the distribution is not installed (a bare source checkout),
it falls back to a hardcoded string.

The fallback belongs to the release in which it was written. If the version
in the ``pyproject.toml`` of the catalog is bumped without touching the
fallback, the checkout reports a version that never existed as a release.
The two spellings are held together here, so a version bump fails the suite
until the fallback follows.
"""

import pathlib
import re

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# distribution catalog → the module carrying its version fallback
_DISTRIBUTIONS = [
    ("advexp-settings", pathlib.Path("src/advexp/settings/_internal/version.py")),
    ("advexp-configuration", pathlib.Path("src/advexp/configuration/_internal/version.py")),
]


@pytest.mark.parametrize(("distribution", "module"), _DISTRIBUTIONS)
def test_fallback_tracks_the_distribution_version(distribution, module):
    catalog = _REPO_ROOT / "packages" / distribution / "pyproject.toml"
    declared = tomllib.loads(catalog.read_text(encoding="utf-8"))["project"]["version"]

    version_module = _REPO_ROOT / module
    text = version_module.read_text(encoding="utf-8")
    # the fallback is the only string-literal assignment; the primary
    # resolution assigns the result of version(), not a literal
    fallback = re.findall(r'__version__\s*=\s*"([^"]+)"', text)

    assert fallback == [declared], (
        f"{module} falls back to {fallback} while {catalog.relative_to(_REPO_ROOT)} "
        f"declares {declared!r}; bump the fallback together with the distribution"
    )
