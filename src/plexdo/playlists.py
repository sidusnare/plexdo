# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist resolution, creation, and copy naming rules."""

from typing import Any, Dict, List, Optional, Tuple
import argparse
import sys

from plexapi.exceptions import NotFound
from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.console import clean_text, output
from plexdo.constants import LOG, MediaItem
from plexdo.titles import display_title


def resolve_playlist(user_plex: PlexServer, identifier: str) -> Playlist:
    """Return a Playlist located by name or ratingKey string.

    If *identifier* parses as an integer it is treated as a ratingKey;
    otherwise it is treated as a title.  Fails fast with a clear message if
    not found or if the ratingKey refers to a non-playlist item.
    """
    try:
        rk = int(identifier)
        item = user_plex.fetchItem(rk)
        if not isinstance(item, Playlist):
            sys.exit(
                f"ratingKey {rk} is not a playlist (got {type(item).__name__})"
            )
        return item
    except ValueError:
        pass  # identifier is not numeric - fall through to name lookup
    try:
        return user_plex.playlist(identifier)
    except NotFound:
        sys.exit(f"Playlist not found: {identifier!r}")


def preview_rows(items: List[MediaItem]) -> List[Dict[str, Any]]:
    """Build the numbered preview of the items a playlist will hold."""
    return [
        {
            "index": i + 1,
            "ratingKey": int(item.ratingKey),
            "title": display_title(item),
        }
        for i, item in enumerate(items)
    ]


def existing_playlist(plex: PlexServer, name: str) -> Optional[Playlist]:
    """Return a playlist with exactly this title, or None."""
    for playlist in plex.playlists():
        if clean_text(playlist.title) == clean_text(name):
            return playlist
    return None


def require_items(items: List[MediaItem]) -> None:
    """Refuse an empty playlist.

    Asked once by whichever caller assembled the list, which is the same
    list for every user a fan-out then creates it for.
    """
    if not items:
        sys.exit("Playlist is empty - aborting.")


def _refuses_replacement(
    duplicate: Optional[Playlist], args: argparse.Namespace
) -> bool:
    """True when the name is taken and --overwrite was not given.

    The fatal path and the per-user path both ask here, so the rule that
    decides whether a name may be reused lives in exactly one place. When it
    returns True the caller has a duplicate to report on.
    """
    return duplicate is not None and not getattr(args, "overwrite", False)


def _write_playlist(
    plex: PlexServer,
    name: str,
    items: List[MediaItem],
    duplicate: Optional[Playlist],
    args: argparse.Namespace,
) -> str:
    """Replace or create the playlist, honouring --dry-run.

    Returns "created" or "replaced". The caller has already established that
    *duplicate* may be replaced, so no further check happens here.
    """
    LOG.info("Playlist '%s': %d items", name, len(items))
    outcome = "replaced" if duplicate is not None else "created"

    if args.dry_run:
        if duplicate is not None:
            LOG.info("--dry-run: would replace the existing '%s'", name)
        LOG.info("--dry-run: skipping playlist creation.")
        return outcome

    if duplicate is not None:
        duplicate.delete()
        LOG.info("Removed the existing playlist '%s'", name)

    plex.createPlaylist(name, items=items)
    LOG.info("Playlist '%s' created with %d items.", name, len(items))
    return outcome


def finalize_playlist(
    plex: PlexServer,
    name: str,
    items: List[MediaItem],
    args: argparse.Namespace,
    preview: bool = True,
) -> str:
    """Validate, preview, and (unless --dry-run) create the playlist.

    Returns "created" or "replaced" so a caller copying to many users can
    report per-user outcomes. Set *preview* to False when the caller has
    already shown the item list once and printing it again per user would
    bury the report.

    Refuses to clobber an existing playlist of the same name unless
    --overwrite is given, and checks that before printing the preview so a
    doomed run fails immediately rather than after a screen of output.
    """
    require_items(items)

    duplicate = existing_playlist(plex, name)
    if _refuses_replacement(duplicate, args):
        sys.exit(
            f"A playlist named {name!r} already exists (ratingKey "
            f"{int(duplicate.ratingKey)}). Nothing has been "
            "created or removed.\n"
            "Re-run with --overwrite to replace it, or choose another name."
        )

    if preview:
        output(preview_rows(items), args)

    return _write_playlist(plex, name, items, duplicate, args)


def create_for_user(
    user_plex: PlexServer,
    name: str,
    items: List[MediaItem],
    args: argparse.Namespace,
) -> Tuple[str, str]:
    """Create the playlist for one user, reporting instead of exiting.

    Returns (status, detail); status is "created", "replaced", or "skipped".
    A refused name collision comes back as a skip rather than a sys.exit,
    because SystemExit would tear down a run that still has other users to
    serve - the same reason UserAccessError is an ordinary exception.
    """
    duplicate = existing_playlist(user_plex, name)
    if _refuses_replacement(duplicate, args):
        return "skipped", (
            f"{name!r} already exists (ratingKey "
            f"{int(duplicate.ratingKey)}); --overwrite would replace it"
        )
    return _write_playlist(user_plex, name, items, duplicate, args), ""


def _resolve_dest_name(
    user_plex: PlexServer, desired_name: str, force_overwrite: bool = False
) -> Optional[Tuple[str, bool]]:
    """
    Return (final_name, delete_first), or None if the copy should be skipped.

    With force_overwrite (--overwrite), the desired name is always used and
    is replaced if it already exists; the ' admin copy' fallback is skipped.

    Otherwise the default naming rules apply:
    If desired_name doesn't exist -> use it.
    If desired_name exists -> fall back to desired_name + ' admin copy'.
    If BOTH already exist -> return None so the caller skips this target
    without destroying either playlist; --overwrite is required to replace.
    """
    existing = {pl.title for pl in user_plex.playlists()}
    if force_overwrite:
        return desired_name, desired_name in existing
    if desired_name not in existing:
        return desired_name, False
    candidate = desired_name + " admin copy"
    if candidate not in existing:
        return candidate, False
    return None


def copy_playlist_to(
    src_items: List[MediaItem],
    user_plex: PlexServer,
    desired_name: str,
    args: argparse.Namespace,
    *,
    target_label: str = "target",
    preview: bool = True,
) -> Tuple[str, str, str]:
    """Copy items to user_plex under the resolved name.

    Returns (status, final_name, detail); status is "created", "replaced", or
    "skipped".
    """
    resolved = _resolve_dest_name(
        user_plex, desired_name, getattr(args, "overwrite", False)
    )
    if resolved is None:
        detail = (
            f"both {desired_name!r} and {desired_name + ' admin copy'!r} "
            "already exist; use --overwrite to replace"
        )
        # Reported by the caller as a result row, so this is detail rather
        # than a warning; stderr stays for things the caller cannot show.
        LOG.info("Skipping %s: %s. Nothing was created or deleted.",
                 target_label, detail)
        return "skipped", desired_name, detail

    final_name, replacing = resolved
    LOG.info("Copying to '%s' (replacing=%s)", final_name, replacing)

    # No delete here: _resolve_dest_name only reports replacing=True when
    # --overwrite was given, and finalize_playlist performs the replacement
    # itself. Doing it in both places would be the same logic twice.
    status = finalize_playlist(user_plex, final_name, src_items, args, preview)
    return status, final_name, ""
