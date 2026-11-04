# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The JSON Pointer mechanics that are shared by the file backends.

The ``path=`` of a setting attribute of a file backend locates the key of the
setting in the document tree as a JSON Pointer (RFC 6901): a leading ``/``
and slash-separated reference tokens, each unescaped as the standard says
(``~1`` is ``/``, and ``~0`` is ``~``). The spelling is the same for every
self-describing document format in which the family stores settings: the
pointer names a place in the tree, and the format decides what a node looks
like.

The parser, the rule for array positions, and the display form therefore
live here once, next to the other shared vocabulary. The ``path=`` of every
backend is validated through :func:`pointer_steps`, and the storage walks of
the backend step through the segments that this function returns. Whether a
token that consists only of digits names an array position or an object key
is decided by the node that it steps into, not by the syntax.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

_ARRAY_INDEX = re.compile(r"0|[1-9][0-9]*")
"""The segments that may name an array position — RFC 6901 array indexes
only, so ``"01"`` and similar values stay object keys, never positions."""


def array_index(segment: str) -> Optional[int]:
    """The array position a digits-only segment names, or ``None``."""
    if _ARRAY_INDEX.fullmatch(segment):
        return int(segment)
    return None


def pointer_steps(path: str) -> List[str]:
    """Return the validated location segments of a ``path=`` value, which is a JSON
    Pointer.

    The path follows RFC 6901: a leading ``/`` and slash-separated reference
    tokens, each unescaped as the standard says (``~1`` is ``/``, and ``~0`` is
    ``~``). For example, ``"/net/proxy"`` is parsed into ``["net", "proxy"]``,
    and ``"/mirrors/1"`` into ``["mirrors", "1"]``. Whether a segment that
    consists only of digits names an object key or an array position is decided
    by the node that it steps into, not by the syntax. The empty string is the
    empty pointer (the document root), in the same way as ``None``.
    """
    if not path:
        return []
    if not path.startswith("/"):
        raise ValueError(
            f"Invalid path {path!r}: a JSON Pointer path must start with '/' "
            "(path=None or path='' means the document root)"
        )
    # ~1 before ~0: "~01" must unescape into "~1", not into "/"
    return [token.replace("~1", "/").replace("~0", "~") for token in path.split("/")[1:]]


def pointer_display(segments: Sequence[str]) -> str:
    """The slash form of a location, for error messages."""
    return "/" + "/".join(segments)
