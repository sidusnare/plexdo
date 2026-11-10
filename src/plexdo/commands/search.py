# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Library search command."""

import argparse
import sys
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


# The kind of library that holds each media type; a section's type is the
# type of its top-level items, so a music library is "artist".
_SECTION_FOR = {
    "movie": "movie",
    "show": "show",
    "episode": "show",
    "artist": "artist",
    "album": "artist",
    "track": "artist",
    "photo": "photo",
}


def _holds(section: Any, media_type: str | None) -> bool:
    """Whether a library can hold items of the media type asked for."""
    return media_type is None or section.type == _SECTION_FOR[media_type]


def _search_in_section(
    section: Any,
    query: str,
    media_type: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Search one library: its rows, and why it failed if it did.

    A failure is handed back rather than reported here: whether it is worth
    a word depends on whether the search found anything anywhere else.
    """
    kwargs: dict[str, Any] = {}
    if media_type:
        kwargs["libtype"] = media_type
    try:
        hits = section.search(query, **kwargs)
    except Exception as exc:  # pylint: disable=broad-except
        # One library's failure must not cost the results of the others.
        reason = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
        LOG.debug("Search failed in library '%s': %s", section.title, reason)
        return [], f"library '{section.title}': {reason}"
    return [_search_result_row(item) for item in hits], None  # type: ignore[arg-type]


def _search_all_sections(
    user_plex: PlexServer,
    query: str,
    media_type: str | None,
    library_id: int | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Search one library or all of them: the rows, and what failed.

    A library that cannot hold the media type asked for is passed over when
    every library is searched, since asking it would only be refused. Named
    outright, it is an error: the search could never find anything there.
    """
    sections = resolve_sections(user_plex, library_id)
    if library_id is not None and not _holds(sections[0], media_type):
        sys.exit(
            f"Library '{sections[0].title}' is a {sections[0].type} library "
            f"and holds no {media_type} items, so --media-type {media_type} "
            "can find nothing in it."
        )
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for section in sections:
        if not _holds(section, media_type):
            LOG.debug(
                "Library '%s' holds no %s items; not searched.",
                section.title,
                media_type,
            )
            continue
        found, failure = _search_in_section(section, query, media_type)
        rows.extend(found)
        if failure:
            failures.append(failure)
    return rows, failures


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
    rows, failures = _search_all_sections(
        user_plex, args.query, media_type, library_id
    )

    if not rows:
        # Only now is a failure worth reporting: with results in hand, a
        # library that could not be searched is beside the point.
        if failures:
            LOG.warning("Search failed in %s", "; ".join(failures))
        else:
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
        help="Search for titles matching a query.",
    )
    add_user_argument(parser)
    parser.add_argument(
        "query",
        metavar="QUERY",
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
            "with libraries-list."
        ),
    )


COMMANDS = {"search": cmd_search}

REQUIRES_PLEX = frozenset(COMMANDS)
