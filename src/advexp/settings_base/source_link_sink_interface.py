# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The source link sink: a serializer's seat for its link's parameters."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from advexp.settings_base.source_link import SourceLink


class ISourceLinkSink(abc.ABC):
    """Receive the link that a serializer serves in a layered class.

    This is a serializer capability that the chain machinery delivers. A backend
    that runs as a link of a
    :class:`~advexp.settings_base.sources.Sources` chain reads its file, its
    subtree, and its naming from the link, not from the own bindings of the
    class, which a layered class does not have.

    The delivery happens right after the delivery of the context and before the
    first storage call, so the link is in place by the time a load asks for a
    value. A backend that never runs as a link never sees this call, and the
    bindings of its class keep governing it as before. The interface is a seat
    for the link, not an obligation.
    """

    @abc.abstractmethod
    def set_source_link(self, link: "SourceLink") -> None:
        """Take delivery of the link that this serializer serves.

        The :meth:`~advexp.settings_base.source_link.SourceLink.params` property of
        the link already serves a fresh copy on every read. An implementation
        therefore keeps the link itself and reads its parameters on every pass, so a
        link that was reconfigured reaches the next resolution without a new
        delivery.
        """
