# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Logging goes to stderr at the level asked for, plexapi's included."""

import logging

import plexapi  # noqa: F401  pylint: disable=unused-import  (sets its INFO)
import pytest

from plexdo.logs import configure_logging


@pytest.fixture
def root_handlers():
    """Restore the root logger after configure_logging adds to it."""
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    yield
    root.handlers[:], _ = saved
    root.setLevel(saved[1])


@pytest.mark.parametrize("verbose, shown", [(False, False), (True, True)])
def test_plexapi_info_shows_only_with_verbose(
    root_handlers, capsys, verbose, shown
):
    """The handler filters plexapi's INFO messages out.

    plexapi sets its own logger to INFO, so without a filter on the handler
    its chatter reached stderr on every run.
    """
    assert logging.getLogger("plexapi").level == logging.INFO
    configure_logging(verbose=verbose, debug=False)
    logging.getLogger("plexapi").info('Failed to parse "" to datetime')
    logging.getLogger("plexdo").warning("a warning always shows")
    err = capsys.readouterr().err
    assert ("Failed to parse" in err) is shown
    assert "a warning always shows" in err
