# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Library search command."""

import argparse
from typing import Any

from plexapi.server import PlexServer

from plexdo.accounts import server_for_user
from plexdo.arguments import add_user_argument
from plexdo.console import output
from plexdo.constants import LOG
from plexdo.sections import resolve_sections
from plexdo.titles import display_title

_SEARCH_MEDIA_TYPES = (
    "movie",
    "show",
    "episode",
    "track",
    "photo",
    "album",
    "artist",
)


def _search_result_row(item: Any) -> dict[str, Any]:
    """Build a result row from a search hit, resolving the library id."""
    # plexapi attaches a librarySectionID attribute to all fetched items.
    lib_id = int(getattr(item, "librarySectionID", 0))
    return {
        "ratingKey": int(item.ratingKey),
        "libraryId": lib_id,
        "type": item.type,
        "title": display_title(item),
    }


def _search_in_section(
    section: Any,
    query: str,
    media_type: str | None,
) -> list[dict[str, Any]]:
    """Search a single library section, optionally filtered by media type."""
    kwargs: dict[str, Any] = {}
    if media_type:
        kwargs["libtype"] = media_type
    try:
        hits = section.search(query, **kwargs)
    except Exception as exc:  # pylint: disable=broad-except
        LOG.warning("Search failed in library '%s': %s", section.title, exc)
        return []
    return [_search_result_row(item) for item in hits]  # type: ignore[arg-type]


def _search_all_sections(
    user_plex: PlexServer,
    query: str,
    media_type: str | None,
    library_id: int | None,
) -> list[dict[str, Any]]:
    """Run the search across one or all library sections."""
    sections = resolve_sections(user_plex, library_id)
    rows: list[dict[str, Any]] = []
    for section in sections:
        rows.extend(_search_in_section(section, query, media_type))
    return rows


def cmd_search(plex: PlexServer, args: argparse.Namespace) -> None:
    """Search Plex for titles matching a query string."""
    user_plex = server_for_user(plex, args.user_id)
    library_id: int | None = args.library_id
    media_type: str | None = args.media_type

    LOG.info(
        "Searching for %r (type=%s library=%s)",
        args.query,
        media_type,
        library_id,
    )
    rows = _search_all_sections(user_plex, args.query, media_type, library_id)

    if not rows:
        LOG.info("No results found.")
    output(rows, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the search subparser."""
    parser = sub.add_parser(
        "search",
        parents=parents,
        help="Search Plex for titles matching a query string.",
    )
    add_user_argument(parser)
    parser.add_argument(
        "query",
        help="Search string (str). Plex performs a prefix/substring match.",
    )
    parser.add_argument(
        "--media-type",
        dest="media_type",
        choices=list(_SEARCH_MEDIA_TYPES),
        default=None,
        metavar="TYPE",
        help=(
            "Restrict results to a single media type. "
            f"Choices: {', '.join(_SEARCH_MEDIA_TYPES)}."
        ),
    )
    parser.add_argument(
        "--library-id",
        dest="library_id",
        default=None,
        metavar="LIBRARY",
        help=(
            "Restrict search to one library, by ID or title. Obtain both "
            "with list-libraries."
        ),
    )


COMMANDS = {"search": cmd_search}

REQUIRES_PLEX = frozenset(COMMANDS)
