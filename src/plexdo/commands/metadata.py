# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Per-item metadata display and update command."""

import argparse
import json
import math
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from plexapi.audio import Track
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show

from plexdo.arguments import add_rating_key_argument
from plexdo.console import clean_text, output, output_format
from plexdo.constants import LOG
from plexdo.convert import format_duration
from plexdo.records import file_paths
from plexdo.titles import display_title, fetch_item


def _base_metadata(item: Any) -> dict[str, Any]:
    """Return metadata fields common to all media types."""
    return {
        "ratingKey": int(item.ratingKey),
        "type": item.type,
        "title": display_title(item),
        "year": getattr(item, "year", "") or "",
        "contentRating": clean_text(getattr(item, "contentRating", "") or ""),
        "rating": getattr(item, "rating", "") or "",
        "duration": format_duration(getattr(item, "duration", None)),
        "addedAt": str(getattr(item, "addedAt", "") or ""),
        "updatedAt": str(getattr(item, "updatedAt", "") or ""),
        "summary": clean_text(getattr(item, "summary", "") or ""),
    }


def _episode_metadata(ep: Episode) -> dict[str, Any]:
    """Return metadata fields specific to Episode items."""
    record = _base_metadata(ep)
    record.update(
        {
            "show": clean_text(ep.grandparentTitle or ""),
            "season": ep.seasonNumber,
            "episode": ep.index,
            "airDate": str(ep.originallyAvailableAt or ""),
            "studio": clean_text(getattr(ep, "studio", "") or ""),
        }
    )
    return record


def _movie_metadata(movie: Movie) -> dict[str, Any]:
    """Return metadata fields specific to Movie items."""
    record = _base_metadata(movie)
    record.update(
        {
            "studio": clean_text(getattr(movie, "studio", "") or ""),
            "airDate": str(getattr(movie, "originallyAvailableAt", "") or ""),
            "tagline": clean_text(getattr(movie, "tagline", "") or ""),
            "genres": ", ".join(g.tag for g in getattr(movie, "genres", [])),
            "directors": ", ".join(
                d.tag for d in getattr(movie, "directors", [])
            ),
        }
    )
    return record


def _show_metadata(show: Show) -> dict[str, Any]:
    """Return metadata fields specific to Show items."""
    record = _base_metadata(show)
    record.update(
        {
            "studio": clean_text(getattr(show, "studio", "") or ""),
            "firstAired": str(getattr(show, "originallyAvailableAt", "") or ""),
            "seasons": getattr(show, "childCount", ""),
            "episodes": getattr(show, "leafCount", ""),
            "genres": ", ".join(g.tag for g in getattr(show, "genres", [])),
            "network": clean_text(getattr(show, "network", "") or ""),
        }
    )
    return record


def _track_metadata(track: Track) -> dict[str, Any]:
    """Return metadata fields specific to Track items."""
    record = _base_metadata(track)
    record.update(
        {
            "album": clean_text(getattr(track, "parentTitle", "") or ""),
            "artist": clean_text(getattr(track, "grandparentTitle", "") or ""),
            "trackNumber": getattr(track, "index", ""),
            "year": getattr(track, "year", "") or "",
        }
    )
    return record


_METADATA_BUILDERS = {
    "episode": _episode_metadata,
    "movie": _movie_metadata,
    "show": _show_metadata,
    "track": _track_metadata,
}


def _file_fields(paths: list[str]) -> dict[str, str]:
    """One row per file, numbered only when there is more than one."""
    if len(paths) == 1:
        return {"file": paths[0]}
    return {f"file {number}": path for number, path in enumerate(paths, 1)}


def _metadata_record(item: Any) -> dict[str, Any]:
    """The fields metadata prints for an item, without its files."""
    builder = _METADATA_BUILDERS.get(item.type, _base_metadata)
    return builder(item)


def _show_record(item: Any, args: argparse.Namespace) -> None:
    """Print an item's metadata in the chosen format."""
    record = _metadata_record(item)
    # A list reads naturally in a structured format, but the key/value table
    # wants one row per file. A container (show, season, album) has no files
    # of its own, so it gets no file rows and no files key rather than an
    # empty list that reads as "the files are missing".
    paths = file_paths(item)
    if output_format(args) == "table":
        record.update(_file_fields(paths))
    elif paths:
        record["files"] = paths
    output(record, args)


# --- --update ----------------------------------------------------------------


class _Invalid(ValueError):
    """A value in the update file that cannot be used for its field."""


def _text(value: Any, _item: Any) -> str:
    """A text field; null and empty both clear it."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _Invalid("must be text")
    return value.strip()


def _title(value: Any, item: Any) -> str:
    """A title, which cannot be empty.

    metadata shows an episode as "Show - Episode", so that prefix is taken
    off again: only the episode's own title is stored on the episode.
    """
    text = _text(value, item)
    if item.type == "episode":
        prefix = f"{clean_text(item.grandparentTitle or '')} - "
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    if not text:
        raise _Invalid("cannot be empty")
    return text


def _number(value: Any) -> float | None:
    """A JSON number or numeric text as a float; null and empty are None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise _Invalid("must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise _Invalid("must be a number") from None
    if not math.isfinite(number):
        raise _Invalid("must be a number")
    return number


def _rating(value: Any, _item: Any) -> float | None:
    """A critic rating from 0 to 10; null or empty clears it."""
    number = _number(value)
    if number is not None and not 0 <= number <= 10:
        raise _Invalid("must be from 0 to 10")
    return number


def _count(value: Any, _item: Any) -> int | None:
    """A whole number of zero or more; null or empty clears it."""
    number = _number(value)
    if number is None:
        return None
    if number < 0 or not number.is_integer():
        raise _Invalid("must be a whole number of 0 or more")
    return int(number)


def _parse_time(value: Any) -> datetime:
    """YYYY-MM-DD, optionally followed by a time, as metadata prints it."""
    if not isinstance(value, str):
        raise _Invalid("must be a date, YYYY-MM-DD")
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        raise _Invalid("must be a date, YYYY-MM-DD") from None


def _day(value: Any, _item: Any) -> date | None:
    """A release date; null or empty clears it. Any time of day is dropped."""
    if value is None or value == "":
        return None
    return _parse_time(value).date()


def _moment(value: Any, _item: Any) -> datetime:
    """When the item was added, which Plex cannot leave empty."""
    if value is None or value == "":
        raise _Invalid("cannot be empty")
    return _parse_time(value)


def _tags(value: Any, _item: Any) -> tuple[str, ...]:
    """Tags as a comma-separated string, as metadata prints them, or a list.

    A list is the way to give a tag that itself contains a comma.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        parts = value
    else:
        raise _Invalid("must be comma-separated text or a list of text")
    unique: dict[str, None] = {}
    for part in parts:
        if part.strip():
            unique[part.strip()] = None
    return tuple(unique)


@dataclass(frozen=True)
class _Editable:
    """A field --update can change, and how.

    ``method`` is the plexapi edit method; an item without it cannot have
    the field changed. ``tag`` names the tag for tag fields, which are
    edited through plexapi's tag helper rather than through ``method``.
    """

    method: str
    parse: Callable[[Any, Any], Any]
    tag: str = ""


_EDITABLE = {
    "title": _Editable("editTitle", _title),
    "summary": _Editable("editSummary", _text),
    "contentRating": _Editable("editContentRating", _text),
    "rating": _Editable("editCriticRating", _rating),
    "addedAt": _Editable("editAddedAt", _moment),
    "airDate": _Editable("editOriginallyAvailable", _day),
    "firstAired": _Editable("editOriginallyAvailable", _day),
    "studio": _Editable("editStudio", _text),
    "tagline": _Editable("editTagline", _text),
    "trackNumber": _Editable("editTrackNumber", _count),
    "genres": _Editable("addGenre", _tags, tag="genre"),
    "directors": _Editable("addDirector", _tags, tag="director"),
}

# Why a field metadata prints cannot be changed, where there is more to say
# than that Plex does not allow it.
_PARENT_FIELDS = {
    "show": "the show",
    "season": "the season",
    "album": "the album",
    "artist": "the artist",
}
_DERIVED_FIELDS = {
    "ratingKey": "it identifies the item; the file describes a different one",
    "type": "it is the kind of item",
    "duration": "it is measured from the media",
    "updatedAt": "Plex sets it when the metadata changes",
    "seasons": "it is counted from the show's seasons",
    "episodes": "it is counted from the show's episodes",
    "files": "they are the media on disk",
}


def _a(kind: str) -> str:
    """An item type with its article: "a movie", "an episode"."""
    return f"{'an' if kind[:1] in 'aeiou' else 'a'} {kind}"


def _why_fixed(field: str, item: Any) -> str:
    """Explain why a field cannot be changed on this item."""
    if field in _DERIVED_FIELDS:
        return _DERIVED_FIELDS[field]
    if field in _PARENT_FIELDS:
        return (
            f"it is {_PARENT_FIELDS[field]}'s; update "
            f"{_PARENT_FIELDS[field]} instead"
        )
    if field == "year" and hasattr(item, "editOriginallyAvailable"):
        date_field = "firstAired" if item.type == "show" else "airDate"
        return f"Plex derives it from the release date; change {date_field}"
    if field == "episode":
        return "Plex numbers episodes from the agent or the file name"
    if field in _EDITABLE:
        return f"Plex cannot edit it on {_a(item.type)}"
    return "Plex does not allow it to be edited"


def _same(left: Any, right: Any) -> bool:
    """Whether two values read the same, as JSON and as metadata prints.

    Null and empty text are both "nothing", text is compared without
    surrounding space, and 7 and 7.0 are one number.
    """
    if isinstance(left, list) or isinstance(right, list):
        if not (isinstance(left, list) and isinstance(right, list)):
            return False
        return len(left) == len(right) and all(map(_same, left, right))
    left = "" if left is None else left
    right = "" if right is None else right
    if isinstance(left, str) and isinstance(right, str):
        return left.strip() == right.strip()
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return str(left).strip() == str(right).strip()


def _shown(value: Any) -> str:
    """A value as an error or change line quotes it."""
    if isinstance(value, tuple):
        value = ", ".join(value)
    if isinstance(value, datetime):
        value = value.isoformat(sep=" ")
    elif isinstance(value, date):
        value = value.isoformat()
    if value is None or value == "":
        return "(empty)"
    return repr(value) if isinstance(value, str) else str(value)


def _server_value(
    field: str, editable: _Editable, item: Any, shown: Any
) -> Any:
    """The server's value of a field, in the form its parser gives.

    The title is the item's own, not the "Show - Episode" form metadata
    shows. A value the parser refuses is kept as shown, so it simply
    differs from whatever the file gives.
    """
    if field == "title":
        return clean_text(item.title or "")
    try:
        return editable.parse(shown, item)
    except _Invalid:
        return shown


@dataclass(frozen=True)
class _Change:
    """One field the update file changes."""

    field: str
    editable: _Editable
    old: Any
    new: Any


def _plan_update(
    item: Any, wanted: dict[str, Any]
) -> tuple[list[_Change], list[str]]:
    """Compare the update file with the item: what to change, what is wrong.

    A field the file leaves out is not touched. A field it gives the same
    value the server has is skipped, changeable or not. A changed value is
    a change if the field can be edited on this item and an error if not.
    """
    current = _metadata_record(item)
    current["files"] = file_paths(item)
    changes: list[_Change] = []
    problems: list[str] = []
    for field, value in wanted.items():
        if field not in current:
            problems.append(
                f"{field}: not a field metadata shows for {_a(item.type)}"
            )
            continue
        editable = _EDITABLE.get(field)
        if editable is None or not hasattr(item, editable.method):
            if not _same(value, current[field]):
                problems.append(
                    f"{field}: cannot be changed ({_why_fixed(field, item)}); "
                    f"the server has {_shown(current[field])}, the file "
                    f"{_shown(value)}"
                )
            continue
        try:
            new = editable.parse(value, item)
        except _Invalid as exc:
            problems.append(f"{field}: {exc}, not {_shown(value)}")
            continue
        old = _server_value(field, editable, item, current[field])
        if editable.tag:
            unchanged = set(new) == set(old)
        else:
            unchanged = new == old
        if not unchanged:
            changes.append(_Change(field, editable, old, new))
    return changes, problems


def _apply(item: Any, change: _Change) -> None:
    """Queue one change on an item in plexapi's batch edit mode.

    plexapi locks each edited field, so a later metadata refresh from the
    agent does not put the old value back.
    """
    if change.editable.tag:
        # Giving the whole list sets the tags; naming the dropped ones with
        # the removal key clears them even when the list is empty. plexapi's
        # addGenre would prepend the current tags, dropped ones included.
        helper = item._tagHelper  # pylint: disable=protected-access
        edits: dict[str, Any] = {}
        if change.new:
            edits.update(helper(change.editable.tag, list(change.new)))
        dropped = [tag for tag in change.old if tag not in change.new]
        if dropped:
            edits.update(helper(change.editable.tag, dropped, remove=True))
        item._edit(**edits)  # pylint: disable=protected-access
        return
    value = change.new
    if isinstance(value, date) and not isinstance(value, datetime):
        value = value.isoformat()
    getattr(item, change.editable.method)("" if value is None else value)


def _read_update_file(path: str) -> dict[str, Any]:
    """Load the update file, exiting with the reason if it is unusable."""
    name = "standard input" if path == "-" else path
    try:
        if path == "-":
            data = json.load(sys.stdin)
        else:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
    except OSError as exc:
        sys.exit(f"Cannot read {name}: {exc.strerror or exc}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        sys.exit(f"{name} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        sys.exit(
            f"{name} must hold one JSON object, as metadata --json prints, "
            f"not a {type(data).__name__}."
        )
    return data


def _update(plex: PlexServer, args: argparse.Namespace) -> None:
    """Change the item's metadata to match the update file."""
    item = fetch_item(plex, args.rating_key)
    changes, problems = _plan_update(item, args.update_fields)
    if problems:
        name = "standard input" if args.update == "-" else args.update
        sys.exit(
            f"Not updating {display_title(item)!r} (ratingKey "
            f"{int(item.ratingKey)}): {name} has\n"
            + "\n".join(f"  {problem}" for problem in problems)
        )
    if not changes:
        print(
            "Nothing to change: every field given matches the server.",
            file=sys.stderr,
        )
    verb = "Would change" if args.dry_run else "Changing"
    for change in changes:
        print(
            f"{verb} {change.field}: {_shown(change.old)} -> "
            f"{_shown(change.new)}",
            file=sys.stderr,
        )
    if args.dry_run:
        return
    if changes:
        LOG.info("Saving %d field(s) in one request", len(changes))
        item.batchEdits()
        for change in changes:
            _apply(item, change)
        item.saveEdits()
        item = fetch_item(plex, args.rating_key)
    _show_record(item, args)


def cmd_show_metadata(plex: PlexServer, args: argparse.Namespace) -> None:
    """Display, or with --update change, the metadata of one item."""
    if getattr(args, "update", None) is not None:
        _update(plex, args)
        return
    _show_record(fetch_item(plex, args.rating_key), args)


def _check_metadata(args: argparse.Namespace) -> None:
    """Read the update file before connecting, so a bad one costs nothing."""
    if args.update is not None:
        args.update_fields = _read_update_file(args.update)


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the metadata subparser."""
    parser = sub.add_parser(
        "metadata",
        parents=parents,
        help="Show or update the metadata of one item, by ratingKey.",
        description=textwrap.fill(
            "Show the metadata of one item. With --update, first change it "
            "to match a JSON file shaped like the output of metadata --json: "
            "fields the file leaves out, and fields it gives unchanged, are "
            "left alone; a changed field that cannot be edited is an error, "
            "and nothing is changed.",
            width=78,
        ),
        epilog=(
            "changeable fields, where the item type allows them:\n"
            "  title, summary, contentRating, rating, addedAt, airDate,\n"
            "  firstAired, studio, tagline, trackNumber, genres, directors\n"
            "\n"
            "examples:\n"
            "  plexdo metadata 881 --json > 881.json\n"
            "  plexdo metadata 881 --update 881.json --dry-run\n"
            "  plexdo metadata 881 -u 881.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_rating_key_argument(parser)
    parser.add_argument(
        "-u",
        "--update",
        metavar="FILE",
        help=(
            "Change the item to match this JSON file, or standard input "
            "for -. Edited fields are locked against agent refreshes."
        ),
    )
    parser.set_defaults(check_arguments=_check_metadata)


COMMANDS = {"metadata": cmd_show_metadata}

REQUIRES_PLEX = frozenset(COMMANDS)
