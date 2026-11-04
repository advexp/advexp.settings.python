# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The setting attribute base class: the contract plus the conventions.

Python decorators apply only to functions and classes, so a setting member
is declared by *assigning* the attribute instance. The settings metaclass
wraps the instance into a
:class:`~advexp.settings_base.setting_descriptor.SettingDescriptor`::

    class LocalSettings(Settings):
        airplane_mode: bool = Setting(name="airplaneMode", default=False)
"""

from __future__ import annotations

import collections.abc
import copy
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
)

from advexp.settings_base.constraints import (
    Check,
    build_checks,
    build_condition,
    build_member_rules,
)
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.setting_attribute_interface import ISettingAttribute

if TYPE_CHECKING:  # pragma: no cover - typing only
    from advexp.settings_base.constraints import _MemberRule

AttributeT = TypeVar("AttributeT", bound=ISettingAttribute)
"""The attribute class a serializer narrows ``attr`` to (attribute_of)."""


class BaseAttribute(ISettingAttribute):
    """Base class for setting attributes: the contract plus the conventions.

    When it is assigned to a member of a settings class, it marks the member as
    a setting that is served by the serializer registered for the attribute
    class.

    The abstract fields of the interface are implemented as properties over
    per-instance storage, which is declared and initialized by ``__init__``; the
    class body carries no field values. The ``__init__`` parameters carry no
    defaults either, on purpose: the defaults are for the distributions to
    spell, and the attribute base of each package declares its own (the base of
    the settings package spells ``NO_DEFAULT``, and the base of the
    configuration package spells ``REQUIRED``). If you derive from this base
    directly, you must pass every parameter.

    Subclasses extend ``__init__``: call the base with
    ``name``/``default``/``metadata``/``aliases`` and the constraint
    parameters, and then set the own parameters of the backend on ``self``
    (keyword-only parameters all the way, like the base).

    The comparison parameters (``gt`` to ``ne``) accept either a literal or the
    attribute object of a member that was declared earlier in the same class
    body. The second form is a member reference, which is compared with the
    current value of that member. The ``when=`` parameter gates everything
    declared on the member on the truthiness of a sibling member.

    Declare members through the factory function of the backend (``json_setting``
    and the like). Assigning the attribute instance to an annotated member is
    valid Python (the settings metaclass replaces it with a value descriptor),
    but type checkers cannot see the replacement and report a type mismatch. A
    plain function that returns ``Any`` is the only spelling that all of them
    accept.
    """

    FAMILY_NAME: ClassVar[Optional[str]] = None
    """The import name of the distribution this attribute base serves.

    ``None`` on the family's own skeleton — a base like this belongs to no
    distribution. A distribution's attribute base declares its package
    name, and the machinery words the distribution boundary with it: a
    member of one distribution's settings class declared with another
    distribution's attribute fails the ``class`` statement naming both
    (:mod:`advexp.settings_base.family_boundaries`)."""

    SOURCELESS: ClassVar[bool] = False
    """Whether the member never reads a source of its own accord.

    ``False`` everywhere but the constant members: an attribute that
    spells ``True`` declares a member whose value is its declared
    default alone — the load pass serves it without asking any source,
    and the load overrides skip it. The load machinery reads this flag;
    no code sets it at runtime."""

    def __init__(
        self,
        *,
        name: Optional[str],
        default: Any,
        metadata: Optional[Mapping[str, Any]],
        aliases: Optional[Sequence[str]],
        gt: Any,
        ge: Any,
        lt: Any,
        le: Any,
        eq: Any,
        ne: Any,
        min_length: Optional[int],
        max_length: Optional[int],
        regex: Optional[str],
        validator: Optional[Callable[[Any], bool]],
        when: Any = None,
    ) -> None:
        # ``when`` is the one defaulted parameter: it joined the signature
        # after the base had shipped, so subclass ``__init__``s calling the
        # base without it keep working
        if metadata is not None and not isinstance(metadata, collections.abc.Mapping):
            raise TypeError(
                f"metadata must be a mapping of metadata names to values, "
                f"got {type(metadata).__name__}"
            )
        self.__name: Optional[str] = name
        self.__default: Any = default
        self.__metadata: Optional[Mapping[str, Any]] = metadata
        self.__aliases: Tuple[str, ...] = self.__checked_aliases(aliases, name)
        self.__bound_name: Optional[str] = None
        self.__declaring_class: Optional[type] = None
        self.__checks: Tuple[Check, ...] = build_checks(
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            eq=eq,
            ne=ne,
            min_length=min_length,
            max_length=max_length,
            regex=regex,
            validator=validator,
        )
        self.__member_rules = build_member_rules(gt=gt, ge=ge, lt=lt, le=le, eq=eq, ne=ne)
        self.__condition = build_condition(when)

    @staticmethod
    def __checked_aliases(aliases: Optional[Sequence[str]], name: Optional[str]) -> Tuple[str, ...]:
        """Validate the declared aliases and return them as a tuple.

        An alias that repeats an address that the declaration already has (the
        explicit ``name=`` or an earlier alias) is a mistake: a load would never
        reach it. The declaration therefore refuses it, instead of storing dead
        entries.
        """
        if aliases is None:
            return ()
        if isinstance(aliases, str) or not isinstance(aliases, collections.abc.Sequence):
            raise TypeError(
                f"aliases must be a sequence of non-empty strings, got {type(aliases).__name__}"
            )
        checked: Tuple[str, ...] = tuple(aliases)
        for alias in checked:
            if not isinstance(alias, str) or not alias:
                raise TypeError(f"aliases must be a sequence of non-empty strings, got {alias!r}")
            if alias == name:
                raise ValueError(f"aliases must not repeat the address given by name=: {alias!r}")
            if checked.count(alias) > 1:
                raise ValueError(f"aliases must not contain the same address twice: {alias!r}")
        return checked

    @property
    def name(self) -> Optional[str]:
        """The storage name of the setting; ``None`` means that the name pattern is
        expanded.
        """
        return self.__name

    @property
    def aliases(self) -> Tuple[str, ...]:
        """Additional full storage addresses, in their declared order.

        The tuple is empty for an attribute that is declared without ``aliases=``.
        A load looks up the primary address first (the explicit ``name=`` or the
        built one), then these addresses, and the first address found wins. An alias
        is a full address in the storage and has the same status as an explicit
        ``name=``: the naming options of the family never change it.
        """
        return self.__aliases

    @property
    def default(self) -> Any:
        """The declared default value (:data:`NO_DEFAULT` when none is given).

        :data:`~advexp.settings_base.required.REQUIRED` declares a member that must
        get its value from a source: serving its default raises an error.
        """
        return self.__default

    @property
    def metadata(self) -> Dict[str, Any]:
        """The declared metadata of the setting, keyed by metadata name.

        This is the declarative form of the runtime metadata channel: it is what the
        settings class reads as the initial metadata of the member, before any
        ``set_setting_metadata`` call. The values are arbitrary. The mapping is
        served as a deep copy, so changing what the property returns never affects
        the declaration. An attribute that is declared without ``metadata=``
        returns an empty dict.
        """
        if self.__metadata is None:
            return {}
        return dict(copy.deepcopy(self.__metadata))

    @property
    def bound_name(self) -> Optional[str]:
        """The name of the member that this attribute is bound to; it is set by the
        metaclass.
        """
        return self.__bound_name

    @bound_name.setter
    def bound_name(self, value: Optional[str]) -> None:
        # the field is declared in __init__; this is the metaclass's write
        # on binding, not an initializer re-run
        # noinspection PyAttributeOutsideInit
        self.__bound_name = value

    @property
    def declaring_class(self) -> Optional[type]:
        """The settings class whose body declared this member; the metaclass sets it
        when the declaring class is created.
        """
        return self.__declaring_class

    @declaring_class.setter
    def declaring_class(self, value: Optional[type]) -> None:
        # the same first-binding write as bound_name: only the declaring
        # class's creation stamps it, and a subclass inheriting the member
        # never rewrites it
        # noinspection PyAttributeOutsideInit
        self.__declaring_class = value

    @property
    def default_in_use(self) -> bool:
        """Return whether an explicit default was passed to the attribute.

        This is a convenience helper that reads the sentinel semantics which the
        contract defines for :attr:`default`; it is not part of the interface.
        :data:`REQUIRED` does not count: it states that the member is required, and
        it is not a value to serve.
        """
        return self.default is not NO_DEFAULT and self.default is not REQUIRED

    @property
    def constraint_checks(self) -> Tuple[Check, ...]:
        """The declared value constraints as check callables.

        The checks are compiled at declaration from the ``gt/ge/lt/le``,
        ``eq/ne``, ``min_length/max_length``, ``regex`` and ``validator``
        parameters. The tuple is empty for an attribute that is declared without
        them. It is read by the places that validate values
        (:func:`~advexp.settings_base.constraints.check_value` and similar
        helpers). An attribute whose declaration fails the checks never exists, so
        the tuple is never revisited.
        """
        return self.__checks

    @property
    def constraint_member_rules(self) -> Tuple["_MemberRule", ...]:
        """The comparison bounds that are declared as references to sibling members.

        The ``gt/ge/lt/le/eq/ne`` parameters may carry the attribute object of a
        member that was declared earlier in the same class body. Such bounds are
        stored here instead of in :attr:`constraint_checks`: a member rule cannot
        check a value in isolation. It compares the value with the current value of
        the referenced member, which only the class-wide validation passes know. The
        tuple is empty for an attribute that is declared with literals only (or
        without comparisons).
        """
        return self.__member_rules

    @property
    def constraint_condition(self) -> Optional["ISettingAttribute"]:
        """The ``when=`` reference: the member whose truthiness gates the
        constraints.

        It is ``None`` for an attribute that is declared without ``when=``. While
        the value of the referenced member is falsy, none of the declared
        constraints of this member apply: neither the field checks in
        :attr:`constraint_checks` nor the member rules in
        :attr:`constraint_member_rules`.
        """
        return self.__condition
