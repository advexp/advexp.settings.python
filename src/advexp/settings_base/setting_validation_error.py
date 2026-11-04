# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The error of a value violating the constraints declared on a setting."""

from typing import Dict, List, Optional


class SettingValidationError(ValueError):
    """A value violates the constraints that are declared on a setting member.

    The error is raised wherever a value meets the declared constraints:
    assignment to a setting, ``update_from_dict``/``update_from_object``, a save
    of a value that no longer satisfies them, and the manual
    ``validate_settings()``. A load keeps its own error policy: it falls back to
    the default with a logged warning, like a value that does not convert.

    A check over the whole settings object (an update, a save, or the manual
    validation) collects every violation of every member at once. Such an error
    carries the findings as ``problems``: a dict of member name to the list of
    its problem descriptions. Tools can read the data instead of parsing the
    message, while the message itself lists the same findings for the reader of
    the log.

    Subclassing :class:`ValueError` keeps a plain ``except ValueError`` working.
    In that case, a violation cannot be distinguished from a failed conversion,
    while the precise class can still be caught on its own.
    """

    def __init__(self, message: str, problems: Optional[Dict[str, List[str]]] = None) -> None:
        super().__init__(message)
        #: findings of the whole-object check, keyed by member name; set
        #: only by the checks that collect every violation at once
        self.problems = problems
