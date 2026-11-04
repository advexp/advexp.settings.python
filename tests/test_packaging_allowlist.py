"""The packaging allowlists must cover exactly the packages under ``src/``.

Every catalog discovers its packages through an explicit ``include`` list.
This list is the boundary of the edition: a module that is not on the list
does not ship, so a plugin that is not part of the edition cannot leak into
its wheel just because it exists in the shared source tree.

The lists and the tree must not drift apart in either direction:

- A package that is present under ``src/`` but missing from every list
  silently drops out of all builds. It imports from a checkout, but it
  raises ``ImportError`` from the wheel.
- A name on a list without a package breaks the build.
- A package sits on exactly one edition's list. The same subpackage in two
  wheels would mean two owners of one import path.
"""

import pathlib

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_PACKAGES = _REPO_ROOT / "packages"
_SRC = _REPO_ROOT / "src"
_FREE_EDITION = "advexp-settings"


def _edition_includes():
    """Distribution name → its allowlist, for every catalog with metadata."""
    editions = {}
    for pyproject in sorted(_PACKAGES.glob("*/pyproject.toml")):
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        editions[data["project"]["name"]] = set(
            data["tool"]["setuptools"]["packages"]["find"]["include"]
        )
    return editions


def _other_edition_packages():
    editions = _edition_includes()
    return set().union(*(include for name, include in editions.items() if name != _FREE_EDITION))


def _source_packages():
    # the whole advexp namespace: the settings tree, the shared base and the
    # configuration skeleton — each ships in the edition that owns it
    packages = {
        "advexp.settings",
        "advexp.settings_base",
        "advexp.configuration",
    }
    for init in sorted((_SRC / "advexp").rglob("__init__.py")):
        packages.add(init.parent.relative_to(_SRC).as_posix().replace("/", "."))
    return packages


def test_every_source_package_ships_in_some_edition():
    shipping = set().union(*_edition_includes().values())
    missing_from_all = _source_packages() - shipping
    assert not missing_from_all, (
        f"packages under src/ are on no edition's packaging allowlist "
        f"(packages/*/pyproject.toml [tool.setuptools.packages.find] include) "
        f"and will not ship: {sorted(missing_from_all)} — add them to the list "
        f"of the edition they belong to, or move them out of the source tree"
    )


def test_allowlists_name_no_absent_package():
    shipping = set().union(*_edition_includes().values())
    listed_without_package = shipping - _source_packages()
    assert not listed_without_package, (
        f"packaging allowlists name packages that do not exist under src/: "
        f"{sorted(listed_without_package)} — the build breaks; drop the stale names"
    )


def test_no_package_ships_in_two_editions():
    editions = _edition_includes()
    owned_twice = set()
    for name, include in editions.items():
        others = set().union(*(v for k, v in editions.items() if k != name))
        owned_twice |= include & others
    assert not owned_twice, (
        f"the same package is on several editions' allowlists: "
        f"{sorted(owned_twice)} — two wheels would own one import path; keep "
        f"every package on exactly one list"
    )


def test_free_edition_ships_everything_not_owned_by_another_edition():
    free = _edition_includes()[_FREE_EDITION]
    assert free == _source_packages() - _other_edition_packages(), (
        "the free edition's allowlist must cover exactly the packages no other "
        "edition owns — a missing name drops out of the free wheel, an extra "
        "one leaks another edition's plugin into it"
    )
