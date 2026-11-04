# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The bytes wrapper that keeps its value out of prints and messages."""

from __future__ import annotations

_MASK = "**********"


class SecretBytes:
    """Bytes whose ``repr`` and ``str`` return the mask, not the value.

    This is the annotated type of a member that carries a secret. Loading wraps
    the payload of the source into it (a string is encoded as UTF-8, as the bytes
    conversion does). A casual print, a log record, or an error message
    therefore shows ``'**********'``. The only way to get the value is
    :meth:`get_secret_value`, which is an explicit step that is easy to grep for.

    The constraint checks look at the inner payload, while their messages keep
    the mask. The storage form is the plain bytes: the save path unwraps the
    value before the serializers see it. The masking is carried by the wrapper:
    plain bytes that are assigned to the member keep the semantics of plain
    bytes.
    """

    __slots__ = ("_value",)

    def __init__(self, value: bytes) -> None:
        self._value = value

    def get_secret_value(self) -> bytes:
        """Return the wrapped value. This call is the explicit step to take, and it is
        easy to grep for.
        """
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}(b'{_MASK}')"

    def __str__(self) -> str:
        return _MASK

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecretBytes):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)
