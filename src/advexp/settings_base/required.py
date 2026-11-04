# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The ``REQUIRED`` marker of members that must get their value from a source."""

from __future__ import annotations


class _Required:
    """Sentinel: the member has no default to serve — a value must arrive."""

    def __repr__(self) -> str:
        return "REQUIRED"


REQUIRED = _Required()
"""The default that makes a member required: its value must come from a
source.

Declared as the default (``default=REQUIRED``). Every boundary that would
serve the default — a load that found nothing usable in the source, a read
of a never-loaded member — raises
:class:`~advexp.settings_base.member_load_error.MemberLoadError`
instead: the load-time reasons are entries of the load pass's aggregate
abort. The family-wide spelling of an optional member is
:data:`~advexp.settings_base.no_default.NO_DEFAULT`: ``None`` stands in,
and its load problems land in the report the loading method returns.
"""
