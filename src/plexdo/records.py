# SPDX-License-Identifier: GPL-3.0-or-later

"""Turning plexapi objects into plain records for listing output.

Attribute access on a partial plexapi object triggers a reload whenever the
value is None or empty, which would mean one HTTP request per item across a
whole library. Everything here reads `vars()` instead, so a listing reports
what the server already sent and costs no extra calls. `show-metadata` is the
route to the complete picture for a single item.
"""

from typing import Any, Dict, List
import datetime

from plexdo.console import clean_text
from plexdo.convert import parse_date
from plexdo.formats import _scalar


# Columns shown by the plain table renderer. Machine-readable formats get
# every field the listing carried.
SUMMARY_FIELDS = ("ratingKey", "title", "releaseDate", "rating", "studio")


# How far to descend into nested plexapi objects. Media -> parts -> Part is
# two levels, which is what carries the file paths.
_MAX_DEPTH = 2


def _scalar(value: Any, depth: int = 0) -> Any:
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
        return [_scalar(item, depth) for item in value]
    # Genres, directors, collections and friends are tag objects.
    for attribute in ("tag", "title"):
        tagged = getattr(value, attribute, None)
        if isinstance(tagged, str):
            return tagged
    if depth < _MAX_DEPTH:
        try:
            nested = {
                name: _scalar(inner, depth + 1)
                for name, inner in sorted(vars(value).items())
                if not name.startswith("_") and not callable(inner)
            }
        except TypeError:
            nested = {}          # no __dict__ to look into
        if nested:
            return nested
    return str(value)


def loaded_fields(item: Any) -> Dict[str, Any]:
    """Every attribute already present on the item, JSON-safe and sorted.

    A "files" key is added alongside: the paths are nested several levels
    down under media, and having them at the top is worth the repetition.
    """
    fields = {
        name: _scalar(value)
        for name, value in sorted(vars(item).items())
        if not name.startswith("_") and not callable(value)
    }
    paths = file_paths(item)
    if paths:
        fields["files"] = paths
    return fields


def file_paths(item: Any) -> List[str]:
    """Server-side paths of every file backing an item.

    An item can have several media versions and each several parts, so this
    is a list. Shows and seasons have no media of their own and yield none.
    """
    paths: List[str] = []
    for media in vars(item).get("media") or []:
        for part in getattr(media, "parts", None) or []:
            path = getattr(part, "file", None)
            if path:
                paths.append(path)
    return paths


def release_date(item: Any) -> str:
    """The item's release date, falling back to the year alone."""
    stamp = parse_date(vars(item).get("originallyAvailableAt"))
    if stamp is not None:
        return stamp.date().isoformat()
    year = vars(item).get("year")
    return str(year) if year else ""


def summary_row(item: Any) -> Dict[str, Any]:
    """The compact record shown in table output."""
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
