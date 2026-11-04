# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The setting attribute of the dotenv file backend."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from advexp.settings.plugin_api import NO_DEFAULT, SettingsAttribute


class DotenvSetting(SettingsAttribute):
    """Setting attribute: the value is stored in a variable of a ``.env`` file."""


def dotenv_setting(
    *,
    name: Optional[str] = None,
    default: Any = NO_DEFAULT,
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
    """Declare a dotenv-file setting. This is the type-checker-friendly spelling
    of ``DotenvSetting``.

    It is the same attribute with the same keyword parameters. Only the
    spelling differs, and the reason for it is typing. Assigning an attribute
    instance to an annotated member is valid Python (the settings metaclass
    replaces it with a value descriptor), but type checkers cannot see the
    replacement and report a type mismatch. They accept a plain function that
    returns ``Any``, and the ``Any`` also prevents a default in storage form
    (``default="8080"`` for an ``int`` member) from being flagged.

    ``aliases=`` declares additional full variable names. A load looks up the
    primary name first, then the aliases in their order, and the first name
    found wins.

    The keyword parameters after ``aliases`` are the declared value constraints
    (``gt/ge/lt/le/eq/ne``, ``min_length/max_length``, ``regex``,
    ``validator``, ``when``). They are the same constraints that
    :func:`~advexp.settings.setting` documents, and they are applied wherever a
    value reaches the member.
    """
    return DotenvSetting(
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
