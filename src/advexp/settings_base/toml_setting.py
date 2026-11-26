# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The family-wide member declaration of the TOML file source."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings_base.base_attribute import BaseAttribute
from advexp.settings_base.pointer import pointer_steps
from advexp.settings_base.required import REQUIRED


class TOMLSetting(BaseAttribute):
    """Setting attribute: the value lives in the TOML source of the class.

    ``name=`` is the address of the setting in the document. Every dot in the
    name (the table separator of TOML) separates a table level, and the last
    part is the key. For example, ``name="net.host"`` places the key inside
    the ``[net]`` table, and a name without a dot is a plain key. Without a
    name, the name pattern of the class's TOML source is used, and its dots
    nest in the same way. A literal key that contains a dot is reached
    through ``path=``, because the segments of a pointer are never split.

    The optional ``path=`` locates the key in the document tree as a JSON
    Pointer (RFC 6901): a leading ``/`` and slash-separated segments, where
    ``~1`` escapes ``/`` and ``~0`` escapes ``~``. For example,
    ``path="/net/proxy"`` places the value inside ``[net.proxy]``, and
    ``path="/mirrors/1"`` inside the second element of the ``mirrors`` array.
    A segment that consists only of digits indexes an array if the node it
    steps into is an array, and names a table key otherwise. ``path=""`` and
    ``path=None`` both mean the document root.
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


def toml_setting(
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
    """Declare a member whose value lives in the TOML source of its class.

    The member reads the TOML source that the class declares — the one TOML
    binding of a settings class, or a TOML link of a configuration class's
    chain — and the class may not declare none: the ``class`` statement
    refuses a TOML member whose class has no TOML source to serve it.

    The factory is family-wide: it belongs to no distribution, works in the
    body of a settings class of either package and in a declaration base
    (:class:`~advexp.settings_base.setting_declarations.SettingDeclarations`)
    that the settings and configuration classes inherit, and both packages
    re-export it from their roots — the import may name either one, it is the
    same function. If ``default=`` is omitted (or is
    :data:`~advexp.settings_base.required.REQUIRED`), the member is required:
    the TOML source must provide its value, or the load aborts. An optional
    member says so explicitly with ``default=None``.

    ``name=`` is the address in the TOML document: every dot in it separates
    a table level, the last part is the key, and a literal key that contains
    a dot is reached through ``path=``. Without it, the name pattern of the
    class's TOML source is used. ``path=`` locates the key in the document
    tree as a JSON Pointer (RFC 6901), the same pointer that
    :class:`TOMLSetting` documents. ``aliases=`` declares additional full
    addresses: a load looks up the primary address first, then the aliases in
    their order, and the first one found wins. Every alias is placed under
    the same ``path=``.

    The keyword parameters after ``aliases=`` are the declared value
    constraints (``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, ``when``). They are the same constraints that
    :func:`~advexp.settings_base.setting.setting` documents, and they are
    applied wherever a value reaches the member.
    """
    return TOMLSetting(
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
