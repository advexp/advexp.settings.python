"""One public class per module: every public class under ``src/`` lives in its
own file.

The rule keeps files easy to find by the name of the class: a public class
has its own module, which is named after it in snake_case (see AGENTS.md,
"Стиль").

Private classes (with a leading underscore) do not move out: a helper stays
next to the code that it serves, as the JSON serializers keep their
``_SharedDocument`` next to themselves. Tests and samples are also exempt:
fixtures and demos gather several classes into one file on purpose.
"""

import ast
import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"


def _source_files():
    yield from sorted(_SRC.rglob("*.py"))


@pytest.mark.parametrize(
    "path", list(_source_files()), ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_one_public_class_per_module(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    public = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    ]
    assert len(public) <= 1, (
        f"{path.relative_to(_REPO_ROOT)} defines {len(public)} public classes "
        f"({', '.join(public)}); one public class per file — move the extra "
        "class into its own module named after it (snake_case), per AGENTS.md"
    )
