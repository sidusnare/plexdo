# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""User lookup, per-user servers, and account classification."""

import argparse
import sys
from collections.abc import Iterator
from typing import Any

from plexapi.exceptions import BadRequest, NotFound, Unauthorized
from plexapi.myplex import MyPlexAccount, MyPlexUser
from plexapi.server import PlexServer

from plexdo.config import cached_config, configured_users, user_option
from plexdo.console import clean_text
from plexdo.constants import LOG
from plexdo.identify import resolve_identifier
from plexdo.tokens import lookup, saved_password, store_token


class UserAccessError(RuntimeError):
    """The server refused to act on behalf of a user.

    Deliberately an ordinary Exception rather than a sys.exit: it must be
    catchable so copy-playlist-all-users can skip one inaccessible user and
    carry on down the list. cli.main turns it into a clean exit for the
    single-user commands.

    Carries a one-line ``summary`` alongside the full explanation, so a loop
    over many users can report each failure in one line instead of repeating
    three paragraphs of advice per user.
    """

    def __init__(self, message: str, summary: str) -> None:
        super().__init__(message)
        self.summary = summary


def _access_denied(user_title: str, user_id: int) -> UserAccessError:
    """Build the explanation shown when a user's token is rejected."""
    return UserAccessError(
        f"Access denied for user {user_title!r} (id={user_id}): the Plex "
        f"server rejected that user's token.\n\n"
        "Plex scopes every token to what that user can actually see, and "
        "being the server admin does not override it. A user with no "
        "libraries shared to them has no access to this server at all, so "
        "there is nothing an admin token can do on their behalf.\n\n"
        f"Share at least one library with {user_title!r} in Plex under "
        "Settings > Users & Sharing, then try again.\n\n"
        "If that user does have access under their own login, add a "
        f"users: {user_id}: entry with their username to the config file, "
        "and sign them in once with plexdo login --username; their token "
        "will then be used automatically. Pass 0 to act as the admin "
        "account itself.",
        summary=(
            f"access denied (401) - no libraries are shared with "
            f"{user_title!r} on this server"
        ),
    )


def connect_with_token(plex: PlexServer, token: str) -> PlexServer | None:
    """Return a server connected with a token, or None if it is refused."""
    try:
        # pylint: disable-next=protected-access
        return PlexServer(plex._baseurl, token)
    except Unauthorized as exc:
        # plexapi attaches the server's HTML error page here; keep it for
        # --debug so it never reaches the user's terminal.
        LOG.debug("Token rejected by server: %s", exc)
        return None


def _candidate_usernames(user_id: int, user: MyPlexUser) -> list[str]:
    """Names this user's token might be filed under, most specific first."""
    configured = user_option(cached_config(), user_id, "username")
    names = [
        configured,
        getattr(user, "username", None),
        getattr(user, "email", None),
        getattr(user, "title", None),
    ]
    seen: list[str] = []
    for name in names:
        text = clean_text(name or "")
        if text and text not in seen:
            seen.append(text)
    return seen


def connect_as_shared_user(
    plex: PlexServer, user: MyPlexUser
) -> PlexServer | None:
    """Stage 1: the admin-issued, server-scoped token for this user."""
    try:
        token = user.get_token(plex.machineIdentifier)
    except (BadRequest, NotFound, Unauthorized) as exc:
        LOG.debug("get_token failed for %r: %s", user.title, exc)
        return None
    if not token:
        LOG.debug("get_token returned nothing for %r", user.title)
        return None
    return connect_with_token(plex, token)


def _connect_from_store(
    plex: PlexServer, user: MyPlexUser, user_id: int
) -> PlexServer | None:
    """Stage 2: a token saved previously for this user."""
    for name in _candidate_usernames(user_id, user):
        token = lookup(name)
        if not token:
            continue
        server = connect_with_token(plex, token)
        if server is not None:
            LOG.info("Using stored token for %r", name)
            return server
        LOG.debug("Stored token for %r was rejected; will try logging in", name)
    return None


def _login_entry(user_id: int) -> tuple[str, MyPlexAccount] | None:
    """Sign in as the users entry for user_id, with its saved password.

    Returns the configured username with the account, since that is the
    name its token is filed under, or None when there is no entry, no
    password was saved for it, or plex.tv refuses it.
    """
    username = user_option(cached_config(), user_id, "username")
    password = saved_password(username) if username else None
    if not (username and password):
        LOG.debug(
            "No users entry with a saved password for user id %s", user_id
        )
        return None

    LOG.info("Logging in as %r for user id %s", username, user_id)
    try:
        return username, MyPlexAccount(username=username, password=password)
    except (Unauthorized, BadRequest) as exc:
        LOG.warning("Login failed for %r: %s", username, exc)
        return None


def _connect_by_login(plex: PlexServer, user_id: int) -> PlexServer | None:
    """Stage 3: log in as the users entry, with its saved password."""
    login = _login_entry(user_id)
    if login is None:
        return None
    username, account = login

    token = account.authenticationToken
    server = connect_with_token(plex, token)
    if server is None:
        LOG.warning(
            "%r signed in to plex.tv but that account cannot reach this "
            "server; nothing has been shared with it.",
            username,
        )
        return None

    store_token(username, token)
    LOG.info("Saved a token for %r for future runs", username)
    return server


def _stored_account(username: str) -> MyPlexAccount | None:
    """The plex.tv account behind a stored token, or None if it is stale."""
    token = lookup(username)
    if not token:
        return None
    try:
        return MyPlexAccount(token=token)
    except Unauthorized as exc:
        LOG.debug("Stored token for %r was rejected: %s", username, exc)
        return None


def configured_entries() -> list[tuple[int, str]]:
    """(user id, username) for each users entry in the config."""
    return configured_users(cached_config())


def configured_account(user_id: int, username: str) -> MyPlexAccount | None:
    """The account of one users entry, signed in, or None.

    A token already stored for the entry's username is used when plex.tv
    still accepts it; otherwise a password saved for it signs in, and the
    new token is saved so that happens once.
    """
    account = _stored_account(username)
    if account is not None:
        return account
    login = _login_entry(user_id)
    if login is None:
        return None
    account = login[1]
    store_token(username, account.authenticationToken)
    LOG.info("Saved a token for %r for future runs", username)
    return account


def configured_accounts() -> Iterator[tuple[int, MyPlexAccount]]:
    """Each account with a users entry in the config, signed in.

    Accounts are produced one at a time, so a caller that finds what it
    wants early signs in no more.
    """
    for user_id, username in configured_entries():
        account = configured_account(user_id, username)
        if account is not None:
            yield user_id, account


def server_for_user(plex: PlexServer, user_id: int) -> PlexServer:
    """Return a PlexServer scoped to the given user.

    Pass user_id=0 to use the admin account (the saved admin token).

    Otherwise three sources are tried in turn, because a server will refuse
    an admin-issued token for a user it has shared nothing with:

    1. the server-scoped token the admin can mint via get_token()
    2. a token already saved in the secret store for that user
    3. a fresh login as the users entry for the user ID, with a password
       saved by login --save-password, whose token is then saved for next
       time

    Raises UserAccessError when none of them yields access.
    """
    if user_id == 0:
        LOG.debug("user_id=0: using admin account")
        return plex

    account = plex.myPlexAccount()
    user: MyPlexUser = _find_user_by_id(account, user_id)

    for stage, connect in (
        ("admin-issued token", lambda: connect_as_shared_user(plex, user)),
        ("stored token", lambda: _connect_from_store(plex, user, user_id)),
        ("configured credentials", lambda: _connect_by_login(plex, user_id)),
    ):
        server = connect()
        if server is not None:
            LOG.debug("Connected as %r via %s", user.title, stage)
            return server
        LOG.debug("Could not connect as %r via %s", user.title, stage)

    raise _access_denied(user.title, user_id)


def _find_user_by_id(account: MyPlexAccount, user_id: int) -> MyPlexUser:
    """Locate a MyPlexUser by numeric id, failing fast if absent."""
    for user in account.users():
        if int(user.id) == user_id:
            return user
    sys.exit(f"User ID not found: {user_id}")


def _is_restricted(user: MyPlexUser) -> bool:
    """Return True if the user is a restricted (managed) account.

    plexapi exposes `restricted` as the raw XML string rather than a bool,
    so a plain truth test would treat the common "0" value as True and
    mislabel every account as managed.
    """
    raw = getattr(user, "restricted", None)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() not in ("", "0", "false")


def account_type(user: MyPlexUser) -> str:
    """Classify a user account as managed, home, friend, or shared."""
    if _is_restricted(user):
        return "managed"
    if getattr(user, "home", False):
        return "home"
    if getattr(user, "friend", False):
        return "friend"
    return "shared"


# Namespace attributes that hold a user identifier, resolved centrally in
# cli.main() so every command handler receives a plain numeric user ID.
USER_ID_ARGUMENTS = (
    "user_id",
    "user_a",
    "user_b",
    "source_user_id",
    "dest_user_id",
)


def user_roster(plex: PlexServer) -> list[tuple[int, str]]:
    """Return (id, title) for the admin account and every shared user."""
    account = plex.myPlexAccount()
    roster = [(0, clean_text(getattr(account, "title", "") or "admin"))]
    roster.extend(
        (int(user.id), clean_text(user.title or "")) for user in account.users()
    )
    return roster


def resolve_user_identifier(roster: list[tuple[int, str]], value: Any) -> int:
    """Resolve a numeric user ID or a user title to a numeric user ID."""
    return resolve_identifier(roster, value, "user", "list-users")


def resolve_user_arguments(
    plex: PlexServer, args: "argparse.Namespace"
) -> None:
    """Replace user ID/title arguments with numeric user IDs, in place.

    The roster is fetched once per invocation, so a command taking two user
    arguments costs a single extra API call rather than two, and a command
    given none of them costs nothing.
    """
    present = [
        name
        for name in USER_ID_ARGUMENTS
        if getattr(args, name, None) is not None
    ]
    if not present:
        return
    roster = user_roster(plex)
    for name in present:
        setattr(
            args, name, resolve_user_identifier(roster, getattr(args, name))
        )
