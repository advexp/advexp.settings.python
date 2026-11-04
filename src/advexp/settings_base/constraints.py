# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Declared value constraints of a setting member: the checking machinery.

A constraint is declared as a keyword parameter of the setting attribute
(``setting(gt=0, le=65535)``). :func:`build_checks` turns the declared
parameters into a tuple of check callables, which the attribute stores, and
the rest of this module applies them to values.

The value-only checks see the value of one member in isolation. A comparison
bound may instead reference a sibling member of the same class (``ge=min_port``,
where ``min_port`` is the attribute object that was assigned to an earlier
member). Such bounds are compiled into member rules
(:func:`build_member_rules`), which
:func:`collect_member_rule_problems` checks against the current values of the
whole class. The ``when=`` parameter gates everything declared on the member:
while the referenced member is falsy, none of the constraints of the member
apply.

``None`` passes the ordering, length, and regex checks silently, because it
is the value of an unset ``Optional`` member, but it takes part in the
``eq``/``ne`` comparisons. Values that cannot be compared (``gt=`` on a
non-number) and values without a length are reported as violations instead
of crashing: the message says what could not be done. A failing custom
``validator`` is a violation. An exception that it raises propagates as it
is, because that is a bug in the validator, not a property of the value.

A secret wrapper is opened for the check: the constraint applies to the
wrapped string or bytes, and the validator receives them too. The messages
keep the mask.
"""

from __future__ import annotations

import operator
import re
from typing import Any, Callable, List, Mapping, NamedTuple, Optional, Tuple

from advexp.settings_base.secret_bytes import SecretBytes
from advexp.settings_base.secret_str import SecretStr
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.setting_validation_error import SettingValidationError

Check = Callable[[Any], Optional[str]]
"""One declared constraint as a callable over the value.

Returns ``None`` when the value passes and a human-readable problem
description when it does not.
"""

_COMPARISONS = (
    ("gt", "be greater than", operator.gt),
    ("ge", "be greater than or equal to", operator.ge),
    ("lt", "be less than", operator.lt),
    ("le", "be less than or equal to", operator.le),
    ("eq", "be equal to", operator.eq),
    ("ne", "not be equal to", operator.ne),
)
"""The six comparison parameters: their names, message phrases and ops."""


class _MemberRule(NamedTuple):
    """One comparison bound declared as a reference to a sibling member."""

    parameter: str
    phrase: str
    op: Callable[[Any, Any], bool]
    reference: ISettingAttribute


def build_checks(
    *,
    gt: Any = None,
    ge: Any = None,
    lt: Any = None,
    le: Any = None,
    eq: Any = None,
    ne: Any = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    regex: Optional[str] = None,
    validator: Optional[Callable[[Any], bool]] = None,
) -> Tuple[Check, ...]:
    """Compile the literal constraint parameters into check callables.

    The attribute constructor calls this function. Every parameter is the value
    that the declarer gave, or ``None``.

    Comparison bounds that are declared as member references (the attribute
    object of a sibling member) are not compiled here: they go to
    :func:`build_member_rules`. A bound that is taken through a settings class
    (``OtherSettings.member``, which is a value descriptor) fails at the
    declaration site right away, because references across classes are not
    supported.

    The declaration itself is also validated here, and a failure is raised at
    the declaration site:

    - A ``regex=`` that does not compile raises :class:`ValueError`.
    - A non-callable ``validator=`` raises :class:`TypeError`.
    - A mix of value-ordering parameters (``gt/ge/lt/le``) with string or length
      parameters (``min_length/max_length/regex``) raises :class:`TypeError`.

    An attribute that is declared without constraints gets an empty tuple.
    """
    if validator is not None and not callable(validator):
        raise TypeError(f"validator must be callable, got {type(validator).__name__}")
    literals, _ = _split_comparisons(gt=gt, ge=ge, lt=lt, le=le, eq=eq, ne=ne)
    ordered = [
        name
        for name, bound in (("gt", gt), ("ge", ge), ("lt", lt), ("le", le))
        if bound is not None
    ]
    shaped = [
        name
        for name, bound in (
            ("min_length", min_length),
            ("max_length", max_length),
            ("regex", regex),
        )
        if bound is not None
    ]
    if ordered and shaped:
        raise TypeError(
            f"conflicting constraints: {', '.join(ordered)} compare the value, "
            f"while {', '.join(shaped)} apply to strings and lengths"
        )

    checks: List[Check] = [
        _comparison(name, phrase, op, bound) for name, phrase, op, bound in literals
    ]
    checks.extend(
        _length_check(name, phrase, op, bound)
        for name, phrase, op, bound in (
            ("min_length", "be at least", operator.ge, min_length),
            ("max_length", "be at most", operator.le, max_length),
        )
        if bound is not None
    )
    if regex is not None:
        checks.append(_regex_check(regex, _compile_regex(regex)))
    if validator is not None:
        checks.append(_validator_check(validator))
    return tuple(checks)


def build_member_rules(
    *,
    gt: Any = None,
    ge: Any = None,
    lt: Any = None,
    le: Any = None,
    eq: Any = None,
    ne: Any = None,
) -> Tuple[_MemberRule, ...]:
    """Compile the comparison bounds that are declared as member references.

    This is the counterpart of :func:`build_checks` for the other kind of
    comparison bound: an attribute object that was assigned to an earlier member
    of the same class body (``ge=min_port``). The reference is stored as it is.
    It is resolved to the current value of the member at check time by
    :func:`collect_member_rule_problems`, and it is validated for membership and
    cycles at class creation (``cross_validation``).
    """
    _, references = _split_comparisons(gt=gt, ge=ge, lt=lt, le=le, eq=eq, ne=ne)
    return tuple(_MemberRule(name, phrase, op, bound) for name, phrase, op, bound in references)


def build_condition(when: Any) -> Optional[ISettingAttribute]:
    """Validate the ``when=`` declaration and return it unchanged.

    The condition accepts only one spelling: a reference to a member of the
    same class, whose truthiness gates the constraints of the member. A literal
    (a plain value of any type) fails at the declaration site. This way, an
    attempt to use a constant condition is not silently stored as a bound that
    nobody reads.
    """
    if when is None or isinstance(when, ISettingAttribute):
        return when
    raise TypeError(
        f"when must reference a member of the same class, got {when!r}; "
        f"use the __validate__ hook for compound conditions"
    )


def _split_comparisons(
    *, gt: Any, ge: Any, lt: Any, le: Any, eq: Any, ne: Any
) -> Tuple[
    List[Tuple[str, str, Callable[[Any, Any], bool], Any]],
    List[Tuple[str, str, Callable[[Any, Any], bool], Any]],
]:
    """Split the declared comparison bounds into literals and member references."""
    literals = []
    references = []
    for name, phrase, op in _COMPARISONS:
        bound = {"gt": gt, "ge": ge, "lt": lt, "le": le, "eq": eq, "ne": ne}[name]
        if bound is None:
            continue
        if isinstance(bound, ISettingAttribute):
            references.append((name, phrase, op, bound))
        elif _descriptor_bound(bound):
            raise TypeError(
                f"the {name}= bound {bound!r} is a member of another "
                f"class. A member reference must be the attribute object "
                f"of a member declared in the same class body"
            )
        else:
            literals.append((name, phrase, op, bound))
    return literals, references


def _descriptor_bound(bound: Any) -> bool:
    """Return whether the bound is the value descriptor of a settings class in
    disguise.

    ``OtherSettings.member`` reads as the descriptor of the class, which carries
    the attribute under ``.attribute``. The descriptor is recognized by its
    structure, without importing the descriptor class (the descriptor module
    imports this module).
    """
    return isinstance(getattr(bound, "attribute", None), ISettingAttribute) and not isinstance(
        bound, ISettingAttribute
    )


def collect_problems(
    attribute: ISettingAttribute, value: Any, siblings: Optional[Mapping[str, Any]] = None
) -> List[str]:
    """Return the descriptions of the problems of the value against the
    constraints of the attribute.

    An empty list means that the value passes. Attributes that implement the
    contract without the base class carry no checks, so they also return an
    empty list.

    ``siblings`` holds the current values of the whole class, keyed by member
    name. It is used to resolve the ``when=`` condition of the member: while
    the referenced member is falsy, the constraints do not apply, and the empty
    list is returned. Without ``siblings``, the checks apply as declared (every
    call site of the library passes the sibling values).
    """
    checks: Tuple[Check, ...] = getattr(attribute, "constraint_checks", ())
    if not checks:
        return []
    if _condition_off(attribute, siblings):
        return []
    problems: List[str] = []
    for check in checks:
        problem = check(value)
        if problem is not None:
            problems.append(problem)
    return problems


def check_value(
    attribute: ISettingAttribute,
    value: Any,
    context: str,
    siblings: Optional[Mapping[str, Any]] = None,
) -> None:
    """Raise :class:`SettingValidationError` when the value violates the
    constraints.

    ``context`` names the value for the message, for example ``invalid value for
    setting 'port' of NetSettings``. The first violated constraint is appended
    to it. ``siblings`` resolves the ``when=`` condition in the same way as in
    :func:`collect_problems`.
    """
    problems = collect_problems(attribute, value, siblings)
    if problems:
        raise SettingValidationError(f"{context}: {problems[0]}")


def collect_member_rule_problems(
    attribute: ISettingAttribute, value: Any, siblings: Mapping[str, Any]
) -> List[str]:
    """Return the descriptions of the problems of the value against the bounds
    that reference other members.

    This is the cross-member half of the declared constraints: each rule
    compares the value with the current value of the referenced sibling, which
    is taken from ``siblings``, keyed by member name. A rule does not apply if
    the referenced member holds no value (for example, a required member that
    nothing has loaded yet). No rule applies while the own ``when=`` condition
    of the member is falsy. The messages name both members and keep secret
    values masked.
    """
    rules: Tuple[_MemberRule, ...] = getattr(attribute, "constraint_member_rules", ())
    if not rules:
        return []
    if _condition_off(attribute, siblings):
        return []
    problems: List[str] = []
    for rule in rules:
        name = rule.reference.bound_name
        if name is None or name not in siblings:
            continue
        bound, bound_shown = _opened(siblings[name])
        value, shown = _opened(value)
        skip_none = rule.parameter not in ("eq", "ne")
        if skip_none and value is None:
            continue
        try:
            passes = rule.op(value, bound)
        except TypeError:
            problems.append(
                f"value {shown} is not comparable with the {rule.parameter} bound, "
                f"the value of '{name}' ({bound_shown})"
            )
            continue
        if not passes:
            problems.append(
                f"value {shown} must {rule.phrase} the value of '{name}' ({bound_shown})"
            )
    return problems


def _condition_off(attribute: ISettingAttribute, siblings: Optional[Mapping[str, Any]]) -> bool:
    """Whether the attribute's ``when=`` condition is falsy in the values."""
    condition = getattr(attribute, "constraint_condition", None)
    if condition is None or siblings is None:
        return False
    return not siblings.get(condition.bound_name)


def _compile_regex(regex: str) -> "re.Pattern":
    """Compile a declared pattern; a bad one fails the declaration site."""
    try:
        return re.compile(regex)
    except re.error as exc:
        raise ValueError(f"Invalid regex {regex!r}: {exc}") from exc


def _opened(value: Any) -> Tuple[Any, str]:
    """The value that a check runs on, and the form that its message shows.

    A secret wrapper is opened for the check and stays masked in the message.
    """
    if isinstance(value, (SecretStr, SecretBytes)):
        return value.get_secret_value(), str(value)
    return value, repr(value)


def _comparison(name: str, phrase: str, op: Callable[[Any, Any], bool], bound: Any) -> Check:
    """A ``gt/ge/lt/le/eq/ne`` bound as a check. ``None`` passes automatically,
    except in the ``eq``/``ne`` checks, where it takes part in the comparison.
    """
    skip_none = name not in ("eq", "ne")

    def check(value: Any) -> Optional[str]:
        value, shown = _opened(value)
        if skip_none and value is None:
            return None
        try:
            passes = op(value, bound)
        except TypeError:
            return f"value {shown} is not comparable with the {name} bound {bound!r}"
        if passes:
            return None
        return f"value {shown} must {phrase} {bound!r}"

    return check


def _length_check(name: str, phrase: str, op: Callable[[Any, Any], bool], bound: int) -> Check:
    """A ``min_length/max_length`` bound as a check over ``len(value)``."""

    def check(value: Any) -> Optional[str]:
        value, shown = _opened(value)
        if value is None:
            return None
        try:
            length = len(value)
        except TypeError:
            return f"value {shown} has no length to check against {name}"
        if op(length, bound):
            return None
        return f"length {length} must {phrase} {bound!r}"

    return check


def _regex_check(source: str, compiled: "re.Pattern") -> Check:
    """A ``regex=`` pattern as a check; the search is unanchored."""

    def check(value: Any) -> Optional[str]:
        value, shown = _opened(value)
        if value is None:
            return None
        if not isinstance(value, str):
            return f"value {shown} is not a string to match regex {source!r}"
        if compiled.search(value) is None:
            return f"value {shown} does not match regex {source!r}"
        return None

    return check


def _validator_check(validator: Callable[[Any], bool]) -> Check:
    """A custom validator predicate as a check."""

    def check(value: Any) -> Optional[str]:
        value, shown = _opened(value)
        if validator(value):
            return None
        return f"value {shown} failed the validator {validator!r}"

    return check
