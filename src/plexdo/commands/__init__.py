# SPDX-License-Identifier: GPL-3.0-or-later

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
    (``login``, ``write-config-example``) run before a token necessarily exists.

Adding a command means adding a module here - ``cli`` needs no edit.
"""

import argparse
from typing import Any, Callable, Dict, FrozenSet, List, Tuple

from plexdo.commands import (auth, build, copy, libraries, metadata, missing,
                             playlists, rescan, search, status, stream, users,
                             watched)

# Order determines the order subcommands appear in --help.
MODULES = (
    libraries,
    missing,
    search,
    users,
    playlists,
    metadata,
    stream,
    rescan,
    status,
    build,
    copy,
    watched,
    auth,
)

Handler = Callable[[Any, argparse.Namespace], None]


def register_all(
    sub: "argparse._SubParsersAction",  # pylint: disable=protected-access
    parents: List[argparse.ArgumentParser],
) -> None:
    """Register every command module's subparsers."""
    for module in MODULES:
        module.register(sub, parents)


def build_registry() -> Tuple[Dict[str, Handler], FrozenSet[str]]:
    """Return the merged command map and the set needing a Plex connection."""
    handlers: Dict[str, Handler] = {}
    needs_plex: set = set()
    for module in MODULES:
        handlers.update(module.COMMANDS)
        needs_plex.update(module.REQUIRES_PLEX)
    return handlers, frozenset(needs_plex)
