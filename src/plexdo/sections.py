# SPDX-License-Identifier: GPL-3.0-or-later

"""Library section lookup shared by the library, search, and sync commands."""

from typing import Any, List, Optional, Tuple
import sys

from plexapi.exceptions import NotFound
from plexapi.server import PlexServer

from plexdo.console import clean_text
from plexdo.identify import resolve_identifier


def resolve_section(plex: PlexServer, library_id: int) -> Any:
    """Return one library section by ID, failing fast if it does not exist."""
    try:
        return plex.library.sectionByID(library_id)
    except NotFound:
        sys.exit(f"Library ID not found: {library_id}")


def resolve_sections(plex: PlexServer, library_id: Optional[int]) -> List[Any]:
    """Return one section when library_id is given, otherwise every section."""
    if library_id is not None:
        return [resolve_section(plex, library_id)]
    return list(plex.library.sections())


# Namespace attribute holding a library identifier, resolved centrally during
# dispatch so every command handler receives a plain numeric library ID.
LIBRARY_ID_ARGUMENT = "library_id"


def _library_roster(plex: PlexServer) -> List[Tuple[int, str]]:
    """Return (id, title) for every library section on the server."""
    return [
        (int(section.key), clean_text(section.title or ""))
        for section in plex.library.sections()
    ]


def resolve_library_identifier(roster: List[Tuple[int, str]], value: Any) -> int:
    """Resolve a numeric library ID or a library title to a numeric ID."""
    return resolve_identifier(roster, value, "library", "list-libraries")


def resolve_library_arguments(plex: PlexServer, args: "argparse.Namespace") -> None:
    """Replace a library ID/title argument with a numeric ID, in place.

    The roster is fetched only when a library argument is actually present, so
    commands that take none cost no extra API call.
    """
    value = getattr(args, LIBRARY_ID_ARGUMENT, None)
    if value is None:
        return
    roster = _library_roster(plex)
    setattr(args, LIBRARY_ID_ARGUMENT, resolve_library_identifier(roster, value))
