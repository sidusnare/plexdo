# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist copying commands."""

from typing import Any, Dict, List
import argparse
import sys

from plexapi.myplex import MyPlexUser
from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.accounts import UserAccessError, server_for_user
from plexdo.console import clean_text, output, output_format, print_table
from plexdo.constants import LOG, MediaItem
from plexdo.playlists import copy_playlist_to, preview_rows, resolve_playlist
from plexdo.throttle import paced


def _copy_to_one_user(
    plex: PlexServer,
    user: MyPlexUser,
    src_items: List[MediaItem],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """Copy to a single user, converting any failure into a result record."""
    user_id = int(user.id)
    label = f"user {user.title!r} (id={user_id})"
    try:
        user_plex = server_for_user(plex, user_id)
        status, final_name, detail = copy_playlist_to(
            src_items, user_plex, args.source_playlist, args,
            target_label=label, preview=False,
        )
    except UserAccessError as exc:
        status, final_name, detail = "skipped", "", exc.summary
    except Exception as exc:  # pylint: disable=broad-except
        # One user's failure must not end the run over the remaining users.
        LOG.debug("Copy failed for %s: %s", label, exc)
        status, final_name, detail = "failed", "", str(exc)
    return {
        "user": clean_text(user.title or ""),
        "id": user_id,
        "status": status,
        "playlist": final_name,
        "detail": detail,
    }


def _report_line(record: Dict[str, Any]) -> str:
    """Format one per-user outcome as a single line."""
    line = f"  {record['status']:<8} {record['user']}"
    extra = record["detail"] or (
        record["playlist"] if record["playlist"] else ""
    )
    return f"{line}  ({extra})" if extra else line


def cmd_copy_playlist_all_users(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to all managed users."""
    src_plex = server_for_user(plex, args.source_user_id)
    src: Playlist = resolve_playlist(src_plex, args.source_playlist)
    src_items: List[MediaItem] = list(src.items())
    if not src_items:
        sys.exit(f"Source playlist {src.title!r} is empty - nothing to copy.")

    # The item list is identical for every user, so it is shown once here and
    # suppressed per user; each user then costs a single line of output.
    table_mode = output_format(args) == "table"
    if table_mode:
        print(f"{src.title} ({len(src_items)} items)")
        print_table(preview_rows(src_items))
        print()

    results: List[Dict[str, Any]] = []
    for user in paced(list(plex.myPlexAccount().users()), args, "users"):
        user_id = int(user.id)
        if user_id == args.source_user_id:
            record = {
                "user": clean_text(user.title or ""), "id": user_id,
                "status": "skipped", "playlist": "", "detail": "source user",
            }
        else:
            record = _copy_to_one_user(plex, user, src_items, args)
        results.append(record)
        if table_mode:
            # Printed as each user completes, so a long run shows progress.
            print(_report_line(record))

    if not table_mode:
        output(results, args)


def cmd_copy_playlist_to_user(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to a specific user."""
    src_plex = server_for_user(plex, args.source_user_id)
    src: Playlist = resolve_playlist(src_plex, args.source_playlist)

    src_items: List[MediaItem] = list(src.items())
    user_plex = server_for_user(plex, args.user_id)
    status, final_name, detail = copy_playlist_to(
        src_items, user_plex, args.dest, args,
        target_label=f"user id={args.user_id}",
    )
    record = {
        "user": str(args.user_id), "id": args.user_id,
        "status": status, "playlist": final_name, "detail": detail,
    }
    if output_format(args) == "table":
        print(_report_line(record))
    else:
        output(record, args)


_SRC_UID_HELP = (
    "Source user ID (int) or user title (str); use 0 for the admin "
    "account. Obtain both with list-users."
)
_OVERWRITE_HELP = (
    "Overwrite an existing playlist of the same name on the destination "
    "instead of appending ' admin copy'."
)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the playlist copying subparsers."""
    playlist_help = (
        "Playlist name (str) or ratingKey (int). Obtain either with "
        "list-playlists."
    )
    uid_help = (
        "User ID (int) or user title (str); use 0 for the admin account. "
        "Obtain both with list-users."
    )

    p_all = sub.add_parser(
        "copy-playlist-all-users", parents=parents,
        help="Copy a playlist from any user to all managed users.",
    )
    p_all.add_argument("source_user_id", metavar="USER", help=_SRC_UID_HELP)
    p_all.add_argument("source_playlist", help="Source. " + playlist_help)
    p_all.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help=_OVERWRITE_HELP,
    )

    p_one = sub.add_parser(
        "copy-playlist-to-user", parents=parents,
        help="Copy a playlist from any user to a specific user.",
    )
    p_one.add_argument("source_user_id", metavar="USER", help=_SRC_UID_HELP)
    p_one.add_argument("source_playlist", help="Source. " + playlist_help)
    p_one.add_argument("user_id", metavar="USER", help="Target " + uid_help)
    p_one.add_argument("dest", help="Destination playlist title (str).")
    p_one.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help=_OVERWRITE_HELP,
    )


COMMANDS = {
    "copy-playlist-all-users": cmd_copy_playlist_all_users,
    "copy-playlist-to-user": cmd_copy_playlist_to_user,
}

REQUIRES_PLEX = frozenset(COMMANDS)
