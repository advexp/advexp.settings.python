# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The parent error of the reasons why a member's load produced no valid
value."""

from __future__ import annotations

from typing import Optional


class MemberLoadError(ValueError):
    """A member could not get a valid value from its source.

    This is the parent of the load-time reasons: the source provided no value,
    a value that cannot be converted, a constraint violation, or a failed source.
    It is also the parent of the aggregate abort of the load pass.

    Where the reason is unknown, the error is raised directly. For example,
    reading a member that was never loaded serves its default, and a member that
    is declared :data:`~advexp.settings_base.required.REQUIRED` has none to
    serve.

    The error names a problem, not a policy: the declaration of a member decides
    the channel. The load error of a required member is an entry of the load
    abort. The load error of an optional member is an entry of the load report
    that the loading method returns, and the member itself stands at its default.
    Subclassing :class:`ValueError` keeps a plain ``except ValueError`` working:
    the value errors of the family are all subclasses of ``ValueError``.

    ``member_name`` carries the member that the error is about, when the one who
    raises the error knows it. The required-read error of the member descriptor
    always knows it, so a handler can report the finding on that member without
    parsing the message. Errors that are raised without it leave it ``None``.
    """

    def __init__(self, message: str, member_name: Optional[str] = None) -> None:
        super().__init__(message)
        self.member_name = member_name
