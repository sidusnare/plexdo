# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Library rescan and scan-status commands."""

import argparse
import sys
from functools import partial
from typing import Any

from plexapi.server import PlexServer

from plexdo.console import clean_text, output, output_format
from plexdo.constants import LOG
from plexdo.sections import resolve_section


def _cancel_all_scans(plex: PlexServer) -> None:
    """Cancel any running or queued scan on every library section."""
    for section in plex.library.sections():
        try:
            section.cancelUpdate()
            LOG.debug("Cancelled scan on '%s'", section.title)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.debug(
                "cancelUpdate on '%s' raised %s (may already be idle)",
                section.title,
                exc,
            )


def _activity_rows(plex: PlexServer) -> list[dict[str, Any]]:
    """Return scan-related activity rows from the Plex server."""
    rows = []
    for act in plex.activities:
        rows.append(
            {
                "type": clean_text(getattr(act, "type", "") or ""),
                "title": clean_text(getattr(act, "title", "") or ""),
                "subtitle": clean_text(getattr(act, "subtitle", "") or ""),
                "progress": getattr(act, "progress", ""),
                "uuid": clean_text(getattr(act, "uuid", "") or ""),
            }
        )
    return rows


def _check_rescan(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Refuse a rescan that names no library, or names one and all; exit 2."""
    if args.status:
        return
    if args.all_libraries and args.library_id is not None:
        parser.error(
            f"give a library or --all, not both; drop {args.library_id!r} "
            "to rescan every library"
        )
    if not args.all_libraries and args.library_id is None:
        parser.error(
            "name the library to rescan, or use --all to rescan every library"
        )


def cmd_rescan(plex: PlexServer, args: argparse.Namespace) -> None:
    """Trigger a library rescan, optionally cancelling pending scans first."""
    if args.status:
        rows = _activity_rows(plex)
        if rows or output_format(args) != "table":
            # A machine-readable format gets an empty document, not prose
            # that would break whatever parses it.
            output(rows, args)
        else:
            print("No active scan jobs.", file=sys.stderr)
        return

    if args.all_libraries:
        count = len(plex.library.sections())
        what = f"all {count} libraries"
    else:
        section = resolve_section(plex, args.library_id)
        what = f"library {section.title!r}"

    if args.dry_run:
        first = "cancel every pending scan, then " if args.now else ""
        print(f"--dry-run: would {first}rescan {what}.", file=sys.stderr)
        return

    if args.now:
        LOG.info("Cancelling all pending scans before rescan.")
        _cancel_all_scans(plex)

    LOG.info("Triggering rescan of %s", what)
    if args.all_libraries:
        # One request: the server queues a scan of each library itself.
        plex.library.update()
        print(f"Rescan triggered for {what}.")
    else:
        section.update()
        print(f"Rescan triggered for library: {section.title!r}")


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the rescan subparser."""
    parser = sub.add_parser(
        "rescan",
        parents=parents,
        help="Rescan libraries, or show the scans under way.",
    )
    parser.set_defaults(check_arguments=partial(_check_rescan, parser))
    parser.add_argument(
        "library_id",
        metavar="LIBRARY",
        nargs="?",
        default=None,
        help=(
            "The library to rescan: its ID (int) or title (str). Obtain "
            "both with libraries-list. Required unless -a or -s is given."
        ),
    )
    parser.add_argument(
        "-a",
        "--all",
        dest="all_libraries",
        action="store_true",
        default=False,
        help="Rescan every library, in place of naming one.",
    )
    parser.add_argument(
        "-s",
        "--status",
        action="store_true",
        default=False,
        help=(
            "Print all active scan jobs with their type, progress, and "
            "subtitle, and rescan nothing."
        ),
    )
    parser.add_argument(
        "-n",
        "--now",
        action="store_true",
        default=False,
        help=(
            "Cancel all pending scans on every library before triggering the "
            "rescan."
        ),
    )


COMMANDS = {"rescan": cmd_rescan}

REQUIRES_PLEX = frozenset(COMMANDS)
