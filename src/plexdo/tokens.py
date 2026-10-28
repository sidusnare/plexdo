# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Saved credentials: plex.tv tokens, passwords, and Plex Home PINs.

All of them are kept in the secret store (plexdo.secret_store), never in
the configuration file. Tokens are filed by the username they were saved
under; a password is saved only when login is asked to, so plexdo can sign
in again by itself once a token stops working; a PIN is filed by user id.
"""

from collections.abc import Iterable

from plexdo import secret_store
from plexdo.constants import LOG

# Key holding the admin token when no admin username is configured. The "@"
# prefix cannot occur in a Plex username, so it can never collide with one.
ADMIN_KEY = "@admin"

TokenStore = dict[str, str]


def load_store() -> TokenStore:
    """Every saved token, as username -> token."""
    return secret_store.load("tokens")


def lookup(username: str) -> str | None:
    """Return the stored token for a username, or None."""
    return load_store().get(username)


def store_token(username: str, token: str) -> None:
    """Add or replace one username's token, preserving the others."""
    store = load_store()
    store[username] = token
    secret_store.save("tokens", store)
    LOG.debug("Stored token for %r", username)


def admin_token(username: str | None) -> str | None:
    """Return the admin token.

    Tries the configured admin username, then the reserved key, and finally a
    store holding exactly one entry - which is what a fresh `login` with no
    configured username leaves behind.
    """
    store = load_store()
    if username and username in store:
        return store[username]
    if ADMIN_KEY in store:
        return store[ADMIN_KEY]
    if len(store) == 1:
        return next(iter(store.values()))
    return None


def forget_tokens(usernames: Iterable[str]) -> int:
    """Remove usernames' tokens, returning how many are left.

    The entry goes once the last token does, so no secret outlives it and
    the next command says to run `login`, which is the advice that then
    applies.
    """
    store = load_store()
    for username in usernames:
        store.pop(username, None)
    secret_store.save("tokens", store)
    return len(store)


def saved_password(username: str) -> str | None:
    """The password saved for a username, or None."""
    return secret_store.load("passwords").get(username)


def save_password(username: str, password: str) -> None:
    """Save one username's password, preserving the others."""
    passwords = secret_store.load("passwords")
    passwords[username] = password
    secret_store.save("passwords", passwords)
    LOG.debug("Saved the password for %r", username)


def forget_passwords(usernames: Iterable[str]) -> int:
    """Remove usernames' saved passwords, returning how many were removed."""
    passwords = secret_store.load("passwords")
    removed = [name for name in usernames if passwords.pop(name, None)]
    if removed:
        secret_store.save("passwords", passwords)
    return len(removed)


def saved_pin(user_id: int) -> str | None:
    """The Plex Home PIN saved for a user id, or None."""
    return secret_store.load("pins").get(str(user_id))


def save_pin(user_id: int, pin: str | None) -> None:
    """Save a user id's PIN, or remove it when pin is None."""
    pins = secret_store.load("pins")
    if pin is None:
        pins.pop(str(user_id), None)
    else:
        pins[str(user_id)] = pin
    secret_store.save("pins", pins)
