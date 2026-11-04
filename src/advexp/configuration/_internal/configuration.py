# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The configuration base class.

Subclass :class:`Configuration`, declare the class's source chain in the
``options=`` keyword of the ``class`` statement, and declare the members,
either plainly (a bare annotation for a required member, an annotated
assignment for a member with a default) or through a family factory. Then
load the class through its chain. The values are stored per class and are
never written back to the sources::

    class AppConfig(
        Configuration,
        options=Sources(env_source(...), json_source(file="app.json")),
    ):
        token: str
        session_ttl: timedelta = timedelta(minutes=30)

    AppConfig.load_configuration()
    print(repr(AppConfig.session_ttl))

Members are declared in exactly the same way as in :mod:`advexp.settings`:
the same attribute class conventions, the same constraints, the same
conversion of the values that a source hands over, and the same load
behavior. The difference is the direction. A settings class reads from and
writes to its storages, while a configuration class only reads its
sources. Only a load writes the values: assigning to a declared member, on
the class or on an instance, raises ``TypeError``.

A member declared without ``default=`` is required: it must get its value
from a source. If a load finds nothing usable for it, the load raises one
:class:`~advexp.configuration.AggregateLoadError` with an entry for each
failed member (:class:`~advexp.configuration.MissingValueError` and its
sibling classes, all subclasses of
:class:`~advexp.settings_base.member_load_error.MemberLoadError`).

The ``default`` parameter of the bundled sources is itself
:data:`~advexp.settings_base.required.REQUIRED`, the sentinel that states
this explicitly. Declaring
:data:`~advexp.settings_base.no_default.NO_DEFAULT` instead keeps the
family-wide meaning: the member is optional, ``None`` stands in for it, and
its load problems go into the report that :meth:`load_configuration`
returns instead of aborting the load.
"""

from __future__ import annotations

import copy
import logging
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple, Type, TypeVar, cast

from advexp.configuration._internal import pipeline
from advexp.configuration._internal.configuration_attribute import ConfigurationAttribute
from advexp.configuration._internal.configuration_meta import ConfigurationMeta
from advexp.configuration._internal.package_name import PACKAGE_NAME
from advexp.settings_base.context import SettingsContext
from advexp.settings_base.instance_values import INSTANCE_VALUES_ATTR, instance_values
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.settings_base_plugin import PluginT

_T = TypeVar("_T", bound="Configuration")


class Configuration(metaclass=ConfigurationMeta):
    """Base class for read-only application configuration.

    All operations are class-level: the configuration class itself is the
    singleton. Instances are supported for reads, but they share the class
    storage. :meth:`to_object` copies the values out to a detached instance of
    the class, and :meth:`to_dict` copies them to a read-only mapping.

    Sources are only ever read. There is no write-back pass; this is the main
    difference between this package and :mod:`advexp.settings`. The values
    themselves are set only by a load: assigning to a declared member, on the
    class or on an instance, raises ``TypeError``. A :meth:`to_object`
    snapshot is completely frozen: none of its attributes can be written or
    deleted.

    A member declared without ``default=`` is required: it must get its value
    from a source. If a load finds nothing usable for a required member, it
    raises one abort of the package's load pass,
    :class:`~advexp.configuration.AggregateLoadError`, with an entry for each
    failed member (a distinct class for each cause, all subclasses of
    :class:`~advexp.settings_base.member_load_error.MemberLoadError`). It
    raises one error however many members failed, so one run reports them all.
    Reading a required member that was never loaded raises the same error.

    An optional member never aborts a load: it stands at its default, and its
    load error goes into the report that :meth:`load_configuration` returns.
    If a run has both an abort and fallbacks, the fallbacks are kept next to
    the abort in its ``fallbacks`` attribute.

    :data:`~advexp.settings_base.required.REQUIRED` is the explicit spelling
    of a required member, and the ``default`` parameter of the bundled sources
    defaults to it. :data:`~advexp.settings_base.no_default.NO_DEFAULT` keeps
    its family-wide meaning: the member is optional, and ``None`` stands in
    for it.
    """

    # Injected by the settings metaclass at class creation (annotations only:
    # they hold no values, keeping every configuration class on its own
    # storage). The types resolve at runtime on purpose: they end up in the
    # class __annotations__, which typing.get_type_hints evaluates for
    # subclasses.
    __settings_members__: Dict[str, SettingMember]
    __settings_values__: Dict[str, Any]
    __settings_context__: SettingsContext

    # the machinery's records for this distribution's classes are carried by
    # the import-name channel: the base routes them by this declaration,
    # every subclass inherits it (all classes of the distribution share the
    # one logger), and a sibling distribution declares its own root the same
    # way
    __logger_name__ = PACKAGE_NAME

    # the distribution boundary: members are declared through this base,
    # and the class statement refuses a member declared with another
    # distribution's attribute — the bases spell different defaults, so a
    # misplaced attribute would silently change what the member means
    __attribute_base__ = ConfigurationAttribute

    # the word the machinery's diagnostics call this distribution's
    # members by: this package's own vocabulary — its records never speak
    # the settings package's word
    __member_term__ = "member"

    # -- logging ---------------------------------------------------------------

    @classmethod
    def logger(cls) -> logging.Logger:
        """Return this distribution's logging channel, ready to be configured.

        There is one channel per distribution: the one that ``__logger_name__``
        declares and that every class of the package shares. A subclass inherits
        the method and returns the same channel. Unlike
        :meth:`~advexp.configuration.LibraryConfiguration.logger`, which returns
        the channel of the whole family, this channel addresses only the records of
        this package: a level set here overrides the family's level for this
        package, and a handler added here receives only this package's records.
        The propagation rule is the same as for the family channel: a handler added
        here, next to the application's ``logging.basicConfig()``, duplicates every
        record unless propagation of this channel is turned off.
        """
        return logging.getLogger(cls.__logger_name__)

    def __setattr__(self, name: str, value: Any) -> None:
        # the instance-side twin of the metaclass guard: member writes raise
        # on every instance, and a to_object snapshot is frozen outright;
        # its own value storage in __dict__ is the snapshot marker
        self.__assert_writable(name)
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        # the deletion twin of the write guard
        self.__assert_writable(name)
        super().__delattr__(name)

    def __assert_writable(self, name: str) -> None:
        if name in type(self).__settings_members__:
            raise TypeError(
                f"'{name}' is a read-only member of {type(self).__name__}: "
                "configuration values are loaded from their sources and cannot be "
                "assigned. Call load_configuration() to reload them"
            )
        if instance_values(self) is not None:
            raise TypeError(
                f"a snapshot of {type(self).__name__} is frozen: none of its "
                "attributes can be written or deleted"
            )

    # -- loading ---------------------------------------------------------------

    @classmethod
    def load_configuration(
        cls, overrides: Optional[Mapping[str, Any]] = None
    ) -> Tuple[MemberLoadError, ...]:
        """Load all declared members from their sources and report the fallbacks.

        Every member is loaded, whatever happened to the previous one. A required
        member (one declared ``REQUIRED``) whose sources provide nothing usable
        records an error. The error names the cause (no value, a value that cannot
        be converted, a constraint violation, or a failed source), the member, its
        setting, and the class. An optional member records the same error, but it
        stands at its default instead.

        A plain miss is not an error. For an optional member, a miss is the normal
        way in which the default gets used, so it is not reported at the usual log
        levels; a debug record names the address that came up empty. When the pass
        aborts, the optional misses are attached to the abort in the aggregate's
        ``misses``, so the reader of the failure can see which optional members
        stood at their defaults.

        At the end, one abort reports every required failure at once. It is always
        :class:`~advexp.configuration.AggregateLoadError`, however many members
        failed. Its ``errors`` tuple holds each member's own error, and its
        ``fallbacks`` tuple holds the optional fallbacks of the same run. If there
        is no required failure, there is no abort: the method returns the
        fallbacks as its report (an empty tuple when every member loaded cleanly),
        so a caller can learn what fell back without parsing logs. A user-facing
        source condition (a corrupt or inaccessible source) does not wait for the
        end: if the failing member has a default that would mask it, the condition
        propagates and aborts the whole pass immediately.

        Each member is resolved through the class's source chain, and the first
        link that provides a value wins. A member declared through a family's
        factory reads only the links of that family. A broken link ends the walk
        down the chain, so the layers below it never hide the problem.

        ``overrides`` is a layer above the whole chain, not a declared link. Its
        keys are member names, and its values go through the same conversion and
        constraint checks as the values of a link. It can reach any member, even
        one that a ``path=`` hides. Keys that name no member (for example, a
        ``model_dump()`` of another model may carry keys that this class never
        declared) and keys that name constant members (which no override reaches)
        are dropped, with one debug record for each. A foreign dictionary therefore
        never makes the load fail.

        The pass builds the class state from scratch and applies it in one step. A
        completed load fully determines the state: every member takes either the
        value that its sources produced or its declared default. A value from an
        earlier load therefore never survives when the current sources hold
        nothing for that member, so one class can be reused across loads, and each
        pass stands on its own. A pass that ends in the aggregate abort, or in a
        propagating source condition, leaves the class exactly as the call found
        it: no values are partly applied, and no defaults are served by the failed
        run. So if a reload fails, the process keeps the configuration that it is
        already running with. Nothing is written back: sources are read-only for
        this class, and the load pass is the only writer of the values themselves.
        """
        return pipeline.load_configuration(cls.__settings_context__, overrides)

    # -- snapshot (in-memory) -------------------------------------------------
    #
    # The configuration class is the singleton storage, so a "copy" must be
    # a different object: a read-only mapping or a detached instance of the
    # class itself. A snapshot is frozen: item writes on the mapping raise,
    # and the object form accepts no attribute writes or deletions at all;
    # bringing new values in always goes through the sources, by calling
    # load_configuration again.

    @classmethod
    def to_dict(cls) -> Mapping[str, Any]:
        """Return a frozen snapshot of all declared members, keyed by member name.

        The mapping is read-only (a ``MappingProxyType``): item assignment and
        deletion raise ``TypeError``, the same guard that the values themselves
        have. Wrap it in ``dict(...)`` to get a mutable copy. Values are
        deep-copied, so nothing that the caller does with them affects the class,
        and vice versa. A member that was never loaded reports its effective
        default. A required member (declared ``REQUIRED``) raises an error instead,
        because it has nothing to report. Members that hold secrets are included
        as they are, so treat the snapshot accordingly::

            snapshot = AppConfig.to_dict()
        """
        with cls.__settings_context__.lock:
            return MappingProxyType(
                {name: copy.deepcopy(getattr(cls, name)) for name in cls.__settings_members__}
            )

    @classmethod
    def to_object(cls: Type[_T]) -> _T:
        """Return a snapshot of all declared members as a detached instance.

        The returned instance is of the configuration class itself, so its fields
        carry the declared names and annotations. If you rename a member, every
        stale field access on a snapshot becomes a type-checker error (and an
        ``AttributeError`` at runtime). The instance holds its own deep-copied
        values: reading them never affects the class, and vice versa. The instance
        is completely frozen: writing or deleting any attribute, member or not,
        raises ``TypeError``. New values come only from a reload. A member that was
        never loaded reports its effective default. A required member (declared
        ``REQUIRED``) raises an error instead, because it has nothing to report.
        Members that hold secrets are included as they are, so treat the snapshot
        accordingly::

            snapshot = AppConfig.to_object()
        """
        with cls.__settings_context__.lock:
            # object.__new__ is the detached-instance construction (the class
            # __new__ belongs to the metaclass); the cast states the result type
            snapshot = object.__new__(cls)
            # a plain attribute write into the fresh instance: its own value
            # storage, which the descriptors read (vars() would go through a
            # proxy the stubs type as read-only); object.__setattr__ also
            # bypasses the write guard above, which is how the snapshot gets
            # its values in place
            object.__setattr__(
                snapshot,
                INSTANCE_VALUES_ATTR,
                {name: copy.deepcopy(getattr(cls, name)) for name in cls.__settings_members__},
            )
        return cast(_T, snapshot)

    # -- plugins -----------------------------------------------------------

    @classmethod
    def get_plugin(cls, plugin_class: Type[PluginT]) -> PluginT:
        """Return the plugin instance bound to this configuration class (cached)."""
        return cls.__settings_context__.get_plugin(plugin_class)
