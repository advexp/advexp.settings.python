# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Readable spellings of annotated types for error messages."""

from __future__ import annotations

import types
import typing
from typing import Any

_UnionType = getattr(types, "UnionType", None)

# the typing spelling of the built-in containers: the declarations of the
# family use it, and it keeps its look on every Python version, where the
# raw alias objects print as ``typing.List[int]`` or change with the
# runtime's own fashion
_CONTAINER_NAMES = {dict: "Dict", frozenset: "Frozenset", list: "List", set: "Set", tuple: "Tuple"}


def type_display(value: Any) -> Any:
    """The readable spelling of a type for error messages.

    A class shows as its name (``int``, not ``<class 'int'>``); a typing
    form shows in the bracketed spelling of its declaration —
    ``Optional[datetime]``, ``List[int]``, ``Literal['a', 'b']`` — stable
    across Python versions, never the ``typing.`` machinery the raw
    objects print. A non-type value still shows as itself.
    """
    return _display(_unwrap_annotated(value))


def _unwrap_annotated(annotation: Any) -> Any:
    while typing.get_origin(annotation) is typing.Annotated:
        annotation = typing.get_args(annotation)[0]
    return annotation


def _display(annotation: Any) -> Any:
    origin = typing.get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", annotation)
    args = typing.get_args(annotation)
    if origin is typing.Literal:
        return f"Literal[{', '.join(repr(item) for item in args)}]"
    if origin is typing.Union or (_UnionType is not None and origin is _UnionType):
        if len(args) == 2 and args[1] is type(None):
            return f"Optional[{_display(args[0])}]"
        return f"Union[{', '.join(_display(arg) for arg in args)}]"
    name = _CONTAINER_NAMES.get(origin, getattr(origin, "__name__", str(origin)))
    return f"{name}[{', '.join(_display(arg) for arg in args)}]"
