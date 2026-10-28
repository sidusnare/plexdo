# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Watched-state winner selection, in both directions."""

import datetime

import pytest

from plexdo.commands.watched import WatchState, _select_winner, _states_match
from plexdo.commands.watched import _planned_action as planned_action


def D(day):
    return datetime.datetime(2024, 1, day)


def S(played=False, offset=0, day=None):
    return WatchState(played, offset, D(day) if day else None, item=None)


def pick(a, b, unwatch):
    got = _select_winner(a, b, unwatch)
    return None if got is None else ("a" if got[0] is a else "b")


def test_neither_watched_is_a_no_op():
    assert pick(S(), S(), False) is None


def test_identical_states_are_a_no_op():
    assert pick(S(played=True, day=1), S(played=True, day=9), False) is None


def test_offsets_within_tolerance_count_as_identical():
    """Plex rewrites viewOffset in playback; without this every run churns."""
    assert _states_match(S(offset=100_000), S(offset=105_000))


def test_offsets_beyond_tolerance_differ():
    assert not _states_match(S(offset=100_000), S(offset=900_000))


def test_default_sync_propagates_the_watched_state_outward():
    assert pick(S(played=True, day=5), S(), False) == "a"
    assert pick(S(), S(played=True, day=5), False) == "b"


def test_unwatch_propagates_the_unwatched_state_instead():
    assert pick(S(played=True, day=5), S(), True) == "b"
    assert pick(S(), S(played=True, day=5), True) == "a"


def test_when_both_watched_the_latest_wins_by_default():
    """Both fully played needs no sync, so the states must actually differ."""
    assert pick(S(played=True, day=9), S(offset=900_000, day=5), False) == "a"
    assert pick(S(played=True, day=1), S(offset=900_000, day=9), False) == "b"


def test_when_both_watched_unwatch_takes_the_earliest():
    assert pick(S(offset=100_000, day=5), S(offset=900_000, day=9), True) == "a"


@pytest.mark.parametrize("unwatch", [False, True])
def test_an_undated_state_never_wins(unwatch):
    """A missing lastViewedAt must not win by accident either way."""
    dated, undated = S(offset=100_000, day=5), S(offset=900_000)
    assert pick(dated, undated, unwatch) == "a"


def test_actions_match_the_winners_state():
    assert planned_action(S(played=True)) == "markPlayed"
    assert planned_action(S(offset=5000)) == "setProgress"
    assert planned_action(S()) == "markUnplayed"
