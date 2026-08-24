# SPDX-License-Identifier: GPL-3.0-or-later

"""Media streaming to stdout."""

import argparse
import os
import sys
import textwrap

import requests
from plexapi.server import PlexServer

from plexdo.console import output_format
from plexdo.constants import LOG
from plexdo.titles import display_title, fetch_item


def _stream_to_stdout(url: str, label: str) -> None:
    """Stream a URL to binary stdout, handling a closed pipe gracefully."""
    if sys.stdout.isatty():
        LOG.warning(
            "stdout is a terminal - pipe into a player, e.g.: "
            "plexdo read <lib> <key> | mpv -"
        )
    LOG.info("Streaming: %s", label)
    try:
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=65536):
                sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        # Downstream player exited (e.g. user quit mpv) - not an error.
        # Point stdout at the null device so the interpreter's final flush
        # does not print "BrokenPipeError ignored" to stderr on exit.
        LOG.debug("Downstream closed pipe; stream ended.")
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
    except requests.HTTPError as exc:
        sys.exit(f"HTTP error while streaming: {exc}")


def cmd_read(plex: PlexServer, args: argparse.Namespace) -> None:
    """Stream a media file to stdout by library ID and ratingKey."""
    if output_format(args) != "table":
        LOG.warning(
            "Output format flags have no effect on the read command; "
            "binary media data goes to stdout."
        )

    rating_key = int(args.rating_key)
    item = fetch_item(plex, rating_key)

    item_lib_id = int(getattr(item, "librarySectionID", 0))
    if item_lib_id != args.library_id:
        sys.exit(
            f"ratingKey {rating_key} belongs to library {item_lib_id}, "
            f"not library {args.library_id}."
        )

    if not getattr(item, "media", None):
        sys.exit(f"No media attached to ratingKey: {rating_key}")

    parts = item.media[0].parts
    if not parts:
        sys.exit(f"No parts found for ratingKey: {rating_key}")

    if len(item.media) > 1 or len(parts) > 1:
        LOG.warning(
            "Multiple media/parts found; streaming first part only. "
            "Use list-show or show-metadata to inspect."
        )

    part = parts[0]
    label = display_title(item)
    url = plex.url(part.key, includeToken=True)

    LOG.info("File : %s", part.file or "(no server path)")
    LOG.info("URL  : %s", url)

    if args.dry_run:
        print(f"title : {label}", file=sys.stderr)
        print(f"file  : {part.file or '(none)'}", file=sys.stderr)
        print(f"url   : {url}", file=sys.stderr)
        return

    _stream_to_stdout(url, label)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the read subparser."""
    parser = sub.add_parser(
        "read", parents=parents,
        help=(
            "Stream a media file to stdout. Pipe into a player: "
            "plexdo read <lib> <key> | mpv -"
        ),
        description=textwrap.fill(
            "Stream a media file to standard output, for piping into a player "
            "or redirecting to a file. Quitting the player early is not an "
            "error.",
            width=78,
        ),
        epilog=(
            "examples:\n"
            "  plexdo read 3 12345 > episode.mkv\n"
            "  plexdo read 3 12345 | mpv -\n"
            "\n"
            "On Linux with a display attached but no desktop environment, mpv\n"
            "can draw straight to the console through the kernel modesetting\n"
            "driver, so playback needs neither X nor Wayland:\n"
            "\n"
            "  plexdo read 3 12345 | mpv --vo=drm -\n"
            "\n"
            "Run it from a virtual terminal rather than a terminal emulator,\n"
            "and make sure your user can reach the DRM device (usually via the\n"
            "video group)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "library_id", metavar="LIBRARY",
        help="Library ID (int) or library title (str). Obtain both with list-libraries.",
    )
    parser.add_argument(
        "rating_key", type=int,
        help="Item ratingKey (int). Obtain with list-titles or list-show.",
    )


COMMANDS = {"read": cmd_read}

REQUIRES_PLEX = frozenset(COMMANDS)
