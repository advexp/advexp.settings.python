# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Validation across members: declared member references and the class hook.

There are two ways to declare a rule that binds several members, and one
mechanism checks them. A comparison bound may reference a sibling member
(``max_port = setting(ge=min_port)``), and the ``when=`` parameter makes the
constraints of a member conditional on the truthiness of a sibling.
Everything that a comparison cannot express (conditional requirements, "at
least one of", invariants) goes into the class hook ``__validate__``. The
hook reads the whole settings object and returns a dict that maps a member
name to a problem.

The checks run at the points where all values are known at once:

- Class creation (against the declared defaults, together with the field
  checks of the defaults).
- A load. A violation becomes an entry in the channel of the violating
  member: it is fatal for a required member, and for an optional member it
  causes a fallback to the declared defaults with a logged warning. The
  pass aborts if no reset to the defaults settles the violation.
- ``update_from_dict``, ``update_from_object``, and a save. These checks are
  strict: the collected report raises :class:`SettingValidationError`, and
  the operation applies nothing.
- The manual ``validate_settings()``.

A single assignment never runs the cross-member checks, because a rule may
be violated between two related assignments. It checks only the own
constraints of the member, with the ``when=`` condition resolved against the
current values.

The exceptions of the user code behind the checks follow one contract: an
exception that a ``validator`` callable or the body of the hook raises
propagates as it is, because it is a bug in that code, not a property of the
values. The one data condition that can surface from the hook is a read of a
required member that holds no value. At every checkpoint, this read becomes
a finding for that member instead of a crash.
"""

from __future__ import annotations

import collections.abc
import copy
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, cast

from advexp.settings_base.constraints import (
    collect_member_rule_problems,
    collect_problems,
)
from advexp.settings_base.instance_values import INSTANCE_VALUES_ATTR, instance_values
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.setting_member import SettingMember
    from advexp.settings_base.settings_meta import SettingsMeta

VALIDATE_HOOK_NAME = "__validate__"
"""The class hook of cross-member validation.

``def __validate__(self) -> dict`` in the body of a settings class: the
hook runs wherever the cross-member checks run, always on a fully built
settings object (never a half-loaded one), and returns a dict of member
name to problem description — an empty dict means the class is fine. The
hook reads and reports; fixing values is the load pass's job. An
exception its body raises propagates as is, and reading a member that
holds no value is that member's finding, not a crash.
"""


def validate_member_references(
    settings_class: "SettingsMeta", members: "Dict[str, SettingMember]"
) -> None:
    """Validate the declared member references of a class that is being created.

    The settings metaclass calls this function before the defaults are
    validated. A reference must name a member of the same class. The ``class``
    statement fails with a :class:`TypeError` if the attribute belongs to a
    member that no settings class declares, or to a member that this class does
    not declare. It fails in the same way for a cycle of references (``a``
    references ``b``, which references ``a``), which the error names in full.
    """
    graph: Dict[str, List[str]] = {}
    for name, member in members.items():
        referenced: List[str] = []
        for rule in getattr(member.attribute, "constraint_member_rules", ()):
            referenced.append(
                _require_member(settings_class, members, name, rule.parameter, rule.reference)
            )
        condition = getattr(member.attribute, "constraint_condition", None)
        if condition is not None:
            referenced.append(_require_member(settings_class, members, name, "when", condition))
        graph[name] = referenced
    cycle = _find_cycle(graph)
    if cycle is not None:
        raise TypeError(
            f"circular member references in {settings_class.__name__}: {' -> '.join(cycle)}"
        )


def effective_values(settings_class: "SettingsMeta", obj: Any = None) -> Dict[str, Any]:
    """Return the effective value of every member that holds one, keyed by member
    name.

    A member with a stored value reads it, and the other members resolve their
    declared default. A member that holds no value at all (nothing stored and no
    default declared, that is, ``NO_DEFAULT``, or a ``REQUIRED`` member that
    nothing has loaded yet) is left out of the mapping. There is nothing to
    check against, so the field checks skip the member, and a member rule that
    references it does not apply.

    A snapshot instance that is passed as ``obj`` reads its own values instead
    of the class storage, and it falls back in the same way for the members that
    it does not carry. The values are references to the stored objects, not
    copies, because the checks only read them.
    """
    members: Dict[str, SettingMember] = settings_class.__settings_members__
    stored: Dict[str, Any] = settings_class.__settings_values__
    own = instance_values(obj) if obj is not None else None
    values: Dict[str, Any] = {}
    for name, member in members.items():
        if own is not None and name in own:
            values[name] = own[name]
            continue
        if name in stored:
            values[name] = stored[name]
            continue
        if member.attribute.default is NO_DEFAULT or member.attribute.default is REQUIRED:
            continue
        values[name] = member.descriptor.resolved_default()
    return values


def collect_rule_problems(
    settings_class: "SettingsMeta", values: Mapping[str, Any]
) -> Dict[str, List[str]]:
    """Return the problems of the declared member-reference rules against the
    values.

    This is the declarative half alone, without the field checks and without the
    hook. It is the form that the class-creation check of the defaults needs.
    The keys of the result are member names, and the values are descriptions of
    the problems.
    """
    report: Dict[str, List[str]] = {}
    for name, member in settings_class.__settings_members__.items():
        if name not in values:
            continue
        problems = collect_member_rule_problems(member.attribute, values[name], values)
        if problems:
            report[name] = problems
    return report


def collect_settings_problems(
    settings_class: "SettingsMeta", values: Mapping[str, Any]
) -> Dict[str, List[str]]:
    """Return the full report of every declared constraint against the values.

    In one pass, this function collects the field constraints (with the
    ``when=`` condition of each member resolved against the same values), the
    member-reference rules, and the :data:`VALIDATE_HOOK_NAME` hook. The result
    contains every problem of every member, keyed by member name. An empty dict
    means that the values pass everything.

    The hook runs on a detached snapshot that carries the given values. The
    values are deep-copied, so a hook that mutates its object cannot affect the
    class. The hook therefore sees exactly the state that the declarative checks
    saw.
    """
    report: Dict[str, List[str]] = {}
    for name, member in settings_class.__settings_members__.items():
        if name not in values:
            continue
        problems = collect_problems(member.attribute, values[name], values)
        problems.extend(collect_member_rule_problems(member.attribute, values[name], values))
        if problems:
            report[name] = problems
    for name, problem in _hook_problems(settings_class, values).items():
        report.setdefault(name, []).append(problem)
    return report


def rule_participants(settings_class: "SettingsMeta", report: Mapping[str, List[str]]) -> List[str]:
    """Return the members that take part in the violated rules, in declaration
    order.

    For every member that the report names, the result contains the member
    itself and every member that its declaration references (the comparison
    bounds and the ``when=`` condition). These are the members that a load pass
    resets to their defaults when a rule is violated. The findings of a hook
    take part only through the members that they name: a hook states a problem,
    and it declares no references.
    """
    members: Dict[str, SettingMember] = settings_class.__settings_members__
    involved = set(report)
    for name in report:
        if name not in members:
            # a hook named something that is not a member: nothing to reset
            continue
        attribute = members[name].attribute
        for rule in getattr(attribute, "constraint_member_rules", ()):
            referenced = rule.reference.bound_name
            if referenced is not None:
                involved.add(referenced)
        condition = getattr(attribute, "constraint_condition", None)
        if condition is not None and condition.bound_name is not None:
            involved.add(condition.bound_name)
    return [name for name in members if name in involved]


def format_problems(settings_class: "SettingsMeta", report: Mapping[str, List[str]]) -> str:
    """Format the report as the message of a :class:`SettingValidationError`.

    The message has one line per problem, in the same style as the report of the
    declared defaults that the ``class`` statement raises.
    """
    listing = "\n".join(
        f"  - {name}: {problem}" for name, problems in report.items() for problem in problems
    )
    return f"invalid settings in {settings_class.__name__}:\n{listing}"


def _hook_problems(settings_class: "SettingsMeta", values: Mapping[str, Any]) -> Dict[str, str]:
    """Return the findings of the validation hook, or an empty dict if there is no
    hook.

    An exception that the body of the hook raises propagates as it is. It is a
    bug in the code of the hook, not a property of the values, and a custom
    ``validator`` follows the same contract.

    One condition is a property of the values instead. Reading a required member
    that holds no value raises the reading error of the member, and this read
    becomes a finding for that member rather than a crash: the hook ran on a
    fully built object, and the member simply has nothing loaded.
    """
    hook = getattr(settings_class, VALIDATE_HOOK_NAME, None)
    if hook is None:
        return {}
    # a detached instance carrying the checked values: the hook reads a
    # fully built settings object through the ordinary descriptors
    # (object.__new__ is the detached-instance construction, the way
    # ``Settings.to_object`` builds its snapshots)
    subject: "SettingsMeta" = object.__new__(cast("type", settings_class))
    object.__setattr__(subject, INSTANCE_VALUES_ATTR, copy.deepcopy(dict(values)))
    try:
        findings = hook(subject)
    except MemberLoadError as exc:
        if exc.member_name is None:
            # an error the hook's own code raised, not a member read
            raise
        return {
            exc.member_name: f"no loaded value to read; the {VALIDATE_HOOK_NAME} hook "
            f"read the member"
        }
    if not isinstance(findings, collections.abc.Mapping):
        raise TypeError(
            f"{settings_class.__name__}.{VALIDATE_HOOK_NAME}() must return a dict "
            f"mapping member names to problems, got {type(findings).__name__}"
        )
    return {name: str(problem) for name, problem in findings.items()}


def _require_member(
    settings_class: "SettingsMeta",
    members: "Dict[str, SettingMember]",
    member_name: str,
    parameter: str,
    reference: Any,
) -> str:
    """The referenced member's name, after checking the reference names a member."""
    referenced = reference.bound_name
    if referenced is None:
        raise TypeError(
            f"{settings_class.__name__}: the {parameter}= of '{member_name}' references "
            f"an attribute that is not declared as a member by any settings class. "
            f"Assign the attribute to a member of this class first"
        )
    if referenced not in members:
        raise TypeError(
            f"{settings_class.__name__}: the {parameter}= of '{member_name}' references "
            f"'{referenced}', which this class does not declare. Reference a member "
            f"declared earlier in the same class body"
        )
    return referenced


def _find_cycle(graph: Mapping[str, List[str]]) -> Optional[List[str]]:
    """A cycle of member references as a closed chain of names, if there is one."""
    visiting, done = 1, 2
    state: Dict[str, int] = {}
    stack: List[str] = []

    def visit(node: str) -> Optional[List[str]]:
        state[node] = visiting
        stack.append(node)
        for referenced in graph.get(node, ()):
            if referenced not in graph:
                continue
            if state.get(referenced) == visiting:
                start = stack.index(referenced)
                return stack[start:] + [referenced]
            if referenced not in state:
                found = visit(referenced)
                if found is not None:
                    return found
        state[node] = done
        stack.pop()
        return None

    for start in graph:
        if start not in state:
            cycle = visit(start)
            if cycle is not None:
                return cycle
    return None
