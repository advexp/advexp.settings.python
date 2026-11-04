# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Parsing a dotenv text through python-dotenv, with its parse warnings."""

from __future__ import annotations

import io
import logging
import threading
from typing import Dict, List, Tuple

from dotenv import dotenv_values

# python-dotenv's own channel: it skips a line it cannot parse and warns here
_DOTENV_LOGGER_NAME = "dotenv.main"


class _ParseWarnings(logging.Handler):
    """The parse warnings of one call, for the current thread only.

    Parallel passes share the global channel, and each of them collects its own
    warnings. The level floor keeps records below WARNING out.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: List[str] = []
        self.__thread = threading.get_ident()

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread == self.__thread:
            self.messages.append(record.getMessage())


def parse_dotenv_variables(text: str) -> Tuple[Dict[str, str], List[str]]:
    """Return the variables of a dotenv text, and the lines that python-dotenv
    could not parse.

    python-dotenv skips a line that it cannot parse and writes a warning to its
    own ``dotenv.main`` channel. This function takes those warnings over (for
    the current thread only) and returns their messages, so a caller can report
    them in the channel of the family, together with the path of the file.

    While the call runs, the takeover turns off the propagation of that
    channel. Otherwise, a fully configured log would print each warning twice:
    once from python-dotenv and once from the replay of the family. A ``None``
    value (a key with no ``=``) addresses nothing and is left out of the
    variables.
    """
    collector = _ParseWarnings()
    channel = logging.getLogger(_DOTENV_LOGGER_NAME)
    channel.addHandler(collector)
    had_propagate = channel.propagate
    channel.propagate = False
    try:
        parsed = dotenv_values(stream=io.StringIO(text))
    finally:
        channel.propagate = had_propagate
        channel.removeHandler(collector)
    variables = {name: value for name, value in parsed.items() if value is not None}
    return variables, collector.messages
