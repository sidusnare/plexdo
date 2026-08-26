# SPDX-License-Identifier: GPL-3.0-or-later

"""Find gaps in the episode numbering of every season of every show."""

from typing import Any, Dict, List, Optional, Set, Tuple
import argparse
import textwrap

from plexapi.server import PlexServer
from plexapi.video import Show

from plexdo.console import clean_text, output
from plexdo.constants import LOG
from plexdo.identify import resolve_identifier
from plexdo.sections import resolve_sections
from plexdo.throttle import paced
from plexdo.titles import fetch_item


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


def parse_seasons(text: str) -> Set[int]:
    """Parse "1" or "1,3,5" into a set of season numbers."""
    numbers: Set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            numbers.add(int(part))
        except ValueError:
            raise SystemExit(
                f"Not a season number: {part!r}. Give one number, or several "
                "separated by commas, as in --season 1,3,5."
            ) from None
    if not numbers:
        raise SystemExit("--season needs at least one season number.")
    return numbers


def _wanted(number: Any, chosen: Optional[Set[int]], include_specials: bool) -> bool:
    """Whether a season should be examined.

    Naming a season explicitly overrides the usual skipping of season 0:
    asking for --season 0 can only mean the specials.
    """
    if chosen is not None:
        return number in chosen
    return include_specials or number != 0


def _show_rows(
    show: Any, include_specials: bool, chosen: Optional[Set[int]] = None
) -> List[Dict[str, Any]]:
    """Report every incomplete season of one show."""
    rows: List[Dict[str, Any]] = []
    for season in show.seasons():
        if not _wanted(vars(season).get("index"), chosen, include_specials):
            continue
        row = _season_row(show, season)
        if row is not None:
            rows.append(row)
    return rows


def _show_sections(plex: PlexServer, library_id: Optional[str]) -> List[Any]:
    """Every show library, or the single one named."""
    sections = [
        section for section in resolve_sections(plex, library_id)
        if section.type == "show"
    ]
    if not sections:
        where = f"library {library_id!r}" if library_id else "this server"
        raise SystemExit(f"No show libraries found in {where}.")
    return sections


def resolve_show(plex: PlexServer, identifier: str, library_id: Optional[str]) -> Any:
    """Find one show by ratingKey or title.

    Uses the same precedence as every other identifier in plexdo: a numeric
    value is a ratingKey, a title matches exactly before case-insensitively,
    and an ambiguous title aborts rather than guessing.
    """
    roster: List[Tuple[int, str]] = []
    for section in _show_sections(plex, library_id):
        roster.extend(
            (int(show.ratingKey), clean_text(vars(show).get("title") or ""))
            for show in section.all()
        )
    key = resolve_identifier(roster, identifier, "show", "list-titles <library>")
    show = fetch_item(plex, key)
    if not isinstance(show, Show):
        raise SystemExit(
            f"ratingKey {key} is a {type(show).__name__.lower()}, not a show."
        )
    return show


def _flatten(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Render the missing list as text, for the table renderer."""
    return [dict(row, missing=", ".join(str(n) for n in row["missing"]))
            for row in rows]


def cmd_find_missing(plex: PlexServer, args: argparse.Namespace) -> None:
    """Report seasons whose episode numbering has holes in it."""
    chosen = parse_seasons(args.seasons) if args.seasons else None

    if args.all_shows:
        if args.show:
            raise SystemExit(
                f"Give a show or --all, not both; drop {args.show!r} to check "
                "every show."
            )
        if chosen is not None:
            raise SystemExit("--season applies to a single show, not to --all.")
        rows = _scan_libraries(plex, args)
    else:
        if not args.show:
            raise SystemExit(
                "Name a show, by title or ratingKey, or pass --all to check "
                "every show in every library."
            )
        show = resolve_show(plex, args.show, args.library_id)
        rows = _show_rows(show, args.include_specials, chosen)

    if not rows:
        LOG.info("Every season examined is complete.")
        print("No gaps found.")
        return

    LOG.info("%d season(s) with gaps", len(rows))
    output(_flatten(rows) if args.format == "table" else rows, args)


def _scan_libraries(plex: PlexServer, args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Walk every show of every selected library."""
    rows: List[Dict[str, Any]] = []
    for section in _show_sections(plex, args.library_id):
        shows = section.all()
        LOG.info("Checking %d show(s) in '%s'", len(shows), section.title)
        for show in paced(shows, args, "shows"):
            rows.extend(_show_rows(show, args.include_specials))
    return rows


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the find-missing subparser."""
    parser = sub.add_parser(
        "find-missing", parents=parents,
        help="Find gaps in the episode numbering of a show's seasons.",
        description=textwrap.fill(
            "Report the episode numbers missing between the start of a "
            "season and its highest episode. Names one show by default; -A "
            "checks every show. A season that simply stops early is not "
            "reported, since an unaired episode cannot be told from a missing "
            "one.",
            width=78,
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "show", metavar="SHOW", nargs="?", default=None,
        help=(
            "Show title (str) or ratingKey (int) to check. Obtain either with "
            "list-titles. Omit only when using -A."
        ),
    )
    parser.add_argument(
        "-l", "--library", dest="library_id", metavar="LIBRARY", default=None,
        help=(
            "Library ID (int) or title (str) to look in. Obtain both with "
            "list-libraries. Narrows the search for SHOW, or the sweep for -A."
        ),
    )
    parser.add_argument(
        "-A", "--all", dest="all_shows", action="store_true", default=False,
        help="Check every show, rather than one named show.",
    )
    parser.add_argument(
        "-s", "--season", dest="seasons", metavar="SEASONS", default=None,
        help=(
            "Season number, or several separated by commas, as in 1,3,5. "
            "Applies to a single show. Naming season 0 includes the specials."
        ),
    )
    parser.add_argument(
        "--include-specials", action="store_true", default=False,
        help=(
            "Also check season 0 when no season is named. Specials are "
            "numbered irregularly, so this is off by default."
        ),
    )


COMMANDS = {"find-missing": cmd_find_missing}

REQUIRES_PLEX = frozenset(COMMANDS)
