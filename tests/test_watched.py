# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Watched-state winner selection, in both directions."""

import datetime

import pytest

from plexdo.commands import watched
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


def test_actions_bring_the_loser_to_the_winners_state():
    assert planned_action(S(played=True), S()) == "markPlayed"
    assert planned_action(S(offset=5000), S()) == "setProgress"
    assert planned_action(S(), S(played=True)) == "markUnplayed"


# --- played and progress are copied as they stand ---------------------------


def test_a_rewatch_differs_from_a_finished_play():
    """Both played, but one is part way through again: that is a change."""
    assert not _states_match(S(played=True), S(played=True, offset=900_000))
    assert _states_match(
        S(played=True, offset=900_000), S(played=True, offset=905_000)
    )


def test_a_rewatch_copies_the_played_flag_and_the_resume_point():
    rewatch = S(played=True, offset=900_000, day=9)
    assert planned_action(rewatch, S()) == "markPlayed+setProgress"
    assert planned_action(rewatch, S(played=True)) == "setProgress"
    assert planned_action(S(played=True), rewatch) == "clearProgress"
    assert planned_action(S(offset=5000), S(played=True)) == (
        "markUnplayed+setProgress"
    )


class Recorder:
    """An item that records the calls made on it."""

    def __init__(self):
        self.calls = []

    def markPlayed(self):
        self.calls.append("markPlayed")

    def markUnplayed(self):
        self.calls.append("markUnplayed")

    def updateProgress(self, offset):
        self.calls.append(("updateProgress", offset))


def applied(winner, loser):
    item = Recorder()
    loser = loser._replace(item=item)
    watched._apply_action(
        watched.PlannedChange(
            1, "T", planned_action(winner, loser), "b", winner, loser
        )
    )
    return item.calls


def test_unwatch_clears_a_resume_point_that_was_never_a_full_play():
    """It planned markUnplayed and then called nothing, on every run."""
    assert planned_action(S(), S(offset=90_000)) == "clearProgress"
    assert applied(S(), S(offset=90_000)) == ["markUnplayed"]


def test_clearing_progress_keeps_a_played_item_played():
    assert applied(S(played=True), S(played=True, offset=90_000)) == [
        "markPlayed"
    ]


def test_the_played_flag_is_set_before_the_resume_point():
    """Marking clears the resume point on the server, so it comes first."""
    assert applied(S(played=True, offset=7000), S()) == [
        "markPlayed",
        ("updateProgress", 7000),
    ]
    assert applied(S(offset=7000), S(played=True)) == [
        "markUnplayed",
        ("updateProgress", 7000),
    ]


# --- a ratingKey naming a container stands for its members ------------------


class Container:
    def __init__(self, kind, members=()):
        self.ratingKey, self.type, self._members = 50, kind, list(members)

    def episodes(self):
        return self._members

    def tracks(self):
        return self._members


@pytest.mark.parametrize("kind", ["movie", "episode", "track", "clip"])
def test_an_item_with_its_own_state_stands_for_itself(kind):
    item = Container(kind)
    assert watched._members(item) == [item]


@pytest.mark.parametrize("kind", ["show", "season", "artist", "album"])
def test_a_container_stands_for_everything_in_it(kind):
    assert watched._members(Container(kind, ["one", "two"])) == ["one", "two"]


def test_an_item_with_no_watched_state_is_refused():
    with pytest.raises(SystemExit) as exc:
        watched._members(Container("photo"))
    assert "no watched state" in str(exc.value)
