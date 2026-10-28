# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Loading the YAML configuration, and permission checks on secret files.

The file holds no secrets: passwords, tokens, and PINs live in the secret
store (plexdo.secret_store). What is read here is checked as it is loaded,
so a mistyped option is reported once, by name, rather than surfacing later
as a baffling default.
"""

import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from plexdo.constants import (
    CONFIG_PATH,
    LOG,
    PERMISSIVE_MODE_MASK,
    SECRET_STORES,
)

# The parsed configuration: {"plex": {option: text}, "users": {id: {...}}},
# every value a stripped string, every user id a string of digits.
Config = dict[str, dict[str, Any]]

_PLEX_OPTIONS = ("url", "username", "cache_dir", "secret_store", "secrets_file")
_USER_OPTIONS = ("username",)

# Secrets plexdo 1.x kept in its INI file, which must not come back here.
_SECRET_OPTIONS = ("password", "pin", "token", "token_path")


def check_file_permissions(path: Path, label: str) -> None:
    """Warn if a secret-bearing file is readable by group or other.

    Emitted at WARNING level so it surfaces without --verbose, and on stderr
    so it can never contaminate --json output.
    """
    if os.name == "nt":
        # Windows has no POSIX mode bits; os.stat synthesises 0o666, which
        # would trip this check on every run with advice (chmod) that cannot
        # help. Access there is governed by ACLs instead.
        LOG.debug("Skipping POSIX permission check for %s on Windows", path)
        return
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    leaked = mode & PERMISSIVE_MODE_MASK
    if leaked:
        LOG.warning(
            "SECURITY: %s at %s has mode %04o - readable by %s. "
            "Tighten it with: chmod 600 %s",
            label,
            path,
            mode & 0o7777,
            "group and others" if leaked & 0o007 else "group",
            path,
        )


def expand_environment(value: str, where: str) -> str:
    """Expand environment variables in one value, warning about unset ones.

    os.path.expandvars follows the platform: $VAR and ${VAR} everywhere, plus
    %VAR% on Windows. It leaves an unset variable as literal text, which would
    surface later as a baffling "no such file" for a path like
    "$XDG_STATE_HOME/plexdo", so an unresolved name is warned about here in
    whichever spelling the platform accepts.
    """
    expanded = os.path.expandvars(value)
    if expanded != value:
        LOG.debug("Expanded environment variables in %s", where)
    unresolved = re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", expanded)
    if os.name == "nt":
        unresolved += re.findall(r"%([A-Za-z_][A-Za-z0-9_]*)%", expanded)
    for name in unresolved:
        LOG.warning(
            "%s references the environment variable %s, which is not set; "
            "leaving it literal. Set it, or use an absolute path in %s.",
            where,
            name,
            CONFIG_PATH,
        )
    return expanded


def _text(value: Any, where: str) -> str | None:
    """A scalar option as stripped text, or None when empty.

    A list or mapping where a value belongs is an error naming the option.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        sys.exit(
            f"{where} in {CONFIG_PATH} must be a single value, not a "
            f"{'mapping' if isinstance(value, dict) else 'list'}."
        )
    text = str(value).strip()
    return text or None


def _options(raw: Any, allowed: tuple[str, ...], where: str) -> dict[str, str]:
    """One mapping of options, checked.

    Unknown names are warned about, and a secret is refused, since it
    belongs in the secret store.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        sys.exit(f"{where} in {CONFIG_PATH} must be a mapping of options.")
    options = {}
    for key, value in raw.items():
        name = str(key)
        if name in _SECRET_OPTIONS:
            LOG.warning(
                "%s: %s in %s is ignored: secrets are kept in the system "
                "keyring now. Remove it from the file, and see plexdo login "
                "--save-password and plexdo set-pin.",
                where,
                name,
                CONFIG_PATH,
            )
            continue
        if name not in allowed:
            LOG.warning(
                "%s: unknown option %r in %s is ignored; the options are %s.",
                where,
                name,
                CONFIG_PATH,
                ", ".join(allowed),
            )
            continue
        text = _text(value, f"{where}: {name}")
        if text is not None:
            options[name] = text
    return options


def parse_config(text: str) -> Config:
    """Parse and check the configuration file's text."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        sys.exit(f"{CONFIG_PATH} is not valid YAML: {exc}")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        sys.exit(f"{CONFIG_PATH} must be a mapping with a plex: section.")
    for key in raw:
        if key not in ("plex", "users"):
            LOG.warning(
                "Unknown section %r in %s is ignored; the sections "
                "are plex and users.",
                key,
                CONFIG_PATH,
            )

    plex = _options(raw.get("plex"), _PLEX_OPTIONS, "plex")
    for key in ("cache_dir", "secrets_file", "url"):
        if key in plex:
            plex[key] = expand_environment(plex[key], f"plex: {key}")
    store = plex.get("secret_store", "auto")
    if store not in SECRET_STORES:
        sys.exit(
            f"plex: secret_store in {CONFIG_PATH} is {store!r}; it must "
            f"be one of {', '.join(SECRET_STORES)}."
        )

    users_raw = raw.get("users") or {}
    if not isinstance(users_raw, dict):
        sys.exit(f"users in {CONFIG_PATH} must be a mapping of user ids.")
    users = {}
    for key, entry in users_raw.items():
        user_id = str(key).strip()
        if not user_id.isdigit():
            sys.exit(
                f"users: {key!r} in {CONFIG_PATH} is not a user id; "
                "use the numeric id plexdo list-users shows."
            )
        users[user_id] = _options(entry, _USER_OPTIONS, f"users: {user_id}")
    return {"plex": plex, "users": users}


def load_config() -> Config:
    """Load and return the configuration, failing fast if absent."""
    if not CONFIG_PATH.exists():
        sys.exit(
            f"Config not found: {CONFIG_PATH}\n"
            "Run `plexdo write-config-example` to create a template."
        )
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        sys.exit(f"Could not read {CONFIG_PATH}: {exc}")
    cfg = parse_config(text)
    LOG.debug("Loaded config from %s", CONFIG_PATH)
    return cfg


@lru_cache(maxsize=1)
def cached_config() -> Config:
    """Return the parsed config, reading the file at most once per process.

    Memoised so the per-user paths can reach the users entries without
    re-reading the file, and re-emitting its warnings, once per user in a
    loop.
    """
    return load_config()


def config_optional(cfg: Config, key: str) -> str | None:
    """Return an optional plex: option, or None."""
    return cfg["plex"].get(key)


def user_option(cfg: Config, user_id: int, key: str) -> str | None:
    """Return an option of one users entry, or None."""
    return cfg["users"].get(str(user_id), {}).get(key)


def configured_users(cfg: Config) -> list[tuple[int, str]]:
    """(user id, username) for each users entry naming a username."""
    return [
        (int(user_id), entry["username"])
        for user_id, entry in cfg["users"].items()
        if "username" in entry
    ]
