# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The lookup of a built environment name in the namespace of one source.

``name_case=NameCase.ANY`` changes the lookup, not the name. The name is
built as declared, and the namespace is searched for any spelling of it. The
exact spelling wins over spellings that differ in case. Two spellings that
differ in case, with no exact spelling among them, cannot be told apart, so
the helper names both instead of choosing silently: the iteration order of
a process environment is not something to build value resolution on.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from advexp.settings_base.environment_options import NAME_CASE, NameCase
from advexp.settings_base.user_facing_error import UserFacingError


def environment_key(
    namespace: Mapping[str, str],
    name: str,
    options: Mapping[str, Any],
    source: str,
) -> Optional[str]:
    """Return the key under which ``name`` lives in ``namespace``; ``None`` if it is
    absent.

    The exact spelling is served as it is, whatever the case option of the
    family says. Under ``NameCase.ANY``, a spelling that differs in case is
    served too. If there are two such spellings and no exact one among them, the
    function raises
    :class:`~advexp.settings_base.user_facing_error.UserFacingError` that names
    ``source`` and both keys: the machinery must not choose which one holds the
    value. Under the other case options, the lookup stays exact.
    """
    if name in namespace:
        return name
    if options.get(NAME_CASE) != NameCase.ANY:
        return None
    folded = name.casefold()
    matches: List[str] = [key for key in namespace if key.casefold() == folded]
    if len(matches) > 1:
        spellings = " and ".join(repr(key) for key in sorted(matches))
        raise UserFacingError(
            ValueError(
                f"{source} holds two differently-cased spellings of the "
                f"environment variable ({spellings}); the lookup cannot "
                f"choose between them — remove one spelling or set "
                f"{NAME_CASE} to the exact case"
            )
        )
    return matches[0] if matches else None
