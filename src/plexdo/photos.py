# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Photo album traversal and library item collection."""

import sys
from typing import Any, NamedTuple

from plexapi.photo import Photo

from plexdo.console import clean_text
from plexdo.constants import LOG, MediaItem
from plexdo.records import file_paths
from plexdo.throttle import paced
from plexdo.titles import non_special_episodes

_LIBRARY_ITEM_TYPES = ("show", "movie", "photo")


# How deep albums inside albums are followed. Far beyond any library a
# person would arrange, and a bound on a server that nests without end.
MAX_ALBUM_DEPTH = 16


class AlbumVisit(NamedTuple):
    """One album met on a walk of a photo library."""

    album: Any
    contents: list[Any]  # what is directly in it, nested albums left out
    titles: tuple[
        str, ...
    ]  # its own title, after those of the albums around it


def is_album(item: Any) -> bool:
    """True for an album, as opposed to a track, photo, or clip in one.

    Albums are the only children Plex sends as a Directory element; plexapi
    keeps the element name on each class as TAG.
    """
    return getattr(type(item), "TAG", None) == "Directory"


def album_children(album: Any) -> list[Any]:
    """Everything directly inside an album, in one request."""
    return list(album.fetchItems(f"{album.key}/children"))


def walk_photo_albums(section: Any, args: Any = None) -> list[AlbumVisit]:
    """Every album of a photo library, nested ones included, with contents.

    Depth first, so an album inside another follows it. Finding nested
    albums means opening every album, which reads its contents too.

    An album met a second time is passed over, which is what stops a
    library whose albums contain one another from being walked for ever,
    and what lists an album once when the server shows it at the top level
    as well. Albums nested more than MAX_ALBUM_DEPTH deep are not opened;
    the first one left out is warned about.
    """
    visits: list[AlbumVisit] = []
    seen: set[int] = set()
    too_deep: list[str] = []

    def walk(albums: list[Any], above: tuple[str, ...]) -> None:
        if len(above) >= MAX_ALBUM_DEPTH:
            if albums and not too_deep:
                too_deep.append(" / ".join(above))
            return
        for album in paced(albums, args, "albums"):
            key = int(album.ratingKey)
            if key in seen:
                LOG.debug("Album %d met again; not walked twice.", key)
                continue
            seen.add(key)
            titles = (*above, clean_text(vars(album).get("title") or ""))
            children = album_children(album)
            visits.append(
                AlbumVisit(
                    album, [c for c in children if not is_album(c)], titles
                )
            )
            walk([c for c in children if is_album(c)], titles)

    walk([item for item in section.all() if is_album(item)], ())
    if too_deep:
        LOG.warning(
            "Albums nested more than %d deep are not followed; those inside "
            "'%s' were left out.",
            MAX_ALBUM_DEPTH,
            too_deep[0],
        )
    return visits


def _is_photo(item: Any) -> bool:
    """True for a photo, as opposed to a clip filed in the same album."""
    return vars(item).get("type") == "photo"


def collect_photos(
    section: Any, album: str | None = None, args: Any = None
) -> list[Photo]:
    """Return photos from a photo library section, optionally filtered by album.

    Walks the albums, nested ones included, since the photos of an album
    inside another are in neither the library listing nor the outer album's
    own. section.search(libtype="photo") is NOT used because Plex requires a
    non-empty query string and returns nothing for an empty one.

    If *album* is given, only the photos of the album with that title and
    of the albums inside it are returned (case-insensitive title match).
    Fails fast if the name is not found.
    """
    wanted = album.lower() if album is not None else None
    photos: list[Photo] = []
    matched = False
    for visit in walk_photo_albums(section, args):
        if wanted is not None:
            if wanted not in (title.lower() for title in visit.titles):
                continue
            matched = True
        photos.extend(item for item in visit.contents if _is_photo(item))

    if album is not None and not matched:
        sys.exit(
            f"Album '{album}' not found in library '{section.title}'. "
            "Use albums-list to see available albums."
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
        # One request per show for its episodes, so paced like any other
        # per-element loop.
        for show in paced(list(section.all()), args, "shows"):
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
