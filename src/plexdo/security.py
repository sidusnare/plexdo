# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Command-line secret scrubbing for --password."""

import argparse
import ctypes
import sys

from plexdo.constants import LOG


def _overwrite_argv_memory(replacement: str) -> bool:
    """Overwrite the process argv block so `ps` no longer shows the password.

    sys.argv is only a copy; `ps` reads the original argv buffer, so it must
    be rewritten in place via the interpreter's retained pointers.  This is
    best-effort and platform-dependent, hence the broad guard.
    """
    try:
        # Newer astroid infers a required "value" argument for ctypes
        # scalars; the zero-argument form is correct and works at runtime.
        argc = ctypes.c_int()  # pylint: disable=no-value-for-parameter
        argv = ctypes.POINTER(ctypes.c_char_p)()
        ctypes.pythonapi.Py_GetArgcArgv(ctypes.byref(argc), ctypes.byref(argv))
        if argc.value < 1:
            return False
        span = sum(len(argv[i]) + 1 for i in range(argc.value))
        buffer = ctypes.create_string_buffer(span)
        buffer.value = replacement.encode("utf-8")[: span - 1]
        ctypes.memmove(argv[0], buffer, span)
        return True
    except Exception:  # pylint: disable=broad-except
        return False


def _mask_argv_copy(secret: str) -> None:
    """Redact the secret from sys.argv so tracebacks and logs cannot leak it."""
    for index, token in enumerate(sys.argv):
        if token == secret:
            sys.argv[index] = "***"
        elif token.startswith("--password=") or token.startswith("-p="):
            sys.argv[index] = token.split("=", 1)[0] + "=***"


def scrub_password_argument(args: argparse.Namespace) -> None:
    """Hide a --password value from ps output and warn that it was exposed."""
    secret = getattr(args, "password", None)
    if not secret:
        return

    hidden = _overwrite_argv_memory("plexdo login")
    _mask_argv_copy(secret)

    LOG.warning(
        "SECURITY: --password was supplied on the command line. It was very "
        "likely recorded in your shell history, and was visible to other "
        "users via `ps` until this process overwrote it. Prefer the "
        "interactive prompt, with --save-password to keep the password in "
        "the system keyring.",
    )
    if not hidden:
        LOG.warning(
            "The process command line could not be overwritten on this "
            "platform; the password may remain visible in `ps` output."
        )
