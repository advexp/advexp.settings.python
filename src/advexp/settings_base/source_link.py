# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""One link of a source chain.

A link is the unit through which a layered class resolves its members. The
builder that the source family of a package spells (``json_source(file=...)``
and the like) gives the ``class`` statement one link, and the chain
:class:`~advexp.settings_base.sources.Sources` carries the links in their
order.

The link itself is plain data:

- the attribute class that names the family (the same class that the member
  factory of the family builds, so the chain and the factories use one
  family name);
- the serializer class, when the family knows it outright;
- the own parameters of the link: the file and the subtree of a file link,
  or the mapping of a mapping link.

Everything that a backend reads from its link arrives through these
parameters, and nothing about a link is stored anywhere else.

A link with no ``attribute_class`` serves no family. Every member factory
skips it, and only the neutral members (the plain declarations and the rich
spelling of the chain) read through it.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Type

from advexp.settings_base.context import SettingsContext
from advexp.settings_base.family_boundaries import settings_family
from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.settings_serializer_wishes_interface import (
    ISettingsSerializerWishes,
)
from advexp.settings_base.source_link_sink_interface import ISourceLinkSink


class SourceLink:
    """One link of a source chain: a family, a serializer, and the own parameters
    of the link.

    The source builders of a package construct links, and an application never
    builds one by hand.

    - ``attribute_class`` names the family that the link serves. It is the class
      that the member factory of the family builds, so a member that is declared
      through that factory reads this link and no other. ``None`` means that the
      link serves no family: only the neutral members read through it.
    - ``serializer_class``, when given, is the serializer that the link runs,
      after a registered subclass of the member asks for its own. Without it,
      the machinery resolves the serializer that is registered for
      ``attribute_class``, in the same registry that the non-layered pass uses.
    - ``params`` carries everything that the serializer reads from the link. The
      builders of the family fill it, the serializer of the family reads it, and
      no other code touches it.
    """

    def __init__(
        self,
        attribute_class: Optional[Type[Any]] = None,
        serializer_class: Optional[Type[ISettingsSerializer]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.__attribute_class = attribute_class
        self.__serializer_class = serializer_class
        self.__params: Mapping[str, Any] = dict(params) if params else {}

    @property
    def attribute_class(self) -> Optional[Type[Any]]:
        """The attribute class naming the family this link serves.

        ``None`` for a family-less link: a member factory never matches
        it, and the neutral members read through it.
        """
        return self.__attribute_class

    @property
    def serializer_class(self) -> Optional[Type[ISettingsSerializer]]:
        """The serializer class that the link carries, when the builder of its
        family spelled one.

        ``None`` for a link whose serializer resolves through the registry.
        A rebuild of the link carries the class over, so that the copy serves
        its members exactly as the original did.
        """
        return self.__serializer_class

    @property
    def params(self) -> Mapping[str, Any]:
        """The link's own parameters, as the family's builder spelled them."""
        return dict(self.__params)

    def param(self, name: str, default: Any = NO_DEFAULT) -> Any:
        """Read one link parameter; ``default`` when the link has none.

        A missing parameter with no ``default`` raises ``KeyError``, the way a
        plain dictionary lookup does; ``default`` serves the fallback instead.
        """
        if name not in self.__params:
            if default is NO_DEFAULT:
                available = ", ".join(sorted(self.__params)) or "none"
                raise KeyError(
                    f"'{name}' is not a parameter of the source link; "
                    f"available parameters: {available}; "
                    "pass default= to serve a fallback"
                )
            return default
        return self.__params[name]

    def serves(self, attribute: Any) -> bool:
        """Return whether a member that is declared through ``attribute`` reads this
        link.

        A family link serves the attributes of its family: the members that its
        ``attribute_class`` accepts, including a registered subclass. A link without
        a family serves none of them. Only the neutral members read through such a
        link, and the machinery routes them by its own rule.
        """
        if self.__attribute_class is None:
            return False
        return isinstance(attribute, self.__attribute_class)

    def serializer(
        self, context: SettingsContext, attribute_class: Optional[Type[Any]] = None
    ) -> ISettingsSerializer:
        """Build the serializer of this link, bound to the context of the pass.

        ``attribute_class`` names the own attribute class of the member when it
        differs from the family of the link. The serializer is resolved in three
        steps: a registered subclass of the family runs its own registered
        serializer first; then the serializer class that the link itself carries
        decides — this is how the links of the shared families bring the
        serializer of their package, one member class of a family being read by
        two distributions; and the registry for the family class of the link is
        the last resort, the same resolution the non-layered pass uses.

        The context is delivered in the same way as every pass delivers it, and the
        link follows it. A serializer that implements
        :class:`~advexp.settings_base.source_link_sink_interface.ISourceLinkSink`
        also receives this link. This is how the serializer of a family reads the
        file, the subtree, and the naming of the link.
        """
        family = settings_family(context.settings_class)
        factory = None
        if attribute_class is not None:
            factory = LibraryConfiguration._get_serializer_factory(attribute_class, family)
        if factory is None:
            factory = self.__serializer_class
        if factory is None and self.__attribute_class is not None:
            factory = LibraryConfiguration._get_serializer_factory(self.__attribute_class, family)
        if factory is None:
            named = (
                "the family's attribute"
                if self.__attribute_class is None
                else (f"'{self.__attribute_class.__name__}'")
            )
            raise ValueError(
                f"the source link has no serializer to run: no serializer_class was "
                f"given, and none is registered for {named}. Import the family's "
                "plugin module to enable it"
            )
        serializer = factory()
        if isinstance(serializer, ISettingsSerializerWishes):
            serializer.set_serializer_params(context)
        if isinstance(serializer, ISourceLinkSink):
            serializer.set_source_link(self)
        return serializer

    def __repr__(self) -> str:
        family = (
            self.__attribute_class.__name__ if self.__attribute_class is not None else "neutral"
        )
        return f"SourceLink({family})"
