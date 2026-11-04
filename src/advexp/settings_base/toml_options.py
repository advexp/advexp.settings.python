# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The naming options of the family of TOML file backends.

A TOML file backend ships in two distributions. One of them loads and stores
settings, and the other reads the same file as a configuration source. Both
build the static keys of the document by the same rules, so the options live
here, in the foundation of the family, next to the file bindings: one
metadata key, the option names, the validation, and the options helpers.
Backends that build keys in any other way would silently split one document
between two spellings of the same setting.

The placement rule belongs here for the same reason. Both distributions
store every key at the address that it names (:func:`toml_table_levels`), so
one document never holds the same setting under two layouts.

The options govern **static keys only**, that is, the keys of the declared
members. An explicit ``name=`` is the full address in the document and never
passes through the pattern. The dynamic side (the runtime-named entries of
the dynamic collections) has its own parameter in its configuration, because
it lives only in the settings distribution.

The options are stored **per declaring class**: the entry of each class is
stored under the family key joined with the module and the name of the
class. A subclass that declares its own options therefore coexists with the
base class instead of replacing it. The key of a member is built with the
entry of the class that declared the member: the nearest entry at or above
that class.
"""

from __future__ import annotations

import collections.abc
from typing import Any, Dict, List, Mapping, Optional

from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.names import (
    DEFAULT_SETTINGS_NAME_PATTERN,
    FIELD_NAME_PATTERN_NAME,
)

TOML_METADATA_OPTIONS = "TOMLMetadataOptions"
"""The class metadata key of the family — one key for every backend reading
or writing the static keys of a TOML document. The options are declared
once per settings class and reach every backend of the family at once."""

NAME_PATTERN = "name_pattern"
"""The pattern building the document key of a member without an explicit
``name=``; ``None`` keeps the default full pattern
``{module}.{class}.{member}`` (the name builder's own constant), so a
declaration without it changes nothing."""


def _pattern_problem(pattern: Any) -> Optional[str]:
    """Why ``pattern`` cannot serve as the family's name pattern."""
    if pattern is None:
        return None
    if not isinstance(pattern, str) or not pattern:
        return f"{NAME_PATTERN} must be None or a non-empty string, got {pattern!r}"
    if FIELD_NAME_PATTERN_NAME not in pattern:
        return (
            f"{NAME_PATTERN} must contain the {FIELD_NAME_PATTERN_NAME} slot: "
            "without it every built key of the class would be the same key"
        )
    return None


def check_toml_options(value: Any) -> Optional[str]:
    """Describe why ``value`` is not a valid options mapping; return ``None`` if it
    is valid.

    This is the single validator of the metadata entry of the family. It checks
    the shape of the mapping, the known option names (a mistyped option would
    otherwise sit silently and do nothing), and the form of the value: the
    pattern is ``None`` or a non-empty string that holds the ``{FieldName}``
    slot.
    """
    if not isinstance(value, collections.abc.Mapping):
        return f"must be a mapping of option name to value, got {type(value).__name__}"
    problems = []
    unknown = sorted(set(value) - {NAME_PATTERN})
    if unknown:
        problems.append(f"unknown option name(s): {', '.join(repr(name) for name in unknown)}")
    problem = _pattern_problem(value.get(NAME_PATTERN))
    if problem is not None:
        problems.append(problem)
    return "; ".join(problems) or None


def _checked_options(name_pattern: Optional[str]) -> Dict[str, Any]:
    """Validate the pattern; return the stored form of the entry."""
    options: Dict[str, Any] = {NAME_PATTERN: name_pattern}
    problem = check_toml_options(options)
    if problem is not None:
        raise TypeError(f"invalid TOML options: {problem}")
    return options


def toml_name_pattern(options: Mapping[str, Any]) -> str:
    """Return the effective name pattern of the stored options entry of the family.

    ``None`` (an entry that is declared without the option, or no entry at all;
    callers pass an empty mapping) gives the default full pattern, which is the
    same spelling that an absent declaration leaves in force. The pattern is the
    vocabulary of the name builder: the backend hands it to
    ``get_full_setting_name`` and never expands it on its own.
    """
    pattern = options.get(NAME_PATTERN)
    return pattern if pattern else DEFAULT_SETTINGS_NAME_PATTERN


TOML_TABLE_SEPARATOR = "."
"""The table separator of the TOML document keys. In a TOML document
``a.b.c = v`` and ``[a.b] c = v`` name one place — the separator stands
for a table level — while a quoted ``"a.b"`` is a single key holding a
dot, a different place. The backends of the family store every key at
the address it names, so a storage name carries no quotes: its
separator-delimited parts are table levels and the last part is the key
itself (:func:`toml_table_levels`)."""


def toml_table_levels(key: str) -> List[str]:
    """Return the levels of the document that the storage ``key`` names. The last
    level is the key itself.

    The dot, which is the table separator of TOML itself, splits the key:
    ``a.b.c`` walks the tables ``a`` and ``b`` to the key ``c``. This is a place
    that the flat quoted spelling of the same text does not name. A key without
    the separator is a plain key.

    The spelling of the key itself (an explicit ``name=`` or the pattern of the
    family) stays the business of the name builder. This function is concerned
    with placement alone. A ``path=`` segment is never split: it names one
    literal level.
    """
    return key.split(TOML_TABLE_SEPARATOR)


LibraryConfiguration.register_class_metadata_validator(TOML_METADATA_OPTIONS, check_toml_options)
