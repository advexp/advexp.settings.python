# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The load pass that is shared by the loading packages of the family.

The pass walks the members that are declared on a settings class. For each
member, it resolves a serializer for the attribute, builds the full storage
name, and performs the load, applying defaults and type conversion.

The declaration of a member decides the channel of its load error:

- A member declared :data:`~advexp.settings_base.required.REQUIRED` has no
  default to serve. If its source provides nothing usable (no value, a value
  that cannot be converted, a constraint violation, or a failed source), the
  pass records a user-facing error of the own class of the member and walks
  on. One abort at the end,
  :class:`~advexp.settings_base.aggregate_load_error.AggregateLoadError`,
  carries every recorded failure.
- A member with a default (a value or
  :data:`~advexp.settings_base.no_default.NO_DEFAULT`) records the same
  error, but it stands at its default instead. These errors are the load
  report that the pass returns, so a caller can learn what fell back without
  parsing logs.

A plain miss is not an error. For a member with a default, a miss is the
normal way in which the default gets used, so it is not reported at the
usual log levels. A debug record names the address that came up empty, so a
variable name that does not match can be seen when the log level allows it.
Only an abort gathers the misses: they are attached to it in the ``misses``
of the aggregate, and they show the reader of the failure which optional
members stood at their defaults.

A user-facing condition of a source (a corrupt or inaccessible source) does
not wait for the end. On an optional member, it aborts the pass as it is,
because a served default must not hide it. On a required member, it is the
failed source of the member: it is recorded like any other failure, with the
cause in the message. A plain error of a source follows the log-and-continue
policy of the family: the record goes to the log, the member takes its
default, and the load error of the member joins the report.

After the walk, the cross-member rules run over the loaded state. Every
violation is an entry of its member: it is fatal for a required member, and
it is a fallback entry for an optional one. If only optional members are
involved, the pass then settles the state: the members that take part in a
violated rule fall back to their declared defaults. A violation that no
reset can settle aborts the pass instead. Examples are a hook finding that
names a member that is already at its default, and a rule whose required
participant holds its loaded value. A completed load therefore always
reaches a consistent state, and the report still names what the sources
actually produced. Loading goes in one direction only: nothing here writes a
source back.

The pass has two phases over the class storage. The walk builds the fresh
state aside: every member takes either the value that its sources produced
or its declared default, so a value from an earlier pass never survives a
completed load, even where the current sources hold nothing for the member.
Only a completed pass applies that state, in one step. A pass that ends in
any other way leaves the class exactly as the call found it, with no values
partly applied and no resets to defaults. The other ways to end are the
aggregate abort, a user-facing condition of a source, and a crash of user
validation code. For a reload in a live application, the last working
configuration is safer than defaults: a reload that hits a corrupt file keeps
the process on the addresses and timeouts that it already runs with.

A crash of user validation code (an exception that a custom ``validator`` or
the body of the ``__validate__`` hook raises) is not a load failure and joins
no channel. The exception propagates as it is, after an ERROR record, because
a bug in that code is not a property of the values.

The optional interfaces (wishes, notification sink) are probed with
``isinstance``: a backend that implements only ``ISettingsSerializer`` is a
valid backend.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type

from advexp.settings_base.aggregate_load_error import AggregateLoadError
from advexp.settings_base.constraint_violation_error import ConstraintViolationError
from advexp.settings_base.constraints import collect_problems
from advexp.settings_base.context import SettingsContext
from advexp.settings_base.conversion import correct_type, is_secret_type
from advexp.settings_base.conversion_error import ConversionError
from advexp.settings_base.cross_validation import (
    collect_settings_problems,
    rule_participants,
)
from advexp.settings_base.library_configuration import LibraryConfiguration, logger_for, member_term
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.missing_value_error import MissingValueError
from advexp.settings_base.names import get_full_setting_name
from advexp.settings_base.not_found import NOT_FOUND
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.serializer_cache import SerializerCache
from advexp.settings_base.serializer_notification_sink_interface import (
    ISerializerNotificationSink,
)
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.setting_name_describer_interface import ISettingNameDescriber
from advexp.settings_base.settings_meta import SettingsMeta
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.source_describer_interface import ISourceDescriber
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.source_load_error import SourceLoadError
from advexp.settings_base.sources import (
    SOURCE_CHAIN_METADATA,
    Sources,
    declared_source_links,
)
from advexp.settings_base.type_display import type_display
from advexp.settings_base.user_facing_error import UserFacingError


def unique_serializers(
    context: SettingsContext,
    cache: SerializerCache,
    links: Optional["LinkSerializers"] = None,
) -> List[ISettingsSerializer]:
    """Return the serializers that this pass reads through, in reading order.

    A layered class reads the links of the chain first, in the order of the
    chain. The members that the chain does not serve (a memory member, for
    example) add their own serializers after them. A constant member adds
    nothing, because its value never asks a source. A settings class that is
    bound through the source seats is read in the same way, over its anchors. A
    member of an unbound family keeps its own serializer, as the pass has always
    resolved it.

    Without ``links``, the resolution builds its own view of the sources of the
    class, so a caller that holds no pass of its own reads the serializers of
    the members as it always did.
    """
    if links is None:
        links = LinkSerializers(context)
    serializers: List[ISettingsSerializer] = []
    for member in context.settings_class.__settings_members__.values():
        if getattr(type(member.attribute), "SOURCELESS", False):
            continue
        for serializer in links.member_serializers(cache, member):
            if serializer not in serializers:
                serializers.append(serializer)
    return serializers


class LinkSerializers:
    """The per-pass resolution of the declared sources of a class.

    A layered class resolves through its source chain, and a settings class
    resolves through its source seats (one ``*_source`` builder per family). Both
    follow one shared rule here: the links of the class are read once from the
    metadata of the class, with one serializer per link for the whole pass. Every
    member that walks a link therefore reads through the same serializer: the
    same shared document for a file link, and the same parsed view for a dotenv
    link.

    The seats of the members follow from the order of the links:

    - A member that is declared through a factory of a family reads only the
      links of that family.
    - A neutral member (a plain declaration) reads every link that the class
      declares.
    - A member that no link serves keeps its own serializer, as the pass
      resolves it.
    """

    def __init__(self, context: SettingsContext) -> None:
        self._context = context
        self._chain: Optional[Sources] = context.get_class_metadata(SOURCE_CHAIN_METADATA)
        # the settings-side spelling: no chain, the source seats instead
        self._anchors: Tuple[SourceLink, ...] = (
            () if self._chain is not None else declared_source_links(context)
        )
        self._serializers: Dict[Tuple[int, Optional[type]], ISettingsSerializer] = {}

    @property
    def chain(self) -> Optional[Sources]:
        """The class's source chain; ``None`` for a class without one."""
        return self._chain

    def links(self) -> Tuple[SourceLink, ...]:
        """The class's declared links: the chain's, or the seats'."""
        if self._chain is not None:
            return tuple(self._chain)
        return self._anchors

    def serializer_for(
        self, link: SourceLink, attribute_class: Optional[type] = None
    ) -> ISettingsSerializer:
        """Return the serializer through which one member reads a link.

        The attribute class of the member decides the serializer, by the same rule
        that resolves a member: a registered subclass of the attribute of the family
        runs its own registered serializer. The link configures that serializer: its
        file, its subtree, and its naming. One serializer per (link, attribute class)
        serves the whole pass, so every member over one link reads through the same
        instance, which means the same shared document for a file link.
        """
        key = (id(link), attribute_class)
        serializer = self._serializers.get(key)
        if serializer is None:
            serializer = link.serializer(self._context, attribute_class)
            self._serializers[key] = serializer
        return serializer

    def member_serializers(
        self, cache: SerializerCache, member: SettingMember
    ) -> List[ISettingsSerializer]:
        """The serializers one member reads, in the order it reads them."""
        attribute = member.attribute
        declared = self.links()
        if not declared:
            return [cache.get_for_attribute(attribute)]
        family_links = [link for link in declared if link.serves(attribute)]
        if family_links:
            return [self.serializer_for(link, type(attribute)) for link in family_links]
        if LibraryConfiguration._get_serializer_factory(type(attribute)) is not None:
            # a member of its own serializer, no declared link serves it
            return [cache.get_for_attribute(attribute)]
        # a neutral member: every declared link, in their order
        return [self.serializer_for(link) for link in declared]


class _OverrideSource(ISettingsSerializer, ISettingNameDescriber, ISourceDescriber):
    """The load overrides: a layer above the whole chain, which is never declared.

    It holds the values that one :meth:`load_configuration` call carried, keyed
    by member name. The pass reads it before any link, so an override outranks
    every source. The keys of the call that name no member, or that name a
    constant member (which no override reaches), were dropped with a debug record
    when the layer was built.
    """

    def __init__(self, values: Mapping[str, Any]) -> None:
        # name-mangled: the layer's own state, dispatched through self
        self.__values: Dict[str, Any] = dict(values)

    # -- ISettingsSerializer ---------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        name = attr.bound_name if attr is not None else None
        if name is not None and name in self.__values:
            return copy.deepcopy(self.__values[name])
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """No-op: this is a layer of the pass, not a storage, so nothing stands behind
        it.
        """

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """No-op: this is a layer of the pass, not a storage, so nothing stands behind
        it.
        """

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        name = attr.bound_name if attr is not None else None
        return name is not None and name in self.__values

    def synchronize(self) -> None:
        """No-op: this is a layer of the pass, not a storage, so nothing stands behind
        it.
        """

    # -- ISettingNameDescriber ---------------------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        name = attr.bound_name if attr is not None else None
        if name is None:
            return None
        return f"the overrides entry '{name}'"

    # -- ISourceDescriber --------------------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        return "the load overrides", None


def _override_source(
    context: SettingsContext, overrides: Optional[Mapping[str, Any]]
) -> Optional[_OverrideSource]:
    """Build the overrides layer of one pass; return ``None`` if none was given.

    The layer keeps only the values of the members that the call addressed. A
    key that names no member (for example, a ``model_dump()`` of another model
    may carry keys that this class never declared) and a key that names a
    constant member (which no override reaches) are dropped, with one debug
    record for each. A foreign dictionary therefore never makes the load fail.
    The values are deep-copied: the pass owns its layer, and the caller owns the
    dictionary that it passed in.
    """
    if overrides is None:
        return None
    if not isinstance(overrides, Mapping):
        raise TypeError(
            f"overrides must be a mapping of member names to values, got {type(overrides).__name__}"
        )
    members: Dict[str, SettingMember] = context.settings_class.__settings_members__
    values: Dict[str, Any] = {}
    for key, value in overrides.items():
        member = members.get(key)
        if member is None:
            context.logger.debug(
                "the overrides entry %r does not match any member of '%s'; ignoring it",
                key,
                context.settings_class.__name__,
            )
            continue
        if getattr(type(member.attribute), "SOURCELESS", False):
            context.logger.debug(
                "the overrides entry %r refers to the constant member of '%s', "
                "which cannot be overridden; ignoring it",
                key,
                context.settings_class.__name__,
            )
            continue
        values[key] = copy.deepcopy(value)
    return _OverrideSource(values)


def notify_start(serializers: List[ISettingsSerializer], mode: str) -> None:
    for serializer in serializers:
        if isinstance(serializer, ISerializerNotificationSink):
            serializer.on_start_serializer_action()
            getattr(serializer, f"on_start_{mode}_settings")()


def notify_end(serializers: List[ISettingsSerializer], mode: str) -> None:
    for serializer in serializers:
        if isinstance(serializer, ISerializerNotificationSink):
            getattr(serializer, f"on_end_{mode}_settings")()
            serializer.on_end_serializer_action()


def member_where(
    settings_class: SettingsMeta,
    member: SettingMember,
    serializers: List[ISettingsSerializer],
    full_name: str,
) -> str:
    """Return the place of the member in load diagnostics: name, storage
    addresses, and class.

    One serializer names one address, as the non-layered pass has always worded
    it. For a chain, the text names the address of each link in the order in
    which the pass read them, joined by semicolons, so the reader of a miss
    record sees every address that the pass checked.

    The address is the own wording of the serializer when it can name the
    address (``environment variable 'APP_MODE'``). Otherwise, it is the storage
    name that the pattern built. The designation of a source is added to the
    address when it adds the file that the address alone cannot name (``key
    'port' in the JSON file /etc/app.json``). A storage with no file keeps the
    address as it is.
    """
    parts: List[str] = []
    for serializer in serializers:
        described: Optional[str] = None
        if isinstance(serializer, ISettingNameDescriber):
            described = serializer.describe_setting_name(full_name, member.attribute)
        shown = described if described is not None else full_name
        designation = _source_of(serializer, member.attribute)
        if designation is not None and designation[1] is not None:
            shown = f"{shown} in {designation[0]} {designation[1]}"
        parts.append(shown)
    joined = "; ".join(parts) if parts else full_name
    term = member_term(settings_class)
    return f"{term} '{member.name}' ({joined}) of '{settings_class.__name__}'"


def load_settings_class(
    context: SettingsContext, overrides: Optional[Mapping[str, Any]] = None
) -> Tuple[MemberLoadError, ...]:
    """Load every member of the class from its sources.

    This is the shared pass behind the loading methods of the family. It builds
    the fresh state of the class aside and applies it in one step when the pass
    completes. A pass that aborts, or crashes, leaves the class exactly as the
    call found it.

    The function returns the load report, which holds the errors of the members
    that fell back to their defaults. It raises :class:`AggregateLoadError` when
    the pass cannot complete: a required member failed, or a cross-member
    violation could not be settled by a reset to the declared defaults. The
    aborting errors are in ``errors``. The fallbacks of the same run are kept
    next to them in ``fallbacks``. The optional misses (members whose sources
    held no value) are in ``misses``: a miss stays out of the report of a
    successful run, but it is attached to an abort, where the reader of the
    failure wants to see the whole class at once.

    A layered class resolves each member through its source chain, and the first
    link that provides a value wins. A member that is declared through a factory
    of a family reads only the links of that family, and a neutral member reads
    the whole chain. A settings class reads through its source seats in the same
    way: one ``*_source`` builder per family, and a neutral member reads the one
    seat that its class declares.

    ``overrides``, when the caller passes a mapping, is a layer above the whole
    chain. Its values go through the same conversion and constraints as the
    values of a link. Keys that name no member (or a constant member) are
    dropped, with a debug record, so a foreign dictionary never makes the load
    fail.
    """
    settings_class = context.settings_class
    with context.lock:
        members: Dict[str, SettingMember] = settings_class.__settings_members__
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        override_source = _override_source(context, overrides)
        serializers = unique_serializers(context, cache, links)
        # the fresh state of this pass, built aside from the class storage:
        # the values the when= conditions resolve against, kept current as
        # the pass walks the members (a referenced member is declared — and
        # therefore loaded — before the member whose condition reads it),
        # and the state a completed pass applies to the class in one step
        staged: Dict[str, Any] = {}

        context.open_parameter_pass()
        try:
            notify_start(serializers, "load")
            try:
                fatal: List[MemberLoadError] = []
                fallbacks: List[MemberLoadError] = []
                misses: List[MemberLoadError] = []
                for member in members.values():
                    _load_member(
                        settings_class,
                        member,
                        cache,
                        links,
                        override_source,
                        staged,
                        fatal,
                        fallbacks,
                        misses,
                    )
                _cross_validation(settings_class, staged, fatal, fallbacks)
                if fatal:
                    # the abort is a single aggregate however many members
                    # failed: the exception type never depends on the failure
                    # count, and the message opens with the distribution's
                    # channel, so a printed abort names its package
                    raise AggregateLoadError(
                        fatal, fallbacks, misses, logger_for(settings_class).name
                    )
                # a completed pass alone touches the class: the fresh state
                # replaces the old wholesale, so an earlier pass's value never
                # survives where the current sources held nothing for the
                # member — a clean slate, then the sources' say
                stored: Dict[str, Any] = settings_class.__settings_values__
                stored.clear()
                stored.update(staged)
                return tuple(fallbacks)
            finally:
                notify_end(serializers, "load")
        finally:
            context.close_parameter_pass()


def load_error_entry(
    error_class: Type[MemberLoadError],
    where: str,
    required: bool,
    cause: str,
    cause_exc: Optional[BaseException] = None,
) -> MemberLoadError:
    """Return the load error of one member, in the spelling of its channel.

    This is the one builder behind the report entries of the family. The class
    pass collects what it builds, and the single-setting load returns the entry
    of its one member, so both forms report a fallback in the same spelling.
    """
    channel = "is required" if required else "fell back to its default"
    error = error_class(f"{where} {channel}: {cause}")
    if cause_exc is not None:
        error.__cause__ = cause_exc
    return error


def _source_of(
    serializer: ISettingsSerializer, attr: ISettingAttribute
) -> Optional[Tuple[str, Optional[str]]]:
    """Return the own designation of the backend for itself, if it offers one.

    A ``SettingsBaseSerializer`` backend carries the
    :class:`~advexp.settings_base.source_describer_interface.ISourceDescriber`
    capability, with ``None`` as the default. A backend that is built on the raw
    contract may not have it, and then the causes fall back to the unnamed
    spelling ``its source``. The naming is a best effort of the pass: if a
    describe call itself breaks (for example, an unresolvable file binding), it
    degrades to the unnamed spelling instead of disturbing the load that it
    reports on.
    """
    if not isinstance(serializer, ISourceDescriber):
        return None
    try:
        return serializer.describe_source(attr)
    except Exception:  # noqa: BLE001 - diagnostics never break the pass
        return None


def _source_text(designation: Optional[Tuple[str, Optional[str]]], where: str) -> Optional[str]:
    """Return the designation of a source, laid out for a message whose member
    line is ``where``. This is the one place that decides where the path goes.

    The phrase of the storage carries its file only if the member line of the
    message does not already name that file. The address phrase of a member
    (inside ``where``) names the exact file of a file storage, and a message that
    quoted the path twice would read it twice. A dynamic entry carries no
    address, and a backend without a name describer spells none, so there the
    phrase brings the path itself.
    """
    if designation is None:
        return None
    phrase, path = designation
    if path is None or path in where:
        return phrase
    return f"{phrase} {path}"


def conversion_problem(raw_value: Any, annotation: Any, exc: Exception) -> str:
    """Return the phrase for a conversion failure: the canonical statement, with
    the cause in parentheses when the cause adds information.

    The conversion machinery raises some failures as the canonical statement
    itself (``cannot convert 'x' to timedelta``), with or without a further
    detail on the same line. The cause is therefore quoted alone when it already
    opens with the statement, so that it never appears next to a copy of itself.

    An ``Optional`` annotation widens this rule by one step. The conversion runs
    on the unwrapped type, so the cause names the concrete type (``to datetime``
    for an ``Optional[datetime]`` member). It carries everything that the
    statement of the wrapper would carry, with the type named more precisely, so
    the cause alone is the phrase.
    """
    statement = f"cannot convert {raw_value!r} to {type_display(annotation)}"
    detail = str(exc)
    if detail.startswith(f"cannot convert {raw_value!r} to "):
        return detail
    return f"{statement} ({detail})"


def source_failure_cause(
    serializer: ISettingsSerializer, attribute: ISettingAttribute, where: str, exc: BaseException
) -> str:
    """Return the phrase that names the source that raised, for a member-failure
    record.

    The phrase bundles three steps: the designation of the backend for itself
    (a best effort), the place of that designation next to the member line, and
    the exception that was raised. Examples are ``the dotenv file /etc/app.env
    raised ValueError (boom)``, or ``its source raised …`` when the backend names
    nothing. The single-setting passes of the write-direction packages reuse the
    phrase that the shared load pass puts into its log records and report
    entries.
    """
    return _raised_cause(_source_text(_source_of(serializer, attribute), where), exc)


def _raised_cause(source: Optional[str], exc: BaseException) -> str:
    who = source if source is not None else "its source"
    return f"{who} raised {type(exc).__name__} ({exc})"


def _miss_cause(source: Optional[str]) -> str:
    who = source if source is not None else "its source"
    return f"{who} provided no value"


def _load_member(
    settings_class: SettingsMeta,
    member: SettingMember,
    cache: SerializerCache,
    links: LinkSerializers,
    override_source: Optional["_OverrideSource"],
    state: Dict[str, Any],
    fatal: List[MemberLoadError],
    fallbacks: List[MemberLoadError],
    misses: List[MemberLoadError],
) -> None:
    log = logger_for(settings_class)
    attribute = member.attribute
    required = attribute.default is REQUIRED
    if getattr(type(attribute), "SOURCELESS", False):
        # a constant member: its declared default alone, immune to every
        # source and to the overrides — the load pass writes nothing the
        # declaration did not already say
        state[member.name] = member.descriptor.resolved_default(settings_class)
        return
    serializers = links.member_serializers(cache, member)
    if override_source is not None:
        serializers = [override_source, *serializers]
    full_name = get_full_setting_name(
        member.name,
        attribute,
        settings_class,
        serializers[0] if serializers else None,
    )
    where = member_where(settings_class, member, serializers, full_name)

    # the walk down: the first seat providing a value wins, a miss walks
    # on, and a seat that breaks ends the walk right there — the layers
    # below never mask a broken one above them
    raw_value: Any = NOT_FOUND
    for serializer in serializers:
        source = _source_text(_source_of(serializer, attribute), where)
        try:
            candidate = serializer.load(full_name, attribute)
        except UserFacingError as user_error:
            # a broken source on a required member is that member's error like
            # any other (no default exists to mask it), so it collects with
            # the rest and the pass walks on; on an optional member a served
            # default would mask the condition, so it propagates as-is
            if required:
                fatal.append(
                    load_error_entry(
                        SourceLoadError,
                        where,
                        required,
                        _raised_cause(source, user_error.inner),
                        user_error.inner,
                    )
                )
                return
            raise user_error.inner from user_error
        except Exception as exc:  # noqa: BLE001 - the entry and the log carry it
            # a plain source failure keeps the log-and-continue policy, and the
            # member's load error joins the pass's records either way; the
            # record carries the full fallback context — the shape of the
            # value-fallback warnings at the louder level a broken source earns
            cause = _raised_cause(source, exc)
            if required:
                log.error("%s: %s", where, cause)
                fatal.append(load_error_entry(SourceLoadError, where, required, cause, exc))
                return
            log.error("%s: %s; using the default value", where, cause)
            fallbacks.append(load_error_entry(SourceLoadError, where, required, cause, exc))
            state[member.name] = member.descriptor.resolved_default(settings_class)
            return
        if candidate is not NOT_FOUND:
            raw_value = candidate
            break

    if raw_value is NOT_FOUND:
        # every seat came up empty. One seat names its source the way it
        # always did; several name the chain as a whole — the addresses
        # sit in the message's member line, each beside its source
        if len(serializers) == 1:
            source = _source_text(_source_of(serializers[0], attribute), where)
            miss_cause = _miss_cause(source)
        else:
            miss_cause = "no source of the chain provided a value"
        if required:
            fatal.append(load_error_entry(MissingValueError, where, required, miss_cause))
            return
        # a miss on a member with a default is that default's normal way
        # of happening: served silently at the usual levels and out of the
        # successful run's report, and the debug record still names the
        # address that came up empty — the debugging seat for a variable
        # name that does not match. When the pass aborts anyway, the miss
        # rides the abort in misses: the reader of the failure sees which
        # optional members stood at their defaults — what a storage
        # matching none of the class's keys looks like
        log.debug("%s: %s; using the default value", where, miss_cause)
        misses.append(MissingValueError(f"{where}: {miss_cause}"))
        value = member.descriptor.resolved_default(settings_class)
    else:
        try:
            value = correct_type(raw_value, member.annotation)
        except (ValueError, TypeError) as exc:
            if is_secret_type(member.annotation):
                # the payload stays out of the message whatever it was
                problem = f"cannot convert <secret> to {type_display(member.annotation)}"
            else:
                problem = conversion_problem(raw_value, member.annotation, exc)
            if required:
                fatal.append(load_error_entry(ConversionError, where, required, problem))
                return
            log.warning("%s: %s; using the default value", where, problem)
            fallbacks.append(load_error_entry(ConversionError, where, required, problem))
            value = member.descriptor.resolved_default(settings_class)
        else:
            try:
                problems = collect_problems(member.attribute, value, state)
            except Exception as exc:  # noqa: BLE001 - recorded, then re-raised as is
                # a validator that breaks is a bug in user code: the pass
                # crashes as is, the log record keeping the crash visible
                log.error(
                    "validation exception for %s '%s': %s",
                    member_term(settings_class),
                    member.name,
                    exc,
                )
                raise
            if problems:
                problem = f"the value violates its constraints ({'; '.join(problems)})"
                if required:
                    fatal.append(
                        load_error_entry(ConstraintViolationError, where, required, problem)
                    )
                    return
                log.warning("%s: %s; using the default value", where, problem)
                fallbacks.append(
                    load_error_entry(ConstraintViolationError, where, required, problem)
                )
                value = member.descriptor.resolved_default(settings_class)

    state[member.name] = value


def _collect_logged(
    settings_class: SettingsMeta, log: Any, values: Dict[str, Any]
) -> Dict[str, List[str]]:
    """Return the problem report of the whole class. A crash of user validation
    code is recorded before it propagates.

    An exception that a hook or a custom validator raises is a bug in that code,
    not a property of the values. It leaves the pass as it is, and the traceback
    leads to the own frame of the user. The log record keeps the crash visible
    even where the application swallows the traceback.
    """
    try:
        return collect_settings_problems(settings_class, values)
    except Exception as exc:  # noqa: BLE001 - recorded, then re-raised as is
        log.error(
            "validation exception in the cross-member checks of '%s': %s",
            settings_class.__name__,
            exc,
        )
        raise


def _cross_validation(
    settings_class: SettingsMeta,
    staged: Dict[str, Any],
    fatal: List[MemberLoadError],
    fallbacks: List[MemberLoadError],
) -> None:
    """Run the cross-member checks over the fresh state, and settle it in the
    lenient way.

    This is the point where every member of the pass holds its loaded value or
    its default. A required member that failed its load holds none, and the
    rules that reference it wait.

    What the sources produced is the entry: each violated rule names its member.
    The entry is fatal for a required member, and it is a fallback entry for an
    optional one. If there is no fatal entry, the pass then settles the state:
    the members of a violated rule fall back to their declared defaults. A
    violation that the resets cannot settle aborts the pass: a completed load is
    either consistent, or it did not complete.

    The hook runs on a detached snapshot of the checked state. A member that it
    tries to read may hold no value, and this read is the finding of that member,
    like any other, instead of an abort of the pass. An exception that the hook
    or a validator raises is none of these: a bug in user code crashes the pass
    as it is, after a record in the log.
    """
    log = logger_for(settings_class)
    members: Dict[str, SettingMember] = settings_class.__settings_members__
    report = _collect_logged(settings_class, log, staged)
    if not report:
        return
    if any(name in members and members[name].attribute.default is REQUIRED for name in report):
        # a finding on a required member aborts like the member's own
        # load failure; settling is pointless, for the pass will not
        # complete either way
        for name, problems in report.items():
            required = name in members and members[name].attribute.default is REQUIRED
            (fatal if required else fallbacks).append(
                _violation_entry(settings_class, name, problems)
            )
        return
    remaining = _settle(settings_class, staged, log)
    for name, problems in report.items():
        if name not in remaining:
            fallbacks.append(_violation_entry(settings_class, name, problems))
    for name, problems in remaining.items():
        fatal.append(_violation_entry(settings_class, name, problems, unsettled=True))


def _violation_entry(
    settings_class: SettingsMeta, name: str, problems: List[str], unsettled: bool = False
) -> ConstraintViolationError:
    """Return one finding as the entry of the channel of its member, in the spelling
    of both outcomes: the fallback entry for a violation that the resets settled,
    and the abort entry for a violation that no reset can settle.
    """
    message = (
        f"{member_term(settings_class)} '{name}' of '{settings_class.__name__}' "
        f"violates its constraints ({'; '.join(problems)})"
    )
    if unsettled:
        message += "; no reset to the declared defaults settles it"
    return ConstraintViolationError(message)


def _settle(settings_class: SettingsMeta, staged: Dict[str, Any], log: Any) -> Dict[str, List[str]]:
    """Reset the members of violated rules to their defaults until the state is
    consistent.

    The state in which every member has its default was verified at class
    creation, so a reset reaches a consistent state. A second round runs only if
    a reset broke another rule through a shared member. A required member has no
    default to reset to, and it keeps its staged value.

    The function returns the report that remains when a round changes nothing.
    This is the set of violations that no reset can settle: a hook finding that
    names a member that is already at its default, or a rule whose required
    participant keeps its loaded value. If the resets brought the state home,
    the function returns an empty dict. The caller turns a remaining report into
    the abort of the pass, because a completed load is either consistent or did
    not complete. The resets are applied to the fresh state of the pass, next to
    the loads that they settle.
    """
    members: Dict[str, SettingMember] = settings_class.__settings_members__
    report: Dict[str, List[str]] = {}
    for _ in range(len(members) + 1):
        report = _collect_logged(settings_class, log, staged)
        if not report:
            return {}
        listing = "; ".join(
            f"{name}: {problem}" for name, problems in report.items() for problem in problems
        )
        reset = rule_participants(settings_class, report)
        changed = False
        for name in reset:
            if name not in staged:
                # already at its default
                continue
            try:
                default = members[name].descriptor.resolved_default(settings_class)
            except MemberLoadError:
                log.warning("member '%s' is required and has no default to reset to", name)
                continue
            if staged[name] != default:
                staged[name] = default
                changed = True
        if not changed:
            log.error(
                "cross-member constraint violations remain (%s); "
                "resetting to the declared defaults does not resolve them, so the pass is aborted",
                listing,
            )
            return report
        log.warning(
            "found cross-member constraint violations after load (%s); "
            "resetting the members to their defaults: %s",
            listing,
            ", ".join(reset),
        )
    # a changed round resets a member to its default for good, so the
    # loop cannot run out of members before a round changes nothing
    return report
