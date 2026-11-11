# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Albums: what is in them, and what is played.

library-list on a music or photo library lists every album through
list_albums here, and album-list shows one album, item by item.

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

from plexdo.console import (
    clean_text,
    output,
    output_format,
    print_metadata,
    print_table,
    table_limit,
)
from plexdo.constants import LOG
from plexdo.convert import format_duration, parse_date
from plexdo.photos import album_children, is_album, walk_photo_albums
from plexdo.records import file_paths
from plexdo.throttle import paced
from plexdo.titles import fetch_item

PLAYED = "played"
IN_PROGRESS = "in progress"
UNPLAYED = "unplayed"

# A music library's section type: Plex names it for its top level, artists.
_MUSIC = "artist"

# An album's own type, mapped to whether it is a music album. A photo album
# shares the type "photo" with the photos in it, and only TAG tells them
# apart.
_ALBUM_TYPES = {"album": True, "photo": False}

# Formats that can carry an album with its contents nested inside it. The
# others hold one value per column, so they get the contents alone.
_NESTING_FORMATS = ("json", "yaml")

Record = dict[str, Any]


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
    """Every album of a photo library, nested ones included, with contents."""
    return [
        (visit.album, visit.contents)
        for visit in walk_photo_albums(section, args)
    ]


def list_albums(
    section: Any, args: argparse.Namespace, filters: dict | None = None
) -> list[Any]:
    """Output the albums of a music or photo library; return them.

    A table shows one row per album. A machine-readable format adds each
    album's contents, which costs one request per album. The albums are
    returned for the completion cache.

    With *filters*, plexapi's filter dictionary, the server picks the
    albums: only those it returns are listed, a photo library's without
    walking into the albums inside them, which its filtering does not do.
    """
    music = section.type == _MUSIC
    table = output_format(args) == "table"

    if filters is not None:
        albums = list(
            section.search(
                libtype="album" if music else "photoalbum", filters=filters
            )
        )
        LOG.info("%d album(s) match in '%s'", len(albums), section.title)
        if music and table:
            output([table_row(album, None, True) for album in albums], args)
            return albums
        listed = [
            (album, [c for c in album_children(album) if not is_album(c)])
            for album in paced(albums, args, "albums")
        ]
    elif music:
        albums = list(section.albums())
        LOG.info("%d album(s) in '%s'", len(albums), section.title)
        if table:
            output([table_row(album, None, True) for album in albums], args)
            return albums
        LOG.info("Reading the contents of %d album(s)", len(albums))
        listed = [
            (album, album_children(album))
            for album in paced(albums, args, "albums")
        ]
    else:
        listed = _photo_albums(section, args)
        LOG.info("%d album(s) in '%s'", len(listed), section.title)

    if table:
        output([table_row(a, c, music) for a, c in listed], args)
    else:
        output([album_record(a, c, music) for a, c in listed], args)
    return [album for album, _ in listed]


def _position_text(progress: Record) -> str:
    """Where an item in progress stands: resume point, length, percentage."""
    offset = progress["viewOffset"]
    if offset is None:
        return ""
    if not progress["duration"]:
        return format_duration(offset)
    return (
        f"{format_duration(offset)} / {format_duration(progress['duration'])}"
        f" ({progress['progress']}%)"
    )


def album_summary(record: Record, nested: int) -> Record:
    """The album itself, as album-list's table shows it above its items.

    Only what applies is shown: no artist for a photo album, and no played
    state for one holding photos alone.
    """
    summary: Record = {"ratingKey": record["ratingKey"]}
    if record["artist"]:
        summary["artist"] = record["artist"]
    summary["title"] = record["title"]
    if record["year"]:
        summary["year"] = record["year"]
    summary["items"] = record["items"]
    if nested:
        summary["nested albums"] = f"{nested}, listed by library-list"
    if record["duration"]:
        summary["length"] = format_duration(record["duration"])
    if record["state"] is not None:
        summary["state"] = record["state"]
        summary["played"] = f"{record['playedItems']} of {record['items']}"
        if record["inProgressItems"]:
            summary["in progress"] = record["inProgressItems"]
    if record["progress"] is not None:
        summary["progress"] = f"{record['progress']}%"
    if record["lastViewedAt"]:
        summary["last played"] = record["lastViewedAt"]
    return summary


def item_rows(record: Record) -> list[Record]:
    """album-list's table: one row per item, with the columns that apply.

    The track number carries the disc as well, as 2-03, only when the album
    spans several. The artist column appears only when some track's artist
    is not the album's, as on a compilation. A photo album has no track or
    artist column, and no played columns when it holds photos alone.
    """
    contents = record["contents"]
    discs = {r["disc"] for r in contents if r["disc"] is not None}
    tracks = any(r["track"] is not None for r in contents)
    artists = any(
        r["artist"] and r["artist"] != record["artist"] for r in contents
    )
    watchable = any(r["state"] is not None for r in contents)
    rows = []
    for item in contents:
        row: Record = {"#": item["index"], "ratingKey": item["ratingKey"]}
        if tracks:
            number = "" if item["track"] is None else item["track"]
            if len(discs) > 1 and number != "":
                number = f"{item['disc']}-{number:02d}"
            row["track"] = number
        row["title"] = item["title"]
        if artists:
            row["artist"] = item["artist"] or ""
        row["length"] = format_duration(item["duration"])
        if watchable:
            row["state"] = item["state"] or ""
            row["progress"] = _position_text(item)
            row["last played"] = (item["lastViewedAt"] or "")[:10]
        rows.append(row)
    return rows


def cmd_list_album(plex: PlexServer, args: argparse.Namespace) -> None:
    """Show one album's contents, with each item's played state and progress.

    A table shows the album, then its items. JSON and YAML carry the same
    record library-list gives for each album; CSV and CLIXML, which cannot
    nest, carry the item records alone.
    """
    album = fetch_item(plex, args.rating_key)
    kind = vars(album).get("type")
    if not is_album(album) or kind not in _ALBUM_TYPES:
        sys.exit(
            f"ratingKey {args.rating_key} is not an album (it is a "
            f"{kind or type(album).__name__}); library-list lists the albums "
            "of a library."
        )
    children = album_children(album)
    contents = [child for child in children if not is_album(child)]
    nested = len(children) - len(contents)
    if nested:
        LOG.info(
            "%d album(s) nested in '%s' are not listed here; library-list "
            "lists them.",
            nested,
            vars(album).get("title"),
        )
    record = album_record(album, contents, _ALBUM_TYPES[kind])

    chosen = output_format(args)
    if chosen in _NESTING_FORMATS:
        output(record, args)
    elif chosen != "table":
        output(record["contents"], args)
    else:
        limit = table_limit(args)
        print_metadata(album_summary(record, nested), limit)
        rows = item_rows(record)
        if rows:
            print()
            print_table(rows, limit)


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the album-list subparser."""
    single = sub.add_parser(
        "album-list",
        parents=parents,
        help="Show one album's contents, played state, and progress.",
        description=textwrap.fill(
            "Show one music or photo album: the album, with its played "
            "state and progress, then every track, photo, or clip in it, "
            "with its own played state, and where it stands when it is part "
            "way through. JSON and YAML carry the album with its contents "
            "nested; CSV and CLIXML carry one row per item.",
            width=78,
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    single.add_argument(
        "rating_key",
        type=int,
        metavar="ratingKey",
        help="The album's ratingKey (int). Obtain with library-list.",
    )


COMMANDS = {"album-list": cmd_list_album}

REQUIRES_PLEX = frozenset(COMMANDS)
