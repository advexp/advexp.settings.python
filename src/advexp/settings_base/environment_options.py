# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Shared naming options of the environment family of backends.

The process environment and a ``.env`` file form one namespace: ``APP_MODE``
in the environment and in the file is one variable that arrives from two
sources. The rules for building names therefore belong to the namespace, not
to any single backend. This module is the single vocabulary of the family:
the class metadata key, the option names, the validation, the options
helpers, and the name-building function that every backend of the family
calls.

It lives here, in the foundation of the family, because the namespace spans
several distributions. A settings backend and a read-only configuration
source that read the same variables must resolve ``APP_MODE`` in the same
way. Backends that build names in any other way would one day split one
variable into two settings, silently.

The options are stored **per declaring class**: the entry of each class is
stored under the family key joined with the module and the name of the
class. A subclass that declares its own options therefore coexists with the
base class instead of replacing it. The variable name of a member is built
with the entry of the class that declared the member: the nearest entry at
or above that class.
"""

from __future__ import annotations

import collections.abc
from typing import Any, Dict, Mapping, Optional

from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.name_case import NameCase

ENVIRONMENT_METADATA_OPTIONS = "__EnvironmentMetadataOptions"
"""The class metadata key of the family — one key for every backend reading
or writing environment-style names. The options are declared once per
settings class and a runtime change reaches the whole family at once."""

NAME_PREFIX = "name_prefix"
"""The prefix in front of every built name; ``None`` adds none."""

NAME_CASE = "name_case"
"""The case of the member-name part: ``None`` keeps the member name as
written, ``"upper"`` / ``"lower"`` recase it, and ``"any"`` keeps the
built name as written while the lookup of it accepts any spelling
(:class:`NameCase` is the enum spelling of the same choice)."""

NESTED_DELIMITER = "nested_delimiter"
"""The delimiter that opens a nested object's fields in a built name:
``None`` (the default) keeps every member a single flat variable, a
string spells ``APP_DB__PORT``-style addresses (the member's variable,
the delimiter, the cased field name). Applies to members annotated with
a dataclass — the family's nested objects — in every backend of the
family; the addressing rules live in
:mod:`advexp.settings_base.environment_nested` beside this vocabulary."""

_KNOWN_OPTIONS = frozenset({NAME_PREFIX, NAME_CASE, NESTED_DELIMITER})
# a tuple, not a set: the str-enum members compare equal to the plain
# spellings, but their hash is not guaranteed to match one across the
# supported Python versions
_CASE_VALUES = tuple(member.value for member in NameCase)


def check_environment_options(value: Any) -> Optional[str]:
    """Describe why ``value`` is not a valid options mapping; return ``None`` if it
    is valid.

    This is the single validator of the metadata entry of the family. It checks
    the shape of the mapping, the known option names (a mistyped option would
    otherwise sit silently and do nothing), and the forms of the values:

    - the prefix is ``None`` or a non-empty string;
    - the case is ``None`` or a
      :class:`~advexp.settings_base.name_case.NameCase` member;
    - the nested delimiter is ``None`` or a non-empty string.

    The plain string values of the members (the stored data form,
    ``"upper"``/``"lower"``/``"any"``) are accepted in the same way: the raw
    metadata channel works with data, and the helper works with the enum.
    """
    if not isinstance(value, collections.abc.Mapping):
        return f"must be a mapping of option name to value, got {type(value).__name__}"
    problems = []
    unknown = sorted(set(value) - _KNOWN_OPTIONS)
    if unknown:
        problems.append(f"unknown option name(s): {', '.join(repr(name) for name in unknown)}")
    prefix = value.get(NAME_PREFIX)
    if prefix is not None and (not isinstance(prefix, str) or not prefix):
        problems.append(f"{NAME_PREFIX} must be None or a non-empty string, got {prefix!r}")
    case = value.get(NAME_CASE)
    if isinstance(case, NameCase):
        case = case.value
    if case is not None and case not in _CASE_VALUES:
        problems.append(f"{NAME_CASE} must be None or a NameCase member, got {case!r}")
    delimiter = value.get(NESTED_DELIMITER)
    if delimiter is not None and (not isinstance(delimiter, str) or not delimiter):
        problems.append(f"{NESTED_DELIMITER} must be None or a non-empty string, got {delimiter!r}")
    return "; ".join(problems) or None


def _checked_options(
    name_prefix: Optional[str],
    name_case: Optional[NameCase],
    nested_delimiter: Optional[str],
) -> Dict[str, Any]:
    """Validate one (prefix, case, delimiter) triple; return the stored form."""
    if name_case is not None and not isinstance(name_case, NameCase):
        members = " / ".join(f"NameCase.{member.name}" for member in NameCase)
        raise TypeError(
            f"{NAME_CASE} must be None or a NameCase member ({members}), got {name_case!r}"
        )
    if nested_delimiter is not None and (
        not isinstance(nested_delimiter, str) or not nested_delimiter
    ):
        raise TypeError(
            f"{NESTED_DELIMITER} must be None or a non-empty string, got {nested_delimiter!r}"
        )
    options: Dict[str, Any] = {
        NAME_PREFIX: name_prefix,
        NAME_CASE: None if name_case is None else name_case.value,
        NESTED_DELIMITER: nested_delimiter,
    }
    problem = check_environment_options(options)
    if problem is not None:
        raise TypeError(f"invalid environment options: {problem}")
    return options


def environment_options(
    name_prefix: Optional[str] = None,
    name_case: Optional[NameCase] = None,
    nested_delimiter: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build the options of the family: the own entry of the declaring class.

    Pass them to the ``class`` statement:

    ```python
        class AppSettings(Settings, options=environment_options(
            name_prefix="APP_", name_case=NameCase.UPPER,
        )):

            # APP_SESSION_TTL
            session_ttl: timedelta = environment_variable_setting(default="0:30:00")
    ```

    The ``options=`` keyword of the ``class`` statement is the readable spelling
    of the ``class_metadata`` declaration of the class. The result of the helper
    is a ready mapping for it, and an assignment in the class body
    (``class_metadata = environment_options(...)``) does the same thing.

    A class may use both spellings at once. The keyword carries the entries of
    the families, the body carries the own keys of the application, and the two
    are merged. The key of a family is its own long distinctive name, so the two
    sides do not collide. A name that is declared on both sides makes the
    ``class`` statement fail, and the error names it. To combine families and
    free keys inside one spelling, use the sequence form of the keyword
    (``options=(environment_options(...), {"config-version": 2})``).

    The entry belongs to the class that declares it: the machinery stores it
    under the family key joined with the module and the name of the class. A
    subclass that declares its own ``environment_options(...)`` adds its own
    entry. The entry of the base class stays, and each entry governs the members
    that its class declared (the nearest entry at or above the declaring class).
    To retune the entry of an ancestor from a subclass, use
    :func:`environment_options_for`. The flat family key of the runtime channel
    addresses the own entry of the class in the same way
    (``set_class_metadata(ENVIRONMENT_METADATA_OPTIONS, ...)``).

    ``name_case`` takes the members of :class:`NameCase`. The stored entry keeps
    their plain string values, which is the data form that the raw channel
    accepts (a hand-written entry, or a runtime ``set_class_metadata`` call). The
    values are also checked here, so an invalid pair fails at the call of the
    helper, before the ``class`` statement.

    ``nested_delimiter`` (``None`` or a non-empty string) opens nested addressing
    for the dataclass members of the class. If it is set, one variable may
    address a single field of the object (``APP_DB__PORT`` with the delimiter
    ``"__"``), and a load merges such variables onto the declared default. The
    addressing rules are the shared vocabulary of the family in
    :mod:`advexp.settings_base.environment_nested`.
    """
    return {
        ENVIRONMENT_METADATA_OPTIONS: _checked_options(name_prefix, name_case, nested_delimiter)
    }


def apply_environment_case(member_name: str, options: Mapping[str, Any]) -> str:
    """Apply the case option of the family to the member-name part alone.

    Nested addressing composes its field addresses from this piece. The part of
    a field changes case in exactly the same way as the part of the member
    (``db`` and ``maxPort`` under ``upper`` become ``DB`` and ``MAXPORT``), and
    no other transformation happens.

    ``any`` builds a name in exactly the same way as ``None``: the member name
    as it is written. It changes the lookup
    (:func:`advexp.settings_base.environment_lookup.environment_key`), not the
    built name. The ``options`` mapping is the stored data form: the case
    arrives as its plain stored string (a ``NameCase`` member compares equal and
    works in the same way).
    """
    case = options.get(NAME_CASE)
    if case == NameCase.UPPER:
        return member_name.upper()
    if case == NameCase.LOWER:
        return member_name.lower()
    return member_name


def build_environment_name(member_name: str, options: Mapping[str, Any]) -> str:
    """Return the environment name of one settings member: ``prefix + case(member
    name)``.

    The prefix is added exactly as written. The case applies to the member name
    alone, and no other transformation happens (``dbHost`` in upper case is
    ``DBHOST``, with no conversion from camelCase to snake_case).

    Under ``any``, the name is built as declared, in the same way as under
    ``None``: ``any`` governs how the name is looked up, not how it is built.

    An explicit ``name=`` never passes through this function: it is the full
    address in the storage, not a name to build on.

    The ``options`` mapping is the stored data form: the case arrives as its
    plain stored string (a ``NameCase`` member compares equal and works in the
    same way).
    """
    cased = apply_environment_case(member_name, options)
    prefix = options.get(NAME_PREFIX)
    return f"{prefix}{cased}" if prefix else cased


LibraryConfiguration.register_class_metadata_validator(
    ENVIRONMENT_METADATA_OPTIONS, check_environment_options
)
