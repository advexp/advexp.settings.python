# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Serialization passes.

The class-level load is the shared pass of the family
(:mod:`advexp.settings_base.loading`). It walks the members declared on a
settings class, applies defaults and type conversion, and reports the load
problem of each member through the channel that the declaration of the
member selects.

The passes in this module are everything else: the write directions (save
and delete) and the single-setting forms. These keep the lenient policy: a
failure at the level of one member serves the effective default of the
member (``None`` if no default is declared), and the failure is logged. The
single-setting write operations follow their class-level forms. A plain
storage error is logged as an ERROR record, and the operation is skipped. A
user-facing error is raised unwrapped, as the inner exception. The
``contains`` probe has no lenient answer, because it asks a question, so it
gives the caller the error of the source, unwrapped in the same way.

The optional interfaces (wishes, notification sink) are probed with
``isinstance``: a backend that implements only ``ISettingsSerializer`` is a
valid backend.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from advexp.settings_base.constraint_violation_error import ConstraintViolationError
from advexp.settings_base.constraints import check_value, collect_problems
from advexp.settings_base.context import SettingsContext
from advexp.settings_base.conversion import correct_type, is_secret_type, unwrap_secret
from advexp.settings_base.conversion_error import ConversionError
from advexp.settings_base.cross_validation import (
    collect_settings_problems,
    effective_values,
    format_problems,
)
from advexp.settings_base.library_configuration import logger_for
from advexp.settings_base.loading import (
    LinkSerializers,
    conversion_problem,
    load_error_entry,
    load_settings_class,
    member_where,
    notify_end,
    notify_start,
    source_failure_cause,
    unique_serializers,
)
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.names import get_full_setting_name
from advexp.settings_base.not_found import NOT_FOUND
from advexp.settings_base.required import REQUIRED
from advexp.settings_base.serializer_cache import SerializerCache
from advexp.settings_base.setting_member import SettingMember, resolve_member
from advexp.settings_base.setting_validation_error import SettingValidationError
from advexp.settings_base.settings_meta import SettingsMeta
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.source_load_error import SourceLoadError
from advexp.settings_base.type_display import type_display
from advexp.settings_base.user_facing_error import UserFacingError


def _member_value(settings_class: SettingsMeta, member: SettingMember) -> Any:
    """Current member value: stored value or the effective default."""
    values: Dict[str, Any] = settings_class.__settings_values__
    if member.name in values:
        return values[member.name]
    return member.descriptor.resolved_default(settings_class)


def _set_member_value(settings_class: SettingsMeta, member: SettingMember, value: Any) -> None:
    settings_class.__settings_values__[member.name] = value


def _reset_member_value(settings_class: SettingsMeta, member: SettingMember) -> None:
    """Reset one member to its effective default, without touching the storages.

    A required member has no default to serve, so the reset takes it to the
    never-loaded state instead: the stored value is cleared, and a read raises
    the required error, exactly as before any load.
    """
    if member.attribute.default is REQUIRED:
        settings_class.__settings_values__.pop(member.name, None)
        return
    _set_member_value(settings_class, member, member.descriptor.resolved_default(settings_class))


def _synchronize(serializers: List[ISettingsSerializer], settings_class: SettingsMeta) -> None:
    for serializer in serializers:
        try:
            serializer.synchronize()
        except UserFacingError as user_error:
            # user errors rethrow the inner exception
            raise user_error.inner from user_error
        except Exception as exc:  # noqa: BLE001 - sync errors are logged and skipped by design
            logger_for(settings_class).error(
                "synchronization failed for %s: %s", type(serializer).__name__, exc
            )


# ---------------------------------------------------------------------------
# class-level passes
# ---------------------------------------------------------------------------


def load_settings(context: SettingsContext) -> Tuple[MemberLoadError, ...]:
    """Load all declared settings from their storages.

    This is the shared load pass of the family: see
    :func:`advexp.settings_base.loading.load_settings_class`. The returned
    report holds the errors of the members that fell back to their defaults. A
    required member that got nothing usable aborts the pass with
    :class:`~advexp.settings.AggregateLoadError`.
    """
    return load_settings_class(context)


def _load_member(
    settings_class: SettingsMeta,
    member: SettingMember,
    serializer: ISettingsSerializer,
    state: Dict[str, Any],
) -> Optional[MemberLoadError]:
    """The single-setting form of the lenient load policy.

    A failure at the level of one member serves the effective default of the
    member, and the failure is logged. The returned entry is the row of the
    member in the report that :meth:`load_settings` returns: the same error
    that the class pass would collect. ``None`` stands for a member that loaded
    cleanly or took its default the normal way (a plain miss).

    A required member has no default to serve, so the caller sees its
    never-loaded read error. A failing source follows the policy of the shared
    pass. The log record carries the full fallback context at the error level.
    An optional member stands at its default, and its entry is the answer. For
    a required member, the caller gets the exception itself, because this form
    has no aggregate to carry it.
    """
    full_name = get_full_setting_name(member.name, member.attribute, settings_class, serializer)
    where = member_where(settings_class, member, [serializer], full_name)
    entry: Optional[MemberLoadError] = None
    try:
        raw_value = serializer.load(full_name, member.attribute)
    except UserFacingError as user_error:
        # the family unwraps a user-facing condition into the inner exception
        raise user_error.inner from user_error
    except Exception as exc:  # noqa: BLE001 - logged, then the soft policy applies
        cause = source_failure_cause(serializer, member.attribute, where, exc)
        if member.attribute.default is REQUIRED:
            logger_for(settings_class).error("%s: %s", where, cause)
            raise
        logger_for(settings_class).error("%s: %s; using the default value", where, cause)
        entry = load_error_entry(SourceLoadError, where, False, cause, exc)
        value = member.descriptor.resolved_default(settings_class)
        _set_member_value(settings_class, member, value)
        state[member.name] = value
        return entry

    if raw_value is NOT_FOUND:
        value = member.descriptor.resolved_default(settings_class)
    else:
        try:
            value = correct_type(raw_value, member.annotation)
        except (ValueError, TypeError) as exc:
            if is_secret_type(member.annotation):
                # the payload stays out of the log whatever it was
                problem = f"cannot convert <secret> to {type_display(member.annotation)}"
                logger_for(settings_class).warning(
                    "%s: cannot convert the <secret> value to the annotated type;"
                    "using the default value",
                    where,
                )
            else:
                problem = conversion_problem(raw_value, member.annotation, exc)
                logger_for(settings_class).warning(
                    "%s: %s; using the default value",
                    where,
                    problem,
                )
            entry = load_error_entry(ConversionError, where, False, problem)
            value = member.descriptor.resolved_default(settings_class)
        else:
            try:
                problems = collect_problems(member.attribute, value, state)
            except Exception as exc:  # noqa: BLE001 - recorded, then re-raised as is
                # a validator that breaks is a bug in user code: the pass
                # crashes as is, the log record keeping the crash visible
                logger_for(settings_class).error(
                    "validation exception for setting '%s': %s", member.name, exc
                )
                raise
            if problems:
                problem = f"the value violates its constraints ({'; '.join(problems)})"
                logger_for(settings_class).warning(
                    "%s: %s; using the default value",
                    where,
                    problem,
                )
                entry = load_error_entry(ConstraintViolationError, where, False, problem)
                value = member.descriptor.resolved_default(settings_class)

    _set_member_value(settings_class, member, value)
    state[member.name] = value
    return entry


def validate_settings(context: SettingsContext) -> None:
    """Check every declared setting against all its constraints; change nothing.

    This is the strict manual form of the lenient step of the load pass. It
    checks the field constraints with their ``when=`` conditions, the
    member-reference rules, and the ``__validate__`` hook. All findings are
    collected into one :class:`SettingValidationError`, which carries the
    report for each member. Values and storages are left exactly as they were.
    """
    settings_class = context.settings_class
    with context.lock:
        report = collect_settings_problems(settings_class, effective_values(settings_class))
        if report:
            raise SettingValidationError(format_problems(settings_class, report), problems=report)


def save_settings(context: SettingsContext) -> None:
    settings_class = context.settings_class
    with context.lock:
        # the whole-object checks gate the pass: a class in violation saves
        # nothing, the collected report names every member at fault
        report = collect_settings_problems(settings_class, effective_values(settings_class))
        if report:
            raise SettingValidationError(format_problems(settings_class, report), problems=report)
        members: Dict[str, SettingMember] = settings_class.__settings_members__
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        serializers = unique_serializers(context, cache, links)

        # a write pass seeds its path parameters with the remembered values
        # of the last load: the values land in the files they were read
        # from, the environment of the load and not the one the process
        # happens to run now
        context.open_parameter_pass(context.remembered_parameter_values())
        try:
            notify_start(serializers, "save")
            try:
                for member in members.values():
                    for serializer in links.member_serializers(cache, member):
                        try:
                            _save_member(settings_class, member, serializer)
                        except UserFacingError as user_error:
                            # user errors rethrow the inner exception
                            raise user_error.inner from user_error
                        except Exception as exc:  # noqa: BLE001 - save errors are logged, not raised
                            logger_for(settings_class).error(
                                "save exception for setting '%s': %s", member.name, exc
                            )

                _synchronize(serializers, settings_class)
            finally:
                notify_end(serializers, "save")
        finally:
            context.close_parameter_pass()


def _save_member(
    settings_class: SettingsMeta,
    member: SettingMember,
    serializer: ISettingsSerializer,
) -> None:
    full_name = get_full_setting_name(member.name, member.attribute, settings_class, serializer)
    value = _member_value(settings_class, member)
    # a violating value is not persisted; the pass's error handling logs it
    # and skips the member, like any other save failure
    check_value(
        member.attribute,
        value,
        f"invalid value for setting '{member.name}' of {settings_class.__name__}",
        siblings=effective_values(settings_class),
    )
    # a secret wrapper is unwrapped for the storage: serializers keep their
    # plain string and bytes contracts, unaware of the wrappers
    serializer.save(full_name, member.attribute, unwrap_secret(value))


def delete_settings(context: SettingsContext) -> None:
    settings_class = context.settings_class
    with context.lock:
        members: Dict[str, SettingMember] = settings_class.__settings_members__
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        serializers = unique_serializers(context, cache, links)

        # the write pass's seeded parameters, the save pass's rule
        context.open_parameter_pass(context.remembered_parameter_values())
        try:
            notify_start(serializers, "delete")
            try:
                for member in members.values():
                    for serializer in links.member_serializers(cache, member):
                        try:
                            _delete_member(settings_class, member, serializer)
                        except UserFacingError as user_error:
                            # user errors rethrow the inner exception
                            raise user_error.inner from user_error
                        except Exception as exc:  # noqa: BLE001 - delete errors are logged, not raised
                            logger_for(settings_class).error(
                                "delete exception for setting '%s': %s", member.name, exc
                            )

                _synchronize(serializers, settings_class)
            finally:
                notify_end(serializers, "delete")
        finally:
            context.close_parameter_pass()


def _delete_member(
    settings_class: SettingsMeta,
    member: SettingMember,
    serializer: ISettingsSerializer,
) -> None:
    full_name = get_full_setting_name(member.name, member.attribute, settings_class, serializer)
    serializer.delete(full_name, member.attribute)
    _reset_member_value(settings_class, member)


def reset_settings(context: SettingsContext) -> None:
    settings_class = context.settings_class
    with context.lock:
        for member in settings_class.__settings_members__.values():
            _reset_member_value(settings_class, member)


def reset_setting(context: SettingsContext, setting_name: str) -> None:
    settings_class = context.settings_class
    with context.lock:
        member = resolve_member(settings_class, setting_name)
        _reset_member_value(settings_class, member)


# ---------------------------------------------------------------------------
# single-setting passes
# ---------------------------------------------------------------------------


def load_setting(context: SettingsContext, setting_name: str) -> Optional[MemberLoadError]:
    settings_class = context.settings_class
    with context.lock:
        member = resolve_member(settings_class, setting_name)
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        serializer = links.member_serializers(cache, member)[0]
        state = effective_values(settings_class)
        notify_start([serializer], "load")
        # the single form reads its variables live and remembers them, the
        # class load's rule
        context.open_parameter_pass()
        try:
            return _load_member(settings_class, member, serializer, state)
        finally:
            context.close_parameter_pass()
            notify_end([serializer], "load")


def save_setting(context: SettingsContext, setting_name: str) -> None:
    settings_class = context.settings_class
    with context.lock:
        member = resolve_member(settings_class, setting_name)
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        serializer = links.member_serializers(cache, member)[0]
        notify_start([serializer], "save")
        # the write pass's seeded parameters, the class save's rule
        context.open_parameter_pass(context.remembered_parameter_values())
        try:
            try:
                _save_member(settings_class, member, serializer)
            except UserFacingError as user_error:
                # user errors rethrow the inner exception
                raise user_error.inner from user_error
            except SettingValidationError:
                # a violating value is the caller's answer everywhere: the
                # assignment and the class gate raise it, and this narrow
                # path — no whole-class gate runs here — raises it too
                raise
            except Exception as exc:  # noqa: BLE001 - save errors are logged, not raised
                logger_for(settings_class).error(
                    "save exception for setting '%s': %s", member.name, exc
                )
            _synchronize([serializer], settings_class)
        finally:
            context.close_parameter_pass()
            notify_end([serializer], "save")


def delete_setting(context: SettingsContext, setting_name: str) -> None:
    settings_class = context.settings_class
    with context.lock:
        member = resolve_member(settings_class, setting_name)
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        serializer = links.member_serializers(cache, member)[0]
        notify_start([serializer], "delete")
        # the write pass's seeded parameters, the class delete's rule
        context.open_parameter_pass(context.remembered_parameter_values())
        try:
            try:
                _delete_member(settings_class, member, serializer)
            except UserFacingError as user_error:
                # user errors rethrow the inner exception
                raise user_error.inner from user_error
            except Exception as exc:  # noqa: BLE001 - delete errors are logged, not raised
                logger_for(settings_class).error(
                    "delete exception for setting '%s': %s", member.name, exc
                )
            _synchronize([serializer], settings_class)
        finally:
            context.close_parameter_pass()
            notify_end([serializer], "delete")


def contains_setting(context: SettingsContext, setting_name: str) -> bool:
    settings_class = context.settings_class
    with context.lock:
        member = resolve_member(settings_class, setting_name)
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        serializer = links.member_serializers(cache, member)[0]
        # a read-only probe: the notification bracket fires, but synchronize
        # does not; a broken source is the caller's error to see — a plain
        # exception leaves as is, a user-facing one unwrapped into the inner
        notify_start([serializer], "contains")
        try:
            full_name = get_full_setting_name(
                member.name, member.attribute, settings_class, serializer
            )
            try:
                return serializer.contains(full_name, member.attribute)
            except UserFacingError as user_error:
                # user errors rethrow the inner exception
                raise user_error.inner from user_error
        finally:
            notify_end([serializer], "contains")
