# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Startup validation and conversion of declared defaults.

Creating a settings class validates every declared ``default=`` against the
annotation of the member. The validation has two tiers, over one division of
annotations: those that the conversion covers, and everything else.

The conversion tier runs the default through
:func:`~advexp.settings_base.conversion.correct_type`, which is the same
conversion that a load applies to what it reads. A default that does not
convert makes the class fail. A default that converts is served in its
converted form: the descriptor keeps the converted form and hands out deep
copies of it, so ``default="8080"`` on an ``int`` member reads as ``8080``
before any storage access. For well-typed defaults, the conversion is the
identity.

Annotations outside the conversion contract (custom classes, ``Any``,
unresolvable strings) convert nothing. For them, the second tier checks the
default with ``isinstance`` against the annotated class instead. The check
reaches inside containers: the element positions of a declared
``List``/``Set``/``Tuple`` and the key and value positions of a ``Dict`` are
walked in lockstep with the converted default and are checked in the same
way. ``Union`` positions and dataclass fields are not checked: a union with
an arm that is a custom class accepts anything, which matches what loading
does.

On top of both tiers, the declared value constraints (``gt``, ``regex``,
``validator``, and the rest of the constraint parameters of the attribute)
are applied to the converted default in the same way as at every other
boundary. The constraints with member references (a comparison bound that
names a sibling, as in ``ge=min_port``, or a ``when=`` condition) are also
checked, against the state in which every member has its default. The member
references were validated first (``cross_validation.validate_member_references``),
and the state with all defaults is what the lenient load policy falls back
to.

A member without a declared default serves ``None`` until a value arrives,
so the same questions are asked about that placeholder: the own constraints
of the member must accept the ``None`` that a ``NO_DEFAULT`` member serves.
Constraints that reject it (``eq=``, or a ``validator`` that returns false)
leave a member with no valid state until a value is assigned. The ``class``
statement reports this here, where the declaration is fixed. The spelling of
the family for such a member is ``REQUIRED``.

All findings are reported through one :class:`TypeError` that is raised at
the ``class`` statement and lists every offending member at once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from advexp.settings_base.constraints import collect_problems
from advexp.settings_base.conversion import (
    container_spec,
    correct_type,
    is_pass_through,
    unwrap_annotation,
)
from advexp.settings_base.cross_validation import (
    collect_member_rule_problems,
    collect_rule_problems,
    effective_values,
)
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.type_display import type_display

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.settings_meta import SettingsMeta


def validate_declared_defaults(
    settings_class: "SettingsMeta", members: "Dict[str, SettingMember]"
) -> None:
    """Validate the declared defaults of a class that is being created, and
    convert the rest.

    The settings metaclass calls this function right after the members are
    collected (and their references are validated). If a default violates its
    rules, the function raises :class:`TypeError` that names the class and
    every offending member. Otherwise, every member with a declared default
    leaves with its descriptor prepared to serve the converted form.

    A member without a declared default is asked the one question that its
    placeholder raises: the ``None`` that it serves until a value arrives must
    pass the own constraints of the member.
    """
    problems: List[str] = []
    for member in members.values():
        attribute = member.attribute
        # REQUIRED is not a value to convert: it carries requiredness, and
        # serving it raises instead
        if attribute.default is NO_DEFAULT or attribute.default is REQUIRED:
            continue
        if member.descriptor.default_prepared:
            # an inherited member: the declaring class has already converted
            # the default on the descriptor both classes share
            continue
        try:
            converted = correct_type(attribute.default, member.annotation)
        except (TypeError, ValueError) as exc:
            problems.append(f"{member.name}: {exc}")
            continue
        member.descriptor.prepare_default(converted)
        _collect_instance_problems(converted, member.annotation, member.name, "default", problems)
    # the constraints are checked against the whole all-default state, so a
    # when= condition resolves against the sibling's default and a member
    # reference against the sibling's converted default
    defaults = effective_values(settings_class)
    for name, default in defaults.items():
        attribute = members[name].attribute
        field_problems = collect_problems(attribute, default, defaults)
        problems.extend(f"{name}: {problem}" for problem in field_problems)
    # a NO_DEFAULT member serves None until a value arrives, so the stand-in
    # faces the member's own constraints here as well; the mapping above
    # holds no entry for it, and the load fallback cannot cure a stand-in
    # the constraints reject (resetting to the default changes nothing)
    for name, member in members.items():
        if member.attribute.default is not NO_DEFAULT:
            continue
        stand_in_problems = collect_problems(member.attribute, None, defaults)
        stand_in_problems.extend(collect_member_rule_problems(member.attribute, None, defaults))
        problems.extend(f"{name}: {problem}" for problem in stand_in_problems)
    for name, rule_problems in collect_rule_problems(settings_class, defaults).items():
        problems.extend(f"{name}: {problem}" for problem in rule_problems)
    if problems:
        listing = "\n".join(f"  - {problem}" for problem in problems)
        raise TypeError(f"invalid defaults in {settings_class.__name__}:\n{listing}")


def _collect_instance_problems(
    value: Any, annotation: Any, path: str, role: str, problems: List[str]
) -> None:
    """Collect the ``isinstance`` violations of one value against an annotation.

    The container positions of the annotation are walked in lockstep with the
    value (the already converted default), down to the positions whose
    annotations the conversion passes through, that is, custom classes. There
    the value must be an instance of the annotated class, or ``None``.

    Positions that are inside the conversion contract are not asked again: the
    conversion tier has already converted (and thereby validated) them, and an
    ``isinstance`` question there would undo its deliberate strictness, which
    treats a bool as not an int. Annotations that are not plain classes
    (``Any``, ``NewType``, subscripted generics) are not asked at all, and
    neither are classes that refuse the ``isinstance`` question (protocols
    without ``@runtime_checkable``).
    """
    annotation = unwrap_annotation(annotation)
    if annotation is None or value is None:
        return
    spec = container_spec(annotation)
    if spec is not None:
        kind, args = spec
        if kind == "mapping":
            if len(args) == 2 and isinstance(value, dict):
                key_type, item_type = args
                for key, item in value.items():
                    _collect_instance_problems(
                        key, key_type, f"{path}[key {key!r}]", "value", problems
                    )
                    _collect_instance_problems(
                        item, item_type, f"{path}[{key!r}]", "value", problems
                    )
        elif kind == "tuple":
            if isinstance(value, (list, tuple)):
                for index, (item, item_type) in enumerate(zip(value, args)):
                    _collect_instance_problems(
                        item, item_type, f"{path}[{index}]", "value", problems
                    )
        elif args and isinstance(value, (list, tuple, set, frozenset)):
            item_type = args[0]
            for index, item in enumerate(value):
                _collect_instance_problems(item, item_type, f"{path}[{index}]", "value", problems)
        return
    if not is_pass_through(annotation):
        return
    if not isinstance(annotation, type):
        return
    try:
        matches = isinstance(value, annotation)
    except TypeError:
        return
    if not matches:
        problems.append(
            f"{path}: {role} {value!r} is not an instance of "
            f"the annotated type {type_display(annotation)}"
        )
