# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The family-wide member declaration of the YAML file source."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.pointer import pointer_steps
from advexp.settings_base.required import REQUIRED


class YAMLSetting(BaseAttribute):
    """Setting attribute: the value lives in the YAML source of the class.

    ``name=`` is the storage key. Without it, the name pattern of the class's
    YAML source is used. The optional ``path=`` locates the key in the
    document tree as a YAML path: a leading ``/`` and slash-separated
    segments, where ``~1`` escapes ``/`` and ``~0`` escapes ``~``. For
    example, ``path="/net/proxy"`` places the value inside
    ``net: {proxy: {...}}``, and ``path="/mirrors/1"`` inside the second
    element of the ``mirrors`` list. A segment that consists only of digits
    indexes a list if the node it steps into is a list, and names a mapping
    key otherwise. ``path=""`` and ``path=None`` both mean the document root.
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = REQUIRED,
        path: Optional[str] = None,
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
        if path is not None:
            # fail at the declaration site, not at the first storage pass
            pointer_steps(path)
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
        self.path: Optional[str] = path


def yaml_setting(
    *,
    name: Optional[str] = None,
    default: Any = REQUIRED,
    path: Optional[str] = None,
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
    """Declare a member whose value lives in the YAML source of its class.

    The member reads the YAML source that the class declares — the one YAML
    binding of a settings class, or a YAML link of a configuration class's
    chain — and the class may not declare none: the ``class`` statement
    refuses a YAML member whose class has no YAML source to serve it.

    The factory is family-wide: it belongs to no distribution, works in the
    body of a settings class of either package and in a declaration base
    (:class:`~advexp.settings_base.setting_declarations.SettingDeclarations`)
    that the settings and configuration classes inherit, and both packages
    re-export it from their roots — the import may name either one, it is the
    same function. If ``default=`` is omitted (or is
    :data:`~advexp.settings_base.required.REQUIRED`), the member is required:
    the YAML source must provide its value, or the load aborts. An optional
    member says so explicitly with ``default=None``.

    ``name=`` is the storage key of the YAML document. Without it, the name
    pattern of the class's YAML source is used. ``path=`` locates the key in
    the document tree as a YAML path, the same path that :class:`YAMLSetting`
    documents. ``aliases=`` declares additional full storage keys: a load
    looks up the primary key first, then the aliases in their order, and the
    first key found wins. Every alias is placed under the same ``path=``.

    The keyword parameters after ``aliases=`` are the declared value
    constraints (``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, ``when``). They are the same constraints that
    :func:`~advexp.settings_base.setting.setting` documents, and they are
    applied wherever a value reaches the member.
    """
    return YAMLSetting(
        name=name,
        default=default,
        path=path,
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
