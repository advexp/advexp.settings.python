# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The family-wide member declaration of the environment variables source."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.required import REQUIRED


class EnvironmentVariableSetting(BaseAttribute):
    """Setting attribute: the value lives in an environment variable.

    ``name=`` is the variable name. Without it, the name pattern of the
    class's environment source is used.
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = REQUIRED,
        metadata: Optional[Mapping[str, Any]] = None,
        aliases: Optional[Sequence[str]] = None,
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
        when: Any = None,
    ) -> None:
        super().__init__(
            name=name,
            default=default,
            metadata=metadata,
            aliases=aliases,
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
            when=when,
        )


def environment_variable_setting(
    *,
    name: Optional[str] = None,
    default: Any = REQUIRED,
    metadata: Optional[Mapping[str, Any]] = None,
    aliases: Optional[Sequence[str]] = None,
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
    when: Any = None,
) -> Any:
    """Declare a member whose value lives in an environment variable.

    The member reads the environment source that the class declares — the one
    environment binding of a settings class, or an environment link of a
    configuration class's chain — and the class may not declare none: the
    ``class`` statement refuses an environment member whose class has no
    environment source to serve it.

    The factory is family-wide: it belongs to no distribution, works in the
    body of a settings class of either package and in a declaration base
    (:class:`~advexp.settings_base.setting_declarations.SettingDeclarations`)
    that the settings and configuration classes inherit, and both packages
    re-export it from their roots — the import may name either one, it is the
    same function. If ``default=`` is omitted (or is
    :data:`~advexp.settings_base.required.REQUIRED`), the member is required:
    the environment must provide its value, or the load aborts. An optional
    member says so explicitly with ``default=None``.

    ``name=`` is the environment variable name. Without it, the name pattern
    of the class's environment source is used. ``aliases=`` declares
    additional full variable names: a load looks up the primary name first,
    then the aliases in their order, and the first name found wins. This is
    how a rename is migrated: the old name keeps working next to the new one.

    The keyword parameters after ``aliases=`` are the declared value
    constraints (``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, ``when``). They are the same constraints that
    :func:`~advexp.settings_base.setting.setting` documents, and they are
    applied wherever a value reaches the member.
    """
    return EnvironmentVariableSetting(
        name=name,
        default=default,
        metadata=metadata,
        aliases=aliases,
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
        when=when,
    )
