# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Logging configuration: stderr, never stdout, and the --debug-log file."""

import logging
import os
import sys
import time
from pathlib import Path
from typing import TextIO

from plexdo.security import redact


class RedactingFormatter(logging.Formatter):
    """A formatter whose every line has its secrets redacted.

    The whole formatted record is redacted, traceback included, so a token
    in a URL that some library logs, or quotes in an exception, never
    reaches the terminal or the file.
    """

    def format(self, record: logging.LogRecord) -> str:
        """The record, formatted, with every secret replaced by ***."""
        return redact(super().format(record))


class TimestampedFormatter(RedactingFormatter):
    """Each line starts with when it was written, in Unix nanoseconds.

    Every line, not every record: a traceback or a profile table spans
    several, and each must still sort and filter on its own.
    """

    def format(self, record: logging.LogRecord) -> str:
        """The record, redacted, with the time at the start of each line."""
        stamp = time.time_ns()
        lines = super().format(record).splitlines() or [""]
        return "\n".join(f"{stamp} {line}" for line in lines)


def open_debug_log(path: str) -> TextIO:
    """Open the --debug-log file to append to, readable by its owner alone.

    Line buffered, so a run that is killed still leaves every line it
    wrote. The file is created with mode 0600; one that already exists
    keeps its mode.
    """
    target = Path(path).expanduser()
    try:
        descriptor = os.open(
            target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
        )
    except OSError as exc:
        sys.exit(f"Cannot open the debug log {target}: {exc.strerror}")
    return os.fdopen(descriptor, "a", encoding="utf-8", buffering=1)


def configure_logging(
    verbose: bool, debug: bool, debug_log: str | None = None
) -> None:
    """Configure logging to stderr only (never stdout), and to debug_log.

    With debug_log, everything --debug would show goes to that file
    instead, and stderr shows only what it would without --debug.
    """
    if debug and not debug_log:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    # The handler filters too: plexapi sets its own logger to INFO, whose
    # records would otherwise reach stderr whatever the level chosen here.
    handler.setLevel(level)
    handler.setFormatter(RedactingFormatter("%(levelname)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)

    if debug_log:
        file_handler = logging.StreamHandler(open_debug_log(debug_log))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            TimestampedFormatter("%(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(file_handler)
        level = logging.DEBUG
    root.setLevel(level)
