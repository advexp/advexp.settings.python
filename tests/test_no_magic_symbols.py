"""No magic symbols: a value that has a constant is spelled through it.

The metadata keys and the option names of the family exist as constants:

- ``ENVIRONMENT_METADATA_OPTIONS``, ``NAME_PREFIX``, and ``NAME_CASE`` in
  ``advexp.settings_base.environment_options``;
- the dotenv file key in ``advexp.settings_base.dotenv_file``;
- the JSON file keys in ``advexp.settings_base.json_file``;
- the TOML file keys in ``advexp.settings_base.toml_file``;
- the source seats and the chain key in ``advexp.settings_base.sources``.

Every string that is built from them (error messages, test expectations, and
sample declarations) goes through the constant, so a change of a value never
leaves stragglers behind (see AGENTS.md, "Стиль").

A guarded value may appear as a literal only in the module of the constants
themselves. Docstrings are free, because prose about a value names it. An
ordinary string literal that embeds a guarded value (an f-string message, or
a ``match=`` expectation) is the violation that this test catches.

The data-form values of ``NameCase`` (``"upper"`` and ``"lower"``) are
deliberately not guarded: the tests pin them as the public stored form, so
there the literal is the tested contract.

The set grows with the family: a new constant of this kind joins
``_GUARDED_VALUES``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, Set

from advexp.settings_base.dotenv_file import DOTENV_FILE_METADATA
from advexp.settings_base.dynamic_document import (
    JSON_DYNAMIC_GROUP_METADATA,
    TOML_DYNAMIC_GROUP_METADATA,
    YAML_DYNAMIC_GROUP_METADATA,
)
from advexp.settings_base.environment_options import (
    ENVIRONMENT_METADATA_OPTIONS,
    NAME_CASE,
    NAME_PREFIX,
    NESTED_DELIMITER,
)
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.json_file import (
    JSON_DYNAMIC_FILE_METADATA,
    JSON_FILE_METADATA,
)
from advexp.settings_base.json_options import JSON_METADATA_OPTIONS, NAME_PATTERN
from advexp.settings_base.sources import (
    DOTENV_SOURCE_METADATA,
    ENVIRONMENT_SOURCE_METADATA,
    JSON_SOURCE_METADATA,
    SOURCE_CHAIN_METADATA,
    TOML_SOURCE_METADATA,
    YAML_SOURCE_METADATA,
)
from advexp.settings_base.toml_file import TOML_DYNAMIC_FILE_METADATA, TOML_FILE_METADATA
from advexp.settings_base.toml_options import TOML_METADATA_OPTIONS
from advexp.settings_base.yaml_file import YAML_DYNAMIC_FILE_METADATA, YAML_FILE_METADATA
from advexp.settings_base.yaml_options import YAML_METADATA_OPTIONS

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCANNED_DIRS = ("src", "tests", "samples")
_DEFINING_MODULES = {
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "environment_options.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "dotenv_file.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "dynamic_document.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "file_bom.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "json_file.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "json_options.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "toml_file.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "toml_options.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "yaml_file.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "yaml_options.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "sources.py",
    _REPO_ROOT / "src" / "advexp" / "settings_base" / "source_link.py",
}
# the link parameters "file" and "path" (and the mapping dictionary's
# "mapping") stay out on purpose: they are words of the plain language a
# message speaks, and the substring guard would flag every "the JSON
# file ..." phrase; the builders and the serializers share them through
# their constants alone
_GUARDED_VALUES = frozenset(
    {
        ENVIRONMENT_METADATA_OPTIONS,
        NAME_PREFIX,
        NAME_CASE,
        NESTED_DELIMITER,
        DOTENV_FILE_METADATA,
        JSON_FILE_METADATA,
        JSON_DYNAMIC_FILE_METADATA,
        JSON_DYNAMIC_GROUP_METADATA,
        UTF8_BOM,
        JSON_METADATA_OPTIONS,
        TOML_FILE_METADATA,
        TOML_DYNAMIC_FILE_METADATA,
        TOML_DYNAMIC_GROUP_METADATA,
        TOML_METADATA_OPTIONS,
        YAML_FILE_METADATA,
        YAML_DYNAMIC_FILE_METADATA,
        YAML_DYNAMIC_GROUP_METADATA,
        YAML_METADATA_OPTIONS,
        NAME_PATTERN,
        SOURCE_CHAIN_METADATA,
        JSON_SOURCE_METADATA,
        TOML_SOURCE_METADATA,
        YAML_SOURCE_METADATA,
        ENVIRONMENT_SOURCE_METADATA,
        DOTENV_SOURCE_METADATA,
    }
)


def _docstrings(tree: ast.AST) -> Set[int]:
    """Ids of the docstring constant nodes of a module."""
    ids: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def _literals(tree: ast.AST) -> Iterator[ast.Constant]:
    docs = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node


def test_constant_values_are_never_spelled_as_literals():
    offenders = []
    for directory in _SCANNED_DIRS:
        for path in sorted((_REPO_ROOT / directory).rglob("*.py")):
            if path in _DEFINING_MODULES:
                continue  # the constants' homes: spelling the values is their job
            for node in _literals(ast.parse(path.read_text(encoding="utf-8"))):
                if any(value in node.value for value in _GUARDED_VALUES):
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")
    assert not offenders, (
        "values that have constants are spelled as string literals; "
        "build from the constants instead: " + ", ".join(offenders)
    )
