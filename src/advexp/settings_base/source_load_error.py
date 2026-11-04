# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The load error of a member whose source raised while loading."""

from __future__ import annotations

from advexp.settings_base.member_load_error import MemberLoadError


class SourceLoadError(MemberLoadError):
    """The source of a member raised an error while loading its value.

    The message names the member, its setting, and the class, and it carries the
    own error of the source (which also stays chained as the cause).

    The handling depends on the kind of error and on the member:

    - A source that reports its problems through the user-facing channel (a
      corrupt or an unreadable file) is handled in the same way on a required
      member, with its exception carried in the message. On an optional member,
      it keeps propagating as its own exception, because a served default must
      not hide it.
    - A plain error of the source (whatever the backend raised without wrapping
      it) is an entry of the load report that the loading method returns for an
      optional member, next to the log record that the pass keeps.
    """
