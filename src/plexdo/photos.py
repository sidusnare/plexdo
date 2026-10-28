# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Photo album traversal and library item collection."""

import sys
from typing import Any

from plexapi.photo import Photo

from plexdo.console import clean_text
from plexdo.constants import MediaItem
from plexdo.records import file_paths
from plexdo.throttle import paced
from plexdo.titles import non_special_episodes

_LIBRARY_ITEM_TYPES = ("show", "movie", "photo")


def collect_photos(
    section: Any, album: str | None = None, args: Any = None
) -> list[Photo]:
    """Return photos from a photo library section, optionally filtered by album.

    Walks section.all() (albums) then album.photos() - the same pattern used
    for show libraries.  section.search(libtype="photo") is NOT used because
    Plex requires a non-empty query string and returns nothing for an empty one.

    If *album* is given, only photos from the matching album are returned
    (case-insensitive title match).  Fails fast if the name is not found.
    """
    photos: list[Photo] = []
    for palbum in paced(list(section.all()), args, "albums"):
        album_title = clean_text(getattr(palbum, "title", "") or "")
        if album is not None and album_title.lower() != album.lower():
            continue
        photos.extend(palbum.photos())

    if album is not None and not photos:
        sys.exit(
            f"Album '{album}' not found in library '{section.title}'. "
            "Use list-titles to see available albums."
        )
    return photos


def collect_library_items(
    section: Any, album: str | None = None, args: Any = None
) -> list[MediaItem]:
    """Expand a library section into a flat list of playable items.

    TV show libraries are walked show -> season (>0) -> episode.
    Movie libraries return movies directly.
    Photo libraries return photos, optionally filtered to a single album.
    """
    if section.type == "show":
        items: list[MediaItem] = []
        for show in section.all():
            items.extend(non_special_episodes(show))
        return items
    if section.type == "movie":
        return list(section.all())
    if section.type == "photo":
        return collect_photos(section, album, args)  # type: ignore[return-value]
    sys.exit(
        f"Library type '{section.type}' is not supported. "
        f"Supported types: {', '.join(_LIBRARY_ITEM_TYPES)}."
    )


def photo_file_path(photo: Photo) -> str | None:
    """Return the server filesystem path for a photo, or None if unavailable."""
    paths = file_paths(photo)
    return paths[0] if paths else None
