# SPDX-License-Identifier: GPL-3.0-or-later

"""Creating one playlist for one user, a chosen user, or every user.

Every build command ends the same way: an item list exists, and it has to
become a playlist somewhere. Without -u or -a that is the account the items
came from, which is what the commands have always done. With them the same
list is created for a named user or for every user on the server.

A run across many users must survive a bad one. Plex scopes a token to what
its user can see, so a user with nothing shared is simply unreachable, and a
name already taken on one account says nothing about the others. Both are
reported as a line in the run and the loop carries on; nothing here raises
past the user it happened to.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import argparse

from plexapi.server import PlexServer

from plexdo.accounts import UserAccessError, server_for_user, user_roster
from plexdo.console import output, output_format, print_table, table_limit
from plexdo.constants import LOG, MediaItem
from plexdo.playlists import (create_for_user, finalize_playlist,
                              preview_rows, require_items)
from plexdo.throttle import paced


def add_user_target_arguments(parser: argparse.ArgumentParser) -> None:
    """Add -u/--user and -a/--all-users to a playlist building command.

    Registered from here rather than written out on each parser: four
    commands carry the identical pair, and repeating the help text inline is
    what trips pylint's duplicate-code.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-u", "--user", dest="dest_user_id", default=None, metavar="USER",
        help=(
            "Create the playlist for this user rather than for the account "
            "the items came from. User ID (int) or user title (str); use 0 "
            "for the admin account. Obtain both with list-users."
        ),
    )
    group.add_argument(
        "-a", "--all-users", dest="all_users", action="store_true",
        default=False,
        help=(
            "Create the playlist for every user on the server, the admin "
            "account included. The item list is shown once and each user "
            "then reports one line; a user that cannot be served is "
            "reported and the run carries on."
        ),
    )


def report_line(record: Dict[str, Any]) -> str:
    """Format one per-user outcome as a single line."""
    line = f"  {record['status']:<8} {record['user']}"
    extra = record["detail"] or (
        record["playlist"] if record["playlist"] else ""
    )
    return f"{line}  ({extra})" if extra else line


def run_per_user(
    targets: Sequence[Tuple[int, str]],
    preview: Tuple[str, List[MediaItem]],
    args: argparse.Namespace,
    action: Callable[[Tuple[int, str]], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Show the item list once, then run *action* per user, one line each.

    The list is identical for every user, so it is printed once here and the
    per-user calls suppress their own preview; each user then costs a single
    line, printed as it completes so a long run shows progress. In a
    machine-readable format the outcomes come back as one record per user
    instead, since one document cannot carry both.

    *action* must turn a failure into a record rather than raising, so that
    one bad user cannot end a run that still has others to serve.
    """
    name, items = preview
    table_mode = output_format(args) == "table"
    if table_mode:
        print(f"{name} ({len(items)} items)")
        print_table(preview_rows(items), table_limit(args))
        print()

    results: List[Dict[str, Any]] = []
    for target in paced(list(targets), args, "users"):
        record = action(target)
        results.append(record)
        if table_mode:
            # Printed as each user completes, so a long run shows progress.
            print(report_line(record))

    if not table_mode:
        output(results, args)
    return results


def _targets(
    plex: PlexServer, args: argparse.Namespace
) -> Optional[List[Tuple[int, str]]]:
    """The (id, title) users to create for, or None for the default account.

    The roster costs one plex.tv round trip, so it is fetched only when -u or
    -a asked for something other than the account the items came from.
    """
    if getattr(args, "all_users", False):
        return user_roster(plex)
    dest = getattr(args, "dest_user_id", None)
    if dest is None:
        return None
    # A title reads better than a bare id in the report, and the roster has
    # one for every user the server knows.
    return [(dest, dict(user_roster(plex)).get(dest, str(dest)))]


def _create_for_one(
    plex: PlexServer,
    target: Tuple[int, str],
    name: str,
    items: List[MediaItem],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """Create the playlist for one user, turning a failure into a record."""
    user_id, title = target
    label = f"user {title!r} (id={user_id})"
    try:
        status, detail = create_for_user(
            server_for_user(plex, user_id), name, items, args
        )
    except UserAccessError as exc:
        status, detail = "skipped", exc.summary
    except Exception as exc:              # pylint: disable=broad-except
        # One user's failure must not end the run over the remaining users.
        LOG.debug("Create failed for %s: %s", label, exc)
        status, detail = "failed", str(exc)
    return {
        "user": title,
        "id": user_id,
        "status": status,
        "playlist": name if status in ("created", "replaced") else "",
        "detail": detail,
    }


def deliver_playlist(
    plex: PlexServer,
    default_plex: PlexServer,
    name: str,
    items: List[MediaItem],
    args: argparse.Namespace,
) -> None:
    """Create the playlist wherever -u, -a, or neither asked for it.

    *plex* is the admin server, the only one able to reach another user;
    *default_plex* is where the playlist goes when neither flag was given,
    which for a command reading an existing playlist is the account that
    playlist came from and otherwise the admin account itself.
    """
    require_items(items)
    targets = _targets(plex, args)
    if targets is None:
        finalize_playlist(default_plex, name, items, args)
        return

    def create(target: Tuple[int, str]) -> Dict[str, Any]:
        return _create_for_one(plex, target, name, items, args)

    results = run_per_user(targets, (name, items), args, create)
    done = sum(1 for r in results if r["status"] in ("created", "replaced"))
    LOG.info("Playlist '%s': %d of %d user(s) served.",
             name, done, len(results))
