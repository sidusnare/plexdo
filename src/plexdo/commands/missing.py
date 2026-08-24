# SPDX-License-Identifier: GPL-3.0-or-later

"""Find gaps in the episode numbering of every season of every show."""

from typing import Any, Dict, List, Optional
import argparse
import textwrap

from plexapi.server import PlexServer

from plexdo.console import clean_text, output
from plexdo.constants import LOG
from plexdo.sections import resolve_sections
from plexdo.throttle import paced


def episode_gaps(numbers: List[int]) -> List[int]:
    """Return the episode numbers missing from a season.

    The run starts at 0 when the season has an episode 0, otherwise at 1, and
    ends at the highest number present: a season simply stopping early is not
    a gap, since there is no way to tell an unaired episode from a missing
    one.
    """
    present = sorted({number for number in numbers if number is not None})
    if not present:
        return []
    start = 0 if present[0] == 0 else 1
    return [n for n in range(start, present[-1] + 1) if n not in present]


def _season_row(show: Any, season: Any) -> Optional[Dict[str, Any]]:
    """Report one season, or None when its numbering is complete."""
    episodes = season.episodes()
    numbers = [vars(episode).get("index") for episode in episodes]
    missing = episode_gaps([n for n in numbers if n is not None])
    if not missing:
        return None
    present = sorted(n for n in numbers if n is not None)
    return {
        "show": clean_text(vars(show).get("title") or ""),
        "ratingKey": int(show.ratingKey),
        "season": vars(season).get("index"),
        "missing": missing,
        "missingCount": len(missing),
        "have": len(present),
        "highest": present[-1] if present else 0,
    }


def _show_rows(show: Any, include_specials: bool) -> List[Dict[str, Any]]:
    """Report every incomplete season of one show."""
    rows: List[Dict[str, Any]] = []
    for season in show.seasons():
        number = vars(season).get("index")
        if not include_specials and number == 0:
            continue
        row = _season_row(show, season)
        if row is not None:
            rows.append(row)
    return rows


def _flatten(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Render the missing list as text, for the table renderer."""
    return [dict(row, missing=", ".join(str(n) for n in row["missing"]))
            for row in rows]


def cmd_find_missing(plex: PlexServer, args: argparse.Namespace) -> None:
    """Report seasons whose episode numbering has holes in it."""
    sections = [
        section for section in resolve_sections(plex, args.library_id)
        if section.type == "show"
    ]
    if not sections:
        target = args.library_id or "this server"
        raise SystemExit(f"No show libraries found in {target}.")

    rows: List[Dict[str, Any]] = []
    for section in sections:
        shows = section.all()
        LOG.info("Checking %d show(s) in '%s'", len(shows), section.title)
        for show in paced(shows, args, "shows"):
            rows.extend(_show_rows(show, args.include_specials))

    if not rows:
        LOG.info("Every season is complete.")
        print("No gaps found.")
        return

    LOG.info("%d season(s) with gaps", len(rows))
    output(_flatten(rows) if args.format == "table" else rows, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the find-missing subparser."""
    parser = sub.add_parser(
        "find-missing", parents=parents,
        help="Find gaps in the episode numbering of every season of every show.",
        description=textwrap.fill(
            "Walk every season of every show and report the episode numbers "
            "missing between the start of the season and its highest episode. "
            "A season that simply stops early is not reported, since an "
            "unaired episode cannot be told from a missing one.",
            width=78,
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "library_id", metavar="LIBRARY", nargs="?", default=None,
        help=(
            "Library ID (int) or library title (str) to check. Obtain both "
            "with list-libraries. Defaults to every show library."
        ),
    )
    parser.add_argument(
        "--include-specials", action="store_true", default=False,
        help=(
            "Also check season 0. Specials are numbered irregularly, so this "
            "is off by default."
        ),
    )


COMMANDS = {"find-missing": cmd_find_missing}

REQUIRES_PLEX = frozenset(COMMANDS)
