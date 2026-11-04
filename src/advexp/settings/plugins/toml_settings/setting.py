# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The setting attribute of the TOML file backend."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings.plugin_api import NO_DEFAULT, SettingsAttribute
from advexp.settings_base.pointer import pointer_steps


class TOMLSetting(SettingsAttribute):
    """Setting attribute: the value is stored in the TOML settings file.

    ``name=`` is the address of the setting in the document. Every dot in the
    name (the table separator of TOML) separates a table level, and the last
    part is the key. For example, ``name="net.host"`` stores the key inside the
    ``[net]`` table, and a name without a dot is a plain key. Without a name,
    the ``{module}.{class}.{member}`` pattern is used, and its dots nest in the
    same way. A literal key that contains a dot is reached through ``path=``,
    because the segments of a pointer are never split.

    The optional ``path=`` locates the key in the document tree as a JSON
    Pointer (RFC 6901): a leading ``/`` and slash-separated segments, where
    ``~1`` escapes ``/`` and ``~0`` escapes ``~``. For example:

    - ``path="/net/proxy"`` stores the setting inside ``[net.proxy]``.
    - ``path="/mirrors/1"`` stores it inside the second element of the
      ``mirrors`` array.
    - ``path="/endpoints/api.internal"`` stores it under a key that contains a
      dot.

    A segment that consists only of digits indexes an array if the node it
    steps into is an array, and names a table key otherwise. ``path=""`` and
    ``path=None`` both mean the document root.
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = NO_DEFAULT,
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
    default: Any = NO_DEFAULT,
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
    """Declare a TOML-file setting. This is the type-checker-friendly spelling of
    ``TOMLSetting``.

    It builds exactly the attribute that the class builds, with the same
    keyword parameters. Both spellings exist because of typing. Assigning an
    attribute instance to an annotated member
    (``port: int = TOMLSetting(...)``) is valid Python (the settings metaclass
    replaces the attribute with a value descriptor), but type checkers cannot
    see the replacement and report a type mismatch. They accept a plain
    function that returns ``Any``. The ``Any`` return also leaves ``default=``
    unchecked, deliberately: a default may be given in its storage form
    (``default="4"`` for an ``int`` member), and it is converted at class
    creation, where a default that cannot be converted makes the ``class``
    statement fail.

    ``aliases=`` declares additional full storage addresses. A load looks up
    the primary address first, then the aliases in their order, and the first
    address found wins. Every alias is placed under the same ``path=`` and is
    nested by its own dots.

    The keyword parameters after ``aliases`` are the declared value constraints
    (``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, ``when``). They are the same constraints that
    :func:`~advexp.settings.setting` documents, and they are applied wherever a
    value reaches the member.
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
