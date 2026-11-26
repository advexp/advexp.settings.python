# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The loading pass of configuration classes.

The pass itself is the shared one of the family
(:func:`advexp.settings_base.loading.load_settings_class`). It walks the
members declared on a configuration class and resolves each of them
through the class's source chain: the first link that provides a value
wins, and the declared default is the implicit last layer. It then applies
type conversion and constraints, and reports each member's load problem
through the channel that the member's declaration selects. Nothing here
writes a source back: this package reads its sources only.

``contains_member`` is the single-member read beside the pass: it asks the
same chain whether any link holds a value for one member, without building
the state of the class.
"""

from __future__ import annotations

from typing import Mapping, Optional, Tuple

from advexp.settings_base.context import SettingsContext
from advexp.settings_base.loading import (
    LinkSerializers,
    load_settings_class,
    notify_end,
    notify_start,
)
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.names import get_full_setting_name
from advexp.settings_base.serializer_cache import SerializerCache
from advexp.settings_base.setting_member import resolve_member
from advexp.settings_base.user_facing_error import UserFacingError


def load_configuration(
    context: SettingsContext, overrides: Optional[Mapping[str, object]] = None
) -> Tuple[MemberLoadError, ...]:
    """Load every member of the class from its sources.

    This is the shared load pass of the family: see
    :func:`advexp.settings_base.loading.load_settings_class`. The returned
    report holds the errors of the members that fell back to their defaults. A
    required member that got nothing usable aborts the load with
    :class:`~advexp.configuration.AggregateLoadError`. If the caller passed a
    mapping as ``overrides``, it is applied above the whole chain as the top
    layer of the pass, not as a declared link.
    """
    return load_settings_class(context, overrides)


def contains_member(context: SettingsContext, setting_name: str) -> bool:
    """Return whether the class's source chain holds a value for the member.

    The chain is walked in load order, and the first link that holds a value
    answers ``True``; a chain where no link holds one answers ``False``. The
    probe reads the sources alone: it loads nothing, so the values of the
    class stand as they were.
    """
    settings_class = context.settings_class
    with context.lock:
        member = resolve_member(settings_class, setting_name)
        if getattr(type(member.attribute), "SOURCELESS", False):
            return False  # no source of the chain holds anything for the member
        cache = SerializerCache(context)
        links = LinkSerializers(context)
        serializers = links.member_serializers(cache, member)
        # a read-only probe: the notification bracket fires, but no state is
        # built; a broken source is the caller's error to see — a plain
        # exception leaves as is, a user-facing one unwrapped into the inner
        notify_start(serializers, "contains")
        try:
            # the name is built once for the whole walk, the way the load
            # pass builds it: a link that shapes addresses by its own rules
            # (an env prefix, a file name pattern, member-name keys)
            # re-derives its address from the attribute, so the passed name
            # serves an explicit name= alone
            full_name = get_full_setting_name(
                member.name, member.attribute, settings_class, serializers[0]
            )
            try:
                for serializer in serializers:
                    if serializer.contains(full_name, member.attribute):
                        return True  # the first link holding a value answers
                return False
            except UserFacingError as user_error:
                # user errors rethrow the inner exception
                raise user_error.inner from user_error
        finally:
            notify_end(serializers, "contains")
