# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The distribution boundaries of the settings family.

Several distributions share the machinery. One of them writes settings back
to its storages, and another reads configuration from its sources. Each of
them spells its own attribute base and its own option helpers.

The boundary keeps the sides apart at the ``class`` statement. A member that
is declared with the attribute of another distribution makes the class
creation fail, and so does an ``options=`` entry that was built by the
helper of another distribution.

Without this boundary, the sides would mix silently, and the mix would change
what a member means. The attribute bases spell different defaults for the
``default=`` parameter. A settings attribute that is placed in a
configuration class would therefore turn a required member into an optional
one: ``None`` would stand in where a load was supposed to abort, with no
error anywhere.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Iterable, Mapping, Optional

from advexp.settings_base.library_configuration import ATTRIBUTE_BASE_ATTR
from advexp.settings_base.setting_descriptor import SettingDescriptor


def class_family(bases: Iterable[type], class_name: str) -> Optional[str]:
    """Return the one distribution family of the class that these bases build.

    The root settings class of every distribution declares its attribute base
    (:data:`~advexp.settings_base.library_configuration.ATTRIBUTE_BASE_ATTR`),
    and this base carries the name of the distribution as its ``FAMILY_NAME``.
    The declarations that are found along the chains of the bases name the
    family.

    A class that is built without a declaration (for example, the own test
    skeletons of the foundation, or a hand-rolled class) belongs to no family,
    and the boundaries of this module leave it alone. Bases of two different
    families cannot build one class: a ``TypeError`` names the class and both
    families.
    """
    declared: Dict[type, Optional[str]] = {}
    for klass in bases:
        for mro_class in inspect.getmro(klass):
            base = vars(mro_class).get(ATTRIBUTE_BASE_ATTR)
            if base is not None:
                declared[base] = getattr(base, "FAMILY_NAME", None)
    families = {family for family in declared.values() if family is not None}
    if len(families) > 1:
        first, second = sorted(families)
        raise TypeError(f"{class_name} belongs to both the {first} and {second} families")
    if families:
        return families.pop()
    return None


def _article(family: str) -> str:
    """The indefinite article that fits the family's name, for message wording."""
    return "an" if family[:1].lower() in "aeiou" else "a"


def validate_attribute_families(settings_class: type) -> None:
    """Make the ``class`` statement fail for a member that is declared with the
    attribute of another family.

    The function walks the members that the body of the class itself declared
    (the inherited members were checked when their declaring class was created).
    It requires every attribute of a declared family to be an instance of the
    family base of the class. A contract-only attribute that derives from the
    interface alone belongs to no family and passes.

    The error names the member and both families, in one line. The class is
    never created, so the mix surfaces at import time, before any pass runs.
    """
    base = getattr(settings_class, ATTRIBUTE_BASE_ATTR, None)
    if base is None:
        return
    family = getattr(base, "FAMILY_NAME", None)
    if family is None:
        return
    for name, value in vars(settings_class).items():
        if not isinstance(value, SettingDescriptor):
            continue
        attribute = value.attribute
        if isinstance(attribute, base):
            continue
        attribute_family = getattr(type(attribute), "FAMILY_NAME", None)
        # an attribute of no declared family — a contract-only implementation
        # derived from the interface alone — crosses no distribution
        # boundary: the boundary reads what the family declared, not what it
        # never spelled
        if attribute_family is None:
            continue
        raise TypeError(
            f"{settings_class.__name__}.{name} is {_article(attribute_family)} "
            f"{attribute_family} attribute in {_article(family)} {family} class"
        )


class _StampedOptions(dict):
    """An options entry carrying the name of the family whose helper built it."""

    family: str


def stamped_options(entry: Mapping[str, Any], family: str) -> Mapping[str, Any]:
    """Return an options entry that a helper built, stamped with the name of the
    family.

    The option helpers of a distribution wrap the results of the shared builders
    in this stamp. The settings metaclass reads the stamp once, at the ``class``
    statement, and the stored metadata keeps the plain mapping: the stamp is a
    mark of declaration time, not a stored form.
    """
    stamped = _StampedOptions(entry)
    stamped.family = family
    return stamped


def settle_options(declaration: Any, family: Optional[str], class_name: str) -> Any:
    """Check one ``options=`` declaration against the family; return it without the
    stamp.

    A stamped declaration of the own family of the class (or of a class outside
    every family) is returned as the plain mapping that it wraps. A stamped
    declaration of another family raises ``TypeError`` that names the class and
    both families. An unstamped declaration (a hand-written mapping) passes as it
    is, because the open channel never carries a stamp.
    """
    if not isinstance(declaration, _StampedOptions):
        return declaration
    if family is None or declaration.family == family:
        return dict(declaration)
    raise TypeError(
        f"{class_name} declares {declaration.family} options in {_article(family)} {family} class"
    )
