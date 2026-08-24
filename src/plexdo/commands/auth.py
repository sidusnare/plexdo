# SPDX-License-Identifier: GPL-3.0-or-later

"""Authentication and config bootstrap commands."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import argparse
import configparser
import getpass
import os
import sys
import textwrap

from plexapi.exceptions import BadRequest, Unauthorized
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from plexdo.config import config_optional, load_config
from plexdo.console import output, output_format
from plexdo.constants import CONFIG_EXAMPLE, CONFIG_PATH, LOG
from plexdo.tokens import ADMIN_KEY, store_token


def _prompt_username(supplied: Optional[str]) -> str:
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
    cfg: configparser.ConfigParser, args: argparse.Namespace
) -> Tuple[str, str]:
    """Resolve (username, password) from arguments and config.

    Precedence rules:
      * --username given: that username is used and the config password is
        ignored entirely, because a config password paired with a different
        username would be a silent credential mismatch.  The password comes
        from --password, or an interactive prompt.
      * --username absent: fall back to the config username, and to the
        config password alongside it.  --password still overrides.
      * Neither present: prompt for both.
    """
    cfg_user = config_optional(cfg, "username")
    cfg_pass = config_optional(cfg, "password")

    if args.username:
        if cfg_pass:
            LOG.debug("--username supplied; ignoring config password.")
        return args.username, args.password or _prompt_password()

    if cfg_user:
        LOG.debug("Using username from config: %s", cfg_user)
        return cfg_user, args.password or cfg_pass or _prompt_password()

    return _prompt_username(None), args.password or _prompt_password()


def _obtain_token(username: str, password: str, code: Optional[str]) -> str:
    """Authenticate against plex.tv and return the account auth token."""
    kwargs: Dict[str, Any] = {"username": username, "password": password}
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


def _save_token(token: str, token_path_raw: str, username: Optional[str]) -> Path:
    """Add this account's token to the JSON store, keeping any others."""
    path = Path(token_path_raw).expanduser()
    store_token(path, username or ADMIN_KEY, token)
    if os.name == "nt":
        # chmod on Windows only toggles the read-only bit, so claiming 0600
        # would be misleading; NTFS ACLs govern access instead.
        LOG.debug("Token written to %s (POSIX mode not applicable)", path)
    else:
        LOG.debug("Token written to %s (mode 0600)", path)
    return path


def _verify_token(url: str, token: str) -> bool:
    """Return True if the token can connect to the configured server."""
    try:
        PlexServer(url, token)
        return True
    except Exception as exc:  # pylint: disable=broad-except
        LOG.warning("Token saved but could not connect to %s: %s", url, exc)
        return False


def cmd_login(_plex: Optional[PlexServer], args: argparse.Namespace) -> None:
    """Authenticate with plex.tv and save the token to token_path."""
    cfg = load_config()
    token_path_raw = cfg.get("plex", "token_path")
    url = cfg.get("plex", "url")

    username, password = resolve_credentials(cfg, args)
    code: Optional[str] = args.code
    if args.two_factor and not code:
        code = input("Two-factor code: ").strip() or None

    LOG.info("Authenticating %s against plex.tv", username)
    token = _obtain_token(username, password, code)

    if args.dry_run:
        LOG.info("--dry-run: not writing token.")
        print(f"Authenticated. Token would be written to: "
              f"{Path(token_path_raw).expanduser()}", file=sys.stderr)
        return

    path = _save_token(token, token_path_raw, username)
    verified = _verify_token(url, token)

    if output_format(args) == "table":
        print(f"Token saved to: {path}")
        if verified:
            print(f"Verified against: {url}")
    else:
        output({"token_path": str(path), "verified": verified}, args)


def cmd_write_config_example(_plex: Optional[PlexServer], _args: argparse.Namespace) -> None:
    """Write a template config file."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(CONFIG_EXAMPLE, encoding="utf-8")
    if os.name != "nt":
        CONFIG_PATH.chmod(0o600)
    print(f"Config example written to: {CONFIG_PATH}")


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the login and config bootstrap subparsers."""
    p_login = sub.add_parser(
        "login", parents=parents,
        help="Authenticate with plex.tv and save the token to token_path.",
    )
    p_login.add_argument(
        "-u", "--username", default=None, metavar="USER",
        help="Plex username or email (str). Prompted for if omitted.",
    )
    p_login.add_argument(
        "-p", "--password", default=None, metavar="PASS",
        help=(
            "Plex password (str). INSECURE: visible in shell history and "
            "briefly in `ps`. Prefer the config file or the interactive prompt."
        ),
    )
    p_login.add_argument(
        "-c", "--code", default=None, metavar="CODE",
        help="Two-factor authentication code (str), if the account requires one.",
    )
    p_login.add_argument(
        "-2", "--two-factor", dest="two_factor", action="store_true", default=False,
        help="Prompt for a two-factor code interactively.",
    )

    sub.add_parser(
        "write-config-example", parents=parents,
        help="Write a template config file.",
        description=textwrap.fill(
            f"Write a template config file to {CONFIG_PATH} with mode 0600, "
            "creating parent directories as needed. An existing file at that "
            "path will be overwritten.",
            width=78,
        ),
        epilog=(
            "template that would be written:\n\n"
            + textwrap.indent(CONFIG_EXAMPLE, "  ")
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


COMMANDS = {
    "login": cmd_login,
    "write-config-example": cmd_write_config_example,
}

# login and write-config-example both run before a token necessarily exists.
REQUIRES_PLEX: frozenset = frozenset()
