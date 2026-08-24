# plexdo - a command-line interface for Plex Media Server.
# Copyright (C) 2026 SidusNare
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level argument parsing and command dispatch."""

import argparse
import sys
from typing import List, Optional

from plexdo import __version__
from plexdo.accounts import UserAccessError, resolve_user_arguments
from plexdo.sections import resolve_library_arguments
from plexdo.commands import build_registry, register_all
from plexdo.formats import OUTPUT_FORMATS
from plexdo.throttle import DEFAULT_THROTTLE, THROTTLE_THRESHOLD
from plexdo.config import cached_config, connect_plex
from plexdo.logs import configure_logging
from plexdo.security import scrub_password_argument


def _add_global_flags(
    parser: argparse.ArgumentParser, suppress: bool = False
) -> None:
    """Add the flags accepted by every command.

    When *suppress* is set the flags default to ``argparse.SUPPRESS`` instead
    of ``False``. That matters for the copies inherited by each subparser: a
    subparser parses into its own namespace and then copies every attribute
    onto the main one, so ordinary ``False`` defaults would clobber a flag
    that was given before the subcommand. With SUPPRESS the attribute only
    exists when the flag was actually passed, so either position works.
    """
    default = argparse.SUPPRESS if suppress else False
    parser.add_argument(
        "-f", "--format", dest="format", choices=list(OUTPUT_FORMATS),
        default=argparse.SUPPRESS if suppress else "table", metavar="FORMAT",
        help=(
            "Output format: " + ", ".join(OUTPUT_FORMATS) + ". "
            "Default is an aligned table."
        ),
    )
    # A convenience alias writing to the same destination as --format, so
    # there is only ever one attribute for a command to consult.
    parser.add_argument(
        "--json", dest="format", action="store_const", const="json",
        default=argparse.SUPPRESS, help="Shorthand for --format json.",
    )
    parser.add_argument(
        "--throttle", type=float, metavar="SECONDS",
        default=argparse.SUPPRESS if suppress else DEFAULT_THROTTLE,
        help=(
            "Seconds to wait between requests in operations that query once "
            f"per item, when there are more than {THROTTLE_THRESHOLD} of them "
            f"(default: {DEFAULT_THROTTLE}). Use 0 to disable."
        ),
    )
    parser.add_argument(
        "-V", "--version", action="version",
        version=f"plexdo {__version__}",
        help="Show the installed version and exit.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=default,
        help="Print high-level progress to stderr.",
    )
    parser.add_argument(
        "--debug", action="store_true", default=default,
        help="Print detailed internal logs to stderr.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=default, dest="dry_run",
        help="Show what would happen without mutating Plex.",
    )


def _global_flags_parent() -> argparse.ArgumentParser:
    """Return a parent parser supplying the global flags to every subcommand."""
    parent = argparse.ArgumentParser(add_help=False)
    _add_global_flags(parent, suppress=True)
    return parent


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="plexdo",
        description=(
            f"Interact with a Plex Media Server via plexapi.  (version {__version__})"
        ),
        epilog=(
            "Global flags (-f/--format, --json, -v/--verbose, --debug, "
            "--dry-run, -V/--version) may be given either before or after the "
            "command name."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_global_flags(parser)
    parents: List[argparse.ArgumentParser] = [_global_flags_parent()]
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    register_all(sub, parents)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the ``plexdo`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    configure_logging(args.verbose, args.debug)
    scrub_password_argument(args)

    handlers, needs_plex = build_registry()
    handler = handlers.get(args.command)
    if handler is None:
        sys.exit(f"Unknown command: {args.command}")

    if args.command in needs_plex:
        plex = connect_plex(cached_config())
        # Commands receive numeric user and library IDs; titles are resolved
        # here so no handler has to care which form the user typed.
        resolve_user_arguments(plex, args)
        resolve_library_arguments(plex, args)
        try:
            handler(plex, args)
        except UserAccessError as exc:
            # Raised deep in accounts.server_for_user so the all-users loop
            # can skip a user; for a single-user command it is fatal.
            sys.exit(str(exc))
    else:
        handler(None, args)
