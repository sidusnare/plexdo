# SPDX-License-Identifier: GPL-3.0-or-later

"""Watched-state synchronisation between two users."""

from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple
import argparse
import datetime
import sys

from plexapi.server import PlexServer

from plexdo.accounts import server_for_user
from plexdo.console import output, output_format
from plexdo.constants import LOG
from plexdo.convert import parse_date
from plexdo.sections import resolve_sections
from plexdo.throttle import paced
from plexdo.titles import display_title, fetch_item


# Library type -> the leaf libtype that actually carries watch state.
# Photo libraries have none and are skipped entirely.
_WATCHABLE_LIBTYPES = {"movie": "movie", "show": "episode", "artist": "track"}


# Plex rewrites viewOffset continuously during playback, so offsets within
# this many milliseconds are treated as identical rather than as a change.
_OFFSET_TOLERANCE_MS = 10_000


class WatchState(NamedTuple):
    """One item's watch progress as seen by one user."""

    played: bool
    offset: int
    last_viewed: Optional[datetime.datetime]
    item: Any


class PlannedChange(NamedTuple):
    """A single pending watch-state update."""

    rating_key: int
    title: str
    action: str
    target: str
    winner: WatchState
    loser: WatchState


def _call_first_method(item: Any, names: Sequence[str], *args: Any) -> bool:
    """Call the first method in names that exists; return True if one ran.

    plexapi renamed these (markWatched -> markPlayed, etc.), so both
    spellings are attempted for compatibility across library versions.
    """
    for name in names:
        method = getattr(item, name, None)
        if callable(method):
            method(*args)
            return True
    LOG.debug("None of %s available on %r", list(names), type(item).__name__)
    return False


def _item_is_played(item: Any) -> bool:
    """Return True if the item is marked fully played for this user."""
    for attr in ("isPlayed", "isWatched"):
        value = getattr(item, attr, None)
        if isinstance(value, bool):
            return value
    return bool(getattr(item, "viewCount", 0))


def _watch_state(item: Any) -> WatchState:
    """Capture the watch state of a single item."""
    return WatchState(
        played=_item_is_played(item),
        offset=int(getattr(item, "viewOffset", 0) or 0),
        last_viewed=parse_date(getattr(item, "lastViewedAt", None)),
        item=item,
    )


def _has_watch_data(state: WatchState) -> bool:
    """Return True if the user has played or partially played the item."""
    return state.played or state.offset > 0


def _states_match(first: WatchState, second: WatchState) -> bool:
    """Return True if two states are close enough to need no update."""
    if first.played != second.played:
        return False
    if first.played:
        return True
    return abs(first.offset - second.offset) <= _OFFSET_TOLERANCE_MS


def _viewed_sort_key(
    state: WatchState, prefer_earliest: bool
) -> datetime.datetime:
    """Timestamp used to pick a winner; undated states never win."""
    if state.last_viewed is not None:
        return state.last_viewed
    return datetime.datetime.max if prefer_earliest else datetime.datetime.min


def _select_winner(
    first: WatchState, second: WatchState, unwatch: bool
) -> Optional[Tuple[WatchState, WatchState]]:
    """Return (winner, loser), or None when no update is needed."""
    first_data, second_data = _has_watch_data(first), _has_watch_data(second)
    if not (first_data or second_data) or _states_match(first, second):
        return None

    if first_data != second_data:
        # Exactly one side has data. The default sync propagates the watched
        # state outward; --unwatch propagates the unwatched state instead.
        first_wins = first_data == (not unwatch)
        return (first, second) if first_wins else (second, first)

    first_key = _viewed_sort_key(first, unwatch)
    second_key = _viewed_sort_key(second, unwatch)
    first_wins = (
        first_key <= second_key if unwatch else first_key >= second_key
    )
    return (first, second) if first_wins else (second, first)


def _planned_action(winner: WatchState) -> str:
    """Return the action label needed to adopt the winner's state."""
    if winner.played:
        return "markPlayed"
    if winner.offset > 0:
        return "setProgress"
    return "markUnplayed"


def _apply_action(change: PlannedChange) -> None:
    """Perform one planned watch-state change on the target user's item."""
    item = change.loser.item
    if change.action == "markPlayed":
        _call_first_method(item, ("markPlayed", "markWatched"))
        return
    if change.loser.played:
        _call_first_method(item, ("markUnplayed", "markUnwatched"))
    if change.action == "setProgress":
        _call_first_method(item, ("updateProgress",), change.winner.offset)


def _watchable_sections(user_plex: PlexServer, library_id: Optional[int]) -> List[Any]:
    """Return the library sections that carry watch state."""
    sections = resolve_sections(user_plex, library_id)
    return [s for s in sections if s.type in _WATCHABLE_LIBTYPES]


def _collect_watch_states(
    user_plex: PlexServer, library_id: Optional[int], rating_key: Optional[int]
) -> Dict[int, WatchState]:
    """Return ratingKey -> WatchState for one user, honouring the filters."""
    states: Dict[int, WatchState] = {}

    if rating_key is not None:
        item = fetch_item(user_plex, rating_key)
        states[int(item.ratingKey)] = _watch_state(item)
        return states

    for section in _watchable_sections(user_plex, library_id):
        libtype = _WATCHABLE_LIBTYPES[section.type]
        # section.all(libtype=...) hits the plain listing endpoint; the search
        # endpoint needs a non-empty query and would silently return nothing.
        for item in section.all(libtype=libtype):
            states[int(item.ratingKey)] = _watch_state(item)
    return states


def _build_sync_plan(
    states_a: Dict[int, WatchState],
    states_b: Dict[int, WatchState],
    args: argparse.Namespace,
) -> List[PlannedChange]:
    """Compare both users' states and return the changes required."""
    plan: List[PlannedChange] = []
    for rating_key in sorted(set(states_a) & set(states_b)):
        first, second = states_a[rating_key], states_b[rating_key]
        selected = _select_winner(first, second, args.unwatch)
        if selected is None:
            continue
        winner, loser = selected
        if args.one_way and loser is first:
            LOG.debug("--one-way: skipping write to first user for %d", rating_key)
            continue
        plan.append(PlannedChange(
            rating_key=rating_key,
            title=display_title(loser.item),
            action=_planned_action(winner),
            target="a" if loser is first else "b",
            winner=winner,
            loser=loser,
        ))
    return plan


def _plan_rows(
    plan: List[PlannedChange], args: argparse.Namespace
) -> List[Dict[str, Any]]:
    """Build display rows describing the planned changes."""
    labels = {"a": f"user {args.user_a}", "b": f"user {args.user_b}"}
    return [
        {
            "ratingKey": change.rating_key,
            "title": change.title,
            "action": change.action,
            "target": labels[change.target],
        }
        for change in plan
    ]


def cmd_copy_watched(plex: PlexServer, args: argparse.Namespace) -> None:
    """Synchronise watched state and resume points between two users."""
    if args.user_a == args.user_b:
        sys.exit("The two user IDs must differ.")

    states_a = _collect_watch_states(
        server_for_user(plex, args.user_a), args.library_id, args.rating_key
    )
    states_b = _collect_watch_states(
        server_for_user(plex, args.user_b), args.library_id, args.rating_key
    )
    LOG.info(
        "Collected %d item(s) for user %d and %d for user %d",
        len(states_a), args.user_a, len(states_b), args.user_b,
    )

    plan = _build_sync_plan(states_a, states_b, args)
    if not plan:
        LOG.info("Watch state already in sync.")
        if output_format(args) == "table":
            print("Watch state already in sync.", file=sys.stderr)
        else:
            output([], args)
        return

    output(_plan_rows(plan, args), args)

    if args.dry_run:
        LOG.info("--dry-run: no watch state was changed.")
        return

    for change in paced(plan, args, "updates"):
        _apply_action(change)
    LOG.info("Applied %d change(s).", len(plan))


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the copy-watched subparser."""
    uid_help = (
        "user ID (int) or user title (str); use 0 for the admin account. "
        "Obtain both with list-users."
    )
    parser = sub.add_parser(
        "copy-watched", parents=parents,
        help="Synchronise watched state and resume points between two users.",
    )
    parser.add_argument("user_a", metavar="USER", help=f"First {uid_help}")
    parser.add_argument("user_b", metavar="USER", help=f"Second {uid_help}")
    parser.add_argument(
        "-1", "--one-way", dest="one_way", action="store_true", default=False,
        help="Only write to the second user; never modify the first.",
    )
    parser.add_argument(
        "-l", "--library", dest="library_id", default=None, metavar="LIBRARY",
        help="Restrict to one library, by ID or title. Obtain both with list-libraries.",
    )
    parser.add_argument(
        "-t", "--title", dest="rating_key", type=int, default=None, metavar="KEY",
        help="Restrict to a single item ratingKey. Obtain with list-titles or search.",
    )
    parser.add_argument(
        "--unwatch", action="store_true", default=False,
        help=(
            "Invert the sync: if either user has an item unwatched, mark it "
            "unwatched for both; if both have progress, the earliest "
            "lastViewedAt wins instead of the most recent."
        ),
    )


COMMANDS = {"copy-watched": cmd_copy_watched}

REQUIRES_PLEX = frozenset(COMMANDS)
