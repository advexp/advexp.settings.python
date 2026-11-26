# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the pydantic model source.

The source is a pydantic model that the application hands to the chain in
code: ``pydantic_source(AppSettings)`` names a link whose storage is the
model. The layer serves the values of the model's ``model_dump()`` in
Python mode, so native types survive: a ``timedelta`` field arrives as a
``timedelta``, a nested model as a dictionary, which is what a dataclass
member of the class expects. Secret fields (``SecretStr``,
``SecretBytes``) arrive as live wrapper objects, which the common
conversion refuses, so the layer unwraps them on the way in and serves the
plain secret value; the member of the class can then wrap it again by
declaring its own ``SecretStr``.

The dictionary uses member names only. This is the same vocabulary that
every dictionary-based handle of the library uses (``to_dict``,
``update_from_dict``, the load overrides, the mapping source). An explicit
``name=`` and declared ``aliases=`` therefore change nothing here: the
member name is the only key that the link looks up. Keys that name no
member of the class are not served and are dropped, with a debug record.

The model reaches the link in one of two forms. The class form,
``pydantic_source(AppSettings)``, carries the model class: every pass
constructs the model once, lazily, when the first member reaches this
link, so the model resolves its own sources (the environment, a ``.env``
file) anew on every load. A model that fails to construct is a broken
source, like a file that cannot be parsed: the load of the member that
reached the link fails with the model's validation error, and sources
below the link never hide it. The instance form,
``pydantic_source(AppSettings(secrets_dir=...))``, carries the values of
the one given instance, resolved once at the declaration: a frozen layer
for values that the class form cannot build itself, such as constructor
arguments and secret directories.

The source is read-only: it responds to ``load`` and ``contains``. The
write operations of the serializer contract refuse with an error (a
``UserFacingError`` around a ``NotImplementedError`` that names the
source), and the facade of the package never calls them.
"""

from __future__ import annotations

import collections.abc
import copy
from typing import Any, Dict, Mapping, Optional, Tuple, Type

from pydantic import BaseModel, SecretBytes, SecretStr, ValidationError

from advexp.configuration.plugin_api import (
    NOT_FOUND,
    PACKAGE_NAME,
    ISettingAttribute,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.source_link_sink_interface import ISourceLinkSink

MODEL_CLASS_PARAM = "model_class"
"""The link parameter carrying the model class that the link reads."""

MODEL_VALUES_PARAM = "model_values"
"""The link parameter carrying the values of a frozen model instance."""


class PydanticSourceSerializer(SettingsBaseSerializer, ISourceLinkSink):
    """Serves members from the values of the link's pydantic model.

    The values are the own copy of the link: the builder froze them at the
    call for the instance form, and the class form builds them once per
    pass from a fresh construction of the model. The value that a load
    finds is served as a deep copy, which gives the same isolation as the
    snapshots of the class.
    """

    def __init__(self) -> None:
        super().__init__()
        # name-mangled: the link's state, dispatched through self,
        # kept out of a subclass's reach
        self.__model_class: Optional[Type[BaseModel]] = None
        self.__values: Mapping[str, Any] = {}
        # True for the instance form: the values were frozen at the
        # declaration and no pass rebuilds them
        self.__frozen = False
        # True when __values is ready to serve: set by the delivery for the
        # frozen form, by the first lookup of a pass for the class form
        self.__built = False

    # -- ISourceLinkSink -------------------------------------------------------

    def set_source_link(self, link: SourceLink) -> None:
        """``ISourceLinkSink`` delivery: the link that this source reads.

        The model of the link is the storage itself. The frozen form reads
        its values once, here; the class form keeps the class and builds
        the values per pass, lazily, when a load first reaches the link.
        """
        model_class = link.param(MODEL_CLASS_PARAM, default=None)
        self.__model_class = model_class if isinstance(model_class, type) else None
        values = link.param(MODEL_VALUES_PARAM, default=None)
        if values is None:
            self.__values = {}
            self.__frozen = False
            self.__built = False
        else:
            self.__values = values if isinstance(values, collections.abc.Mapping) else {}
            self.__frozen = True
            self.__built = True

    # -- own helpers -----------------------------------------------------------

    def __ensure_values(self) -> None:
        """Build the values of the class form: one construction per pass.

        The construction is lazy on purpose. A model that fails validation
        is a broken source, and a broken source ends the search for the
        member that reached it; members that earlier links already served
        never get here and keep loading. The pass caches the result, so one
        load constructs the model at most once, whatever the number of
        members that read the link.
        """
        if self.__built or self.__model_class is None:
            return
        try:
            model = self.__model_class()
        except ValidationError as error:
            raise UserFacingError(
                ValueError(
                    f"{PACKAGE_NAME}: cannot construct the pydantic model "
                    f"{self.__model_class.__name__} of the pydantic source: {error}"
                )
            ) from error
        self.__values = _model_values(model)
        self.__built = True
        self.__report_foreign_keys()

    def __report_foreign_keys(self) -> None:
        # name the model's keys no member answers to, once per pass — the
        # reader debugging an empty load learns the difference between a
        # miss and a key the class never reads
        members: Dict[str, Any] = self.context.settings_class.__settings_members__
        for key in self.__values:
            if key not in members:
                self.context.logger.debug(
                    "the pydantic model source contains the key %r, which does not "
                    "match any member of '%s'; ignoring it",
                    key,
                    self.context.settings_class.__name__,
                )

    # -- ISettingsSerializer ---------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        self.__ensure_values()
        name = attr.bound_name if attr is not None else None
        if name is not None and name in self.__values:
            return copy.deepcopy(self.__values[name])
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """Refused with an error: a read-only source never writes.

        The facade of the package never calls this operation, so a caller that
        reaches it has mistaken the source for a storage backend. The refusal says
        so, instead of a silent no-op that would hide the bug.
        """
        raise UserFacingError(
            NotImplementedError(
                f"the pydantic model source is read-only: it loads and never "
                f"writes ({PACKAGE_NAME})"
            )
        )

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """Refused with an error: a read-only source never deletes.

        The facade of the package never calls this operation, so a caller that
        reaches it has mistaken the source for a storage backend. The refusal says
        so, instead of a silent no-op that would hide the bug.
        """
        raise UserFacingError(
            NotImplementedError(
                f"the pydantic model source is read-only: it loads and never "
                f"deletes ({PACKAGE_NAME})"
            )
        )

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        self.__ensure_values()
        name = attr.bound_name if attr is not None else None
        return name is not None and name in self.__values

    # -- ISettingNameDescriber -------------------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """``member name '<name>'``: the only address that this storage has.

        The model knows member names and nothing else, so the phrase names
        the key in the same way, whatever the declarations of the member say
        elsewhere.
        """
        if attr is None:
            return None
        return f"member name '{attr.bound_name}'"

    # -- ISourceDescriber ------------------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """``("the pydantic model source", <model>)``: the model that this link
        reads. It is not a file, so the designation carries the model's name
        in the place where a file source names its path.
        """
        model = self.__model_class
        return "the pydantic model source", model.__name__ if model is not None else None

    # -- ISerializerNotificationSink -------------------------------------------

    def on_start_load_settings(self) -> None:
        # the pass opened: the class form constructs its model again, once,
        # by the first member that reaches this link; the frozen form keeps
        # the values of its instance and only reports its foreign keys
        if self.__frozen:
            self.__report_foreign_keys()
        else:
            self.__built = False


def _model_values(model: BaseModel) -> Dict[str, Any]:
    """The values of ``model`` as the layer serves them.

    ``model_dump()`` in Python mode keeps native types and turns nested
    models into dictionaries. Secret wrappers it keeps as live objects,
    which the common conversion refuses, so the walk unwraps them: a
    ``SecretStr`` or ``SecretBytes`` anywhere in the tree becomes its plain
    secret value, and the member of the class decides, by its own
    annotation, whether to wrap it again.
    """
    return _plain_value(model.model_dump())


def _plain_value(value: Any) -> Any:
    if isinstance(value, (SecretStr, SecretBytes)):
        return value.get_secret_value()
    if isinstance(value, collections.abc.Mapping):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    return value
