# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Playlist inspection and mutation commands."""

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.accounts import server_for_user
from plexdo.arguments import add_m3u_argument, add_user_argument
from plexdo.cache import write_cache, write_word_caches
from plexdo.console import clean_text, output, output_format
from plexdo.constants import LOG, MediaItem
from plexdo.identify import argument_words
from plexdo.m3u import write_m3u
from plexdo.paths import add_prefix_argument, mapper_for
from plexdo.playlists import resolve_playlist
from plexdo.throttle import paced
from plexdo.titles import display_title, item_is_played, item_view_offset


def cmd_list_playlists(plex: PlexServer, args: argparse.Namespace) -> None:
    """List playlists for a given user."""
    user_plex = server_for_user(plex, args.user_id)
    rows = [
        {
            "ratingKey": int(pl.ratingKey),
            "title": pl.title,
            "items": pl.leafCount,
        }
        for pl in user_plex.playlists()
    ]
    write_cache(f"playlists.{args.user_id}", rows)
    write_word_caches("playlists", argument_words(args, "user_id"), rows)
    output(rows, args)


def _export_m3u(
    plex: PlexServer,
    items: list[MediaItem],
    path: str,
    args: argparse.Namespace,
) -> None:
    """Write a playlist's items to an M3U file, for whichever command asked.

    playlist-list --m3u and playlist-export are two ways to the same file,
    so both come here and neither can write it differently.
    """
    LOG.info("Exporting %d item(s) to %s", len(items), path)
    write_m3u(items, path, mapper_for(plex, args))


def cmd_list_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """List items inside a specific playlist for a user."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    items: list[MediaItem] = list(playlist.items())
    rows = [
        {
            "index": i + 1,
            "ratingKey": int(item.ratingKey),
            "title": display_title(item),
        }
        for i, item in enumerate(items)
    ]
    output(rows, args)

    if args.m3u:
        _export_m3u(plex, items, args.m3u, args)


def cmd_export_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Export an existing playlist to an M3U file."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    items: list[MediaItem] = list(playlist.items())
    if not items:
        sys.exit(f"Playlist '{args.playlist}' is empty - nothing to export.")

    _export_m3u(plex, items, args.m3u, args)
    print(f"Exported {len(items)} items to: {args.m3u}")


def cmd_remove_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Delete a playlist from a user's account."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)
    title = clean_text(getattr(playlist, "title", "") or args.playlist)

    LOG.info("Removing playlist '%s' for user_id=%d", title, args.user_id)
    if args.dry_run:
        # Said outright rather than left to --verbose: a rehearsal that
        # prints nothing cannot be told from one that found nothing to do.
        print(
            f"--dry-run: would delete playlist {title!r} "
            f"(ratingKey {int(playlist.ratingKey)}).",
            file=sys.stderr,
        )
        return
    playlist.delete()
    print(f"Deleted playlist: {title!r}")


def _watched_label(item: MediaItem, include_partial: bool) -> str | None:
    """Return why an entry is being dropped, or None if it stays.

    A part-played item is not a watched one - it is the thing the user is in
    the middle of - so it is kept unless --include-partial asks otherwise.
    That holds for an item played before and part way through again: the
    resume point decides, not the view count.
    """
    if item_view_offset(item) > 0:
        return "partial" if include_partial else None
    return "played" if item_is_played(item) else None


def _watched_entries(
    items: Sequence[MediaItem], include_partial: bool
) -> list[tuple[int, MediaItem, str]]:
    """Return (position, item, label) for every entry to be removed.

    The position is the entry's own place in the playlist as it stands, not
    a number within the removal list, so the preview lines up with what Plex
    shows rather than renumbering around the gaps.
    """
    return [
        (position, item, label)
        for position, item in enumerate(items, start=1)
        if (label := _watched_label(item, include_partial)) is not None
    ]


def _removal_rows(
    entries: list[tuple[int, MediaItem, str]],
) -> list[dict[str, Any]]:
    """Build the preview of the entries a clean run will remove."""
    return [
        {
            "index": position,
            "ratingKey": int(item.ratingKey),
            "title": display_title(item),
            "state": label,
        }
        for position, item, label in entries
    ]


def _report_nothing_watched(
    playlist_name: str, total: int, args: argparse.Namespace
) -> None:
    """Report a playlist that needs no cleaning, in the caller's format."""
    LOG.info(
        "Nothing watched in '%s'; all %d item(s) kept.", playlist_name, total
    )
    if output_format(args) == "table":
        print(f"Nothing watched in {playlist_name!r}.", file=sys.stderr)
    else:
        output([], args)


def cmd_clean_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Remove watched items from a playlist, leaving the rest in order."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)
    if getattr(playlist, "smart", False):
        # Plex answers a delete on a smart playlist's item with a 400: its
        # contents come from a filter, so there is nothing to remove.
        sys.exit(
            f"Playlist {args.playlist!r} is smart - its contents come from a "
            "filter, so entries cannot be removed individually. Nothing has "
            "been changed."
        )

    items: list[MediaItem] = list(playlist.items())
    entries = _watched_entries(items, args.include_partial)
    if not entries:
        _report_nothing_watched(args.playlist, len(items), args)
        return

    if len(entries) == len(items):
        LOG.warning(
            "Every item in '%s' is watched, so the playlist will be left "
            "empty; Plex removes a playlist once its last item is gone.",
            args.playlist,
        )

    output(_removal_rows(entries), args)

    if args.dry_run:
        LOG.info("--dry-run: skipping removal.")
        return

    # One DELETE per entry, so a long playlist is paced like any other
    # per-item loop. The playlist item IDs come from the listing plexapi
    # already holds, so the repeated calls cost nothing extra.
    for _, item, _ in paced(entries, args, "removals"):
        playlist.removeItems([item])
    LOG.info(
        "Removed %d watched item(s) from '%s'; %d remain.",
        len(entries),
        args.playlist,
        len(items) - len(entries),
    )


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the playlist inspection and mutation subparsers."""
    p_lpl = sub.add_parser(
        "playlists-list", parents=parents, help="List a user's playlists."
    )
    add_user_argument(p_lpl)

    p_lp = sub.add_parser(
        "playlist-list",
        parents=parents,
        help="List the items in a playlist.",
    )
    add_user_argument(p_lp)
    p_lp.add_argument(
        "playlist",
        metavar="PLAYLIST",
        type=str,
        help=(
            "Playlist name (str) or ratingKey (int). Obtain either with "
            "playlists-list."
        ),
    )
    add_m3u_argument(p_lp)
    add_prefix_argument(p_lp)

    p_ep = sub.add_parser(
        "playlist-export",
        parents=parents,
        help="Export a playlist to an M3U file.",
    )
    add_user_argument(p_ep)
    p_ep.add_argument(
        "playlist",
        metavar="PLAYLIST",
        help="To export. "
        + "Playlist name (str) or ratingKey (int). Obtain either with "
        "playlists-list.",
    )
    p_ep.add_argument(
        "m3u",
        metavar="PATH",
        help="Destination M3U file path.",
    )
    add_prefix_argument(p_ep)

    p_rp = sub.add_parser(
        "playlist-remove",
        parents=parents,
        help="Delete a playlist.",
    )
    add_user_argument(p_rp)
    p_rp.add_argument(
        "playlist",
        metavar="PLAYLIST",
        help="To delete. "
        + "Playlist name (str) or ratingKey (int). Obtain either with "
        "playlists-list.",
    )

    p_cp = sub.add_parser(
        "playlist-clean",
        parents=parents,
        help="Remove the watched items from a playlist.",
    )
    add_user_argument(p_cp)
    p_cp.add_argument(
        "playlist",
        metavar="PLAYLIST",
        help="To clean. "
        + "Playlist name (str) or ratingKey (int). Obtain either with "
        "playlists-list.",
    )
    p_cp.add_argument(
        "--include-partial",
        dest="include_partial",
        action="store_true",
        default=False,
        help=(
            "Also remove items that are only part-played. By default a "
            "resume point is left alone, since it is what the user is in "
            "the middle of watching."
        ),
    )


COMMANDS = {
    "playlists-list": cmd_list_playlists,
    "playlist-list": cmd_list_playlist,
    "playlist-export": cmd_export_playlist,
    "playlist-remove": cmd_remove_playlist,
    "playlist-clean": cmd_clean_playlist,
}

REQUIRES_PLEX = frozenset(COMMANDS)
