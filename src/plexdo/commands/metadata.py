# SPDX-License-Identifier: GPL-3.0-or-later

"""Per-item metadata display command."""

from typing import Any, Dict, List
import argparse

from plexapi.audio import Track
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show

from plexdo.console import clean_text, output, output_format
from plexdo.convert import format_duration
from plexdo.records import file_paths
from plexdo.titles import display_title, fetch_item


def _base_metadata(item: Any) -> Dict[str, Any]:
    """Return metadata fields common to all media types."""
    return {
        "ratingKey":     int(item.ratingKey),
        "type":          item.type,
        "title":         display_title(item),
        "year":          getattr(item, "year", "") or "",
        "contentRating": clean_text(getattr(item, "contentRating", "") or ""),
        "rating":        getattr(item, "rating", "") or "",
        "duration":      format_duration(getattr(item, "duration", None)),
        "addedAt":       str(getattr(item, "addedAt", "") or ""),
        "updatedAt":     str(getattr(item, "updatedAt", "") or ""),
        "summary":       clean_text(getattr(item, "summary", "") or ""),
    }


def _episode_metadata(ep: Episode) -> Dict[str, Any]:
    """Return metadata fields specific to Episode items."""
    record = _base_metadata(ep)
    record.update({
        "show":          clean_text(ep.grandparentTitle or ""),
        "season":        ep.seasonNumber,
        "episode":       ep.index,
        "airDate":       str(ep.originallyAvailableAt or ""),
        "studio":        clean_text(getattr(ep, "studio", "") or ""),
    })
    return record


def _movie_metadata(movie: Movie) -> Dict[str, Any]:
    """Return metadata fields specific to Movie items."""
    record = _base_metadata(movie)
    record.update({
        "studio":        clean_text(getattr(movie, "studio", "") or ""),
        "airDate":       str(getattr(movie, "originallyAvailableAt", "") or ""),
        "tagline":       clean_text(getattr(movie, "tagline", "") or ""),
        "genres":        ", ".join(g.tag for g in getattr(movie, "genres", [])),
        "directors":     ", ".join(d.tag for d in getattr(movie, "directors", [])),
    })
    return record


def _show_metadata(show: Show) -> Dict[str, Any]:
    """Return metadata fields specific to Show items."""
    record = _base_metadata(show)
    record.update({
        "studio":        clean_text(getattr(show, "studio", "") or ""),
        "firstAired":    str(getattr(show, "originallyAvailableAt", "") or ""),
        "seasons":       getattr(show, "childCount", ""),
        "episodes":      getattr(show, "leafCount", ""),
        "genres":        ", ".join(g.tag for g in getattr(show, "genres", [])),
        "network":       clean_text(getattr(show, "network", "") or ""),
    })
    return record


def _track_metadata(track: Track) -> Dict[str, Any]:
    """Return metadata fields specific to Track items."""
    record = _base_metadata(track)
    record.update({
        "album":         clean_text(getattr(track, "parentTitle", "") or ""),
        "artist":        clean_text(getattr(track, "grandparentTitle", "") or ""),
        "trackNumber":   getattr(track, "index", ""),
        "year":          getattr(track, "year", "") or "",
    })
    return record


_METADATA_BUILDERS = {
    "episode": _episode_metadata,
    "movie":   _movie_metadata,
    "show":    _show_metadata,
    "track":   _track_metadata,
}


def _file_fields(paths: List[str]) -> Dict[str, str]:
    """One row per file, numbered only when there is more than one."""
    if len(paths) == 1:
        return {"file": paths[0]}
    return {f"file {number}": path for number, path in enumerate(paths, 1)}


def cmd_show_metadata(plex: PlexServer, args: argparse.Namespace) -> None:
    """Display metadata for a single item by ratingKey."""
    item = fetch_item(plex, args.rating_key)
    builder = _METADATA_BUILDERS.get(item.type, _base_metadata)
    record: Dict[str, Any] = builder(item)

    # A list reads naturally in a structured format, but the key/value table
    # wants one row per file.
    paths = file_paths(item)
    if output_format(args) == "table":
        record.update(_file_fields(paths))
    else:
        record["files"] = paths

    output(record, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the metadata subparser."""
    parser = sub.add_parser(
        "show-metadata", parents=parents,
        help="Display metadata for a single item by ratingKey.",
    )
    parser.add_argument(
        "rating_key", type=int,
        help="Item ratingKey (int). Obtain with list-titles or list-show.",
    )


COMMANDS = {"show-metadata": cmd_show_metadata}

REQUIRES_PLEX = frozenset(COMMANDS)
