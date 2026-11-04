# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The letter-case regime of the member-name part of an environment name."""

from __future__ import annotations

from enum import Enum


class NameCase(str, Enum):
    """The letter-case regime of the member-name part of an environment name.

    This is the spelling of the ``name_case`` option in code:
    ``name_case=NameCase.UPPER``.

    - ``UPPER`` and ``LOWER`` change the case of the member name in every built
      name.
    - ``ANY`` leaves the built name as declared, and makes its lookup
      case-insensitive instead.

    It is a ``str`` enum, because its members also serve as the values of the
    stored data form. The class metadata keeps the plain
    ``"upper"``/``"lower"``/``"any"`` strings, and the raw metadata channel (a
    hand-written entry, or a runtime ``set_class_metadata`` call) accepts both
    spellings. A member compares equal to its string.
    """

    UPPER = "upper"
    LOWER = "lower"
    ANY = "any"
