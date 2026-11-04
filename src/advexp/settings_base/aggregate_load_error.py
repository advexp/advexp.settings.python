# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The error a failed load raises."""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from advexp.settings_base.member_load_error import MemberLoadError


class AggregateLoadError(MemberLoadError):
    """The error that a failed load raises.

    The pass walks every member before aborting, so one run reports every
    failure at once. The error has three groups of entries:

    - ``errors`` holds the individual exceptions that abort the pass, in
      declaration order: a required member that got no usable value, or a
      cross-member violation that no reset to the declared defaults could
      settle.
    - ``fallbacks`` holds the errors of the optional members whose sources
      provided a value that the members could not take (an unconvertible or
      invalid value). These members stand at their defaults.
    - ``misses`` holds the optional members whose sources provided no value at
      all. These members also stand at their defaults.

    These are the structural marks that tell the three groups apart. The message
    carries each entry as a line. It opens with the channel of the distribution
    that ran the pass (``channel``, the name under which its records are
    logged), spelled as ``<channel> error: the load failed for ...``, so an
    abort that the application prints names its package even away from the log.

    Every load abort is this class, however many members failed: the type of
    the exception never depends on the number of failures. A class in which all
    members are optional aborts only on a violation that the resets cannot
    settle. Otherwise, its load report is the tuple that the loading method
    returns, and the misses stay out of it (a miss is the normal way in which a
    default gets used). The misses are attached only to an abort, where the
    reader of the failure wants to see the whole class at once.

    The class is a subclass of
    :class:`~advexp.settings_base.member_load_error.MemberLoadError`, so a
    family-wide ``except MemberLoadError`` (or ``except ValueError``) handler
    keeps catching load aborts.
    """

    def __init__(
        self,
        errors: Sequence[MemberLoadError],
        fallbacks: Sequence[MemberLoadError] = (),
        misses: Sequence[MemberLoadError] = (),
        channel: Optional[str] = None,
    ) -> None:
        self.errors: Tuple[MemberLoadError, ...] = tuple(errors)
        self.fallbacks: Tuple[MemberLoadError, ...] = tuple(fallbacks)
        self.misses: Tuple[MemberLoadError, ...] = tuple(misses)
        count = len(self.errors)
        noun = "member" if count == 1 else "members"
        lines = "\n".join(f"  - {error}" for error in self.errors)
        prefix = f"{channel} error: " if channel is not None else ""
        message = f"{prefix}the load failed for {count} {noun}:\n{lines}"
        if self.fallbacks:
            fallback_count = len(self.fallbacks)
            fallback_noun = "member" if fallback_count == 1 else "members"
            fallback_verb = (
                "fell back to its default"
                if fallback_count == 1
                else ("fell back to their defaults")
            )
            fallback_lines = "\n".join(f"  - {error}" for error in self.fallbacks)
            message += (
                f"\n{fallback_count} optional {fallback_noun} {fallback_verb}:\n{fallback_lines}"
            )
        if self.misses:
            miss_count = len(self.misses)
            miss_noun = "member" if miss_count == 1 else "members"
            miss_verb = "served its default" if miss_count == 1 else "served their defaults"
            miss_tail = (
                "the source provided no value"
                if miss_count == 1
                else "their sources provided no value"
            )
            miss_lines = "\n".join(f"  - {error}" for error in self.misses)
            message += (
                f"\n{miss_count} optional {miss_noun} {miss_verb} ({miss_tail}):\n{miss_lines}"
            )
        super().__init__(message)
