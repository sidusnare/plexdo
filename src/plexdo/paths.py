# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Rewriting server-side media paths for export.

Exports carry the paths the Plex server itself sees. When the same files are
reached by a different route - an SMB share, a different mount point, a
Windows drive letter - ``--prefix`` swaps the server's library root for one
that makes sense where the export will be read.
"""

from collections.abc import Callable
from typing import Any

from plexapi.server import PlexServer

from plexdo.constants import LOG

PathMapper = Callable[[str], str]

# Shared by every export command's --prefix flag, so the wording (and pylint's
# duplicate-code check) has a single home.
PREFIX_HELP = (
    "Rewrite exported paths onto PREFIX in place of the server-side library "
    "root, for reading the export somewhere the media is mounted "
    "differently. Default: the server's own paths."
)


def add_prefix_argument(parser: Any) -> None:
    """Add the standard -p/--prefix option to an export subparser."""
    parser.add_argument(
        "-p",
        "--prefix",
        default=None,
        metavar="PREFIX",
        help=PREFIX_HELP,
    )


def library_roots(plex: PlexServer) -> list[str]:
    """Every library root path on the server, longest first.

    Longest first so the most specific root wins when one library lives
    inside another's directory tree.
    """
    roots: list[str] = []
    for section in plex.library.sections():
        try:
            roots.extend(location for location in section.locations if location)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.debug("No locations for section %r: %s", section.title, exc)
    return sorted(set(roots), key=len, reverse=True)


def _split_root(file_path: str, roots: list[str]) -> str | None:
    """Return the part of file_path below its library root, or None."""
    normalised = file_path.replace("\\", "/")
    for root in roots:
        stem = root.replace("\\", "/").rstrip("/")
        if normalised == stem or normalised.startswith(stem + "/"):
            return normalised[len(stem) :].lstrip("/")
    return None


def _rejoin(prefix: str, remainder: str) -> str:
    """Join a prefix and remainder using the prefix's own separator style."""
    separator = "\\" if "\\" in prefix else "/"
    remainder = remainder.replace("\\", "/")
    if separator == "\\":
        remainder = remainder.replace("/", "\\")
    return prefix.rstrip("/\\") + separator + remainder


def identity(file_path: str) -> str:
    """Return the path unchanged; the default for every export."""
    return file_path


def mapper_for(plex: PlexServer, args: Any) -> PathMapper:
    """Return the path mapper implied by a command's --prefix argument.

    Without a prefix this is the identity, so the default export keeps the
    server's own paths and costs no extra API call.
    """
    prefix = getattr(args, "prefix", None)
    if not prefix:
        return identity

    roots = library_roots(plex)
    LOG.debug("Rewriting paths onto %r; library roots: %s", prefix, roots)
    warned: list[str] = []

    def mapper(file_path: str) -> str:
        remainder = _split_root(file_path, roots)
        if remainder is None:
            # Below no known library root: keep the whole path so nothing is
            # silently lost, but say so once, since it usually means the
            # prefix is aimed at the wrong level.
            if not warned:
                warned.append(file_path)
                LOG.warning(
                    "%r is not under any library root %s; appending it whole "
                    "to the prefix. Further such paths are not reported.",
                    file_path,
                    roots or "(none found)",
                )
            remainder = file_path.replace("\\", "/").lstrip("/")
        return _rejoin(prefix, remainder)

    return mapper
