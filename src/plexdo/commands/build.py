# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Playlist building commands."""

import argparse
import datetime
import re
import sys
from collections.abc import Iterator, Sequence
from typing import NamedTuple

from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show

from plexdo.accounts import server_for_user
from plexdo.airdates import (
    episodes_in_same_season,
    prompt_for_date,
    resolve_episode_date,
)
from plexdo.arguments import (
    add_m3u_argument,
    add_overwrite_argument,
    add_rating_keys_argument,
    add_user_argument,
)
from plexdo.constants import LOG, MediaItem
from plexdo.convert import parse_date
from plexdo.fanout import add_user_target_arguments, deliver_playlist
from plexdo.m3u import write_m3u
from plexdo.paths import add_prefix_argument, mapper_for
from plexdo.playlists import resolve_playlist
from plexdo.throttle import paced
from plexdo.titles import (
    fetch_item,
    fetch_show,
    non_special_episodes,
    shuffle_list,
)


def _round_robin(episode_lists: list[list[Episode]]) -> Iterator[Episode]:
    """Yield episodes in round-robin order across multiple lists."""
    queues = [list(eps) for eps in episode_lists if eps]
    while queues:
        exhausted = []
        for queue in queues:
            if queue:
                yield queue.pop(0)
            if not queue:
                exhausted.append(queue)
        for q in exhausted:
            queues.remove(q)


def cmd_build_interleaved(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build a round-robin interleaved playlist from multiple shows."""
    rating_keys = [int(k) for k in args.rating_keys]
    episode_lists: list[list[Episode]] = []

    for rk in rating_keys:
        show = fetch_show(plex, rk)
        eps = non_special_episodes(show)
        LOG.info("Show '%s': %d episodes", show.title, len(eps))
        episode_lists.append(eps)

    items: list[MediaItem] = list(_round_robin(episode_lists))
    deliver_playlist(plex, plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(plex, args))


def _chronological_sort_key(
    item_date: tuple[MediaItem, datetime.datetime],
) -> datetime.datetime:
    return item_date[1]


def _build_chronological_items(
    plex: PlexServer,
    rating_keys: list[int],
) -> list[tuple[MediaItem, datetime.datetime]]:
    """Build (item, resolved_datetime) pairs for all given shows/movies."""
    dated_items: list[tuple[MediaItem, datetime.datetime]] = []
    last_used_date: datetime.datetime | None = None

    for rk in rating_keys:
        media_item = fetch_item(plex, rk)
        LOG.debug(
            "Processing ratingKey=%d type=%s", rk, type(media_item).__name__
        )

        if isinstance(media_item, Show):
            all_eps = non_special_episodes(media_item)
            for ep in all_eps:
                season_peers = episodes_in_same_season(ep, all_eps)
                resolved = resolve_episode_date(
                    ep, season_peers, last_used_date
                )
                last_used_date = resolved
                dated_items.append((ep, resolved))

        elif isinstance(media_item, Movie):
            dt = parse_date(media_item.originallyAvailableAt)
            if dt is None:
                dt = prompt_for_date(media_item, last_used_date)
            last_used_date = dt
            dated_items.append((media_item, dt))

        else:
            sys.exit(
                f"ratingKey {rk} is type '{type(media_item).__name__}' "
                "- only Show and Movie are supported."
            )

    return dated_items


def cmd_build_chronological(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build a date-sorted playlist from shows and/or movies."""
    rating_keys = [int(k) for k in args.rating_keys]
    dated_items = _build_chronological_items(plex, rating_keys)

    dated_items.sort(key=_chronological_sort_key)
    items: list[MediaItem] = [item for item, _ in dated_items]

    deliver_playlist(plex, plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(plex, args))


def cmd_build_randomize(plex: PlexServer, args: argparse.Namespace) -> None:
    """Randomize a playlist and save to a new destination playlist."""
    user_plex = server_for_user(plex, args.user_id)
    src: Playlist = resolve_playlist(user_plex, args.source)

    all_items: list[MediaItem] = list(src.items())
    randomized: list[MediaItem] = shuffle_list(all_items)

    LOG.info("Randomized %d items", len(randomized))
    deliver_playlist(plex, user_plex, args.dest, randomized, args)

    if args.m3u:
        write_m3u(randomized, args.m3u, mapper_for(user_plex, args))


def _collect_sources(
    user_plex: PlexServer,
    names: Sequence[str],
    args: argparse.Namespace,
) -> list[tuple[str, list[MediaItem]]]:
    """Resolve each named playlist and read its items, in the order given.

    One listing request per playlist, so the walk is paced like any other
    per-element loop. An empty source is reported rather than passed over in
    silence: a typo that resolved to the wrong playlist looks exactly like a
    playlist that happens to be empty.
    """
    sources: list[tuple[str, list[MediaItem]]] = []
    for name in paced(names, args, "playlists"):
        part: list[MediaItem] = list(resolve_playlist(user_plex, name).items())
        if part:
            LOG.info("Playlist '%s': %d item(s)", name, len(part))
        else:
            LOG.warning("Playlist '%s' is empty; it contributes nothing.", name)
        sources.append((name, part))
    return sources


def _concatenate(
    sources: Sequence[tuple[str, list[MediaItem]]], unique: bool
) -> list[MediaItem]:
    """Join the sources end to end, preserving the order within each.

    With *unique*, an item already added is skipped rather than repeated; a
    ratingKey identifies the item, so the same episode reached through two
    playlists becomes one entry. Without it the result is a faithful
    concatenation, duplicates and all, which is what Plex itself allows.
    """
    items: list[MediaItem] = []
    seen: set[int] = set()
    for _, part in sources:
        for item in part:
            key = int(item.ratingKey)
            if unique and key in seen:
                continue
            seen.add(key)
            items.append(item)
    return items


def cmd_build_concatenated(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build one playlist from several others, joined end to end."""
    user_plex = server_for_user(plex, args.user_id)

    # Every source is read before anything is written, so naming a source as
    # the destination and passing --overwrite still works: the items are
    # already in memory by the time the old playlist is removed.
    sources = _collect_sources(user_plex, args.playlists, args)
    items = _concatenate(sources, args.unique)

    total = sum(len(part) for _, part in sources)
    if args.unique and len(items) < total:
        LOG.info("--unique: skipped %d repeated item(s).", total - len(items))
    LOG.info(
        "Concatenated %d playlist(s) into %d item(s)", len(sources), len(items)
    )

    deliver_playlist(plex, user_plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(user_plex, args))


def _parse_ratio(text: str) -> tuple[int, int]:
    """The two counts of a ratio such as "2:1", for argparse."""
    match = re.fullmatch(r"\s*(\d+)\s*:\s*(\d+)\s*", text, re.ASCII)
    if match:
        first, second = int(match.group(1)), int(match.group(2))
        if first and second:
            return first, second
    raise argparse.ArgumentTypeError(
        f"expected two whole numbers above 0, such as 2:1, not {text!r}"
    )


class Merged(NamedTuple):
    """What _merge made, and what --verbose says about it.

    *ran_out* is 0 or 1 for the playlist that ran out first, or None when
    both ran out on the same turn. *unmixed* counts the items of the other
    that follow on their own; *left_out*, those --stop-short never reached,
    repeats among them; *skipped*, the repeats --unique passed over.
    """

    items: list[MediaItem]
    ran_out: int | None
    unmixed: int
    left_out: int
    skipped: int


def _take_run(
    source: Sequence[MediaItem],
    start: int,
    count: int,
    seen: set[int] | None,
) -> tuple[list[MediaItem], int]:
    """Up to *count* items of *source* from *start*, and where to go on.

    With *seen*, an item whose ratingKey is in it is passed over rather than
    taken, so a repeat does not use up a place in the run, and each item
    taken is added to it.
    """
    run: list[MediaItem] = []
    while len(run) < count and start < len(source):
        item = source[start]
        start += 1
        if seen is not None:
            key = int(item.ratingKey)
            if key in seen:
                continue
            seen.add(key)
        run.append(item)
    return run, start


def _merge(
    first: Sequence[MediaItem],
    second: Sequence[MediaItem],
    ratio: tuple[int, int],
    *,
    stop_short: bool = False,
    unique: bool = False,
) -> Merged:
    """Alternate runs of the two playlists at the given ratio.

    A ratio of 2:1 takes two items from *first*, then one from *second*,
    and so on, each keeping its own order. A playlist has run out on the
    first turn it has nothing to give. From that turn on, the rest of the
    other follows on its own, or with *stop_short* is left out, so the
    result ends with the last turn both took part in.

    Repeats are kept, as Plex allows. With *unique* an item already taken
    is passed over, as in build-concatenated, and the next one takes its
    place, so the ratio still holds.
    """
    sources = (first, second)
    starts = [0, 0]
    seen: set[int] | None = set() if unique else None
    items: list[MediaItem] = []
    ran_out: int | None = None
    tail_start = 0
    while starts[0] < len(first) or starts[1] < len(second):
        before = list(starts)
        runs = []
        for side in (0, 1):
            run, starts[side] = _take_run(
                sources[side], starts[side], ratio[side], seen
            )
            runs.append(run)
        if ran_out is None and bool(runs[0]) != bool(runs[1]):
            ran_out = 0 if not runs[0] else 1
            tail_start = len(items)
            if stop_short:
                starts = before
                break
        items.extend(runs[0] + runs[1])
    return Merged(
        items=items,
        ran_out=ran_out,
        unmixed=0 if stop_short or ran_out is None else len(items) - tail_start,
        left_out=sum(len(s) - n for s, n in zip(sources, starts, strict=True)),
        skipped=sum(starts) - len(items),
    )


def cmd_build_merge(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build one playlist from two others, mixed at a ratio."""
    user_plex = server_for_user(plex, args.user_id)

    # Both sources are read before anything is written, so either may be the
    # destination under --overwrite, as with build-concatenated.
    sources = _collect_sources(user_plex, [args.first, args.second], args)
    first, second = sources[0][1], sources[1][1]
    merged = _merge(
        first,
        second,
        args.ratio,
        stop_short=args.stop_short,
        unique=args.unique,
    )
    items = merged.items

    names = (args.first, args.second)
    if merged.ran_out is not None:
        other = names[1 - merged.ran_out]
        if args.stop_short:
            LOG.info(
                "'%s' runs out first; --stop-short left out the last %d "
                "item(s) of '%s'.",
                names[merged.ran_out],
                merged.left_out,
                other,
            )
        else:
            LOG.info(
                "'%s' runs out first; the last %d item(s) of '%s' follow "
                "unmixed.",
                names[merged.ran_out],
                merged.unmixed,
                other,
            )
    if merged.skipped:
        LOG.info("--unique: skipped %d repeated item(s).", merged.skipped)
    LOG.info(
        "Merged %d and %d item(s) at %d:%d into %d item(s)",
        len(first),
        len(second),
        *args.ratio,
        len(items),
    )

    deliver_playlist(plex, user_plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(user_plex, args))


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the playlist building subparsers."""
    p_bi = sub.add_parser(
        "build-interleaved",
        parents=parents,
        help="Round-robin interleaved playlist from multiple shows.",
    )
    p_bi.add_argument("name", help="Name for the new playlist (str).")
    add_rating_keys_argument(
        p_bi,
        "One or more Show ratingKeys (int). Obtain with list-titles.",
    )
    add_overwrite_argument(p_bi)
    add_m3u_argument(p_bi)
    add_prefix_argument(p_bi)
    add_user_target_arguments(p_bi)

    p_bc = sub.add_parser(
        "build-chronological",
        parents=parents,
        help="Date-sorted playlist from shows and/or movies.",
    )
    p_bc.add_argument("name", help="Name for the new playlist (str).")
    add_rating_keys_argument(
        p_bc,
        ("One or more Show/Movie ratingKeys (int). Obtain with list-titles."),
    )
    add_overwrite_argument(p_bc)
    add_m3u_argument(p_bc)
    add_prefix_argument(p_bc)
    add_user_target_arguments(p_bc)

    p_br = sub.add_parser(
        "build-randomize",
        parents=parents,
        help="Randomize a source playlist into a new destination playlist.",
    )
    add_user_argument(p_br)
    p_br.add_argument(
        "source",
        help=(
            "Playlist name (str) or ratingKey (int). Obtain either with "
            "list-playlists."
        ),
    )
    p_br.add_argument("dest", help="Destination playlist title (str).")
    add_overwrite_argument(p_br)
    add_m3u_argument(p_br)
    add_prefix_argument(p_br)
    add_user_target_arguments(p_br)

    p_bn = sub.add_parser(
        "build-concatenated",
        parents=parents,
        help="Join several playlists end to end into one new playlist.",
    )
    add_user_argument(p_bn)
    p_bn.add_argument("name", help="Name for the new playlist (str).")
    p_bn.add_argument(
        "playlists",
        nargs="+",
        metavar="PLAYLIST",
        help=(
            "The playlists to join, in the order they should appear. "
            "Playlist name (str) or ratingKey (int). Obtain either with "
            "list-playlists."
        ),
    )
    p_bn.add_argument(
        "-U",
        "--unique",
        action="store_true",
        default=False,
        help=(
            "Skip an item an earlier playlist already contributed, so a "
            "title appearing in two of them is listed once."
        ),
    )
    add_overwrite_argument(p_bn)
    add_m3u_argument(p_bn)
    add_prefix_argument(p_bn)
    add_user_target_arguments(p_bn)

    p_bm = sub.add_parser(
        "build-merge",
        parents=parents,
        help="Mix two playlists into one new playlist at a ratio.",
    )
    add_user_argument(p_bm)
    p_bm.add_argument("name", help="Name for the new playlist (str).")
    for which in ("first", "second"):
        p_bm.add_argument(
            which,
            metavar=which.upper(),
            help=(
                f"The {which} playlist to mix. Playlist name (str) or "
                "ratingKey (int). Obtain either with list-playlists."
            ),
        )
    p_bm.add_argument(
        "--ratio",
        type=_parse_ratio,
        default="1:1",
        metavar="A:B",
        help=(
            "Take A items from FIRST, then B from SECOND, in turn (default "
            "1:1). Once one runs out, the rest of the other follows, unless "
            "--stop-short is given."
        ),
    )
    p_bm.add_argument(
        "-s",
        "--stop-short",
        action="store_true",
        default=False,
        help=(
            "Stop when either playlist runs out, leaving out the rest of "
            "the other, so the whole result keeps the ratio."
        ),
    )
    p_bm.add_argument(
        "-U",
        "--unique",
        action="store_true",
        default=False,
        help=(
            "Skip an item already taken, so a title in both playlists is "
            "listed once; the next item takes its place in the ratio."
        ),
    )
    add_overwrite_argument(p_bm)
    add_m3u_argument(p_bm)
    add_prefix_argument(p_bm)
    add_user_target_arguments(p_bm)


COMMANDS = {
    "build-interleaved": cmd_build_interleaved,
    "build-chronological": cmd_build_chronological,
    "build-randomize": cmd_build_randomize,
    "build-concatenated": cmd_build_concatenated,
    "build-merge": cmd_build_merge,
}

REQUIRES_PLEX = frozenset(COMMANDS)
