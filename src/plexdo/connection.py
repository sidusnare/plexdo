# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Connecting to the configured server with the saved admin token."""

import sys

from plexapi.server import PlexServer

from plexdo import secret_store
from plexdo.config import Config, config_optional
from plexdo.constants import CONFIG_PATH, LOG
from plexdo.tokens import admin_token


def read_token(username: str | None) -> str:
    """Return the admin token from the secret store."""
    token = admin_token(username)
    if not token:
        sys.exit(
            f"No admin token in {secret_store.describe()}.\n"
            "Run `plexdo login` to authenticate, or set plex: username in "
            f"{CONFIG_PATH} to the account whose token should be used."
        )
    LOG.debug("Admin token loaded from %s", secret_store.describe())
    return token


def server_url(cfg: Config) -> str:
    """The configured server URL, which every command needs."""
    url = config_optional(cfg, "url")
    if not url:
        sys.exit(
            f"No plex: url in {CONFIG_PATH}; set it to the server's "
            "address, such as http://localhost:32400."
        )
    return url


def connect_plex(cfg: Config) -> PlexServer:
    """Create and return a connected PlexServer instance."""
    url = server_url(cfg)
    token = read_token(config_optional(cfg, "username"))
    LOG.info("Connecting to Plex at %s", url)
    return PlexServer(url, token)
