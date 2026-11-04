# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Member-name extraction from getter lambdas.

A setting getter is an *unexecuted* lambda: the member name is read out of
it, and anything other than a plain member access is ignored. A lambda
carries its compiled bytecode, and the strict shape ``lambda s: s.member``
compiles to an exact instruction sequence on every supported CPython (3.9
lacks the leading ``RESUME``):

```text
RESUME
LOAD_FAST   s
LOAD_ATTR   member
RETURN_VALUE
```

Anything else is rejected with a ``TypeError`` that names the accepted
shape. Examples are calls, arithmetic, nested attributes, closures, and
extra arguments. This way, an accidental misuse fails loudly, instead of
silently targeting the wrong setting.
"""

from __future__ import annotations

import dis
import inspect
import types
from typing import Any, Callable, Optional, Union

_Getter = Callable[[Any], Any]
"""A ``lambda s: s.<member>``; it is never called, only inspected."""

SettingRef = Union[str, _Getter]
"""A setting reference: the member name or a getter lambda for it."""

# instructions that carry no meaning for the shape check — the 3.11+
# prologue and the inline-cache slots; the disassembly hides the caches by
# default, and the filter below is a guard
_NOISE_OPCODES = frozenset({"RESUME", "CACHE"})
# local-load opcodes across supported CPython versions: LOAD_FAST_BORROW and
# LOAD_FAST_READONLY split off from LOAD_FAST in 3.14
_LOAD_FAST_OPCODES = frozenset({"LOAD_FAST", "LOAD_FAST_BORROW", "LOAD_FAST_READONLY"})


def _bad_ref(setting: Any) -> TypeError:
    return TypeError(
        "a setting must be referenced by its member name string or by a getter "
        f"lambda 'lambda s: s.<member>'; got {setting!r}"
    )


def _member_name_from_getter(getter: _Getter) -> str:
    """Return the member name that a getter lambda refers to.

    Raises ``TypeError`` for anything that is not exactly ``lambda s: s.member``
    (one plain attribute load on the single argument).
    """
    code: Optional[types.CodeType] = getattr(getter, "__code__", None)
    if code is None:
        # a plain value (e.g. ServerSettings.port) or a non-lambda callable
        raise _bad_ref(getter)
    if (
        code.co_argcount != 1
        or code.co_kwonlyargcount
        or code.co_flags & (inspect.CO_VARARGS | inspect.CO_VARKEYWORDS)
        or code.co_freevars
        or getattr(getter, "__defaults__", None)
        or getattr(getter, "__kwdefaults__", None)
    ):
        raise _bad_ref(getter)
    instructions = [i for i in dis.get_instructions(code) if i.opname not in _NOISE_OPCODES]
    if (
        len(instructions) != 3
        or instructions[0].opname not in _LOAD_FAST_OPCODES
        or instructions[1].opname != "LOAD_ATTR"
        or instructions[2].opname != "RETURN_VALUE"
    ):
        raise _bad_ref(getter)
    name = instructions[1].argval
    assert isinstance(name, str)  # LOAD_ATTR argval is the co_names entry
    return name


def resolve_setting_name(setting: SettingRef) -> str:
    """Normalize a setting reference to the member name string."""
    if isinstance(setting, str):
        return setting
    return _member_name_from_getter(setting)
