# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""list-albums: the albums of a music or photo library, and what is in them.

Played state is the connected account's own, as Plex keeps it per user. An
item that can be played (a track or a video clip) has a state: played, in
progress, or unplayed. A photo has none, so its state is null, and an album
holding only photos has none either.
"""

import argparse
import sys
import textwrap
from typing import Any

from plexapi.server import PlexServer

from plexdo.arguments import add_library_argument
from plexdo.console import clean_text, output, output_format
from plexdo.constants import LOG
from plexdo.convert import parse_date
from plexdo.records import file_paths
from plexdo.sections import resolve_section
from plexdo.throttle import paced

PLAYED = "played"
IN_PROGRESS = "in progress"
UNPLAYED = "unplayed"

# The section types that hold albums: Plex calls a music library "artist".
_MUSIC, _PHOTO = "artist", "photo"

Record = dict[str, Any]


def _is_album(item: Any) -> bool:
    """True for an album, as opposed to a track, photo, or clip in one.

    Albums are the only children Plex sends as a Directory element; plexapi
    keeps the element name on each class as TAG.
    """
    return getattr(type(item), "TAG", None) == "Directory"


def _children(album: Any) -> list[Any]:
    """Everything directly inside an album, in one request."""
    return list(album.fetchItems(f"{album.key}/children"))


def _timestamp(value: Any) -> str | None:
    """A date as text, or None when there is none."""
    stamp = parse_date(value)
    return stamp.isoformat(sep=" ") if stamp else None


def _percent(part: int, whole: int | None) -> float | None:
    """Part of whole as a percentage to one decimal place."""
    if not whole:
        return None
    return round(min(part, whole) * 100 / whole, 1)


def item_state(fields: Record) -> str | None:
    """An item's played state from its fields, None for a photo.

    Only an item that can be played carries a view count. A resume point
    puts it in progress even when it has been played before: it is being
    played again.
    """
    if "viewCount" not in fields:
        return None
    if (fields.get("viewOffset") or 0) > 0:
        return IN_PROGRESS
    return PLAYED if (fields.get("viewCount") or 0) > 0 else UNPLAYED


def content_record(item: Any, position: int) -> Record:
    """One item of an album, with its played state and progress.

    Read from vars(), as records.py explains, so that a field the listing
    left out costs no request. viewOffset and progress are null unless the
    item is in progress.
    """
    fields = vars(item)
    state = item_state(fields)
    duration = fields.get("duration") or None
    offset = (
        int(fields.get("viewOffset") or 0) if state == IN_PROGRESS else None
    )
    is_track = fields.get("type") == "track"
    artist = fields.get("originalTitle") or fields.get("grandparentTitle")
    return {
        "index": position,
        "ratingKey": int(item.ratingKey),
        "type": fields.get("type") or "",
        "disc": fields.get("parentIndex") if is_track else None,
        "track": fields.get("index") if is_track else None,
        "title": clean_text(fields.get("title") or ""),
        "artist": clean_text(artist) if artist else None,
        "duration": duration,
        "state": state,
        "played": None if state is None else fields["viewCount"] > 0,
        "viewCount": fields.get("viewCount"),
        "lastViewedAt": _timestamp(fields.get("lastViewedAt")),
        "viewOffset": offset,
        "progress": None if offset is None else _percent(offset, duration),
        "files": file_paths(item),
    }


def _album_state(watchable: list[Record]) -> str | None:
    """An album's state from those of its items that can be played."""
    if not watchable:
        return None
    if any(r["state"] == IN_PROGRESS for r in watchable):
        return IN_PROGRESS
    played = sum(1 for r in watchable if r["played"])
    if played == len(watchable):
        return PLAYED
    return IN_PROGRESS if played else UNPLAYED


def _album_progress(watchable: list[Record]) -> float | None:
    """How much of an album's running time has been played, in percent.

    A played item counts in full and an item in progress up to its resume
    point, so an album of one long and one short track is not half done
    when only the short one has been heard.
    """
    heard = 0
    for record in watchable:
        if record["viewOffset"] is not None:
            heard += record["viewOffset"]
        elif record["played"]:
            heard += record["duration"] or 0
    return _percent(heard, sum(r["duration"] or 0 for r in watchable))


def album_record(album: Any, contents: list[Any], music: bool) -> Record:
    """One album, its played state and progress, and its contents.

    The album is played when all of its playable items are, unplayed when
    none is played or in progress, and in progress otherwise. progress is
    null unless it is in progress.
    """
    fields = vars(album)
    items = [content_record(item, n) for n, item in enumerate(contents, 1)]
    watchable = [r for r in items if r["state"] is not None]
    state = _album_state(watchable)
    viewed = [r["lastViewedAt"] for r in items if r["lastViewedAt"]]
    artist = fields.get("parentTitle") if music else None
    return {
        "ratingKey": int(album.ratingKey),
        "artist": clean_text(artist) if artist else None,
        "title": clean_text(fields.get("title") or ""),
        "year": fields.get("year"),
        "items": len(items),
        "duration": sum(r["duration"] or 0 for r in items) or None,
        "state": state,
        "played": None if state is None else state == PLAYED,
        "playedItems": (
            sum(1 for r in watchable if r["played"]) if watchable else None
        ),
        "inProgressItems": (
            sum(1 for r in watchable if r["state"] == IN_PROGRESS)
            if watchable
            else None
        ),
        "lastViewedAt": _timestamp(fields.get("lastViewedAt"))
        or max(viewed, default=None),
        "progress": (
            _album_progress(watchable) if state == IN_PROGRESS else None
        ),
        "contents": items,
    }


def table_row(album: Any, contents: list[Any] | None, music: bool) -> Record:
    """The compact row shown in a table.

    For a music library the counts come from the album listing itself, so
    the table costs one request whatever the library's size. A photo album's
    counts come from its contents, which finding nested albums reads anyway.
    """
    fields = vars(album)
    if contents is None:
        items = fields.get("leafCount")
        played: Any = fields.get("viewedLeafCount")
    else:
        records = [content_record(item, 0) for item in contents]
        items = len(records)
        watchable = [r for r in records if r["state"] is not None]
        played = sum(1 for r in watchable if r["played"]) if watchable else ""
    row: Record = {"ratingKey": int(album.ratingKey)}
    if music:
        row["artist"] = clean_text(fields.get("parentTitle") or "")
    row["title"] = clean_text(fields.get("title") or "")
    row["year"] = fields.get("year") or ""
    row["items"] = "" if items is None else items
    row["played"] = "" if played is None else played
    return row


def _photo_albums(
    section: Any, args: argparse.Namespace
) -> list[tuple[Any, list[Any]]]:
    """Every album of a photo library, nested ones included, with contents.

    Depth first, so an album inside another follows it. Finding nested
    albums means opening every album, which reads its contents too. An album
    met twice, should the server list nested albums at the top as well, is
    listed once.
    """
    found: list[tuple[Any, list[Any]]] = []
    seen: set[int] = set()

    def walk(albums: list[Any]) -> None:
        for album in paced(albums, args, "albums"):
            if int(album.ratingKey) in seen:
                continue
            seen.add(int(album.ratingKey))
            children = _children(album)
            found.append((album, [c for c in children if not _is_album(c)]))
            walk([c for c in children if _is_album(c)])

    walk(list(section.all()))
    return found


def cmd_list_albums(plex: PlexServer, args: argparse.Namespace) -> None:
    """List the albums in a music or photo library.

    A table shows one row per album. A machine-readable format adds each
    album's contents, which costs one request per album.
    """
    section = resolve_section(plex, args.library_id)
    if section.type not in (_MUSIC, _PHOTO):
        sys.exit(
            f"Library '{section.title}' is a {section.type} library; "
            "list-albums takes a music or photo library."
        )
    music = section.type == _MUSIC
    table = output_format(args) == "table"

    if music:
        albums = list(section.albums())
        LOG.info("%d album(s) in '%s'", len(albums), section.title)
        if table:
            output([table_row(album, None, True) for album in albums], args)
            return
        LOG.info("Reading the contents of %d album(s)", len(albums))
        listed = [
            (album, _children(album)) for album in paced(albums, args, "albums")
        ]
    else:
        listed = _photo_albums(section, args)
        LOG.info("%d album(s) in '%s'", len(listed), section.title)

    if table:
        output([table_row(a, c, music) for a, c in listed], args)
    else:
        output([album_record(a, c, music) for a, c in listed], args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the list-albums subparser."""
    parser = sub.add_parser(
        "list-albums",
        parents=parents,
        help="List the albums in a music or photo library.",
        description=textwrap.fill(
            "List the albums in a music or photo library, nested photo "
            "albums included. A table shows each album's rating key, "
            "artist, title, year, how many items it holds, and how many of "
            "them you have played. A machine-readable format (-f json, "
            "yaml, csv, clixml) adds each album's played state and progress, "
            "and its contents: every track, photo, or clip, with its own "
            "played state, and its progress when it is part way through.",
            width=78,
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_library_argument(parser)


COMMANDS = {"list-albums": cmd_list_albums}

REQUIRES_PLEX = frozenset(COMMANDS)
