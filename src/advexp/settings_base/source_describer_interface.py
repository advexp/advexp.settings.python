# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Source describer."""

from __future__ import annotations

import abc
from typing import Optional, Tuple

from advexp.settings_base.setting_attribute_interface import ISettingAttribute


class ISourceDescriber(abc.ABC):
    """Name the backend itself, for messages that a human reads.

    This is a serializer capability that the load diagnostics quote in their
    causes. Instead of the faceless ``its source provided no value``, the
    reader learns which storage came up empty: ``the process environment
    provided no value``, ``the JSON file raised ...``.

    Together with
    :class:`~advexp.settings_base.setting_name_describer_interface.ISettingNameDescriber`,
    this is the side of the backend in the diagnostics. That interface spells
    the storage address of the setting, and this one names the storage that
    holds it.

    The designation reports only the facts: the phrase for the storage and its
    exact file. The caller lays them out. Next to an address that already names
    the file, the phrase stands alone, so a message never reads the path twice.

    :class:`~advexp.settings_base.settings_base_serializer.SettingsBaseSerializer`
    implements this interface with a ``None`` default, which means the unnamed
    spelling ``its source``. A backend that derives from it overrides this one
    method. The interface itself is the contract for a backend that is built on
    :class:`~advexp.settings_base.settings_serializer_interface.ISettingsSerializer`
    alone, and it is probed through ``isinstance``.
    """

    @abc.abstractmethod
    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Return the own designation of the backend, which the load causes quote.

        ``attr`` is the attribute of the member. A backend whose place depends on
        the class (for example, a file binding) resolves it through the context. It
        is ``None`` for an entry of dynamic settings.

        The result is a pair:

        - the phrase for the storage: a short noun phrase with its article (``the
          process environment``, ``the JSON file``);
        - its exact file, as the full path on disk (a relative binding addresses a
          place in the working directory, and the message must name the file
          itself). The path is ``None`` for a storage that is not a file.

        The caller composes the two. Next to the address of a setting that already
        names the file, the phrase stands alone. When there is no address (``attr``
        is ``None``, a dynamic entry), the phrase carries the path. If the whole
        result is ``None``, the backend has no designation, and the caller says
        ``its source`` instead.

        The naming is a best effort of the caller: a describe call that itself
        breaks degrades to the unnamed spelling, instead of disturbing the load
        that it reports on.
        """
