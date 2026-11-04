"""Interface methods live under the section marker of their interface.

This is the style contract of AGENTS.md ("Стиль"). A method that implements
an interface sits in the class body under the section comment
``# -- <Interface> ---``, in the order in which the interface declares its
methods. A method of one interface never hides under the section of another
interface.

The test walks every class of the source tree and of the samples that has
section markers, and it checks the arrangement. The order of the methods
comes from the interface classes themselves, so a new interface method joins
the guard as soon as it is declared.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from advexp.settings_base.dynamic_settings_info_interface import IDynamicSettingsInfo
from advexp.settings_base.serializer_notification_sink_interface import ISerializerNotificationSink
from advexp.settings_base.setting_name_describer_interface import ISettingNameDescriber
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.settings_serializer_wishes_interface import ISettingsSerializerWishes
from advexp.settings_base.source_describer_interface import ISourceDescriber
from advexp.settings_base.source_link_sink_interface import ISourceLinkSink

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCANNED_ROOTS = (_REPO_ROOT / "src", _REPO_ROOT / "samples")

# the serializer-side interfaces the section convention covers, in the
# order their sections appear in a class body
_INTERFACES = (
    ISettingsSerializer,
    ISettingNameDescriber,
    ISourceDescriber,
    ISettingsSerializerWishes,
    ISerializerNotificationSink,
    ISourceLinkSink,
    IDynamicSettingsInfo,
)


def _declared_methods(interface: type) -> list[str]:
    """The interface's own methods, in declaration order."""
    return [
        name
        for name, value in vars(interface).items()
        if callable(value) or isinstance(value, (property, staticmethod, classmethod))
    ]


_METHOD_OWNER = {
    name: interface.__name__ for interface in _INTERFACES for name in _declared_methods(interface)
}
_METHOD_ORDER = {
    interface.__name__: {
        name: position for position, name in enumerate(_declared_methods(interface))
    }
    for interface in _INTERFACES
}

_CLASS_RE = re.compile(r"^class (\w+)")
_SECTION_RE = re.compile(r"^    # -- (\w+)")
_METHOD_RE = re.compile(r"^    def (\w+)\(")


def _scan(root: Path) -> list[tuple[str, str, str, Path, int]]:
    """Return every class-level method of every module as a tuple: (class,
    section, method, file, line). The section is the last marker above the
    method. ``None`` is spelled as an empty string, for tidy reporting.
    """
    entries = []
    for path in sorted(root.rglob("*.py")):
        klass = None
        section = ""
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            matched = _CLASS_RE.match(line)
            if matched:
                klass = matched.group(1)
                section = ""
                continue
            matched = _SECTION_RE.match(line)
            if matched:
                section = matched.group(1)
                continue
            matched = _METHOD_RE.match(line)
            if matched and klass is not None:
                entries.append((klass, section, matched.group(1), path, number))
    return entries


@pytest.mark.parametrize(
    "root",
    _SCANNED_ROOTS,
    ids=["src", "samples"],
)
def test_interface_methods_sit_under_their_own_section_in_order(root: Path) -> None:
    problems = []
    for klass, section, method, path, number in _scan(root):
        owner = _METHOD_OWNER.get(method)
        if owner is None:
            continue  # the class's own helper or a plugin-side method
        if not section:
            continue  # classes without markers are held by their own test
        if section != owner:
            problems.append(
                f"{path.relative_to(_REPO_ROOT)}:{number}: {klass}.{method} of {owner} "
                f"sits under the {section or 'no'} section"
            )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    "root",
    _SCANNED_ROOTS,
    ids=["src", "samples"],
)
def test_marked_classes_keep_no_interface_method_outside_sections(root: Path) -> None:
    # a class that carries the section convention at all must give every
    # interface method its marker: a bare method between sections is the
    # arrangement this guard exists for. The same class name may live in
    # several modules (the two packages mirror their serializers), so the
    # mark is tracked per module
    problems = []
    marked: set[tuple[Path, str]] = set()
    for klass, section, _method, path, _number in _scan(root):
        if section:
            marked.add((path, klass))
    for klass, section, method, path, number in _scan(root):
        if method in _METHOD_OWNER and (path, klass) in marked and not section:
            problems.append(
                f"{path.relative_to(_REPO_ROOT)}:{number}: {klass}.{method} of "
                f"{_METHOD_OWNER[method]} sits outside any interface section"
            )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    "root",
    _SCANNED_ROOTS,
    ids=["src", "samples"],
)
def test_interface_methods_follow_the_declaration_order(root: Path) -> None:
    order: dict[tuple[Path, str], dict[str, int]] = {}
    problems = []
    for klass, section, method, path, number in _scan(root):
        owner = _METHOD_OWNER.get(method)
        if owner is None or section != owner:
            continue
        position = _METHOD_ORDER[owner][method]
        previous = order.get((path, klass), {}).get(owner)
        if previous is not None and previous >= position:
            problems.append(
                f"{path.relative_to(_REPO_ROOT)}:{number}: {klass}.{method} of {owner} "
                f"stands before an earlier-declared method of the same interface"
            )
        order.setdefault((path, klass), {})[owner] = position
    assert not problems, "\n".join(problems)
