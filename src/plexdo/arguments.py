# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Arguments several commands share, defined once so their help agrees."""

import argparse


def add_user_argument(parser: argparse.ArgumentParser) -> None:
    """Add the USER positional: whose playlists or library to act on."""
    parser.add_argument(
        "user_id",
        metavar="USER",
        help=(
            "User ID (int) or user title (str); use 0 for the admin account. "
            "Obtain both with list-users."
        ),
    )


def add_library_argument(parser: argparse.ArgumentParser) -> None:
    """Add the LIBRARY positional, by ID or title."""
    parser.add_argument(
        "library_id",
        metavar="LIBRARY",
        help=(
            "Library ID (int) or library title (str). Obtain both with "
            "list-libraries."
        ),
    )


def add_m3u_argument(parser: argparse.ArgumentParser) -> None:
    """Add --m3u, exporting what was built or listed as an M3U file."""
    parser.add_argument(
        "--m3u",
        metavar="PATH",
        help=(
            "Also export an M3U file at PATH using Plex server filesystem "
            "paths."
        ),
    )


def add_overwrite_argument(parser: argparse.ArgumentParser) -> None:
    """Add -o/--overwrite, replacing a playlist of the same name."""
    parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        default=False,
        help=(
            "Replace an existing playlist of the same name instead of failing."
        ),
    )


def add_rating_keys_argument(
    parser: argparse.ArgumentParser, help_text: str
) -> None:
    """Add the ratingKey... positional: one or more items, by ratingKey."""
    parser.add_argument(
        "rating_keys",
        nargs="+",
        type=int,
        metavar="ratingKey",
        help=help_text,
    )


def add_rating_key_option(
    parser: argparse.ArgumentParser, *flags: str, help_text: str
) -> None:
    """Add an option naming one item by ratingKey, as KEY."""
    parser.add_argument(
        *flags,
        dest="rating_key",
        type=int,
        default=None,
        metavar="KEY",
        help=help_text,
    )
