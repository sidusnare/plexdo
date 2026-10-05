# SPDX-License-Identifier: GPL-3.0-or-later

"""Waiting for a play to end: the end point, the cadence, and the loop."""

import argparse
import json
import types
import xml.etree.ElementTree as ET

import pytest
from plexapi.exceptions import NotFound
from requests import ConnectionError as RequestsConnectionError

from conftest import FakeItem
from plexdo.commands.wait import (Clock, Follow, Target, _check_arguments,
                                  _credits_markers, _credits_start,
                                  _in_fast_window, _locate, _next_delay,
                                  _progress_line, _target_position, _wait_all,
                                  _wait_loop)
from plexdo.console import stream_record

CREDITS = 100_000          # ms into the video the end credits start
LENGTH = 120_000


@pytest.fixture
def wait_args(args):
    """The global flags plus wait's own, at their defaults."""
    args.interval, args.fast_interval = 10.0, 1.0
    args.offset, args.now, args.no_credits = 0, False, False
    args.rating_key = args.session_key = args.paused = None
    args.all = False
    return args


def session(rating_key=7, position=0, user="Alice", key=12, state="playing"):
    """One entry of /status/sessions, on a video LENGTH long."""
    return FakeItem(rating_key, f"Video {rating_key}", sessionKey=key,
                    viewOffset=position, usernames=[user], duration=LENGTH,
                    players=[types.SimpleNamespace(state=state)])


def library_item(rating_key, credits_at=CREDITS):
    """A video as the library returns it, with its credits marker."""
    xml = ET.fromstring(
        f'<Video><Marker type="credits" startTimeOffset="{credits_at}" '
        'final="1"/></Video>'
    )
    return FakeItem(rating_key, f"Video {rating_key}", duration=LENGTH, _data=xml)


def target(position=CREDITS, credits_at=CREDITS):
    return Target(7, "Video 7", LENGTH, credits_at, position)


class FakeServer:
    """Answers /status/sessions from a script, one snapshot per poll."""

    def __init__(self, *snapshots, items=None):
        self.snapshots = list(snapshots)
        self.items = items or {}

    def fetchItem(self, path):
        key = int(str(path).split("/")[-1].split("?")[0])
        if key not in self.items:
            raise NotFound(f"no item {key}")
        return self.items[key]

    def sessions(self):
        snapshot = self.snapshots.pop(0) if len(self.snapshots) > 1 \
            else self.snapshots[0]
        if isinstance(snapshot, Exception):
            raise snapshot
        return snapshot


class FakeClock:
    """A clock whose sleeps advance it instantly, with no jitter."""

    def __init__(self):
        self.time, self.sleeps = 0.0, []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.time += seconds

    def as_clock(self):
        return Clock(lambda: self.time, self.sleep, lambda low, high: 0.0)


def run(server, wait_args, follow=None, goal=None):
    """Drive the loop to completion; return (final state, sleeps taken)."""
    clock = FakeClock()
    follow = follow or Follow("Alice", 12, seen=True)
    final = _wait_loop(server, goal or target(), follow, wait_args,
                       clock.as_clock())
    return final.state, clock.sleeps


def run_all(server, wait_args, capsys):
    """Drive --all to completion; return (states per poll, sleeps taken)."""
    clock = FakeClock()
    _wait_all(server, wait_args, clock.as_clock())
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    return [r["state"] for r in records], clock.sleeps


# --- where the wait ends -------------------------------------------------

def test_the_final_credits_marker_wins_over_an_earlier_one():
    """The earlier marker precedes a mid-credits scene; the final one follows it."""
    assert _credits_start([(80_000, False), (95_000, True)]) == 95_000


def test_without_a_final_flag_the_last_credits_marker_is_used():
    assert _credits_start([(95_000, False), (80_000, False)]) == 95_000


def test_no_credits_marker_means_no_credits_point():
    assert _credits_start([]) is None


def test_markers_are_read_from_the_xml_already_held():
    """Reading the markers property instead could cost a reload request."""
    xml = ET.fromstring(
        '<Video><Marker type="intro" startTimeOffset="1000"/>'
        '<Marker type="credits" startTimeOffset="95000" final="1"/></Video>'
    )
    assert _credits_markers(FakeItem(7, "V", _data=xml)) == [(95_000, True)]


def test_the_credits_are_the_end_point_when_present():
    assert _target_position(LENGTH, CREDITS, 0) == CREDITS


def test_the_end_of_the_video_is_used_without_credits():
    assert _target_position(LENGTH, None, 0) == LENGTH


def test_a_negative_offset_ends_the_wait_that_much_earlier():
    assert _target_position(LENGTH, CREDITS, -60) == CREDITS - 60_000


def test_a_positive_offset_does_not_move_the_end_point():
    """It is a sleep after the wait, not a playback position."""
    assert _target_position(LENGTH, CREDITS, 30) == CREDITS


def test_an_offset_beyond_the_start_clamps_to_zero():
    assert _target_position(LENGTH, CREDITS, -9999) == 0


def test_a_video_with_no_length_has_no_end_point():
    assert _target_position(None, None, -10) is None


# --- cadence -------------------------------------------------------------

def test_fast_polling_starts_thirty_seconds_out_and_continues_past():
    assert not _in_fast_window(CREDITS - 30_001, CREDITS)
    assert _in_fast_window(CREDITS - 30_000, CREDITS)
    assert _in_fast_window(CREDITS + 5_000, CREDITS)


def test_jitter_stays_within_twenty_percent(wait_args):
    highest = _next_delay(False, None, wait_args, lambda low, high: high)
    lowest = _next_delay(False, None, wait_args, lambda low, high: low)
    assert (lowest, highest) == pytest.approx((8.0, 12.0))
    fast = _next_delay(True, None, wait_args, lambda low, high: high)
    assert fast == pytest.approx(1.2)


def test_a_slow_delay_never_sleeps_through_the_fast_window(wait_args):
    """A long --interval would otherwise jump straight past the end point."""
    wait_args.interval = 60.0
    assert _next_delay(False, 4.0, wait_args, lambda low, high: 0.0) == 4.0


# --- following the right session -----------------------------------------

def test_the_original_session_is_preferred():
    sessions = [session(key=30), session(key=12)]
    assert _locate(sessions, Follow("Alice", 12, True), 7).sessionKey == 12


def test_a_restarted_play_is_found_under_its_new_key():
    """Stopping and starting again gives the same play a new sessionKey."""
    assert _locate([session(key=99)], Follow("Alice", 12, True), 7).sessionKey == 99


def test_another_users_play_does_not_count_once_bound():
    assert _locate([session(user="Bob")], Follow("Alice", 12, True), 7) is None


def test_anyone_counts_before_the_video_has_been_seen():
    assert _locate([session(user="Bob")], Follow(None, None, False), 7) is not None


# --- the loop ------------------------------------------------------------

def test_the_wait_ends_at_the_credits_switching_to_fast_polls(wait_args):
    server = FakeServer([session(position=10_000)], [session(position=60_000)],
                        [session(position=75_000)], [session(position=90_000)],
                        [session(position=CREDITS + 500)])
    state, sleeps = run(server, wait_args)
    assert state == "reached"
    assert sleeps == [10.0, 10.0, 1.0, 1.0]


def test_the_wait_ends_when_the_viewer_stops(wait_args):
    state, sleeps = run(FakeServer([session(position=10_000)], []), wait_args)
    assert (state, len(sleeps)) == ("stopped", 1)


def test_autoplay_moving_on_counts_as_the_end(wait_args):
    """The same session on the next episode means this one is over."""
    server = FakeServer([session(position=10_000)], [session(rating_key=8)])
    assert run(server, wait_args)[0] == "stopped"


def test_a_video_not_yet_playing_is_waited_for(wait_args):
    server = FakeServer([session(rating_key=3)], [session(rating_key=3)],
                        [session(position=50_000)], [])
    state, sleeps = run(server, wait_args, Follow("Alice", 12, seen=False))
    assert (state, len(sleeps)) == ("stopped", 3)


def test_now_gives_up_at_once_when_the_video_is_not_playing(wait_args):
    wait_args.now = True
    state, sleeps = run(FakeServer([session(rating_key=3)]), wait_args,
                        Follow("Alice", 12, seen=False))
    assert (state, sleeps) == ("not started", [])


def test_a_failed_poll_is_retried_rather_than_fatal(wait_args):
    server = FakeServer(RequestsConnectionError("reset"), [])
    assert run(server, wait_args)[0] == "stopped"


def test_a_server_that_stays_away_ends_the_wait_with_an_error(wait_args):
    with pytest.raises(SystemExit) as exc:
        run(FakeServer(RequestsConnectionError("refused")), wait_args)
    assert "giving up" in str(exc.value)


def test_every_poll_reports_who_what_and_how_long(wait_args, capsys):
    run(FakeServer([session(position=10_000)], [session(position=CREDITS)]),
        wait_args)
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["state"] for r in records] == ["playing", "reached"]
    first = records[0]
    assert (first["user"], first["playing"], first["waitingFor"]) == \
        ("Alice", "Video 7", "Video 7")
    assert (first["position"], first["elapsed"], first["remaining"]) == (10, 0, 90)


def test_the_progress_line_flags_a_video_not_yet_started():
    line = _progress_line({
        "user": "Alice", "sessionKey": 12, "playing": "Video 3",
        "waitingFor": "Video 7", "ratingKey": 7, "state": "not started",
        "position": None, "duration": 120, "target": 100, "elapsed": 70,
        "remaining": None,
    })
    assert line == ("Alice | playing: Video 3 | waiting for: Video 7 | "
                    "not started | waited 1:10 | -")


# --- streaming output ----------------------------------------------------

def test_csv_streams_with_one_header(capsys):
    csv_args = argparse.Namespace(format="csv")
    stream_record({"a": 1, "b": "x"}, csv_args, first=True)
    stream_record({"a": 2, "b": "y"}, csv_args, first=False)
    assert capsys.readouterr().out.splitlines() == ["a,b", "1,x", "2,y"]


def test_yaml_streams_as_separate_documents(capsys):
    stream_record({"a": 1}, argparse.Namespace(format="yaml"), first=True)
    stream_record({"a": 2}, argparse.Namespace(format="yaml"), first=False)
    assert capsys.readouterr().out.splitlines() == ["---", "a: 1", "---", "a: 2"]


# --- --paused ------------------------------------------------------------

def test_a_play_left_paused_long_enough_is_over(wait_args):
    wait_args.paused = 300
    server = FakeServer([session(position=10_000)],
                        [session(position=20_000, state="paused")])
    state, sleeps = run(server, wait_args)
    assert state == "left paused"
    # Slow polls while paused, the last cut short to land on the deadline.
    assert sum(sleeps[1:]) == pytest.approx(300)


def test_resuming_starts_the_pause_count_again(wait_args):
    wait_args.paused = 15
    server = FakeServer([session(state="paused")], [session(state="paused")],
                        [session(position=30_000)], [session(state="paused")],
                        [session(state="paused")], [])
    assert run(server, wait_args)[0] == "stopped"


def test_paused_zero_ends_at_the_first_sight_of_a_pause(wait_args):
    wait_args.paused = 0
    state, sleeps = run(FakeServer([session(state="paused")]), wait_args)
    assert (state, sleeps) == ("left paused", [])


def test_a_pause_is_ignored_without_the_option(wait_args):
    server = FakeServer([session(state="paused")], [session(state="paused")], [])
    assert run(server, wait_args)[0] == "stopped"


def test_a_paused_play_estimates_the_time_its_pause_has_left(wait_args, capsys):
    wait_args.paused = 60
    run(FakeServer([session(state="paused")], []), wait_args)
    first = json.loads(capsys.readouterr().out.splitlines()[0])
    assert (first["pausedFor"], first["remaining"]) == (0, 60)


# --- --all ---------------------------------------------------------------

def test_all_waits_for_every_play_then_confirms(wait_args, capsys):
    wait_args.all = True
    server = FakeServer(
        [session(position=10_000), session(3, user="Bob", key=40)],
        [session(position=CREDITS), session(3, user="Bob", key=40)],
        [session(position=CREDITS)],
        items={7: library_item(7), 3: library_item(3)},
    )
    states, sleeps = run_all(server, wait_args, capsys)
    assert states == ["playing", "playing",
                      "reached", "playing",
                      "stopped", "reached",
                      "reached"]
    assert len(sleeps) == 3


def test_all_keeps_waiting_for_a_play_started_meanwhile(wait_args, capsys):
    """The confirming poll is what catches autoplay's next episode."""
    wait_args.all = True
    server = FakeServer(
        [session(position=CREDITS)],
        [session(rating_key=8, position=1_000)],
        [],
        items={7: library_item(7), 8: library_item(8)},
    )
    states, _ = run_all(server, wait_args, capsys)
    assert states == ["reached", "stopped", "playing", "stopped",
                      "nothing playing"]


def test_all_with_nothing_playing_still_checks_once_more(wait_args, capsys):
    wait_args.all = True
    states, sleeps = run_all(FakeServer([]), wait_args, capsys)
    assert (states, len(sleeps)) == (["nothing playing"] * 2, 1)


def test_all_judges_an_unfetchable_video_by_its_session(wait_args, capsys):
    """A remote or live item must not end the wait over everyone else."""
    wait_args.all = True
    server = FakeServer([session(position=LENGTH - 1_000)],
                        [session(position=LENGTH)])
    states, _ = run_all(server, wait_args, capsys)
    assert states[:2] == ["playing", "reached"]


def test_all_applies_paused_to_each_play(wait_args, capsys):
    wait_args.all, wait_args.paused = True, 0
    server = FakeServer([session(state="paused")], items={7: library_item(7)})
    states, _ = run_all(server, wait_args, capsys)
    assert states == ["left paused", "left paused"]


@pytest.mark.parametrize("flag", ["session_key", "rating_key"])
def test_all_refuses_a_single_play_selector(wait_args, flag):
    wait_args.all = True
    setattr(wait_args, flag, 5)
    with pytest.raises(SystemExit) as exc:
        _check_arguments(wait_args)
    assert "--all" in str(exc.value)
