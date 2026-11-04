# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The data descriptor backing a settings class member.

The settings metaclass replaces each assigned setting attribute with a
:class:`SettingDescriptor`; the replacement helper
:func:`wrap_attribute_members` lives here with it.
"""

from __future__ import annotations

import copy
import typing
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, cast

from advexp.settings_base.constraints import check_value
from advexp.settings_base.cross_validation import effective_values
from advexp.settings_base.instance_values import instance_values
from advexp.settings_base.library_configuration import member_term
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.setting_attribute_interface import ISettingAttribute

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.settings_meta import SettingsMeta

_UNPREPARED = object()
"""Marker of a descriptor whose declared default has not been converted yet."""


class SettingDescriptor:
    """Data descriptor backing a settings class member.

    The settings metaclass replaces each assigned setting attribute with a
    descriptor. Values live in the per-class ``__settings_values__`` dict,
    giving every settings class its own storage. Access through the class
    and through instances reads the same shared storage. The exception is a
    snapshot instance produced by ``Settings.to_object``: it carries a
    private value mapping in its ``__dict__``, and its reads and writes
    never reach the class storage.

    Every write through the descriptor is first checked against the value
    constraints the attribute declares: a violating value raises
    :class:`~advexp.settings_base.setting_validation_error.SettingValidationError`
    and never reaches any storage.
    """

    def __init__(self, attribute: ISettingAttribute) -> None:
        self.attribute = attribute
        # assigned by __set_name__ during class creation; a descriptor is only
        # reachable through its owning class, where the name is always set
        self.name: str = ""
        # the converted form of the declared default, stored by the settings
        # metaclass at class creation (default_validation prepares it)
        self._converted_default: Any = _UNPREPARED

    @property
    def default_prepared(self) -> bool:
        """Whether the declared default has been converted for serving yet."""
        return self._converted_default is not _UNPREPARED

    def prepare_default(self, converted: Any) -> None:
        """Store the converted form of the declared default.

        The settings metaclass calls this at class creation, right after
        converting the default through the member annotation. A
        descriptor is shared with subclasses (the MRO walk reuses the
        declaring class's descriptor), so the declaring class prepares it
        once and subclasses keep the converted form.
        """
        self._converted_default = converted

    def resolved_default(self, owner: Optional[type] = None) -> Any:
        """Return the effective default: the ``default=`` of the attribute if it was
        given, otherwise ``None``.

        This reads the sentinel semantics of ``default`` from the contract
        directly: ``None`` is a legitimate default value, so "no default" is the
        :data:`NO_DEFAULT` sentinel.

        The default is served in its converted form: the shape of the annotated
        type, prepared at class creation in the same way as a load converts what it
        reads. Mutable defaults are deep-copied on every call. Every consumption (an
        unset read, ``reset_settings``, a load miss, or a delete reset) gets its own
        copy, so changing a setting in place never corrupts the declared default,
        which a subclass shares because it is the same attribute object.

        A required member serves no default at all. For a member that is declared
        :data:`~advexp.settings_base.required.REQUIRED`, the call raises
        :class:`~advexp.settings_base.member_load_error.MemberLoadError`, which is
        the parent of the load-time reasons. This sentinel is how "the value must
        come from a source" is spelled. ``owner`` is the settings class for which
        the default is served, and the error uses the term of the distribution of
        that class. Without it (a hand-built call), the word ``setting`` of the whole
        family is used.
        """
        if self.attribute.default is REQUIRED:
            term = member_term(owner)
            raise MemberLoadError(
                f"{term} '{self.name}' is required: no value was loaded",
                member_name=self.name,
            )
        if self.attribute.default is not NO_DEFAULT:
            if self._converted_default is _UNPREPARED:
                # the metaclass prepares every declared default, so this is
                # only reachable on a hand-built descriptor
                return copy.deepcopy(self.attribute.default)
            return copy.deepcopy(self._converted_default)
        return None

    # -- data descriptor protocol ----------------------------------------------

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        if self.attribute.bound_name is None:
            self.attribute.bound_name = name
            # the same first-binding write: the class whose body declares
            # the member is the anchor for per-class family options, and a
            # subclass inheriting the member never rewrites it
            self.attribute.declaring_class = owner

    def __get__(self, obj: Any, objtype: Optional[type] = None) -> Any:
        if obj is not None:
            own = instance_values(obj)
            if own is not None:
                if self.name in own:
                    return own[self.name]
                return self.resolved_default(objtype)
        owner = objtype if objtype is not None else type(obj)
        values: Optional[Dict[str, Any]] = vars(owner).get("__settings_values__")
        if values is not None and self.name in values:
            return values[self.name]
        return self.resolved_default(owner)

    def __set__(self, obj: Any, value: Any) -> None:
        owner = cast("SettingsMeta", type(obj))
        check_value(
            self.attribute,
            value,
            f"invalid value for {member_term(owner)} '{self.name}' of {owner.__name__}",
            siblings=effective_values(owner, obj),
        )
        own = instance_values(obj)
        if own is not None:
            own[self.name] = value
            return
        values = vars(owner).get("__settings_values__")
        if values is None:
            values = {}
            owner.__settings_values__ = values
        values[self.name] = value


def wrap_attribute_members(namespace: Dict[str, Any]) -> None:
    """Replace setting attribute instances with their descriptors.

    Called by the settings metaclass on the class namespace *before* class
    creation, so ``__set_name__`` fires for the descriptors as usual.
    """
    for name, value in list(namespace.items()):
        if isinstance(value, ISettingAttribute):
            namespace[name] = SettingDescriptor(value)


def is_classvar_annotation(annotation: Any) -> bool:
    """Return whether an annotation spells a ``typing.ClassVar``, which is a
    class-level constant that the member machinery must leave alone.

    Both spellings are recognized: the annotation object (in a module without
    ``from __future__ import annotations``) and the string that the future
    import leaves instead. The string check reads the two spellings that a class
    body can write: ``ClassVar[...]``, with the name spelled in full as the
    module imported it, and ``typing.ClassVar[...]``, with the module itself. An
    alias that the module chose (``from typing import ClassVar as CV``) is its
    own case, and the object path covers it there.
    """
    if isinstance(annotation, str):
        text = annotation.strip()
        return text == "ClassVar" or text.startswith(("ClassVar[", "typing.ClassVar"))
    return typing.get_origin(annotation) is typing.ClassVar


def _namespace_annotations(namespace: Dict[str, Any]) -> Dict[str, Any]:
    """Return the annotations of the class namespace, materialized for this pass.

    Python 3.14 carries the annotations of a class body lazily. The namespace
    reaches the metaclass with the ``__annotate_func__`` builder, not with a
    ready ``__annotations__`` dict. Reading the annotations here therefore means
    calling the builder once and storing the result as the own
    ``__annotations__`` of the namespace, which is the spelling that every
    earlier version writes directly.
    """
    annotations = namespace.get("__annotations__")
    if annotations is not None:
        return annotations
    annotate = namespace.pop("__annotate_func__", None)
    if annotate is None:
        return {}
    import sys

    if sys.version_info < (3, 14):  # pragma: no cover - earlier versions write __annotations__
        return {}
    from annotationlib import Format  # type: ignore[import-not-found]

    try:
        # VALUE is the one format the generated builder serves; an
        # unresolvable name a class body spelled bare still raises there,
        # and such a body keeps its old silence: no member is built from
        # annotations the pass could not read
        annotations = dict(annotate(Format.VALUE))
    except Exception:  # noqa: BLE001 - unreadable annotations build no members
        return {}
    namespace["__annotations__"] = annotations
    return annotations


def expand_plain_members(
    namespace: Dict[str, Any],
    attribute_factory: Callable[[Any], ISettingAttribute],
) -> None:
    """Turn the plain annotations of the body into members, in place.

    This is the shared mechanics of the plain declaration style:

    - A bare annotation (``token: str``) becomes a required member.
    - The value of an annotated assignment (``ttl: timedelta =
      timedelta(minutes=30)``) becomes the declared default of that member.

    ``attribute_factory`` builds the attribute: it is the neutral attribute of
    the package, with the default first, so that the two spellings produce one
    kind of member.

    A ``ClassVar`` annotation is not a member at all, and it keeps its value as
    the class attribute that it always was. A dunder that the class machinery
    itself declared stays untouched in the same way. A member that is already
    declared through a factory keeps its declaration: the plain spelling widens
    the class body and does not take it over.

    Call this function before :func:`wrap_attribute_members`, on the same
    namespace. The wrapping step finishes what this function builds.
    """
    annotations = _namespace_annotations(namespace)
    for name, annotation in list(annotations.items()):
        if name.startswith("__") or is_classvar_annotation(annotation):
            continue
        if name in namespace:
            value = namespace[name]
            if isinstance(value, ISettingAttribute):
                continue  # a factory declaration: the richer spelling stands
            namespace[name] = attribute_factory(value)
        else:
            namespace[name] = attribute_factory(REQUIRED)
