"""The layout of ``options=`` class declarations.

A ``class`` statement that declares ``options=`` always carries it on a line
of its own: the header opens, every base is on its own line, the keyword is
on its own line, and the header closes.

The formatter has no option for a split that is driven by a keyword. It
decides by line width alone, so the layout is pinned in the opposite way:
the declaration carries a trailing comma (the magic trailing comma keeps the
formatter from folding the header back into one line). This test watches
that no declaration returns to a one-line header. In a one-line header, a
reader loses the bases at a glance, and a diff touches the whole header at
once.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, List, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent

_SKIP_PARTS = {".git", ".venv", ".pytest_cache", "node_modules"}


def _python_sources() -> Iterator[Tuple[str, str]]:
    """Return all the Python code that the repository shows to a reader: the
    sources of the packages, the samples, the tests, and the fenced code
    blocks of every markdown file.
    """
    for path in sorted(_REPO_ROOT.rglob("*.py")):
        if _SKIP_PARTS & set(path.parts):
            continue
        yield str(path.relative_to(_REPO_ROOT)), path.read_text(encoding="utf-8")
    for path in sorted(_REPO_ROOT.rglob("*.md")):
        if _SKIP_PARTS & set(path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        offset = 0
        while True:
            start = text.find("```python\n", offset)
            if start < 0:
                break
            end = text.find("```", start + len("```python\n"))
            block = text[start + len("```python\n") : end]
            line = text[:start].count("\n") + 2
            yield f"{path.relative_to(_REPO_ROOT)} (block at line {line})", block
            offset = end


def _options_on_the_class_line(tree: ast.AST) -> List[ast.ClassDef]:
    """Classes whose ``options=`` declaration stays on the ``class`` line."""
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        keywords = [kw for kw in node.keywords if kw.arg == "options"]
        if not keywords:
            continue
        arguments = [*node.bases, *[kw.value for kw in node.keywords]]
        if any(arg.lineno <= node.lineno for arg in arguments):
            offenders.append(node)
    return offenders


def test_options_declarations_carry_their_own_lines():
    offenders = []
    for name, source in _python_sources():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue  # a documentation fragment, not a whole program
        for node in _options_on_the_class_line(tree):
            offenders.append(f"{name}:{node.lineno}: {node.name}")
    assert not offenders, (
        "a class declaring options= must open its header: every base and the "
        "options= keyword on a line of its own, closed with a trailing comma "
        "(the comma is what keeps the formatter from folding the header back); "
        "regressed declarations: " + ", ".join(offenders)
    )
