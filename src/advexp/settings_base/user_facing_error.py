# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The error serializers raise for conditions that must reach the user."""

from __future__ import annotations


class UserFacingError(Exception):
    """Wraps an error that must reach the user.

    Serializers may raise it (with the original exception as the argument) to
    signal conditions that must not be silently logged and skipped.
    """

    def __init__(self, inner: BaseException) -> None:
        self.inner = inner
        super().__init__(str(inner))
