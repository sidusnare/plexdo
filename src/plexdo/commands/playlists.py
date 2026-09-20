# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist inspection and mutation commands."""

from typing import Any, Dict, List, Optional, Sequence, Tuple
import argparse
import sys

from plexapi.exceptions import NotFound
from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.accounts import server_for_user
from plexdo.cache import write_cache
from plexdo.console import output, output_format
from plexdo.constants import LOG, MediaItem
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
    output(rows, args)


def cmd_list_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """List items inside a specific playlist for a user."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    items: List[MediaItem] = list(playlist.items())
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
        write_m3u(items, args.m3u, mapper_for(plex, args))


def cmd_export_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Export an existing playlist to an M3U file."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    items: List[MediaItem] = list(playlist.items())
    if not items:
        sys.exit(f"Playlist '{args.playlist}' is empty - nothing to export.")

    LOG.info("Exporting %d items from '%s' to %s", len(items), args.playlist, args.m3u)
    write_m3u(items, args.m3u, mapper_for(plex, args))
    print(f"Exported {len(items)} items to: {args.m3u}")


def cmd_remove_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Delete a playlist from a user's account."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    LOG.info("Removing playlist '%s' for user_id=%d", args.playlist, args.user_id)
    if args.dry_run:
        LOG.info("--dry-run: skipping playlist deletion.")
        return
    playlist.delete()
    print(f"Deleted playlist: {args.playlist!r}")


def cmd_append_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Append one or more items to an existing playlist."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    rating_keys = [int(k) for k in args.rating_keys]
    new_items: List[MediaItem] = []
    for rk in rating_keys:
        try:
            new_items.append(user_plex.fetchItem(rk))
        except NotFound:
            sys.exit(f"ratingKey not found: {rk}")

    if not new_items:
        sys.exit("No items to append.")

    LOG.info("Appending %d item(s) to '%s'", len(new_items), args.playlist)

    preview_rows = [
        {
            "index": i + 1,
            "ratingKey": int(item.ratingKey),
            "title": display_title(item),
        }
        for i, item in enumerate(new_items)
    ]
    output(preview_rows, args)

    if args.dry_run:
        LOG.info("--dry-run: skipping append.")
        return

    playlist.addItems(new_items)
    LOG.info("Appended %d item(s) to '%s'.", len(new_items), args.playlist)


def _watched_label(item: MediaItem, include_partial: bool) -> Optional[str]:
    """Return why an entry is being dropped, or None if it stays.

    A part-played item is not a watched one - it is the thing the user is in
    the middle of - so it is kept unless --include-partial asks otherwise.
    """
    if item_is_played(item):
        return "played"
    if include_partial and item_view_offset(item) > 0:
        return "partial"
    return None


def _watched_entries(
    items: Sequence[MediaItem], include_partial: bool
) -> List[Tuple[int, MediaItem, str]]:
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
    entries: List[Tuple[int, MediaItem, str]]
) -> List[Dict[str, Any]]:
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
    LOG.info("Nothing watched in '%s'; all %d item(s) kept.", playlist_name, total)
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

    items: List[MediaItem] = list(playlist.items())
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
        len(entries), args.playlist, len(items) - len(entries),
    )


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the playlist inspection and mutation subparsers."""
    p_lpl = sub.add_parser("list-playlists", parents=parents, help="List playlists for a user.")
    p_lpl.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")

    p_lp = sub.add_parser("list-playlist", parents=parents, help="List items in a specific playlist.")
    p_lp.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_lp.add_argument(
        "playlist", type=str,
        help="Playlist name (str) or ratingKey (int). Obtain either with list-playlists.",
    )
    p_lp.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_lp)

    p_ep = sub.add_parser("export-playlist", parents=parents, help="Export an existing playlist to an M3U file.")
    p_ep.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_ep.add_argument("playlist", help="To export. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_ep.add_argument(
        "m3u", metavar="PATH",
        help="Destination M3U file path.",
    )
    add_prefix_argument(p_ep)

    p_rp = sub.add_parser("remove-playlist", parents=parents, help="Delete a playlist from a user's account.")
    p_rp.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_rp.add_argument("playlist", help="To delete. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")

    p_ap = sub.add_parser(
        "append-playlist", parents=parents,
        help="Append one or more items to an existing playlist.",
    )
    p_ap.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_ap.add_argument("playlist", help="To append to. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_ap.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more item ratingKeys to append (int). Obtain with list-titles or list-show.",
    )

    p_cp = sub.add_parser(
        "clean-playlist", parents=parents,
        help="Remove watched items from an existing playlist.",
    )
    p_cp.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_cp.add_argument("playlist", help="To clean. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_cp.add_argument(
        "--include-partial", dest="include_partial", action="store_true",
        default=False,
        help=(
            "Also remove items that are only part-played. By default a "
            "resume point is left alone, since it is what the user is in "
            "the middle of watching."
        ),
    )


COMMANDS = {
    "list-playlists": cmd_list_playlists,
    "list-playlist": cmd_list_playlist,
    "export-playlist": cmd_export_playlist,
    "remove-playlist": cmd_remove_playlist,
    "append-playlist": cmd_append_playlist,
    "clean-playlist": cmd_clean_playlist,
}

REQUIRES_PLEX = frozenset(COMMANDS)
