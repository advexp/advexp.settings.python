# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The load error of a required member whose source provided no value."""

from __future__ import annotations

from advexp.settings_base.member_load_error import MemberLoadError


class MissingValueError(MemberLoadError):
    """The load error of a member for which the source provided no value.

    For a required member, this error goes into the ``errors`` of the load
    abort. An optional member treats a miss as the normal way of serving its
    default. Its miss error is attached only to an abort, in the ``misses`` of
    the aggregate, and it stays out of the report of a successful run.

    The error is an entry of the load abort
    (:class:`~advexp.settings_base.aggregate_load_error.AggregateLoadError`).
    The message names the member, its storage name, and the class, so the reader
    knows exactly what to provide. The storage name is the own spelling of the
    source when it offers one (for example, the name of an environment
    variable), and otherwise it is the storage name that the pattern built.
    """
