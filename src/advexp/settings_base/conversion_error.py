# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The load error of a member whose value does not convert."""

from __future__ import annotations

from advexp.settings_base.member_load_error import MemberLoadError


class ConversionError(MemberLoadError):
    """The value of a member did not convert to the annotated type.

    The source had a value for the member, but the value cannot take the
    annotated shape of the member. The error names the member, its setting, and
    the class, and it shows the value and the type to which the value would not
    convert (the value is masked when the member holds a secret). For a
    required member, it is an entry of the load abort
    (:class:`~advexp.settings_base.aggregate_load_error.AggregateLoadError`).
    For an optional member, it is an entry of the load report that the loading
    method returns, and the member stands at its default.
    """
