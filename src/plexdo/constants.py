# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared constants, type aliases, and the package logger."""

from pathlib import Path
from typing import Mapping, Tuple, Union
import datetime
import logging
import os

from plexapi.audio import Track
from plexapi.photo import Photo
from plexapi.video import Episode, Movie


DateInput = Union[str, datetime.date, datetime.datetime, None]


MediaItem = Union[Episode, Movie, Track, Photo]


def windows_app_dir(env: Mapping[str, str]) -> Path:
    """Return the per-user application directory on Windows.

    LOCALAPPDATA is the right home for both settings and caches; APPDATA is a
    roaming fallback, and the literal path is a last resort for the unusual
    case of neither being set.
    """
    base = env.get("LOCALAPPDATA") or env.get("APPDATA")
    if base:
        return Path(base) / "PlexDo"
    return Path.home() / "AppData" / "Local" / "PlexDo"


def default_paths(
    is_windows: bool, env: Mapping[str, str]
) -> Tuple[Path, Path, str]:
    """Return (config path, cache directory, default token_path).

    Windows has no XDG layout, and a dotted directory in the user profile is
    not where a Windows user would look, so settings and cache live under
    LOCALAPPDATA and the token defaults to the per-user temp directory.
    """
    if is_windows:
        app = windows_app_dir(env)
        return app / "plexdo.ini", app / "Cache", r"%TEMP%\plexdo.token"
    return (
        Path("~/.local/etc/plexdo.ini").expanduser(),
        Path("~/.cache/plexdo").expanduser(),
        "$XDG_RUNTIME_DIR/.plex.token",
    )


CONFIG_PATH, DEFAULT_CACHE_DIR, DEFAULT_TOKEN_PATH = default_paths(
    os.name == "nt", os.environ
)


LOG = logging.getLogger("plexdo")


# Group/other permission bits; any set on a secret file triggers a warning.
PERMISSIVE_MODE_MASK = 0o077


# Template written by `write-config-example` and echoed by its --help output.
_TOKEN_NOTE_POSIX = (
    "# Values may contain environment variables as $VAR or ${VAR}, and ~ for\n"
    "# your home directory. XDG_RUNTIME_DIR is a private, user-only tmpfs on\n"
    "# most Linux systems, which suits a secret -- but it is cleared at logout,\n"
    "# so you will need to run `plexdo login` again after each reboot. Point\n"
    "# token_path somewhere persistent if you would rather not.\n"
)

_TOKEN_NOTE_WINDOWS = (
    "# Values may contain environment variables as %VAR% or $VAR, and ~ for\n"
    "# your user profile. TEMP is per-user, but Windows may clear it and it is\n"
    "# not protected by file permissions, so point token_path at a directory\n"
    "# only your account can read if that matters to you.\n"
)


# Template written by `write-config-example` and echoed by its --help output.
CONFIG_EXAMPLE = (
    "[plex]\n"
    "url = http://localhost:32400\n"
    "\n"
    + (_TOKEN_NOTE_WINDOWS if os.name == "nt" else _TOKEN_NOTE_POSIX)
    + f"token_path = {DEFAULT_TOKEN_PATH}\n"
    "\n"
    "# Where the shell completion cache is kept. The default shown is this\n"
    "# platform's; uncomment to move it somewhere else.\n"
    f"# cache_dir = {DEFAULT_CACHE_DIR}\n"
    "\n"
    "# Optional credentials used by `plexdo login`.\n"
    "# The password is stored in plaintext, so keep this file readable only\n"
    "# by your own account.\n"
    "# Supplying --username on the command line ignores the password below.\n"
    "# username = you@example.com\n"
    "# password = your-plex-password\n"
    "\n"
    # Per-user credentials, one section per user ID (see `plexdo\n"
    "# list-users`). These are used only when the server refuses the\n"
    "# admin-issued token for that user, which happens when nothing has been\n"
    "# shared with them. The resulting token is saved to token_path, so the\n"
    "# login happens once rather than on every run.\n"
    "#\n"
    "# [99]\n"
    "# username = bob@example.com\n"
    "# password = bobs-plex-password\n"
)
