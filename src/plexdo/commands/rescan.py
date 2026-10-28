# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Library rescan and scan-status commands."""

import argparse
import sys
from typing import Any

from plexapi.server import PlexServer

from plexdo.console import clean_text, output
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


def cmd_rescan(plex: PlexServer, args: argparse.Namespace) -> None:
    """Trigger a library rescan, optionally cancelling pending scans first."""
    if args.status:
        rows = _activity_rows(plex)
        if not rows:
            print("No active scan jobs.", file=sys.stderr)
        else:
            output(rows, args)
        return

    if args.library_id is None:
        sys.exit("library_id is required unless --status / -s is used.")

    section = resolve_section(plex, args.library_id)

    if args.now:
        LOG.info("Cancelling all pending scans before rescan.")
        if not args.dry_run:
            _cancel_all_scans(plex)

    LOG.info(
        "Triggering rescan of library '%s' (id=%d)",
        section.title,
        args.library_id,
    )
    if args.dry_run:
        LOG.info("--dry-run: skipping scan trigger.")
        return

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
        help=(
            "Trigger a library rescan, with optional status view or "
            "flush-and-rescan."
        ),
    )
    parser.add_argument(
        "library_id",
        metavar="LIBRARY",
        nargs="?",
        default=None,
        help=(
            "Library ID (int) or title (str). Obtain both with "
            "list-libraries. Required unless -s / --status is used."
        ),
    )
    parser.add_argument(
        "-s",
        "--status",
        action="store_true",
        default=False,
        help=(
            "Print all active scan jobs with their type, progress, and "
            "subtitle."
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
