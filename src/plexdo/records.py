# SPDX-License-Identifier: GPL-3.0-or-later

"""Turning plexapi objects into plain records for listing output.

Attribute access on a partial plexapi object triggers a reload whenever the
value is None or empty, which would mean one HTTP request per item across a
whole library. Everything here reads `vars()` instead, so a listing reports
what the server already sent and costs no extra calls. `show-metadata` is the
route to the complete picture for a single item.
"""

from typing import Any, Dict, Iterator, List, Tuple
import datetime

from plexdo.console import clean_text
from plexdo.convert import parse_date


# How far to descend into nested plexapi objects. Media -> parts -> Part is
# two levels, which is what carries the file paths.
_MAX_DEPTH = 2


def _jsonable(value: Any, depth: int = 0) -> Any:
    """Reduce a plexapi attribute to something a serialiser can carry.

    Nested objects such as Media and Part are expanded rather than repr'd,
    since that is where the file paths, sizes, and codecs live.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat(sep=" ") if isinstance(
            value, datetime.datetime) else value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_jsonable(item, depth) for item in value]
    # Genres, directors, collections and friends are tag objects.
    for attribute in ("tag", "title"):
        tagged = getattr(value, attribute, None)
        if isinstance(tagged, str):
            return tagged
    if depth < _MAX_DEPTH:
        try:
            nested = {
                name: _jsonable(inner, depth + 1)
                for name, inner in sorted(vars(value).items())
                if not name.startswith("_") and not callable(inner)
            }
        except TypeError:
            nested = {}          # no __dict__ to look into
        if nested:
            return nested
    return str(value)


def _readable_names(item: Any) -> List[str]:
    """Every public field name an item exposes.

    Instance attributes alone are not enough: plexapi moved genres,
    directors, media and a dozen others to ``cached_data_property``, which
    does not appear in ``vars()`` until first accessed. A Movie has 18 of
    them, so reading only ``vars()`` reports a fraction of the metadata.
    """
    lazy = getattr(type(item), "_cached_data_properties", set())
    names = set(vars(item)) | set(lazy)
    return sorted(name for name in names if not name.startswith("_"))


def loaded_fields(item: Any) -> Dict[str, Any]:
    """Every field the item carries, JSON-safe and sorted.

    Reads with plexapi's auto-reload disabled, so a field that happens to be
    empty does not trigger an HTTP request; across a library that would be
    one round trip per item. A "files" key is added alongside, since the
    paths are otherwise several levels down.
    """
    fields: Dict[str, Any] = {}
    restore = getattr(item, "_autoReload", None)
    if restore is not None:
        item._autoReload = False        # pylint: disable=protected-access
    try:
        for name in _readable_names(item):
            try:
                value = getattr(item, name)
            except Exception:           # pylint: disable=broad-except
                continue                # a property that cannot resolve offline
            if callable(value):
                continue
            fields[name] = _jsonable(value)
    finally:
        if restore is not None:
            item._autoReload = restore  # pylint: disable=protected-access

    paths = file_paths(item)
    if paths:
        fields["files"] = paths
    return fields


def _media_versions(item: Any) -> Iterator[Tuple[bool, List[Tuple[bool, str]]]]:
    """Yield (selected, parts) for each media version of an item.

    Reads the XML plexapi already holds in ``_data`` rather than the ``media``
    property. That property is a ``cached_data_property``, so it is absent
    from ``vars()`` until something first touches it, and touching it on an
    item that genuinely has no media satisfies plexapi's reload condition and
    costs an HTTP request. The XML is already in memory and always accurate.

    Falls back to the typed objects for anything without ``_data``.
    """
    data = getattr(item, "_data", None)
    if data is not None:
        for element in data.findall("Media"):
            parts = [
                (part.get("selected") == "1", part.get("file") or "")
                for part in element.findall("Part")
            ]
            yield element.get("selected") == "1", parts
        return
    for media in getattr(item, "media", None) or []:
        yield (
            bool(getattr(media, "selected", False)),
            [
                (bool(getattr(part, "selected", False)),
                 getattr(part, "file", None) or "")
                for part in getattr(media, "parts", None) or []
            ],
        )


def file_paths(item: Any) -> List[str]:
    """Server-side paths of every file backing an item.

    An item can have several media versions and a version several parts, so
    this is a list. Containers such as shows and seasons have no media of
    their own and yield nothing; their files belong to their episodes.
    """
    return [
        path
        for _, parts in _media_versions(item)
        for _, path in parts
        if path
    ]


def _preferred(entries: List[Tuple[bool, Any]]) -> List[Any]:
    """Entries Plex marked as selected, or all of them when none is marked.

    A session marks the version and part actually being played, which is the
    only way to tell them apart on a multi-version item. Nothing is marked
    when there is just one, so an empty selection means "all of them".
    """
    chosen = [value for selected, value in entries if selected]
    return chosen or [value for _, value in entries]


def playing_file(item: Any) -> str:
    """The single file a player has open, or empty if none is resolvable."""
    versions = list(_media_versions(item))
    for parts in _preferred(versions):
        for path in _preferred(parts):
            if path:
                return path
    return ""


def release_date(item: Any) -> str:
    """The item's release date, falling back to the year alone."""
    stamp = parse_date(vars(item).get("originallyAvailableAt"))
    if stamp is not None:
        return stamp.date().isoformat()
    year = vars(item).get("year")
    return str(year) if year else ""


def summary_row(item: Any) -> Dict[str, Any]:
    """The compact record shown in table output.

    Machine-readable formats carry every field the listing returned; these
    five are what fits usefully in a terminal.
    """
    fields = vars(item)
    return {
        "ratingKey": int(item.ratingKey),
        "title": clean_text(fields.get("title", "")),
        "releaseDate": release_date(item),
        "rating": fields.get("rating") or "",
        "studio": clean_text(fields.get("studio") or ""),
    }


def cache_row(item: Any) -> Dict[str, Any]:
    """The minimal record the completion cache needs."""
    return {"ratingKey": int(item.ratingKey),
            "title": clean_text(fields_title(item))}


def fields_title(item: Any) -> str:
    """The item's own title, without forcing a reload."""
    return vars(item).get("title", "") or ""


def season_records(show: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Episodes of a show, grouped into an object keyed by season name.

    This walks seasons and episodes, so it costs API calls proportional to the
    size of the show; it is only built for machine-readable output.
    """
    seasons: Dict[str, List[Dict[str, Any]]] = {}
    for season in show.seasons():
        name = clean_text(vars(season).get("title") or "")
        if not name:
            name = f"Season {vars(season).get('index', '?')}"
        seasons[name] = [loaded_fields(episode) for episode in season.episodes()]
    return seasons
