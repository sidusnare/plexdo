# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Logging configuration (stderr only, never stdout)."""

import logging
import sys


def configure_logging(verbose: bool, debug: bool) -> None:
    """Configure logging to stderr only (never stdout)."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    # The handler filters too: plexapi sets its own logger to INFO, whose
    # records would otherwise reach stderr whatever the level chosen here.
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)
