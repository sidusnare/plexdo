# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist building commands."""

from typing import Iterator, List, Optional, Sequence, Set, Tuple
import argparse
import datetime
import sys

from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show

from plexdo.accounts import server_for_user
from plexdo.airdates import episodes_in_same_season, prompt_for_date, resolve_episode_date
from plexdo.constants import LOG, MediaItem
from plexdo.fanout import add_user_target_arguments, deliver_playlist
from plexdo.convert import parse_date
from plexdo.m3u import write_m3u
from plexdo.paths import add_prefix_argument, mapper_for
from plexdo.playlists import resolve_playlist
from plexdo.throttle import paced
from plexdo.titles import fetch_show, non_special_episodes, shuffle_list


def _round_robin(episode_lists: List[List[Episode]]) -> Iterator[Episode]:
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
    episode_lists: List[List[Episode]] = []

    for rk in rating_keys:
        show = fetch_show(plex, rk)
        eps = non_special_episodes(show)
        LOG.info("Show '%s': %d episodes", show.title, len(eps))
        episode_lists.append(eps)

    items: List[MediaItem] = list(_round_robin(episode_lists))
    deliver_playlist(plex, plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(plex, args))


def _chronological_sort_key(
    item_date: Tuple[MediaItem, datetime.datetime]
) -> datetime.datetime:
    return item_date[1]


def _build_chronological_items(
    plex: PlexServer,
    rating_keys: List[int],
) -> List[Tuple[MediaItem, datetime.datetime]]:
    """Build (item, resolved_datetime) pairs for all given shows/movies."""
    dated_items: List[Tuple[MediaItem, datetime.datetime]] = []
    last_used_date: Optional[datetime.datetime] = None

    for rk in rating_keys:
        media_item = plex.fetchItem(rk)
        LOG.debug("Processing ratingKey=%d type=%s", rk, type(media_item).__name__)

        if isinstance(media_item, Show):
            all_eps = non_special_episodes(media_item)
            for ep in all_eps:
                season_peers = episodes_in_same_season(ep, all_eps)
                resolved = resolve_episode_date(ep, season_peers, last_used_date)
                last_used_date = resolved
                dated_items.append((ep, resolved))

        elif isinstance(media_item, Movie):
            dt = parse_date(media_item.originallyAvailableAt)
            if dt is None:
                dt = prompt_for_date(media_item, last_used_date)  # type: ignore[arg-type]
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
    items: List[MediaItem] = [item for item, _ in dated_items]

    deliver_playlist(plex, plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(plex, args))


def cmd_build_randomize(plex: PlexServer, args: argparse.Namespace) -> None:
    """Randomize a playlist and save to a new destination playlist."""
    user_plex = server_for_user(plex, args.user_id)
    src: Playlist = resolve_playlist(user_plex, args.source)

    all_items: List[MediaItem] = list(src.items())
    randomized: List[MediaItem] = shuffle_list(all_items)

    LOG.info("Randomized %d items", len(randomized))
    deliver_playlist(plex, user_plex, args.dest, randomized, args)

    if args.m3u:
        write_m3u(randomized, args.m3u, mapper_for(user_plex, args))


def _collect_sources(
    user_plex: PlexServer,
    names: Sequence[str],
    args: argparse.Namespace,
) -> List[Tuple[str, List[MediaItem]]]:
    """Resolve each named playlist and read its items, in the order given.

    One listing request per playlist, so the walk is paced like any other
    per-element loop. An empty source is reported rather than passed over in
    silence: a typo that resolved to the wrong playlist looks exactly like a
    playlist that happens to be empty.
    """
    sources: List[Tuple[str, List[MediaItem]]] = []
    for name in paced(names, args, "playlists"):
        part: List[MediaItem] = list(resolve_playlist(user_plex, name).items())
        if part:
            LOG.info("Playlist '%s': %d item(s)", name, len(part))
        else:
            LOG.warning("Playlist '%s' is empty; it contributes nothing.", name)
        sources.append((name, part))
    return sources


def _concatenate(
    sources: Sequence[Tuple[str, List[MediaItem]]], unique: bool
) -> List[MediaItem]:
    """Join the sources end to end, preserving the order within each.

    With *unique*, an item already added is skipped rather than repeated; a
    ratingKey identifies the item, so the same episode reached through two
    playlists becomes one entry. Without it the result is a faithful
    concatenation, duplicates and all, which is what Plex itself allows.
    """
    items: List[MediaItem] = []
    seen: Set[int] = set()
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
    LOG.info("Concatenated %d playlist(s) into %d item(s)", len(sources), len(items))

    deliver_playlist(plex, user_plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(user_plex, args))


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the playlist building subparsers."""
    p_bi = sub.add_parser(
        "build-interleaved", parents=parents,
        help="Round-robin interleaved playlist from multiple shows.",
    )
    p_bi.add_argument("name", help="Name for the new playlist (str).")
    p_bi.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more Show ratingKeys (int). Obtain with list-titles.",
    )
    p_bi.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help="Replace an existing playlist of the same name instead of failing.",
    )
    p_bi.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_bi)
    add_user_target_arguments(p_bi)

    p_bc = sub.add_parser(
        "build-chronological", parents=parents,
        help="Date-sorted playlist from shows and/or movies.",
    )
    p_bc.add_argument("name", help="Name for the new playlist (str).")
    p_bc.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more Show/Movie ratingKeys (int). Obtain with list-titles.",
    )
    p_bc.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help="Replace an existing playlist of the same name instead of failing.",
    )
    p_bc.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_bc)
    add_user_target_arguments(p_bc)

    p_br = sub.add_parser(
        "build-randomize", parents=parents,
        help="Randomize a source playlist into a new destination playlist.",
    )
    p_br.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_br.add_argument("source", help="Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_br.add_argument("dest", help="Destination playlist title (str).")
    p_br.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help="Replace an existing playlist of the same name instead of failing.",
    )
    p_br.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_br)
    add_user_target_arguments(p_br)

    p_bn = sub.add_parser(
        "build-concatenated", parents=parents,
        help="Join several playlists end to end into one new playlist.",
    )
    p_bn.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_bn.add_argument("name", help="Name for the new playlist (str).")
    p_bn.add_argument(
        "playlists", nargs="+", metavar="PLAYLIST",
        help=(
            "The playlists to join, in the order they should appear. "
            "Playlist name (str) or ratingKey (int). Obtain either with "
            "list-playlists."
        ),
    )
    p_bn.add_argument(
        "--unique", action="store_true", default=False,
        help=(
            "Skip an item an earlier playlist already contributed, so a "
            "title appearing in two of them is listed once."
        ),
    )
    p_bn.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help="Replace an existing playlist of the same name instead of failing.",
    )
    p_bn.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_bn)
    add_user_target_arguments(p_bn)


COMMANDS = {
    "build-interleaved": cmd_build_interleaved,
    "build-chronological": cmd_build_chronological,
    "build-randomize": cmd_build_randomize,
    "build-concatenated": cmd_build_concatenated,
}

REQUIRES_PLEX = frozenset(COMMANDS)
