# SPDX-License-Identifier: GPL-3.0-or-later

"""The on-disk token store: a JSON object of username -> Plex token.

Earlier versions wrote a single bare token to this path. A file that is not
JSON is therefore read as one legacy admin token and rewritten on the next
save, so upgrading needs no manual step.
"""

from pathlib import Path
from typing import Dict, Iterable, Optional
import json
import os

from plexdo.constants import LOG


# Key holding the admin token when no admin username is configured. The "@"
# prefix cannot occur in a Plex username, so it can never collide with one.
ADMIN_KEY = "@admin"

TokenStore = Dict[str, str]


def load_store(path: Path) -> TokenStore:
    """Read the token store, tolerating an absent, empty, or legacy file."""
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        LOG.warning("Could not read token file %s: %s", path, exc)
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Pre-1.0.4 files held one bare token and nothing else.
        LOG.debug("Reading %s as a legacy single-token file", path)
        return {ADMIN_KEY: raw}
    if not isinstance(data, dict):
        LOG.warning("Token file %s is not a JSON object; ignoring it", path)
        return {}
    return {str(key): str(value) for key, value in data.items() if value}


def save_store(path: Path, store: TokenStore) -> None:
    """Write the token store atomically, owner-readable only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(store, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if os.name != "nt":
        tmp.chmod(0o600)
    tmp.replace(path)
    LOG.debug("Token store written to %s (%d entries)", path, len(store))


def lookup(path: Path, username: str) -> Optional[str]:
    """Return the stored token for a username, or None."""
    return load_store(path).get(username)


def store_token(path: Path, username: str, token: str) -> None:
    """Add or replace one username's token, preserving the others."""
    store = load_store(path)
    store[username] = token
    save_store(path, store)
    LOG.debug("Stored token for %r", username)


def admin_token(path: Path, username: Optional[str]) -> Optional[str]:
    """Return the admin token.

    Tries the configured admin username, then the reserved key, and finally a
    store holding exactly one entry - which is what a fresh `login` with no
    configured username leaves behind.
    """
    store = load_store(path)
    if username and username in store:
        return store[username]
    if ADMIN_KEY in store:
        return store[ADMIN_KEY]
    if len(store) == 1:
        return next(iter(store.values()))
    return None


def forget_tokens(path: Path, usernames: Iterable[str]) -> int:
    """Remove usernames' tokens, returning how many entries are left.

    A store left empty is deleted rather than kept as an empty object, so
    no secrets file outlives its last secret and the next command says to
    run `login`, which is the advice that then applies.
    """
    store = load_store(path)
    for username in usernames:
        store.pop(username, None)
    if store:
        save_store(path, store)
    elif path.exists():
        path.unlink()
        LOG.debug("Token store %s is empty; removed it", path)
    return len(store)
