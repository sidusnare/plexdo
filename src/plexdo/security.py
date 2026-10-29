# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Keeping secrets out of the process listing and out of every log.

scrub_password_argument hides a --password given on the command line.
redact rewrites a log line so no secret survives in it: the value of
anything named like a token, password, PIN, or credential header, the
password in a URL, and any secret this run has met, wherever it appears.
"""

import argparse
import base64
import binascii
import ctypes
import re
import sys
from collections.abc import Mapping
from urllib.parse import parse_qsl, urlsplit

from plexdo.constants import LOG

REDACTED = "***"

# Names whose values are secrets wherever they appear: query parameters,
# HTTP headers, JSON keys, and key=value text. Matched whole, ignoring case.
_SECRET_NAMES = (
    r"[\w.-]*(?:token|password|passwd|secret)"
    r"|x-plex-pin|pin|x-plex-code|verificationcode"
    r"|authorization|proxy-authorization|cookie|set-cookie"
)
_SECRET_NAME = re.compile(rf"(?:{_SECRET_NAMES})", re.IGNORECASE)
# name=value, name: value, 'name': 'value', "name":"value". A credential
# header's scheme, such as Basic, goes with its value.
_ASSIGNED = re.compile(
    rf"(?<![\w.-])({_SECRET_NAMES})(['\"]?\s*[:=]\s*['\"]?)"
    r"((?:(?:basic|bearer|digest)\s+)?[^\s&#'\",;}]+)",
    re.IGNORECASE,
)
# The password in scheme://user:password@host.
_USERINFO = re.compile(r"(\b[a-z][a-z0-9+.-]*://[^/\s:@]*:)[^/\s@]+@", re.I)
# Shorter values are not looked for everywhere: a four-digit PIN would
# blank out every number that happened to match it. Named, it is still
# redacted.
_SHORTEST_HIDDEN = 8


class _KnownSecrets:
    """The secrets this run has met, to be redacted wherever they appear."""

    def __init__(self) -> None:
        self.secrets: set[str] = set()
        self.pattern: re.Pattern[str] | None = None

    def add(self, value: str) -> None:
        """Look for value from now on, if it is long enough to be safe."""
        if len(value) < _SHORTEST_HIDDEN or value in self.secrets:
            return
        self.secrets.add(value)
        # Longest first, so a secret containing another is hidden whole.
        ordered = sorted(self.secrets, key=len, reverse=True)
        self.pattern = re.compile("|".join(map(re.escape, ordered)))

    def sub(self, text: str) -> str:
        """Text with every known secret replaced."""
        return self.pattern.sub(REDACTED, text) if self.pattern else text


_KNOWN = _KnownSecrets()


def hide_in_logs(secret: str | None) -> None:
    """Redact this secret from every log line from now on."""
    if secret:
        _KNOWN.add(str(secret))


def hide_request_secrets(url: str, headers: Mapping[str, str]) -> None:
    """Redact, from now on, every secret an HTTP request carries.

    A token sent in a header or a query parameter is then hidden even where
    some other library logs it without its name, and a Basic credential's
    password with it.
    """
    for name, value in parse_qsl(urlsplit(url).query):
        if _SECRET_NAME.fullmatch(name):
            hide_in_logs(value)
    for name, value in headers.items():
        if not _SECRET_NAME.fullmatch(name):
            continue
        scheme, _, credential = str(value).partition(" ")
        hide_in_logs(credential or scheme)
        if scheme.lower() == "basic" and credential:
            try:
                decoded = base64.b64decode(credential).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                continue
            hide_in_logs(decoded.partition(":")[2])


def redact(text: str) -> str:
    """Text with every secret in it replaced by ***."""
    text = _ASSIGNED.sub(lambda m: m.group(1) + m.group(2) + REDACTED, text)
    text = _USERINFO.sub(lambda m: m.group(1) + REDACTED + "@", text)
    return _KNOWN.sub(text)


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """HTTP headers as a plain dict, with every credential's value hidden."""
    return {
        str(name): REDACTED
        if _SECRET_NAME.fullmatch(str(name))
        else redact(str(value))
        for name, value in headers.items()
    }


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

    hide_in_logs(secret)
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
