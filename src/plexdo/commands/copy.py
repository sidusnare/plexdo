# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Playlist copying commands."""

import argparse
import sys
from functools import partial
from typing import Any

from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.accounts import UserAccessError, server_for_user
from plexdo.arguments import add_overwrite_argument
from plexdo.console import clean_text, output, output_format
from plexdo.constants import LOG, MediaItem
from plexdo.fanout import report_line, run_per_user
from plexdo.playlists import copy_playlist_to, resolve_playlist


def _copy_to_one_user(
    plex: PlexServer,
    target: tuple[int, str],
    src_items: list[MediaItem],
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Copy to a single user, converting any failure into a result record."""
    user_id, title = target
    label = f"user {title!r} (id={user_id})"
    try:
        user_plex = server_for_user(plex, user_id)
        status, final_name, detail = copy_playlist_to(
            src_items,
            user_plex,
            args.source_playlist,
            args,
            target_label=label,
            preview=False,
        )
    except UserAccessError as exc:
        status, final_name, detail = "skipped", "", exc.summary
    except Exception as exc:  # pylint: disable=broad-except
        # One user's failure must not end the run over the remaining users.
        LOG.debug("Copy failed for %s: %s", label, exc)
        status, final_name, detail = "failed", "", str(exc)
    return {
        "user": title,
        "id": user_id,
        "status": status,
        "playlist": final_name,
        "detail": detail,
    }


def _copy_to_all(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to all managed users."""
    src_plex = server_for_user(plex, args.source_user_id)
    src: Playlist = resolve_playlist(src_plex, args.source_playlist)
    src_items: list[MediaItem] = list(src.items())
    if not src_items:
        sys.exit(f"Source playlist {src.title!r} is empty - nothing to copy.")

    def copy_to(target: tuple[int, str]) -> dict[str, Any]:
        """One user's outcome, source user included so it reports its skip."""
        if target[0] == args.source_user_id:
            return {
                "user": target[1],
                "id": target[0],
                "status": "skipped",
                "playlist": "",
                "detail": "source user",
            }
        return _copy_to_one_user(plex, target, src_items, args)

    # The shared users, not the roster: this command has always addressed the
    # accounts a playlist is shared with rather than the admin's own.
    targets = [
        (int(user.id), clean_text(user.title or ""))
        for user in plex.myPlexAccount().users()
    ]
    run_per_user(targets, (src.title, src_items), args, copy_to)


def _copy_to_one(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to a specific user."""
    src_plex = server_for_user(plex, args.source_user_id)
    src: Playlist = resolve_playlist(src_plex, args.source_playlist)

    src_items: list[MediaItem] = list(src.items())
    user_plex = server_for_user(plex, args.user_id)
    # A machine-readable format gets the outcome record alone: printing the
    # item list too would make two documents on one stream, which nothing
    # parsing it expects. --all does the same.
    table_mode = output_format(args) == "table"
    status, final_name, detail = copy_playlist_to(
        src_items,
        user_plex,
        args.dest,
        args,
        target_label=f"user id={args.user_id}",
        preview=table_mode,
    )
    record = {
        "user": str(args.user_id),
        "id": args.user_id,
        "status": status,
        "playlist": final_name,
        "detail": detail,
    }
    if table_mode:
        print(report_line(record))
    else:
        output(record, args)


_COPY_USAGE = """%(prog)s -A USER PLAYLIST [-o] [options]
       %(prog)s -T USER PLAYLIST TO_USER DEST [-o] [options]"""

_COPY_DESCRIPTION = """\
Copy a playlist from one user to others. Exactly one of -A and -T says to
whom:

  -A  every user the server is shared with, each getting a playlist of the
      same name; the source user is skipped.
  -T  the one user TO_USER, as the playlist DEST.

A user is a user ID or title, 0 for the admin account (see users-list)."""


def _check_copy(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Name playlist-copy's trailing arguments for its mode, or exit 2."""
    if args.copy_to == "all":
        if args.target:
            parser.error(
                "--all takes USER PLAYLIST alone; every user gets a "
                "playlist of the same name"
            )
        return
    if len(args.target) != 2:
        parser.error(
            "--to takes USER PLAYLIST TO_USER DEST; got "
            f"{2 + len(args.target)} argument(s)"
        )
    args.user_id, args.dest = args.target


def cmd_playlist_copy(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist to every shared user, or to one."""
    if args.copy_to == "all":
        _copy_to_all(plex, args)
    else:
        _copy_to_one(plex, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the playlist copying subparser."""
    parser = sub.add_parser(
        "playlist-copy",
        parents=parents,
        help="Copy a playlist to one user, or to all of them.",
        usage=_COPY_USAGE,
        description=_COPY_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(check_arguments=partial(_check_copy, parser))

    whom = parser.add_argument_group("who to copy to (exactly one)")
    mode = whom.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "-A",
        "--all",
        dest="copy_to",
        action="store_const",
        const="all",
        help="Copy to every user the server is shared with.",
    )
    mode.add_argument(
        "-T",
        "--to",
        dest="copy_to",
        action="store_const",
        const="one",
        help="Copy to TO_USER, as the playlist DEST.",
    )

    parser.add_argument(
        "source_user_id",
        metavar="USER",
        help="The user the playlist belongs to.",
    )
    parser.add_argument(
        "source_playlist",
        metavar="PLAYLIST",
        help=(
            "The playlist to copy: its name (str) or ratingKey (int). "
            "Obtain either with playlists-list."
        ),
    )
    parser.add_argument(
        "target",
        nargs="*",
        metavar="TO_USER DEST",
        help=("With -T: the user to copy to, and the title to give the copy."),
    )
    add_overwrite_argument(
        parser,
        (
            "Overwrite an existing playlist of the same name on the "
            "destination instead of appending ' admin copy'."
        ),
    )


COMMANDS = {"playlist-copy": cmd_playlist_copy}

REQUIRES_PLEX = frozenset(COMMANDS)
