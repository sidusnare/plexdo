# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Library listing and whole-library export commands."""

import argparse
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from typing import Any

from plexapi.exceptions import BadRequest, NotFound
from plexapi.server import PlexServer
from plexapi.video import Episode

from plexdo.arguments import add_library_argument, add_m3u_argument
from plexdo.cache import write_cache, write_word_caches
from plexdo.commands.albums import list_albums
from plexdo.console import clean_text, output, output_format
from plexdo.constants import LOG
from plexdo.gallery import write_gallery_html
from plexdo.identify import argument_words
from plexdo.m3u import write_m3u
from plexdo.paths import add_prefix_argument, mapper_for
from plexdo.photos import collect_library_items, collect_photos
from plexdo.records import (
    cache_row,
    loaded_fields,
    release_date,
    season_records,
    summary_row,
)
from plexdo.sections import resolve_section
from plexdo.sorting import apply_sort
from plexdo.throttle import paced
from plexdo.titles import display_title, fetch_show, non_special_episodes


def cmd_list_libraries(plex: PlexServer, args: argparse.Namespace) -> None:
    """List all Plex libraries."""
    rows = [
        {
            "id": int(lib.key),
            "type": lib.type,
            "title": lib.title,
        }
        for lib in plex.library.sections()
    ]
    write_cache("libraries", rows)
    output(rows, args)


def _detailed_row(item: Any, with_seasons: bool) -> dict[str, Any]:
    """Every listed field for one item, plus its seasons for a show."""
    record = loaded_fields(item)
    record["releaseDate"] = release_date(item)
    if with_seasons:
        record["seasons"] = season_records(item)
    return record


# What library-list can list in each kind of library, the default first.
# Each is a type /library/sections/{id}/all?type= serves for that kind of
# library: plexapi's section.all(libtype=...) asks for exactly that. A music
# library's section type is "artist", after its top level. Every kind can
# also be listed by folder, which is a different endpoint.
LIST_TYPES: dict[str, tuple[str, ...]] = {
    "movie": ("movie", "collection"),
    "show": ("show", "season", "episode", "collection"),
    "artist": ("album", "artist", "track", "collection"),
    "photo": ("album", "photo", "clip"),
}
FOLDER = "folder"
TYPE_CHOICES = tuple(
    sorted({kind for kinds in LIST_TYPES.values() for kind in kinds} | {FOLDER})
)

# How Plex names a library's kind, for messages.
_KIND_NAMES = {"artist": "music"}


def _list_type(section: Any, args: argparse.Namespace) -> str:
    """The type to list: as asked, or the library's default.

    --album means the photos of an album, and --path a folder, so either
    picks its type when none was named.
    """
    allowed = LIST_TYPES.get(section.type, ())
    if args.list_type is not None:
        wanted = args.list_type
    elif args.path is not None:
        wanted = FOLDER
    elif args.album is not None and section.type == "photo":
        wanted = "photo"
    elif allowed:
        wanted = allowed[0]
    else:
        sys.exit(
            f"Library '{section.title}' is a {section.type} library, which "
            f"library-list cannot list except by folder: use --type {FOLDER}."
        )
    if wanted != FOLDER and wanted not in allowed:
        kind = _KIND_NAMES.get(section.type, section.type)
        choices = ", ".join((*allowed, FOLDER))
        sys.exit(
            f"Library '{section.title}' is a {kind} library, which holds no "
            f"{wanted} items; --type takes {choices} there."
        )
    return wanted


def _table_row(item: Any, kind: str) -> dict[str, Any]:
    """The compact record for a table, with what places the item.

    A title alone says little for an episode or a track, so each of those
    carries what it belongs to.
    """
    fields = vars(item)
    row: dict[str, Any] = {"ratingKey": int(item.ratingKey)}
    if kind == "episode":
        row["show"] = clean_text(fields.get("grandparentTitle") or "")
        row["season"] = fields.get("parentIndex", "")
        row["episode"] = fields.get("index", "")
    elif kind == "season":
        row["show"] = clean_text(fields.get("parentTitle") or "")
        row["season"] = fields.get("index", "")
    elif kind == "track":
        row["artist"] = clean_text(
            fields.get("originalTitle") or fields.get("grandparentTitle") or ""
        )
        row["album"] = clean_text(fields.get("parentTitle") or "")
        row["track"] = fields.get("index", "")
    summary = summary_row(item)
    del summary["ratingKey"]
    if kind == "collection":
        row.update(title=summary["title"], items=fields.get("childCount", ""))
    elif kind in ("season", "track", "photo", "clip"):
        # No studio or rating to speak of; the date says enough.
        row.update(title=summary["title"], date=summary["releaseDate"])
    else:
        row.update(summary)
    return row


# What --filter accepts between a field and its value, as written on the
# command line, mapped to how plexapi spells the operator on the field.
# Longest first, so "!=" is not read as "!" and "=".
_OPERATORS = (("!=", "!"), (">", ">>"), ("<", "<<"), ("=", ""))

# The field --category stands for.
CATEGORY_FIELD = "genre"


def parse_filter(text: str) -> tuple[str, str]:
    """One --filter, FIELD=VALUE, as (field with its operator, value).

    FIELD!=VALUE excludes, and FIELD>VALUE and FIELD<VALUE compare a number
    or a date. The field is checked by the server's list of filters, so any
    it offers works and an unknown one is reported with the others.
    """
    match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)(!=|>|<|=)(.*)", text, re.S)
    if not match or not match.group(3).strip():
        raise argparse.ArgumentTypeError(
            f"expected FIELD=VALUE, such as genre=Drama or year>1990, not "
            f"{text!r}"
        )
    field, written, value = match.groups()
    operator = dict(_OPERATORS)[written]
    return field + operator, value.strip()


def _filters(args: argparse.Namespace) -> dict | None:
    """The --filter and --category options as plexapi's filter dictionary.

    Every one must hold, so two are joined with "and", which plexapi sends
    as the server's advanced search. None when there are none.
    """
    pairs = [
        *(args.filters or ()),
        *((CATEGORY_FIELD, category) for category in args.categories or ()),
    ]
    if not pairs:
        return None
    if len(pairs) == 1:
        return dict(pairs)
    return {"and": [{field: value} for field, value in pairs]}


def _libtype(section: Any, kind: str) -> str:
    """The type plexapi asks for: a photo library's album is a photoalbum."""
    return "photoalbum" if kind == "album" and section.type == "photo" else kind


@contextmanager
def _filtering(section: Any) -> Iterator[None]:
    """Turn a filter the server cannot apply into a message, not a crash.

    plexapi checks each field and value against the library's own list
    before asking, and raises with the fields there are, which is what
    someone who mistyped one needs to see.
    """
    try:
        yield
    except (BadRequest, NotFound) as exc:
        reason = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
        sys.exit(f"Cannot filter library '{section.title}': {reason}")


def _items_of(
    section: Any, kind: str, args: argparse.Namespace, filters: dict | None
) -> list[Any]:
    """Every item of one type in a library, from /all?type=."""
    if kind == "photo" and args.album is not None:
        # An album's photos, nested albums' included, need the album walk.
        return list(collect_photos(section, args.album, args))
    if filters is None:
        return list(section.all(libtype=kind))
    return list(section.all(libtype=kind, filters=filters))


def _categories(section: Any, kind: str) -> list[dict[str, str]]:
    """The categories, which are genres, the items of one type are filed in."""
    choices = section.listFilterChoices(
        CATEGORY_FIELD, libtype=_libtype(section, kind)
    )
    return [{"category": clean_text(choice.title or "")} for choice in choices]


def _show_items(items: list[Any], kind: str, args: argparse.Namespace) -> None:
    """Output the items listed: compact as a table, everything otherwise."""
    if output_format(args) == "table":
        output([_table_row(item, kind) for item in items], args)
        return
    if kind != "show":
        output([_detailed_row(item, False) for item in items], args)
        return
    LOG.info(
        "Collecting seasons and episodes for %d show(s); this walks the "
        "whole library.",
        len(items),
    )
    output(
        [_detailed_row(item, True) for item in paced(items, args, "shows")],
        args,
    )


def cmd_list_titles(plex: PlexServer, args: argparse.Namespace) -> None:
    """List what a library holds, of one type, or folder by folder."""
    library_id = args.library_id
    section = resolve_section(plex, library_id)
    if args.album is not None and section.type != "photo":
        LOG.warning("--album is only applicable to photo libraries; ignoring.")
        args.album = None
    kind = _list_type(section, args)

    if kind == FOLDER:
        output(list_folder(plex, section, args.path or ""), args)
        return
    if args.list_categories:
        with _filtering(section):
            output(_categories(section, kind), args)
        return
    filters = _filters(args)
    with _filtering(section):
        if kind == "album":
            items = list_albums(section, args, filters)
        else:
            items = _items_of(section, kind, args, filters)
            _show_items(items, kind, args)

    if args.list_type is None and args.album is None and filters is None:
        # The completion cache holds the library's default listing, so what
        # it offers does not change with whatever was listed last. It only
        # ever needs the key and the title.
        cached = [cache_row(item) for item in items]
        write_cache(f"titles.{library_id}", cached)
        write_word_caches("titles", argument_words(args, "library_id"), cached)


def _folder_entries(plex: PlexServer, key: str, above: str) -> list[dict]:
    """What one folder holds: its subfolders, then its items, as records.

    Read from the XML, since plexapi has no class for a folder's mixed
    contents. A subfolder carries no ratingKey; its path is what --path
    takes to open it. An item is whatever the folder holds directly, a
    film or a track, or a show or album when the folder is one.
    """
    entries: list[dict] = []
    for element in plex.query(key):
        title = clean_text(element.get("title") or "")
        rating_key = element.get("ratingKey")
        if rating_key is None:
            entries.append(
                {
                    "type": FOLDER,
                    "ratingKey": None,
                    "title": title,
                    "path": f"{above}/{title}" if above else title,
                    "key": element.get("key") or "",
                }
            )
        else:
            entries.append(
                {
                    "type": element.get("type") or element.tag.lower(),
                    "ratingKey": int(rating_key),
                    "title": title,
                    "path": None,
                    "key": None,
                }
            )
    return entries


def _match_folder(entries: list[dict], name: str) -> dict | None:
    """The subfolder titled name, exactly before ignoring case."""
    folders = [e for e in entries if e["type"] == FOLDER]
    for same in (
        lambda e: e["title"] == name,
        lambda e: e["title"].lower() == name.lower(),
    ):
        found = [e for e in folders if same(e)]
        if len(found) == 1:
            return found[0]
        if found:
            sys.exit(f"{len(found)} folders are titled {name!r} here.")
    return None


def list_folder(plex: PlexServer, section: Any, path: str) -> list[dict]:
    """The folder at path in a library, opened one level at a time.

    path is a chain of folder titles separated by "/", from the top of the
    library; empty, it lists the top. Each level costs one request.
    """
    key = f"/library/sections/{section.key}/folder"
    above = ""
    entries = _folder_entries(plex, key, above)
    for name in (part for part in path.split("/") if part):
        found = _match_folder(entries, name)
        if found is None:
            where = f"'{above}'" if above else "the top of the library"
            names = ", ".join(
                repr(e["title"]) for e in entries if e["type"] == FOLDER
            )
            sys.exit(
                f"No folder {name!r} in {where} of '{section.title}'. "
                f"It holds: {names or 'no folders'}."
            )
        above = found["path"]
        entries = _folder_entries(plex, found["key"], above)
    for entry in entries:
        del entry["key"]
    return entries


def cmd_list_show(plex: PlexServer, args: argparse.Namespace) -> None:
    """List all episodes in a show, optionally exporting an M3U."""
    rating_key = int(args.rating_key)
    show = fetch_show(plex, rating_key)
    episodes: list[Episode] = non_special_episodes(show)

    rows = [
        {
            "index": i + 1,
            "ratingKey": int(ep.ratingKey),
            "season": ep.seasonNumber,
            "episode": ep.index,
            "title": display_title(ep),
        }
        for i, ep in enumerate(episodes)
    ]
    output(rows, args)

    if args.m3u:
        write_m3u(episodes, args.m3u, mapper_for(plex, args))  # type: ignore[arg-type]


def cmd_export_titles(plex: PlexServer, args: argparse.Namespace) -> None:
    """Export an entire library to an M3U file."""
    section = resolve_section(plex, args.library_id)

    LOG.info(
        "Collecting items from library '%s' (type=%s)",
        section.title,
        section.type,
    )
    album: str | None = getattr(args, "album", None)
    if album and section.type != "photo":
        LOG.warning("--album is only applicable to photo libraries; ignoring.")
        album = None

    items = collect_library_items(section, album, args)

    if not items:
        sys.exit(f"Library '{section.title}' contains no items.")

    sorted_items = apply_sort(items, args.sort)
    gallery_title = f"{section.title} - {album}" if album else section.title
    LOG.info(
        "Exporting %d item(s) sorted by '%s' to %s",
        len(sorted_items),
        args.sort,
        args.output_path,
    )
    if section.type == "photo":
        write_gallery_html(
            sorted_items,
            args.output_path,
            gallery_title,
            mapper_for(plex, args),
        )
    else:
        write_m3u(sorted_items, args.output_path, mapper_for(plex, args))
        print(f"Exported {len(sorted_items)} items to: {args.output_path}")


_LIST_DESCRIPTION = """\
List what a library holds. --type picks what to list; by default a movie
library lists its movies, a show library its shows, and a music or photo
library its albums.

  movie library   movie, collection
  show library    show, season, episode, collection
  music library   album, artist, track, collection
  photo library   album, photo, clip
  any library     folder: the library's folders, as on disk; --path opens
                  one, as folder titles separated by /

--filter FIELD=VALUE lists only what matches, on any field the library can
be filtered by; --category NAME is --filter genre=NAME, and
--list-categories lists the genres there are.

A table is kept compact. A machine-readable format (-f json, yaml, csv,
clixml) carries every field the server returned for each item, nests each
show's episodes under a seasons object keyed by season name, and gives each
album its played state, progress, and contents."""


def _check_list(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Refuse an option that does not go with the type asked for; exit 2."""
    if args.path is not None and args.list_type not in (None, FOLDER):
        parser.error(
            f"--path lists a folder; it cannot go with --type {args.list_type}"
        )
    if args.album is not None and args.list_type not in (None, "photo"):
        parser.error(
            f"--album lists photos; it cannot go with --type {args.list_type}"
        )
    if args.album is not None and args.path is not None:
        parser.error("--album and --path cannot be used together")
    narrowing = [
        flag
        for flag, given in (
            ("--filter", args.filters),
            ("--category", args.categories),
            ("--list-categories", args.list_categories),
        )
        if given
    ]
    if not narrowing:
        return
    if args.path is not None or args.list_type == FOLDER:
        parser.error(f"{narrowing[0]} cannot go with a folder listing")
    if args.album is not None:
        parser.error(f"{narrowing[0]} cannot go with --album")
    if args.list_categories and len(narrowing) > 1:
        parser.error(
            "--list-categories lists every category; it takes no --filter "
            "or --category"
        )


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the library-related subparsers."""
    sub.add_parser(
        "libraries-list",
        parents=parents,
        help="List the server's libraries.",
    )

    p_lt = sub.add_parser(
        "library-list",
        parents=parents,
        help="List what a library holds, by type or by folder.",
        description=_LIST_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_lt.set_defaults(check_arguments=partial(_check_list, p_lt))
    add_library_argument(p_lt)
    p_lt.add_argument(
        "-t",
        "--type",
        dest="list_type",
        choices=TYPE_CHOICES,
        default=None,
        metavar="TYPE",
        help=(
            "What to list: " + ", ".join(TYPE_CHOICES) + ". The library's "
            "kind decides which apply; the default is movie, show, or album."
        ),
    )
    p_lt.add_argument(
        "--path",
        default=None,
        metavar="PATH",
        help=(
            "With --type folder, the folder to list, as folder titles from "
            "the top of the library separated by /, as in TV/The Wire. "
            "Implies --type folder."
        ),
    )
    p_lt.add_argument(
        "--filter",
        dest="filters",
        action="append",
        type=parse_filter,
        default=None,
        metavar="FIELD=VALUE",
        help=(
            "List only what matches: any field the library can be filtered "
            "by, as genre=Drama, collection=Marvel, contentRating=PG, "
            "label=Kids, or 'year>1990', quoted for the shell. != excludes. "
            "Repeat it, and every one must match."
        ),
    )
    p_lt.add_argument(
        "--category",
        dest="categories",
        action="append",
        default=None,
        metavar="CATEGORY",
        help="Short for --filter genre=CATEGORY. Repeatable.",
    )
    p_lt.add_argument(
        "--list-categories",
        action="store_true",
        default=False,
        help=(
            "List the categories (genres) of the type listed, in place of "
            "the items."
        ),
    )
    p_lt.add_argument(
        "--album",
        default=None,
        metavar="ALBUM",
        help=(
            "Photo libraries only: list the photos of the album titled "
            "ALBUM, and of the albums inside it. Implies --type photo."
        ),
    )

    p_ls = sub.add_parser(
        "show-list",
        parents=parents,
        help="List a show's episodes; optionally export an M3U.",
    )
    p_ls.add_argument(
        "rating_key",
        metavar="ratingKey",
        type=int,
        help="Show ratingKey (int). Obtain with library-list.",
    )
    add_m3u_argument(p_ls)
    add_prefix_argument(p_ls)

    p_et = sub.add_parser(
        "titles-export",
        parents=parents,
        help="Export a library to an M3U file or photo gallery.",
    )
    add_library_argument(p_et)
    p_et.add_argument(
        "output_path",
        metavar="PATH",
        help=(
            "Output file path. M3U for show/movie libraries; "
            "HTML gallery for photo libraries."
        ),
    )
    p_et.add_argument(
        "--sort",
        choices=["alpha", "date", "random"],
        default="alpha",
        help=(
            "Sort order: 'alpha' = alphabetical by title/show+episode "
            "(default), "
            "'date' = by original air date (undated items last), "
            "'random' = randomised."
        ),
    )
    p_et.add_argument(
        "--album",
        default=None,
        metavar="ALBUM",
        help="Photo libraries only: restrict export to a single album name.",
    )
    add_prefix_argument(p_et)


COMMANDS = {
    "libraries-list": cmd_list_libraries,
    "library-list": cmd_list_titles,
    "show-list": cmd_list_show,
    "titles-export": cmd_export_titles,
}

REQUIRES_PLEX = frozenset(COMMANDS)
