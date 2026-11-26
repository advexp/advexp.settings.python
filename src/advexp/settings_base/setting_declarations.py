# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Declaration bases: one set of member declarations for both packages.

A declaration base is a plain class that carries member declarations for a
settings class and a configuration class at once. The applications that work
with both libraries describe their values one time — in the base — and the
two classes inherit the same declarations, each reading them through the
sources of its own package:

```python
from advexp.settings_base import SettingDeclarations, setting

class AppDeclarations(SettingDeclarations):
    retries: int = 3
    timeout = setting(default=30, ge=retries)

class Settings1(AppDeclarations, Settings, options=json_source(file="app.json")):
    ...

class Config1(AppDeclarations, Configuration, options=Sources(json_source(...))):
    ...
```

The class statement of the inheriting class pours the declarations of the
base into its own body: every declaration becomes the member of that class,
as if its body had spelled it. A member that the body declares under the
same name wins over the poured one. The base stays inert after that — a
change to it never reaches the classes that were already created.
"""

from __future__ import annotations

import copy
import inspect
import sys
from typing import Any, Dict, List, Optional, Tuple

from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.context import SETTINGS_CONTEXT_ATTR
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.setting import plain_member
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.setting_descriptor import is_classvar_annotation
from advexp.settings_base.settings_meta import SettingsMeta

_BARE = object()
"""The marker of a bare annotation: no value anywhere in the chain."""


class SettingDeclarations:
    """The marker that turns a plain class into a declaration base.

    A plain class that inherits this marker is a declaration base: the class
    statement of a settings or configuration class that inherits the base
    pours the base's member declarations into its own body. The base itself
    is never a settings class — it loads nothing, validates nothing, and
    serves no values; the classes that inherit it do all of that with the
    declarations it holds.

    Only classes below the marker in the inheritance chain take part. A
    plain mixin without the marker keeps today's silence: its annotations
    stay annotations, and the settings classes that inherit it ignore them.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if isinstance(cls, SettingsMeta):
            # the settings class that inherits a declaration base takes the
            # pour of this module; the refusal below guards the declaration
            # bases themselves, which are plain classes. A class that spells
            # the marker beside a settings base never reaches it: the
            # metaclass of that base wins, and the class is a settings class
            # from the start
            return
        for name, value in vars(cls).items():
            if not isinstance(value, ISettingAttribute):
                continue
            family = getattr(type(value), "FAMILY_NAME", None)
            if family is not None:
                raise TypeError(
                    f"{cls.__name__}.{name} is an {family} attribute in a "
                    "declaration base. A declaration base carries the family-wide "
                    "spellings only — declare this member in the class that reads "
                    "it, or through a factory of advexp.settings_base"
                )


def _declaration_chain(bases: Tuple[type, ...]) -> Optional[List[type]]:
    """The plain classes whose declarations the new class absorbs, or ``None``
    when no declaration base takes part.

    The walk follows the principle of the metadata absorption: every base
    lineage climbs until the first class that owns a settings context, which
    absorbed everything above it when it was created. The classes come out in
    their resolution order — the class that a name resolves to first stands
    first — so a name declared by two of them resolves to the more derived
    declaration.
    """
    chain: List[type] = []
    seen = set()
    marked = False
    for base in bases:
        for klass in inspect.getmro(base):
            if klass is object:
                continue
            if vars(klass).get(SETTINGS_CONTEXT_ATTR) is not None:
                break
            if issubclass(klass, SettingDeclarations):
                marked = True
            if klass in seen:
                continue
            seen.add(klass)
            chain.append(klass)
    if not marked:
        return None
    return chain


def _family_of(attribute: ISettingAttribute) -> Optional[str]:
    """The distribution family that the type of the attribute declares, if any."""
    return getattr(type(attribute), "FAMILY_NAME", None)


def _chain_annotations(klass: type) -> Dict[str, Any]:
    """The own annotations of one chain class, as a plain dict.

    Python 3.14 keeps the annotations of a class lazy: ``vars`` shows none,
    and the attribute access materializes the class's own dict — never the
    one that a base class holds. Earlier versions write that dict into
    ``vars`` directly, and there the attribute would fall back to a base's
    annotations, so the read goes through ``vars`` alone.
    """
    if sys.version_info >= (3, 14):
        return dict(getattr(klass, "__annotations__", None) or {})
    return dict(vars(klass).get("__annotations__") or {})


def _chain_value(chain: List[type], name: str) -> Any:
    """The value of one annotated name, from the first chain class that has
    it, or the bare marker when none does."""
    for klass in chain:
        if name in vars(klass):
            return vars(klass)[name]
    return _BARE


def _resolved_declarations(
    chain: List[type],
) -> Tuple[Dict[str, ISettingAttribute], Dict[str, Any]]:
    """The declarations of the chain, resolved per name.

    The first chain class that declares a name — through its own attributes
    or its own annotations — decides how the name pours. A factory attribute
    of that class pours in as a copy; an annotated name becomes the plain
    member with the value that the chain holds for it (searched from the most
    derived class down) or with the required sentinel when the chain holds
    none. A ``ClassVar`` annotation is no declaration, and neither is a value
    that no chain class annotated.
    """
    factory_names: Dict[str, ISettingAttribute] = {}
    plain_names: Dict[str, Any] = {}
    for klass in chain:
        annotations = _chain_annotations(klass)
        for name in list(vars(klass)) + list(annotations):
            if name.startswith("__") or name in factory_names or name in plain_names:
                continue
            if name not in annotations and not isinstance(vars(klass).get(name), ISettingAttribute):
                continue
            if is_classvar_annotation(annotations.get(name)):
                continue
            value = vars(klass).get(name)
            if isinstance(value, ISettingAttribute):
                factory_names[name] = value
            elif name in annotations:
                plain_names[name] = _chain_value(chain, name)
    return factory_names, plain_names


def _referenced_attributes(attribute: ISettingAttribute) -> List[Tuple[str, Any]]:
    """The references of one attribute: the parameter of each member rule and
    the ``when=`` condition, with the attribute object they name.

    A contract-only attribute that stores its references its own way lists
    none here: the pour never reaches into it, exactly as the validation of
    member references never did.
    """
    referenced: List[Tuple[str, Any]] = [
        (rule.parameter, rule.reference)
        for rule in getattr(attribute, "constraint_member_rules", ())
    ]
    condition = getattr(attribute, "constraint_condition", None)
    if condition is not None:
        referenced.append(("when", condition))
    return referenced


def expand_base_declarations(
    namespace: Dict[str, Any], bases: Tuple[type, ...], class_name: str
) -> None:
    """Pour the declarations of the marked declaration bases into the
    namespace of the class that is being created, in place.

    The settings metaclasses call this after the plain annotations of the
    body became members and before the attributes turn into descriptors. A
    base without the marker leaves the namespace untouched.

    - Every declaration of the chain becomes a member of the class: a
      family-wide attribute pours in as a deep copy, and a plain annotation
      becomes the family-wide plain member with the declared value (a deep
      copy) or the required sentinel as its default.
    - One copy pass with one shared memo serves the whole chain, so the
      references between declarations (``ge=low``, ``when=flag``) land on the
      copies of this class, whichever chain class declared them.
    - A name that the body itself declares wins: the poured declaration of
      that name stays out of the namespace. A poured member that referenced
      it has lost its target, and the class statement says so.
    - A reference from the body to a declaration of the base
      (``ge=Base.low``) turns onto the poured copy of that declaration — the
      same object the class binds as its member. A reference to a name that
      the body overrode cannot turn anywhere: the class statement asks for a
      reference to the body's own member instead.
    """
    chain = _declaration_chain(bases)
    if chain is None:
        return
    # every attribute of the chain must be family-wide: an attribute printed
    # with a third-party family cannot pour into a class of another package
    for klass in chain:
        for name, value in vars(klass).items():
            if isinstance(value, ISettingAttribute) and _family_of(value) is not None:
                family = _family_of(value)
                raise TypeError(
                    f"{class_name} inherits {klass.__name__}.{name}, an {family} "
                    "attribute in a declaration base. A declaration base carries "
                    "the family-wide spellings only — declare this member in the "
                    "class that reads it, or through a factory of "
                    "advexp.settings_base"
                )
    factory_names, plain_names = _resolved_declarations(chain)
    # the body wins over every poured name
    overridden = {name for name in list(factory_names) + list(plain_names) if name in namespace}
    # one copy pass with one shared memo, over every factory declaration of
    # the chain — the overridden names included: the references between
    # declarations regenerate onto the copies, and a copy of an overridden
    # name still exists for the references that point at it. It just never
    # becomes a member, which the checks below name precisely
    # the sentinels keep their identity through the copy: a deep-copied
    # REQUIRED would stop being the REQUIRED the load pass compares with
    memo: Dict[int, Any] = {id(REQUIRED): REQUIRED, id(NO_DEFAULT): NO_DEFAULT}
    poured: Dict[str, BaseAttribute] = {}
    for name, original in factory_names.items():
        poured[name] = copy.deepcopy(original, memo)  # type: ignore[assignment]
    placed: Dict[str, Any] = {
        name: plain_member(REQUIRED if value is _BARE else copy.deepcopy(value))
        for name, value in plain_names.items()
        if name not in overridden
    }
    for name, attribute in poured.items():
        if name not in overridden:
            placed[name] = attribute
    # the orphan copies: the copies of the names the body overrode. A poured
    # member that references one has lost its target to the override
    orphans = {id(poured[name]): name for name in overridden if name in poured}
    for name, attribute in placed.items():
        for parameter, target in _referenced_attributes(attribute):
            if id(target) in orphans:
                target_name = orphans[id(target)]
                raise TypeError(
                    f"{class_name}.{name} references '{target_name}' in "
                    f"{parameter}=, but the body of {class_name} overrides "
                    f"'{target_name}' with its own declaration. The inherited "
                    f"reference is lost: drop the override, or declare '{name}' "
                    "in the body with the reference closed there"
                )
    # the references of the body's own attributes turn onto the poured copies
    originals = {id(original): name for name, original in factory_names.items()}
    redirects = {id(original): poured[name] for name, original in factory_names.items()}
    for name, value in list(namespace.items()):
        if not isinstance(value, ISettingAttribute):
            continue
        for parameter, target in _referenced_attributes(value):
            if id(target) in originals and originals[id(target)] in overridden:
                target_name = originals[id(target)]
                raise TypeError(
                    f"{class_name}.{name} references '{target_name}' in "
                    f"{parameter}=, but the body of {class_name} overrides "
                    f"'{target_name}' with its own declaration. Reference the "
                    "body's own member instead"
                )
        if isinstance(value, BaseAttribute):
            value.redirect_member_references(redirects)
    namespace.update(placed)
