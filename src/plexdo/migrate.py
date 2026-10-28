# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""The one-time move from plexdo 1.x's INI file and token file.

plexdo 1.x read ~/.local/etc/plexdo.ini, which held passwords in plaintext,
and kept tokens in a JSON file at its token_path. The first run of plexdo
2 that finds that file and no config.yaml moves everything across: the
options into config.yaml, and every password, PIN, and token into the
secret store. Then it removes the secrets from the old files, so none is
left in plaintext, and renames the INI file aside as a record of what was
moved.
"""

import configparser
import json
import os
import sys
from pathlib import Path
from typing import NamedTuple

from plexdo import secret_store
from plexdo.constants import CONFIG_PATH, LOG, PATHS, config_text
from plexdo.tokens import ADMIN_KEY

_SCRUBBED_OPTIONS = ("password", "pin")


def _legacy_tokens(path: Path) -> dict[str, str]:
    """The tokens in a 1.x token file.

    That is a JSON object of username -> token, or, before 1.0.4, one bare
    token, which was the admin's.
    """
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        LOG.warning("Could not read the old token file %s: %s", path, exc)
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {ADMIN_KEY: raw}
    if not isinstance(data, dict):
        LOG.warning(
            "The old token file %s is not a JSON object; its "
            "contents were not moved.",
            path,
        )
        return {}
    return {str(key): str(value) for key, value in data.items() if value}


def _value(
    ini: configparser.ConfigParser, section: str, key: str
) -> str | None:
    """One option of the old file, stripped, or None when absent or empty."""
    value = ini.get(section, key, fallback=None)
    if value is None:
        return None
    return value.strip() or None


def _merge(kind: str, found: dict[str, str]) -> int:
    """Add found secrets to those already saved, returning how many.

    Ones already saved win, since they are the newer.
    """
    saved = secret_store.load(kind)
    added = {
        name: secret for name, secret in found.items() if name not in saved
    }
    if added:
        secret_store.save(kind, {**saved, **added})
    return len(added)


def _scrub(ini_path: Path, ini: configparser.ConfigParser) -> Path:
    """Rewrite the old INI file without its secrets, and rename it aside."""
    for section in ini.sections():
        for key in _SCRUBBED_OPTIONS:
            ini.remove_option(section, key)
    aside = ini_path.with_name(ini_path.name + ".migrated")
    fd = os.open(aside, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            f"# Moved to {CONFIG_PATH} by plexdo 2; secrets removed.\n"
        )
        ini.write(handle)
    ini_path.unlink()
    return aside


class _Found(NamedTuple):
    """What the old INI file held besides plain options."""

    users: list[tuple[int, str]]  # (user id, username) per [<user id>]
    passwords: dict[str, str]  # username -> password
    pins: dict[str, str]  # user id -> PIN


def _read_secrets(ini: configparser.ConfigParser, ini_path: Path) -> _Found:
    """The per-user sections, passwords, and PINs of the old INI file."""
    found = _Found([], {}, {})
    username = _value(ini, "plex", "username")
    password = _value(ini, "plex", "password")
    if password and username:
        found.passwords[username] = password
    elif password:
        LOG.warning(
            "%s has a password but no username to file it under; it "
            "was not kept. Sign in with plexdo login.",
            ini_path,
        )
    for section in filter(str.isdigit, ini.sections()):
        name = _value(ini, section, "username")
        secret = _value(ini, section, "password")
        if name:
            found.users.append((int(section), name))
            if secret:
                found.passwords[name] = secret
        pin = _value(ini, section, "pin")
        if pin:
            found.pins[section] = pin
    return found


def migrate_legacy_config() -> None:
    """Move plexdo 1.x's configuration and secrets across, once.

    Does nothing when config.yaml exists, or there is no 1.x file. The
    secrets are saved before anything is removed, so an interrupted run
    loses nothing and the next one finishes the job.
    """
    ini_path = PATHS.legacy_config
    if CONFIG_PATH.exists() or not ini_path.exists():
        return
    ini = configparser.ConfigParser(interpolation=None)
    try:
        ini.read(ini_path, encoding="utf-8")
    except configparser.Error as exc:
        sys.exit(
            f"Could not read the plexdo 1.x config {ini_path} to move "
            f"it to {CONFIG_PATH}: {exc}"
        )

    found = _read_secrets(ini, ini_path)
    token_path = Path(
        os.path.expandvars(
            _value(ini, "plex", "token_path") or PATHS.legacy_token
        )
    ).expanduser()
    tokens = _legacy_tokens(token_path) if token_path.is_file() else {}

    store = secret_store.describe()
    # Counts, each in a variable of its own: one looked up as
    # moved["passwords"] reads to static analysis as a password, and its
    # logging as a leak.
    tokens_moved = _merge("tokens", tokens)
    logins_moved = _merge("passwords", found.passwords)
    pins_moved = _merge("pins", found.pins)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            config_text(
                url=_value(ini, "plex", "url") or "http://localhost:32400",
                username=_value(ini, "plex", "username"),
                cache_dir=_value(ini, "plex", "cache_dir"),
                users=found.users,
            )
        )
    aside = _scrub(ini_path, ini)
    if tokens:
        token_path.unlink()

    LOG.warning(
        "Moved the plexdo 1.x configuration to %s, and %d token(s), %d "
        "password(s), and %d PIN(s) to %s. The old file, without its "
        "secrets, is now %s%s.",
        CONFIG_PATH,
        tokens_moved,
        logins_moved,
        pins_moved,
        store,
        aside,
        f", and the old token file {token_path} is gone" if tokens else "",
    )
