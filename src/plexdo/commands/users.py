# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""User listing command."""

import argparse

from plexapi.server import PlexServer

from plexdo.accounts import user_rows
from plexdo.cache import write_cache
from plexdo.console import output


def cmd_list_users(plex: PlexServer, args: argparse.Namespace) -> None:
    """List the users the server is shared with."""
    rows = user_rows(plex)
    # Completion needs the ID and the title, which every row carries.
    write_cache("users", rows)
    output(rows, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the user listing subparser."""
    sub.add_parser(
        "users-list",
        parents=parents,
        help="List the server's users.",
    )


COMMANDS = {"users-list": cmd_list_users}

REQUIRES_PLEX = frozenset(COMMANDS)
