# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Command registry.

Every command module exposes three names:

``register(sub, parents)``
    Adds the module's subparsers to the top-level ``add_subparsers`` action.
    Every subparser must pass ``parents=parents`` so it inherits the global
    flags and accepts them after the command name as well as before it.
``COMMANDS``
    Maps each command name to its handler function.
``REQUIRES_PLEX``
    The subset of those names needing a connected server. Commands outside it
    (``login``, ``logout``, ``write-config-example``) do not need one.

Adding a command means adding a module here, and its name to ``GROUPS`` so
``--help`` lists it - ``cli`` needs no edit.
"""

import argparse
from collections.abc import Callable
from typing import Any

from plexdo.commands import (
    albums,
    auth,
    build,
    copy,
    libraries,
    metadata,
    missing,
    playlists,
    remote,
    rescan,
    search,
    status,
    stream,
    users,
    wait,
    watched,
)

MODULES = (
    libraries,
    albums,
    missing,
    search,
    users,
    playlists,
    metadata,
    stream,
    rescan,
    status,
    wait,
    remote,
    build,
    copy,
    watched,
    auth,
)

# How --help lists the commands: under these headings, in this order, and
# sorted by name within each. Every command belongs to exactly one group.
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "libraries and titles",
        (
            "album-list",
            "find-missing",
            "libraries-list",
            "library-list",
            "metadata",
            "search",
            "show-list",
            "titles-export",
        ),
    ),
    (
        "playlists",
        (
            "playlist-build",
            "playlist-clean",
            "playlist-copy",
            "playlist-export",
            "playlist-list",
            "playlist-remove",
            "playlists-list",
        ),
    ),
    (
        "playback and watched state",
        ("player-remote-play", "read", "show-watched-cp", "wait"),
    ),
    ("server", ("rescan", "status", "users-list")),
    (
        "account and configuration",
        (
            "login",
            "logout",
            "set-pin",
            "write-config-example",
            "write-secrets-example",
        ),
    ),
)

Handler = Callable[[Any, argparse.Namespace], None]


def register_all(
    sub: "argparse._SubParsersAction",  # pylint: disable=protected-access
    parents: list[argparse.ArgumentParser],
) -> None:
    """Register every command module's subparsers."""
    for module in MODULES:
        module.register(sub, parents)


def build_registry() -> tuple[dict[str, Handler], frozenset[str]]:
    """Return the merged command map and the set needing a Plex connection."""
    handlers: dict[str, Handler] = {}
    needs_plex: set = set()
    for module in MODULES:
        handlers.update(module.COMMANDS)
        needs_plex.update(module.REQUIRES_PLEX)
    return handlers, frozenset(needs_plex)
