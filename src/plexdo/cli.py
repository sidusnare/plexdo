# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
#
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

"""Top-level argument parsing and command dispatch."""

import argparse
import sys
import textwrap

from plexapi.exceptions import PlexApiException, Unauthorized
from requests.exceptions import ConnectionError as ConnectionFailure
from requests.exceptions import RequestException, Timeout

from plexdo import __version__
from plexdo.accounts import UserAccessError, resolve_user_arguments
from plexdo.commands import GROUPS, build_registry, register_all
from plexdo.config import cached_config
from plexdo.connection import connect_plex
from plexdo.constants import CONFIG_PATH, LOG
from plexdo.formats import OUTPUT_FORMATS
from plexdo.logs import configure_logging
from plexdo.migrate import migrate_legacy_config
from plexdo.profiling import profiled, span
from plexdo.sections import resolve_library_arguments
from plexdo.security import redact, scrub_password_argument
from plexdo.throttle import DEFAULT_THROTTLE, THROTTLE_THRESHOLD


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

    The flags sit in a group of their own, sorted by name, so a command's
    help lists them apart from the options that are the command's alone.
    """
    default = argparse.SUPPRESS if suppress else False
    group = parser.add_argument_group(_GLOBAL_GROUP)
    group.add_argument(
        "--debug",
        action="store_true",
        default=default,
        help="Print detailed internal logs to stderr.",
    )
    group.add_argument(
        "--debug-log",
        metavar="PATH",
        default=argparse.SUPPRESS if suppress else None,
        help=(
            "Append detailed internal logs to PATH instead of printing them, "
            "each line starting with a Unix timestamp in nanoseconds, with "
            "profiling: phase and function run times, HTTP requests and "
            "their waits, and CPU and memory use. Secrets are redacted."
        ),
    )
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=default,
        dest="dry_run",
        help="Show what would happen without mutating Plex.",
    )
    group.add_argument(
        "-f",
        "--format",
        dest="format",
        choices=list(OUTPUT_FORMATS),
        default=argparse.SUPPRESS if suppress else "table",
        metavar="FORMAT",
        help=(
            "Output format: " + ", ".join(OUTPUT_FORMATS) + ". "
            "Default is an aligned table."
        ),
    )
    # A convenience alias writing to the same destination as --format, so
    # there is only ever one attribute for a command to consult.
    group.add_argument(
        "--json",
        dest="format",
        action="store_const",
        const="json",
        default=argparse.SUPPRESS,
        help="Shorthand for --format json.",
    )
    group.add_argument(
        "--throttle",
        type=float,
        metavar="SECONDS",
        default=argparse.SUPPRESS if suppress else DEFAULT_THROTTLE,
        help=(
            "Seconds to wait between requests in operations that query once "
            f"per item, when there are more than {THROTTLE_THRESHOLD} of them "
            f"(default: {DEFAULT_THROTTLE}). Use 0 to disable."
        ),
    )
    group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=default,
        help="Print high-level progress to stderr.",
    )
    group.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"plexdo {__version__}",
        help="Show the installed version and exit.",
    )
    group.add_argument(
        "-W",
        "--wide",
        action="store_true",
        default=default,
        help=(
            "Do not shrink table columns to the terminal width. By default "
            "the widest column is truncated so a row fits on one line; "
            "redirected output is never truncated."
        ),
    )


def _global_flags_parent() -> argparse.ArgumentParser:
    """Return a parent parser supplying the global flags to every subcommand."""
    parent = argparse.ArgumentParser(add_help=False)
    _add_global_flags(parent, suppress=True)
    return parent


_GLOBAL_GROUP = "global options"

# The width the hand-laid parts of --help are wrapped to.
_HELP_WIDTH = 79


def _is_global_group(
    group: "argparse._ArgumentGroup",  # pylint: disable=protected-access
) -> bool:
    """Whether a help group is the one holding the global flags."""
    return group.title == _GLOBAL_GROUP


def _tidy_command_help(command: argparse.ArgumentParser) -> None:
    """Keep the global flags from crowding one command's help.

    They are inherited from a parent, which lists them ahead of the groups
    a command adds for its own and spells all of them out in its usage.
    Here their group goes last, and the usage names the command's own
    arguments followed by "[global options]".
    """
    # argparse offers no public way to reorder groups or to leave actions
    # out of the usage, so this reaches into the parser it was handed.
    # pylint: disable=protected-access
    command._action_groups.sort(key=_is_global_group)
    if command.usage is not None:
        return
    shared = {
        id(action)
        for group in command._action_groups
        if _is_global_group(group)
        for action in group._group_actions
    }
    formatter = command._get_formatter()
    formatter.add_usage(
        None,
        [action for action in command._actions if id(action) not in shared],
        command._mutually_exclusive_groups,
    )
    # The formatter wrapped it to follow "usage: ", which argparse puts
    # back in front of a usage it is given.
    lead = "usage: "
    usage = formatter.format_help().strip().removeprefix(lead)
    last = usage.rsplit("\n", 1)[-1]
    first_line = "\n" not in usage
    room = _HELP_WIDTH - len(last) - (len(lead) if first_line else 0)
    note = "[global options]"
    if len(note) < room:
        command.usage = f"{usage} {note}"
    else:
        indent = " " * (len(lead) + len(command.prog) + 1)
        command.usage = f"{usage}\n{indent}{note}"


def _command_list(summaries: dict[str, str]) -> str:
    """The commands for --help: grouped, sorted, one summary each."""
    width = max(len(name) for name in summaries) + 2
    lines = []
    for title, names in GROUPS:
        lines += ["", f"{title}:"]
        for name in sorted(names):
            lines.append(
                textwrap.fill(
                    summaries[name],
                    width=_HELP_WIDTH,
                    initial_indent=f"  {name:<{width}}",
                    subsequent_indent=" " * (width + 2),
                )
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="plexdo",
        usage="%(prog)s [global options] <command> [arguments]",
        epilog=(
            "Run `plexdo <command> --help` for a command's arguments. The "
            "global options may be\ngiven before or after the command name."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parents: list[argparse.ArgumentParser] = [_global_flags_parent()]
    # The list argparse would print is flat and in registration order, so
    # it is suppressed and the description carries a grouped one instead.
    sub = parser.add_subparsers(
        prog="plexdo",
        dest="command",
        metavar="<command>",
        help=argparse.SUPPRESS,
    )
    register_all(sub, parents)
    for command in sub.choices.values():
        _tidy_command_help(command)
    summaries = {
        action.dest: action.help or ""
        for action in sub._get_subactions()  # pylint: disable=protected-access
    }
    parser.description = (
        f"plexdo {__version__} - a command-line interface for Plex Media "
        "Server.\n" + _command_list(summaries)
    )
    _add_global_flags(parser)
    return parser


def parse_arguments(
    parser: argparse.ArgumentParser, argv: list[str] | None = None
) -> argparse.Namespace:
    """Parse the command line, exiting 2 on a usage error.

    A command whose arguments depend on one of its flags registers a
    check_arguments callable, run here to name them or to refuse them, so
    that happens before anything connects to the server.
    """
    args = parser.parse_args(argv)
    check = getattr(args, "check_arguments", None)
    if check is not None:
        check(args)
    return args


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``plexdo`` console script."""
    parser = build_parser()
    args = parse_arguments(parser, argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    configure_logging(args.verbose, args.debug, args.debug_log)
    scrub_password_argument(args)
    # After the scrubbing, so the run start line never shows a --password.
    with profiled(args.debug_log is not None, args.command):
        try:
            _run(args)
        except (RequestException, PlexApiException) as exc:
            # The traceback is for --debug; what the user needs is which of
            # the three things went wrong and what to do about it.
            LOG.debug("Request failed", exc_info=True)
            sys.exit(_request_failure(exc))


def _first_line(exc: Exception) -> str:
    """The first line of an error, with any secret in it redacted.

    plexapi attaches the server's whole HTML error page to some of its
    exceptions, and a URL in a requests error can carry a token.
    """
    lines = str(exc).strip().splitlines()
    return redact(lines[0].strip()) if lines else type(exc).__name__


def _request_failure(exc: Exception) -> str:
    """What to tell the user when a request to Plex or plex.tv failed."""
    reason = _first_line(exc)
    if isinstance(exc, Unauthorized):
        return (
            f"Plex refused the saved token: {reason}\n"
            "Run `plexdo login` to sign in again."
        )
    if isinstance(exc, Timeout):
        return (
            f"Plex did not answer in time: {reason}\n"
            "Check that the server is up and not overloaded, then try again."
        )
    if isinstance(exc, ConnectionFailure):
        return (
            f"Could not reach Plex: {reason}\n"
            f"Check that the server is running and that plex: url in "
            f"{CONFIG_PATH} is its address."
        )
    if isinstance(exc, RequestException):
        return f"The request to Plex failed: {reason}"
    return f"Plex refused the request: {reason}"


def _run(args: argparse.Namespace) -> None:
    """Run the command args names, each phase timed for --debug-log."""
    # Before any command reads the configuration or a secret, so the first
    # run after an upgrade from 1.x finds both where they now belong.
    with span("migrate"):
        migrate_legacy_config()

    handlers, needs_plex = build_registry()
    handler = handlers.get(args.command)
    if handler is None:
        sys.exit(f"Unknown command: {args.command}")

    if args.command in needs_plex:
        with span("connect"):
            plex = connect_plex(cached_config())
        # Commands receive numeric user and library IDs; titles are resolved
        # here so no handler has to care which form the user typed.
        with span("resolve-arguments"):
            resolve_user_arguments(plex, args)
            resolve_library_arguments(plex, args)
        try:
            with span(f"command:{args.command}"):
                handler(plex, args)
        except UserAccessError as exc:
            # Raised deep in accounts.server_for_user so the all-users loop
            # can skip a user; for a single-user command it is fatal.
            sys.exit(str(exc))
    else:
        with span(f"command:{args.command}"):
            handler(None, args)
