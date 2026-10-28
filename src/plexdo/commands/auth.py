# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Authentication, saved secrets, and config bootstrap commands."""

import argparse
import getpass
import os
import sys
import textwrap
from typing import Any

from plexapi.exceptions import BadRequest, PlexApiException, Unauthorized
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from requests import RequestException

from plexdo import secret_store
from plexdo.config import Config, config_optional, load_config
from plexdo.connection import server_url
from plexdo.console import output, output_format
from plexdo.constants import CONFIG_EXAMPLE, CONFIG_PATH, LOG
from plexdo.tokens import (
    ADMIN_KEY,
    TokenStore,
    forget_logins,
    forget_tokens,
    load_store,
    save_password,
    save_pin,
    saved_password,
    store_token,
)

# Outcomes after which a token is gone from plex.tv, so from the store too.
_SIGNED_OUT = ("signed out", "already signed out")


def _prompt_username(supplied: str | None) -> str:
    """Return the username, prompting if it was not supplied."""
    username = supplied or input("Plex username or email: ").strip()
    if not username:
        sys.exit("Username is required.")
    return username


def _prompt_password() -> str:
    """Read the password without echoing it to the terminal."""
    password = getpass.getpass("Plex password: ")
    if not password:
        sys.exit("Password is required.")
    return password


def resolve_credentials(
    cfg: Config, args: argparse.Namespace
) -> tuple[str, str]:
    """Resolve (username, password) from arguments, config, and saved secrets.

    The username is --username, else plex: username, else prompted for. The
    password is --password, else the one saved for that username by an
    earlier login --save-password, else prompted for. A saved password is
    filed by username, so it can never be paired with the wrong account.
    """
    username = args.username or config_optional(cfg, "username")
    if username:
        LOG.debug("Signing in as %s", username)
    else:
        username = _prompt_username(None)
    password = args.password or saved_password(username)
    if password and not args.password:
        LOG.debug("Using the password saved for %s", username)
    return username, password or _prompt_password()


def _obtain_token(username: str, password: str, code: str | None) -> str:
    """Authenticate against plex.tv and return the account auth token."""
    kwargs: dict[str, Any] = {"username": username, "password": password}
    if code:
        kwargs["code"] = code
    try:
        account = MyPlexAccount(**kwargs)
    except Unauthorized:
        sys.exit(
            "Authentication failed: bad username/password, or a two-factor "
            "code is required (retry with --code)."
        )
    except BadRequest as exc:
        sys.exit(f"Login rejected by plex.tv: {exc}")
    return account.authenticationToken


def _verify_token(url: str, token: str) -> bool:
    """Return True if the token can connect to the configured server."""
    try:
        PlexServer(url, token)
        return True
    except Exception as exc:  # pylint: disable=broad-except
        LOG.warning("Token saved but could not connect to %s: %s", url, exc)
        return False


def cmd_login(_plex: PlexServer | None, args: argparse.Namespace) -> None:
    """Authenticate with plex.tv and save the token to the secret store."""
    cfg = load_config()
    url = server_url(cfg)

    username, password = resolve_credentials(cfg, args)
    code: str | None = args.code
    if args.two_factor and not code:
        code = input("Two-factor code: ").strip() or None

    LOG.info("Authenticating %s against plex.tv", username)
    token = _obtain_token(username, password, code)

    store = secret_store.describe()
    if args.dry_run:
        LOG.info("--dry-run: not saving the token.")
        saving = " and the password" if args.remember_login else ""
        print(
            f"Authenticated. The token{saving} would be saved to {store}.",
            file=sys.stderr,
        )
        return

    store_token(username or ADMIN_KEY, token)
    if args.remember_login:
        save_password(username, password)
    verified = _verify_token(url, token)

    if output_format(args) == "table":
        print(f"Token saved to {store}.")
        if args.remember_login:
            print(
                "Password saved alongside it, to sign in again when the "
                "token stops working."
            )
        if verified:
            print(f"Verified against: {url}")
    else:
        output(
            {
                "user": username,
                "store": store,
                "verified": verified,
                "passwordSaved": bool(args.remember_login),
            },
            args,
        )


def _logout_targets(
    store: TokenStore, wanted: str | None, where: str
) -> list[str]:
    """The stored names to sign out: every one, or the one asked for.

    The name matches exactly first and then ignoring case, as an email
    address would; a name the store does not hold is an error listing those
    it does, since signing out nobody would read as success.
    """
    if wanted is None:
        return sorted(store)
    matches = (
        [wanted]
        if wanted in store
        else [name for name in store if name.lower() == wanted.lower()]
    )
    if len(matches) > 1:
        sys.exit(
            f"{wanted!r} matches {', '.join(matches)} in {where}, "
            "ignoring case; give the name exactly."
        )
    if not matches:
        sys.exit(
            f"No session for {wanted!r} in {where}; nothing has been "
            f"signed out. It holds: "
            f"{', '.join(sorted(store)) or 'no sessions'}."
        )
    return matches


def _sign_out(token: str) -> tuple[str, str]:
    """Invalidate one token at plex.tv, returning (status, detail).

    A token plex.tv already refuses is as good as signed out, so it is
    reported that way and removed with the rest; any other failure leaves
    the token valid, and it is kept so a later run can try again.
    """
    try:
        MyPlexAccount(token=token).signout()
    except Unauthorized:
        return "already signed out", "plex.tv no longer accepted the token"
    except (PlexApiException, RequestException) as exc:
        return "failed", str(exc)
    return "signed out", ""


def _logout_line(record: dict[str, str]) -> str:
    """One table line for one stored session."""
    user, status, detail = record["user"], record["status"], record["detail"]
    if status == "dry run":
        return f"{user}: would sign out and remove."
    if status == "signed out":
        return f"{user}: signed out and removed."
    if status == "already signed out":
        return f"{user}: already signed out ({detail}); removed."
    return f"{user}: could not sign out ({detail}); kept."


def cmd_logout(_plex: PlexServer | None, args: argparse.Namespace) -> None:
    """Sign out of plex.tv and remove the saved tokens and passwords."""
    where = secret_store.describe()
    store = load_store()
    names = _logout_targets(store, args.username, where)
    table = output_format(args) == "table"
    if not names:
        if table:
            print(f"No sessions to sign out of in {where}.")
        else:
            output([], args)
        return

    # A token filed under two names is signed out once and reported twice.
    outcomes: dict[str, tuple[str, str]] = {}
    records = []
    for name in names:
        token = store[name]
        if token not in outcomes:
            outcomes[token] = (
                ("dry run", "") if args.dry_run else _sign_out(token)
            )
        status, detail = outcomes[token]
        records.append({"user": name, "status": status, "detail": detail})
        if table:
            print(_logout_line(records[-1]))

    done = [r["user"] for r in records if r["status"] in _SIGNED_OUT]
    if done:
        left = forget_tokens(done)
        # A saved password would sign the account straight back in on the
        # next command that wants it, undoing the logout.
        logins = forget_logins(done)
        LOG.info(
            "Removed %d session(s) and %d saved password(s) from %s; "
            "%d session(s) left.",
            len(done),
            logins,
            where,
            left,
        )
        if not left and table:
            print("No sessions are left; run plexdo login to sign in again.")
    if not table:
        output(records, args)
    failed = sum(r["status"] == "failed" for r in records)
    if failed:
        sys.exit(
            f"{failed} session(s) could not be signed out and were kept in "
            f"{where}; run logout again once plex.tv can be reached."
        )


def _prompt_pin() -> str | None:
    """Read a PIN without echoing it; an empty answer means none."""
    pin = getpass.getpass("Plex Home PIN (empty to remove it): ").strip()
    if pin and not (pin.isdigit() and len(pin) == 4):
        sys.exit("A Plex Home PIN is four digits.")
    return pin or None


def cmd_set_pin(_plex: PlexServer | None, args: argparse.Namespace) -> None:
    """Save, or remove, the Plex Home PIN of one user."""
    pin = None if args.remove else _prompt_pin()
    where = secret_store.describe()
    verb = "save the PIN for" if pin else "remove any PIN saved for"
    if args.dry_run:
        print(
            f"--dry-run: would {verb} user {args.user_id} in {where}.",
            file=sys.stderr,
        )
        return
    save_pin(args.user_id, pin)
    if output_format(args) == "table":
        done = "Saved the PIN for" if pin else "Removed any PIN saved for"
        print(f"{done} user {args.user_id} in {where}.")
    else:
        output(
            {
                "userId": args.user_id,
                "store": where,
                "status": "saved" if pin else "removed",
            },
            args,
        )


def cmd_write_config_example(
    _plex: PlexServer | None, args: argparse.Namespace
) -> None:
    """Write a template config file, refusing to replace one unasked."""
    existing = CONFIG_PATH.exists()
    if existing and not args.overwrite:
        # Checked before --dry-run too, so a rehearsal fails where the real
        # run would, as a refused playlist name does.
        sys.exit(
            f"A config file already exists at {CONFIG_PATH}. Nothing has "
            "been written.\nRe-run with --overwrite to replace it with the "
            "template, or see the template with --help."
        )
    if args.dry_run:
        action = "replace the existing file" if existing else "create it"
        print(
            f"--dry-run: would write the template to {CONFIG_PATH} ({action}).",
            file=sys.stderr,
        )
        return

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(CONFIG_EXAMPLE, encoding="utf-8")
    if os.name != "nt":
        CONFIG_PATH.chmod(0o600)
    print(f"Config example written to: {CONFIG_PATH}")


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the login and config bootstrap subparsers."""
    p_login = sub.add_parser(
        "login",
        parents=parents,
        help=(
            "Authenticate with plex.tv and save the token to the system "
            "keyring."
        ),
    )
    p_login.add_argument(
        "-u",
        "--username",
        default=None,
        metavar="USER",
        help="Plex username or email (str). Prompted for if omitted.",
    )
    p_login.add_argument(
        "-p",
        "--password",
        default=None,
        metavar="PASS",
        help=(
            "Plex password (str). INSECURE: visible in shell history and "
            "briefly in `ps`. Prefer the interactive prompt."
        ),
    )
    p_login.add_argument(
        "--save-password",
        # Not "save_password": a flag named for passwords is taken by static
        # analysis to hold one, and printing it reported as a leak.
        dest="remember_login",
        action="store_true",
        default=False,
        help=(
            "Also save the password in the system keyring, so plexdo can sign "
            "in again by itself when the token stops working."
        ),
    )
    p_login.add_argument(
        "-c",
        "--code",
        default=None,
        metavar="CODE",
        help=(
            "Two-factor authentication code (str), if the account requires one."
        ),
    )
    p_login.add_argument(
        "-2",
        "--two-factor",
        dest="two_factor",
        action="store_true",
        default=False,
        help="Prompt for a two-factor code interactively.",
    )

    p_logout = sub.add_parser(
        "logout",
        parents=parents,
        help="Sign out of plex.tv and remove the saved tokens and passwords.",
    )
    p_logout.add_argument(
        "-u",
        "--username",
        default=None,
        metavar="USER",
        help=(
            "Sign out only this name (str), as login saved it. Default: "
            "every saved session."
        ),
    )

    p_pin = sub.add_parser(
        "set-pin",
        parents=parents,
        help="Save or remove a Plex Home member's PIN in the system keyring.",
    )
    p_pin.add_argument(
        "user_id",
        type=int,
        metavar="USER_ID",
        help=(
            "The plex.tv user id of the Plex Home member (int), as "
            "list-users shows it. The PIN is prompted for."
        ),
    )
    p_pin.add_argument(
        "--remove",
        action="store_true",
        default=False,
        help="Remove the saved PIN instead of prompting for one.",
    )

    p_wce = sub.add_parser(
        "write-config-example",
        parents=parents,
        help="Write a template config file.",
        description=textwrap.fill(
            f"Write a template config file to {CONFIG_PATH} with mode 0600, "
            "creating parent directories as needed. An existing file at that "
            "path is only replaced when --overwrite is given.",
            width=78,
        ),
        epilog=(
            "template that would be written:\n\n"
            + textwrap.indent(CONFIG_EXAMPLE, "  ")
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_wce.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        default=False,
        help="Replace an existing config file instead of refusing to.",
    )


COMMANDS = {
    "login": cmd_login,
    "logout": cmd_logout,
    "set-pin": cmd_set_pin,
    "write-config-example": cmd_write_config_example,
}

# login and write-config-example run before a token necessarily exists,
# logout must still work once the server will no longer accept one, and
# set-pin only touches the secret store.
REQUIRES_PLEX: frozenset = frozenset()
