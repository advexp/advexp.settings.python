# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The load error of a member whose value violates its constraints."""

from __future__ import annotations

from advexp.settings_base.member_load_error import MemberLoadError


class ConstraintViolationError(MemberLoadError):
    """The value of a member violates the constraints that are declared on it.

    The value was converted, but the own declared bounds of the member, or a
    rule across members, reject it. The error names the member, its setting,
    and the class, and it lists every violated constraint. For a required
    member, it is an entry of the load abort
    (:class:`~advexp.settings_base.aggregate_load_error.AggregateLoadError`).
    For an optional member, it is an entry of the load report that the loading
    method returns, and the member stands at its default.
    """
