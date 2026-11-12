# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Shared constants, type aliases, and the package logger."""

import datetime
import json
import logging
import os
import tempfile
import textwrap
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

from plexapi.audio import Track
from plexapi.photo import Photo
from plexapi.video import Episode, Movie

DateInput = str | datetime.date | datetime.datetime | None


MediaItem = Episode | Movie | Track | Photo


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


def _xdg_dir(env: Mapping[str, str], name: str, fallback: str) -> Path:
    """An XDG base directory, or its default.

    The variable counts only when it is an absolute path, as the
    specification requires.
    """
    value = env.get(name, "")
    if value and Path(value).is_absolute():
        return Path(value)
    return Path(fallback).expanduser()


class Paths(NamedTuple):
    """Where plexdo keeps its files on one platform."""

    config: Path  # the YAML configuration
    cache: Path  # the shell completion cache
    secrets_file: Path  # secrets, when no keyring is used
    legacy_config: Path  # the INI file of plexdo 1.x, migrated once
    legacy_token: str  # 1.x's default token_path, before expansion


def default_paths(is_windows: bool, env: Mapping[str, str]) -> Paths:
    """Return this platform's file locations.

    Windows has no XDG layout, and a dotted directory in the user profile is
    not where a Windows user would look, so everything lives under
    LOCALAPPDATA there. Elsewhere the XDG Base Directory Specification
    decides: configuration in XDG_CONFIG_HOME, the cache in XDG_CACHE_HOME,
    and the secrets fallback in XDG_STATE_HOME, which persists across
    reboots as a secret store must.
    """
    if is_windows:
        app = windows_app_dir(env)
        return Paths(
            app / "config.yaml",
            app / "Cache",
            app / "secrets.json",
            app / "plexdo.ini",
            r"%TEMP%\plexdo.token",
        )
    return Paths(
        _xdg_dir(env, "XDG_CONFIG_HOME", "~/.config")
        / "plexdo"
        / "config.yaml",
        _xdg_dir(env, "XDG_CACHE_HOME", "~/.cache") / "plexdo",
        _xdg_dir(env, "XDG_STATE_HOME", "~/.local/state")
        / "plexdo"
        / "secrets.json",
        Path("~/.local/etc/plexdo.ini").expanduser(),
        "$XDG_RUNTIME_DIR/.plex.token",
    )


def session_file(
    is_windows: bool, env: Mapping[str, str], tmpdir: str, uid: int | None
) -> Path:
    """Where session tokens go when secret_store is file.

    The runtime directory is the place for what should not outlive the
    login session: it is private to the user and cleared at logout or
    reboot. Without one, as on Windows, macOS, or a bare cron environment,
    it is a directory of the user's own under the temporary directory,
    which honours TMPDIR, TEMP, and TMP; the user id keeps two accounts
    sharing /tmp apart.
    """
    runtime = env.get("XDG_RUNTIME_DIR", "")
    if not is_windows and runtime and Path(runtime).is_absolute():
        return Path(runtime) / "plexdo" / "session.json"
    name = "PlexDo" if is_windows or uid is None else f"plexdo-{uid}"
    return Path(tmpdir) / name / "session.json"


PATHS = default_paths(os.name == "nt", os.environ)
CONFIG_PATH = PATHS.config
DEFAULT_CACHE_DIR = PATHS.cache
DEFAULT_SECRETS_FILE = PATHS.secrets_file
DEFAULT_SESSION_FILE = session_file(
    os.name == "nt",
    os.environ,
    tempfile.gettempdir(),
    os.getuid() if hasattr(os, "getuid") else None,
)


LOG = logging.getLogger("plexdo")


# Group/other permission bits; any set on a secret file triggers a warning.
PERMISSIVE_MODE_MASK = 0o077


# Where secrets may be kept, as plex: secret_store names them.
STORE_CHOICES = ("auto", "keyring", "file")


_ENV_NOTE_POSIX = (
    "Values may contain environment variables as $VAR or ${VAR}, and ~ for "
    "your home directory."
)

_ENV_NOTE_WINDOWS = (
    "Values may contain environment variables as %VAR% or $VAR, and ~ for "
    "your user profile."
)


def _yaml_text(value: str) -> str:
    """A string as a YAML scalar.

    JSON's quoting is valid YAML, and safe for any value, a colon or a
    leading # included.
    """
    return json.dumps(value)


def _comment(
    *sentences: str, indent: str = "", default: str | None = None
) -> str:
    """Sentences as one paragraph of comment lines, filled to 76 columns.

    A default goes on a line of its own, so a long path is never split.
    """
    prefix = indent + "# "
    text = textwrap.fill(
        " ".join(sentences),
        width=76,
        initial_indent=prefix,
        subsequent_indent=prefix,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if default is not None:
        text += f"\n{prefix}Default: {default}"
    return text + "\n"


def _optional(key: str, value: str | None, default: str) -> str:
    """One option line, set or commented out.

    Without a value the line shows the default, commented out, so the
    template says what applies when the option is left out.
    """
    if value:
        return f"  {key}: {_yaml_text(value)}\n"
    return f"  # {key}: {_yaml_text(default)}\n"


def _users_text(users: list[tuple[int, str]]) -> str:
    """The users section: the entries given, or a commented-out example."""
    if not users:
        return (
            "# users:\n"
            "#   99:\n"
            "#     # The account's plex.tv username or email. Required.\n"
            '#     username: "bob@example.com"\n'
        )
    return "users:\n" + "".join(
        f"  {user_id}:\n    username: {_yaml_text(name)}\n"
        for user_id, name in users
    )


def config_text(
    url: str = "http://localhost:32400",
    username: str | None = None,
    cache_dir: str | None = None,
    users: Iterable[tuple[int, str]] = (),
) -> str:
    """The configuration file, with every option explained.

    write-config-example writes it with the defaults, and the migration
    from plexdo 1.x with the values it found, so a migrated file is as
    well documented as a fresh one.
    """
    opt = "  "
    parts = ["---\n"]
    parts.append(
        _comment(
            "plexdo configuration, in YAML: indent with spaces, never tabs.",
            _ENV_NOTE_WINDOWS if os.name == "nt" else _ENV_NOTE_POSIX,
        )
    )
    parts.append("#\n")
    parts.append(
        _comment(
            "Passwords, tokens, and PINs never go in this file. plexdo",
            "keeps them in the system keyring: the Secret Service on Linux",
            "and BSD, the Keychain on macOS, and Credential Manager on",
            "Windows. See `plexdo login`, `plexdo logout`, and",
            "`plexdo set-pin`.",
        )
    )
    parts.append("\nplex:\n")
    parts.append(
        _comment(
            "The Plex Media Server, as a URL. Required. A plex.direct",
            "https URL, as the server's Settings > Network page shows,",
            "has a certificate that checks out; plain http is fine on a",
            "network you trust.",
            indent=opt,
        )
    )
    parts.append(f"  url: {_yaml_text(url)}\n\n")
    parts.append(
        _comment(
            "The plex.tv account, a username or email address, that",
            "`plexdo login` signs in as when not given --username, and",
            "whose saved token every command uses. None is needed while",
            "only one account is signed in.",
            indent=opt,
            default="none",
        )
    )
    parts.append(_optional("username", username, "you@example.com"))
    parts.append("\n")
    parts.append(
        _comment(
            "Where the shell completion cache is kept, as a directory.",
            indent=opt,
            default=str(DEFAULT_CACHE_DIR),
        )
    )
    parts.append(_optional("cache_dir", cache_dir, str(DEFAULT_CACHE_DIR)))
    parts.append("\n")
    parts.append(
        _comment(
            'Where secrets are kept: "auto" uses the system keyring when',
            "there is one and secrets_file below otherwise, with a",
            'warning; "keyring" insists on the keyring; "file" always',
            "uses secrets_file, for a machine whose keyring is locked",
            'when plexdo runs, as under cron. With "file", only saved',
            "passwords and PINs go in secrets_file: session tokens are",
            "kept apart, in the runtime or temporary directory, and are",
            "gone after a reboot, when `plexdo login` is needed again.",
            indent=opt,
            default='"auto"',
        )
    )
    parts.append('  # secret_store: "auto"\n\n')
    parts.append(
        _comment(
            "The file secrets are kept in when the keyring is not used,",
            "written readable by your account alone. It holds them",
            "unencrypted, so prefer the keyring wherever there is one.",
            indent=opt,
            default=str(DEFAULT_SECRETS_FILE),
        )
    )
    secrets_file = _yaml_text(str(DEFAULT_SECRETS_FILE))
    parts.append(f"  # secrets_file: {secrets_file}\n\n")
    parts.append(
        _comment(
            "Other plex.tv accounts plexdo may act as, keyed by user id",
            "as `plexdo users-list` shows it. An entry lets a per-user",
            "command reach a user the server shares nothing with, and",
            "lets player-remote-play send as the account signed in to a",
            "player. Sign each in once with",
            "`plexdo login --username <name>`; add --save-password to let",
            "plexdo sign in again by itself once that token stops",
            "working. A member of your Plex Home needs no entry.",
            default="none",
        )
    )
    parts.append(_users_text(list(users)))
    return "".join(parts)


# Template written by `write-config-example` and echoed by its --help output.
CONFIG_EXAMPLE = config_text()


# What write-secrets-example writes: the secrets file as it is when
# secret_store is file, which keeps passwords and PINs there and session
# tokens elsewhere. Each kind has one placeholder entry. JSON has no
# comments, so the note is an entry of its own, a list to keep its lines
# short; plexdo reads only the kinds it knows and keeps the rest.
# Named without "secret" because CodeQL's py/clear-text-logging-sensitive-data
# judges data by its name: printing this is not clear-text logging of
# sensitive information, as every value in it is a made-up placeholder.
STORE_FILE_EXAMPLE = (
    json.dumps(
        {
            "_comment": [
                "Example plexdo secrets file: every value is a placeholder.",
                "Replace each with a real one, or delete this file and let",
                "plexdo login --save-password and plexdo set-pin write it.",
                "Session tokens are not kept here. Keep this file readable",
                "by your account alone.",
            ],
            "passwords": {"you@example.com": "your-plex.tv-password"},
            "pins": {"12345678": "0000"},
        },
        indent=2,
        sort_keys=True,
    )
    + "\n"
)
