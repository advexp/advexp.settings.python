# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The result of one source builder: a link and its side entries.

The source builder of a package (``json_source(file=...)`` and the like)
returns this object, and the application passes it to the ``class``
statement. It can be passed alone, for a chain of one link, or inside
:class:`~advexp.settings_base.sources.Sources`, for a layered chain.

The binding carries three things:

- the :class:`~advexp.settings_base.source_link.SourceLink` itself;
- the side metadata entries that the link declares next to the chain (for
  example, the naming of the environment family, when this link is the one
  that declares it);
- the name of the distribution whose builder created it. This is the same
  stamp that the option helpers carry, and it keeps the declarations of the
  two distributions apart at the ``class`` statement.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from advexp.settings_base.source_link import SourceLink


class SourceBinding:
    """The result of a source builder: one link, its side entries, and its stamp.

    The builders of the packages create it, and an application never constructs
    one.

    - ``link`` is the link of the chain proper.
    - ``extras`` are the metadata entries that the link declares next to the
      chain (for example, the environment naming dictionary, when an
      environment link is the one that declares it). They are stored under
      their own family keys, in the same way as the helpers of the families
      store them.
    - ``family`` is the stamp: the name of the distribution whose builder
      created the binding. It is checked against the family of the class at the
      ``class`` statement.
    """

    def __init__(
        self,
        link: SourceLink,
        extras: Optional[Mapping[str, Any]] = None,
        family: Optional[str] = None,
    ) -> None:
        self.__link = link
        self.__extras: Mapping[str, Any] = dict(extras) if extras else {}
        self.__family = family

    @property
    def link(self) -> SourceLink:
        """The chain link this binding contributes."""
        return self.__link

    @property
    def extras(self) -> Mapping[str, Any]:
        """The metadata entries declared beside the chain by this link."""
        return dict(self.__extras)

    @property
    def family(self) -> Optional[str]:
        """The distribution whose builder built this binding; ``None`` for
        a hand-built one, which no family check refuses."""
        return self.__family
