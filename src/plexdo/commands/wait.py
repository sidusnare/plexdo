# SPDX-License-Identifier: GPL-3.0-or-later

"""Sleeping until a session's current play is over.

The point a play ends at is the start of its end credits when the video has a
credits marker, and the end of the video otherwise; --no-credits always uses
the end. A negative --offset moves that point earlier, and a positive one is
a sleep taken once the wait is over. A play is also over, wherever playback
had got to, as soon as it stops - the viewer quit, or autoplay moved on to
the next video - and, with --paused, once its player has sat paused for that
long.

Without --all one play is followed. With it every session is judged by those
same rules, and the wait is over only when two polls an interval apart both
find nothing left: the second is what catches a play started in between, an
autoplayed next episode among them.

Polling is slow until playback is within _FAST_WINDOW_MS of a play's end
point and fast from then on, so the end is noticed within about a second
rather than within a whole slow interval.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple
import argparse
import random
import sys
import time

from plexapi.exceptions import PlexApiException
from plexapi.server import PlexServer
from requests import RequestException

from plexdo.console import (STREAMABLE_FORMATS, clean_text, output_format,
                            stream_record)
from plexdo.constants import LOG
from plexdo.convert import format_duration
from plexdo.titles import display_title, fetch_item, find_item


# Within this much playback of the point being waited for - or past it -
# polling switches to the fast interval.
_FAST_WINDOW_MS = 30_000

# Each delay varies by up to this fraction either way: +/-2s on the default
# 10s interval and +/-0.2s on the default 1s one.
_JITTER = 0.2

# A wait can last hours, so a failed poll is retried rather than fatal; this
# many in a row means the server has gone away rather than hiccuped.
_MAX_FAILED_POLLS = 5

# States in which a play is over.
_FINAL_STATES = ("reached", "stopped", "left paused")


# A play is a session on a video: autoplay keeps the session and changes the
# video, which is a new play with an end point of its own.
_PlayId = Tuple[Any, int]


class Target(NamedTuple):
    """The video waited for, and the playback point that ends the wait."""

    rating_key: int
    title: str
    duration: Optional[int]     # ms
    credits: Optional[int]      # ms; None when absent or --no-credits
    position: Optional[int]     # ms; None when the video has no length


@dataclass
class Follow:
    """Whose playback is being followed, and whether the video has started.

    *user* is None only while waiting for anyone at all to start a given
    ratingKey; the first session seen playing it binds the user, and from
    then on only that user's sessions count.
    """

    user: Optional[str]
    session_key: Optional[int]
    seen: bool
    # When each play was first seen paused, for --paused.
    pauses: Dict[_PlayId, float] = field(default_factory=dict)


class Observation(NamedTuple):
    """What one poll found for one play."""

    state: str                  # playing, paused, buffering, not started,
                                # nothing playing, or one of _FINAL_STATES
    session: Any                # the session described, or None
    position: Optional[int]     # ms, while the play is on
    paused_for: Optional[float]  # seconds seen paused, while paused
    target: Optional[Target]    # the play's end point; None when idle


class Clock(NamedTuple):
    """Time and randomness, passed in so the loop can be tested instantly."""

    now: Callable[[], float]
    sleep: Callable[[float], None]
    uniform: Callable[[float, float], float]


_SYSTEM_CLOCK = Clock(time.monotonic, time.sleep, random.uniform)


# --- where a play ends -----------------------------------------------------

def _credits_markers(item: Any) -> List[Tuple[int, bool]]:
    """(start ms, final) for every credits marker the item carries.

    Read from the XML plexapi already holds in ``_data``, as records does for
    media: ``markers`` is a cached_data_property, and on an item with none it
    satisfies plexapi's reload condition and costs a request of its own.
    """
    data = getattr(item, "_data", None)
    if data is None:
        return []
    return [
        (int(marker.get("startTimeOffset") or 0),
         marker.get("final") in ("1", "true"))
        for marker in data.findall("Marker")
        if marker.get("type") == "credits"
    ]


def _credits_start(markers: Sequence[Tuple[int, bool]]) -> Optional[int]:
    """Where the end credits start: the final marker, else the last one.

    A film with a mid-credits scene carries two credits markers, and Plex
    flags the one after the scene as final; waiting for that one does not
    cut the scene off.
    """
    if not markers:
        return None
    finals = [start for start, final in markers if final]
    return max(finals) if finals else max(start for start, _ in markers)


def _target_position(
    duration: Optional[int], credits_at: Optional[int], offset: int
) -> Optional[int]:
    """The playback position, in ms, at which the wait is over.

    A negative offset moves the point that many seconds earlier. A positive
    one leaves it alone: it is a sleep taken after the wait, not a position,
    since there is no playback left to watch once the video has ended.
    """
    anchor = credits_at if credits_at is not None else duration
    if anchor is None:
        return None
    return max(0, anchor + min(offset, 0) * 1000)


def _make_target(item: Any, args: argparse.Namespace) -> Target:
    """Work out the ending point for a video, from its item or its session."""
    duration = vars(item).get("duration") or None
    credits_at = (None if args.no_credits
                  else _credits_start(_credits_markers(item)))
    return Target(
        rating_key=int(item.ratingKey),
        title=display_title(item),
        duration=duration,
        credits=credits_at,
        position=_target_position(duration, credits_at, args.offset),
    )


def _target_for(
    plex: PlexServer, session: Any, targets: Dict[int, Target],
    args: argparse.Namespace,
) -> Target:
    """A session's end point, fetching each video's markers only once.

    An item the server will not return - a remote or live one - falls back
    to what the session itself says, rather than ending a wait over every
    session because one of them is unusual.
    """
    key = int(session.ratingKey)
    if key not in targets:
        item = find_item(plex, key, markers=True)
        targets[key] = _make_target(item if item is not None else session, args)
    return targets[key]


# --- judging a play --------------------------------------------------------

def _user_of(session: Any) -> str:
    """The name of the user a session belongs to."""
    names = getattr(session, "usernames", None) or []
    return clean_text(names[0]) if names else ""


def _player_state(session: Any) -> str:
    """playing, paused, or buffering, as the player reports it."""
    players = getattr(session, "players", None) or []
    return clean_text(getattr(players[0], "state", "") or "") if players else ""


def _play_id(session: Any) -> _PlayId:
    """What identifies one play: the session, and the video it is on."""
    return getattr(session, "sessionKey", None), int(session.ratingKey)


def _paused_for(
    pauses: Dict[_PlayId, float], play: _PlayId, paused: bool, now: float
) -> Optional[float]:
    """Seconds this play has been seen paused without a break, or None.

    Plex does not say when a pause began, so the count starts at the first
    poll that sees it; any other state starts it again from nothing.
    """
    if not paused:
        pauses.pop(play, None)
        return None
    return now - pauses.setdefault(play, now)


def _assess(
    session: Any, target: Target, pauses: Dict[_PlayId, float], now: float,
    args: argparse.Namespace,
) -> Observation:
    """Judge one session on the video it is playing."""
    position = int(getattr(session, "viewOffset", 0) or 0)
    state = _player_state(session) or "playing"
    paused_for = _paused_for(pauses, _play_id(session), state == "paused", now)
    if target.position is not None and position >= target.position:
        state = "reached"
    elif (args.paused is not None and paused_for is not None
          and round(paused_for, 3) >= args.paused):
        # Rounded to the millisecond: a sleep timed to land on the deadline
        # must count as having reached it, float arithmetic notwithstanding.
        state = "left paused"
    return Observation(state, session, position, paused_for, target)


# --- polling cadence -------------------------------------------------------

def _in_fast_window(position: Optional[int], target: Optional[int]) -> bool:
    """True within _FAST_WINDOW_MS of the target, or past it."""
    if position is None or target is None:
        return False
    return position >= target - _FAST_WINDOW_MS


def _next_delay(
    fast: bool,
    until_next: Optional[float],
    args: argparse.Namespace,
    uniform: Callable[[float, float], float],
) -> float:
    """Seconds to sleep before the next poll, jittered by up to _JITTER.

    A slow delay is cut short at *until_next*, the moment some play next
    needs a look, so a long --interval cannot sleep straight past it.
    """
    base = args.fast_interval if fast else args.interval
    delay = base + uniform(-base * _JITTER, base * _JITTER)
    if not fast and until_next is not None:
        delay = min(delay, max(until_next, args.fast_interval))
    return delay


def _wake_points(observation: Observation, args: argparse.Namespace) -> List[float]:
    """Seconds from now when a play next needs a look.

    That is where its fast window starts, and where an allowed pause runs
    out; either can come sooner than the next slow poll.
    """
    points: List[float] = []
    target = observation.target
    if (observation.position is not None and target is not None
            and target.position is not None):
        points.append(
            (target.position - _FAST_WINDOW_MS - observation.position) / 1000
        )
    if args.paused is not None and observation.paused_for is not None:
        points.append(args.paused - observation.paused_for)
    return points


def _delay_after(
    observations: Sequence[Observation], args: argparse.Namespace,
    uniform: Callable[[float, float], float],
) -> float:
    """The pause before the poll that follows these observations.

    Fast as soon as any unfinished play is near its end point; otherwise slow,
    but never past the moment the soonest of them needs a look.
    """
    pending = [o for o in observations if o.state not in _FINAL_STATES]
    fast = any(
        _in_fast_window(o.position, o.target.position if o.target else None)
        for o in pending
    )
    points = [point for o in pending for point in _wake_points(o, args)]
    return _next_delay(fast, min(points) if points else None, args, uniform)


# --- reading the sessions --------------------------------------------------

def _poll(plex: PlexServer) -> Optional[List[Any]]:
    """The active sessions, or None when the server could not be read."""
    try:
        return list(plex.sessions())
    except (RequestException, PlexApiException) as exc:
        LOG.warning("Could not read the active sessions (%s); will retry.", exc)
        return None


def _read_sessions(
    plex: PlexServer, args: argparse.Namespace, clock: Clock
) -> List[Any]:
    """The active sessions, retrying a failed read a slow interval later.

    Gives up with an error after _MAX_FAILED_POLLS failures in a row.
    """
    for attempt in range(1, _MAX_FAILED_POLLS + 1):
        sessions = _poll(plex)
        if sessions is not None:
            return sessions
        if attempt < _MAX_FAILED_POLLS:
            clock.sleep(_next_delay(False, None, args, clock.uniform))
    sys.exit(
        f"Could not read the active sessions {_MAX_FAILED_POLLS} times in a "
        "row; giving up on the wait."
    )


# --- reporting -------------------------------------------------------------

def _seconds(milliseconds: Optional[int]) -> Optional[int]:
    """Milliseconds as whole seconds, keeping None as None."""
    return None if milliseconds is None else milliseconds // 1000


def _clock_text(seconds: Optional[int]) -> str:
    """Seconds as H:MM:SS or M:SS."""
    return format_duration(None if seconds is None else seconds * 1000)


def _remaining(observation: Observation, args: argparse.Namespace) -> Optional[int]:
    """Estimated seconds until the play is over, offset sleep included.

    A paused play under --paused ends when its pause runs out if nothing
    changes, since its position is not moving towards anything.
    """
    tail = max(args.offset, 0)
    if observation.state in _FINAL_STATES:
        return tail
    if args.paused is not None and observation.paused_for is not None:
        return max(0, int(args.paused - observation.paused_for)) + tail
    target = observation.target
    if observation.position is None or target is None or target.position is None:
        return None
    return max(0, (target.position - observation.position) // 1000) + tail


def _record(
    observation: Observation, args: argparse.Namespace, elapsed: float
) -> Dict[str, Any]:
    """One play's progress. Every record carries every key, for CSV's sake."""
    session, target = observation.session, observation.target
    return {
        "user": _user_of(session) if session is not None else "",
        "sessionKey": getattr(session, "sessionKey", None),
        "playing": display_title(session) if session is not None else "",
        "waitingFor": target.title if target else "",
        "ratingKey": target.rating_key if target else None,
        "state": observation.state,
        "position": _seconds(observation.position),
        "duration": _seconds(target.duration) if target else None,
        "target": _seconds(target.position) if target else None,
        "pausedFor": (None if observation.paused_for is None
                      else int(observation.paused_for)),
        "elapsed": int(elapsed),
        "remaining": _remaining(observation, args),
    }


def _progress_text(record: Dict[str, Any]) -> str:
    """The playback column: position and length, or why there is none."""
    position, state = record["position"], record["state"]
    if position is None:
        return state
    text = _clock_text(position)
    if record["duration"]:
        text = f"{text} / {_clock_text(record['duration'])}"
    if state == "playing":
        return text
    if state == "paused" and record["pausedFor"] is not None:
        return f"{text} paused {_clock_text(record['pausedFor'])}"
    return f"{text} {state}"


def _remaining_text(record: Dict[str, Any]) -> str:
    """The estimate column."""
    if record["state"] in _FINAL_STATES:
        return "done"
    if record["remaining"] is None:
        return "-"
    return f"~{_clock_text(record['remaining'])} left"


def _progress_line(record: Dict[str, Any]) -> str:
    """One play as a line: user, playing, waited for, progress, times."""
    return " | ".join([
        record["user"] or "(nobody)",
        f"playing: {record['playing'] or '(nothing)'}",
        f"waiting for: {record['waitingFor'] or '(anything new)'}",
        _progress_text(record),
        f"waited {_clock_text(record['elapsed'])}",
        _remaining_text(record),
    ])


def _report(record: Dict[str, Any], args: argparse.Namespace, first: bool) -> None:
    """Emit one record in the selected format; *first* heads a CSV stream."""
    if output_format(args) == "table":
        print(_progress_line(record), flush=True)
    else:
        stream_record(record, args, first)


def _say(text: str, args: argparse.Namespace) -> None:
    """A status line: part of the display for a table, a log line otherwise.

    Machine-readable output carries the records alone, so anything else goes
    to the log and stays off stdout.
    """
    if output_format(args) == "table":
        print(text, flush=True)
    else:
        LOG.info("%s", text)


def _ending_clauses(args: argparse.Namespace) -> str:
    """The parts of an opening line that --paused and --offset add."""
    text = ""
    if args.paused is not None:
        text += f", or to sit paused for {_clock_text(args.paused)}"
    if args.offset > 0:
        text += f", then {args.offset}s more"
    return text


def _describe_wait(target: Target, follow: Follow, args: argparse.Namespace) -> str:
    """The opening line naming the video and where the wait will end."""
    who = f" ({follow.user})" if follow.user else ""
    if target.position is None:
        point = "to stop"
    elif target.credits is not None:
        point = f"to reach the credits at {_clock_text(_seconds(target.credits))}"
    else:
        point = f"to reach the end at {_clock_text(_seconds(target.duration))}"
    if args.offset < 0 and target.position is not None:
        point += (f", ending {-args.offset}s early at "
                  f"{_clock_text(_seconds(target.position))}")
    return f'Waiting for "{target.title}"{who} {point}{_ending_clauses(args)}.'


def _describe_all(args: argparse.Namespace) -> str:
    """The opening line for --all."""
    point = "its end" if args.no_credits else "its credits, or its end"
    if args.offset < 0:
        point += f", less {-args.offset}s"
    return (f"Waiting for every play to reach {point}{_ending_clauses(args)}; "
            "then checking once more for anything new.")


# --- following one play ----------------------------------------------------

def _choose_session(sessions: Sequence[Any], args: argparse.Namespace) -> Any:
    """The session the wait starts from, or None.

    --session names it outright. Otherwise --rating-key prefers a session
    already playing that video, whoever it belongs to; failing that, and
    without --rating-key, the first session listed is taken.
    """
    if args.session_key is not None:
        for session in sessions:
            if getattr(session, "sessionKey", None) == args.session_key:
                return session
        active = ", ".join(
            f"{getattr(s, 'sessionKey', '?')} ({_user_of(s)})" for s in sessions
        ) or "none"
        sys.exit(
            f"No active session has sessionKey {args.session_key}. Active "
            f"sessions: {active}. See status --section sessions."
        )
    if args.rating_key is not None:
        return next(
            (s for s in sessions if int(s.ratingKey) == args.rating_key), None
        )
    return sessions[0] if sessions else None


def _start(
    plex: PlexServer, args: argparse.Namespace
) -> Optional[Tuple[Target, Follow]]:
    """What to wait for and whom to follow, or None when nothing is playing."""
    chosen = _choose_session(list(plex.sessions()), args)
    if chosen is None and args.rating_key is None:
        return None

    rating_key = (args.rating_key if args.rating_key is not None
                  else int(chosen.ratingKey))
    playing_it = chosen is not None and int(chosen.ratingKey) == rating_key
    # --session pins the user even before the video starts; otherwise the
    # user is bound only once somebody is actually seen playing it.
    bound = chosen is not None and (playing_it or args.session_key is not None)
    follow = Follow(
        user=_user_of(chosen) if bound else None,
        session_key=getattr(chosen, "sessionKey", None) if bound else None,
        seen=playing_it,
    )
    return _make_target(fetch_item(plex, rating_key, markers=True), args), follow


def _locate(sessions: Sequence[Any], follow: Follow, rating_key: int) -> Any:
    """The followed user's session playing the video, or None.

    The original session is preferred when it is still there; otherwise any
    of that user's sessions playing it will do, since stopping and starting
    again gives the same play a new sessionKey.
    """
    matches = [
        session for session in sessions
        if int(session.ratingKey) == rating_key
        and (follow.user is None or _user_of(session) == follow.user)
    ]
    for session in matches:
        if getattr(session, "sessionKey", None) == follow.session_key:
            return session
    return matches[0] if matches else None


def _context(sessions: Sequence[Any], follow: Follow) -> Any:
    """The session to describe while the video waited for is not on."""
    if follow.user is None:
        return sessions[0] if sessions else None
    return next((s for s in sessions if _user_of(s) == follow.user), None)


def _observe(
    sessions: Sequence[Any], target: Target, follow: Follow, now: float,
    args: argparse.Namespace,
) -> Observation:
    """Classify one poll, binding *follow* to the session once it is seen."""
    located = _locate(sessions, follow, target.rating_key)
    if located is None:
        state = "stopped" if follow.seen else "not started"
        return Observation(state, _context(sessions, follow), None, None, target)

    follow.user = _user_of(located)
    follow.session_key = getattr(located, "sessionKey", None)
    follow.seen = True
    return _assess(located, target, follow.pauses, now, args)


def _wait_loop(
    plex: PlexServer,
    target: Target,
    follow: Follow,
    args: argparse.Namespace,
    clock: Clock,
) -> Observation:
    """Poll until the play is over and return the observation that ended it.

    With --now, the first poll also ends it when the video is not playing.
    """
    started = clock.now()
    first = True
    while True:
        sessions = _read_sessions(plex, args, clock)
        now = clock.now()
        observation = _observe(sessions, target, follow, now, args)
        _report(_record(observation, args, now - started), args, first)
        if observation.state in _FINAL_STATES:
            return observation
        if first and args.now and observation.state == "not started":
            return observation
        first = False
        clock.sleep(_delay_after([observation], args, clock.uniform))


def _conclude(
    observation: Observation, target: Target, args: argparse.Namespace
) -> bool:
    """Say how the play ended; False when --now gave up on it instead."""
    if observation.state == "not started":
        _say(f'"{target.title}" is not playing; not waiting for it (--now).', args)
        return False
    how = {
        "reached": "reached its end point",
        "stopped": "stopped",
        "left paused": f"sat paused for {_clock_text(args.paused)}",
    }[observation.state]
    _say(f'"{target.title}" {how}.', args)
    return True


def _wait_one(plex: PlexServer, args: argparse.Namespace, clock: Clock) -> bool:
    """Wait for one play; False when there was nothing to wait for."""
    started = _start(plex, args)
    if started is None:
        print("Nothing is playing, so there is nothing to wait for.",
              file=sys.stderr)
        return False
    target, follow = started
    _say(_describe_wait(target, follow, args), args)
    observation = _wait_loop(plex, target, follow, args, clock)
    return _conclude(observation, target, args)


# --- waiting for everything ------------------------------------------------

def _gone(
    previous: Dict[_PlayId, Observation], current: Sequence[Observation]
) -> List[Observation]:
    """Plays seen last poll that are gone now, each reported once as stopped."""
    present = {_play_id(o.session) for o in current}
    return [
        Observation("stopped", seen.session, None, None, seen.target)
        for play, seen in previous.items() if play not in present
    ]


def _wait_all(plex: PlexServer, args: argparse.Namespace, clock: Clock) -> None:
    """Poll until no play is left, confirmed by a second poll an interval on.

    Every session is judged on its own video each poll, so a play started
    while waiting - by anyone, or by autoplay - is simply one more to wait
    for. Nothing left to wait for twice running ends it.
    """
    started = clock.now()
    targets: Dict[int, Target] = {}
    pauses: Dict[_PlayId, float] = {}
    previous: Dict[_PlayId, Observation] = {}
    confirming = False
    first = True
    while True:
        sessions = _read_sessions(plex, args, clock)
        now = clock.now()
        current = [
            _assess(s, _target_for(plex, s, targets, args), pauses, now, args)
            for s in sessions
        ]
        shown = _gone(previous, current) + current
        previous = {_play_id(o.session): o for o in current}
        for play in [p for p in pauses if p not in previous]:
            del pauses[play]

        for observation in shown or [
                Observation("nothing playing", None, None, None, None)]:
            _report(_record(observation, args, now - started), args, first)
            first = False

        if any(o.state not in _FINAL_STATES for o in current):
            confirming = False
            clock.sleep(_delay_after(current, args, clock.uniform))
            continue
        if confirming:
            return
        confirming = True
        _say("Nothing left to wait for; checking once more for anything new.",
             args)
        clock.sleep(_next_delay(False, None, args, clock.uniform))


# --- the command -----------------------------------------------------------

def _check_arguments(args: argparse.Namespace) -> None:
    """Refuse combinations that cannot mean anything."""
    chosen_format = output_format(args)
    if chosen_format not in STREAMABLE_FORMATS:
        sys.exit(
            f"--format {chosen_format} cannot report a poll at a time: "
            "Import-Clixml reads one whole document. Use json, which "
            "ConvertFrom-Json reads a line at a time, or yaml or csv."
        )
    if args.now and args.rating_key is None:
        sys.exit(
            "--now only applies with --rating-key: without one, the video "
            "waited for is the one already playing."
        )
    if args.all and (args.session_key is not None or args.rating_key is not None):
        sys.exit(
            "--all waits for every session, so it takes neither --session "
            "nor --rating-key."
        )


def cmd_wait(plex: PlexServer, args: argparse.Namespace) -> None:
    """Sleep until a session's current play, or every play, is over."""
    _check_arguments(args)
    try:
        if args.all:
            _say(_describe_all(args), args)
            _wait_all(plex, args, _SYSTEM_CLOCK)
            _say("Nothing is left playing, and nothing new has started.", args)
        elif not _wait_one(plex, args, _SYSTEM_CLOCK):
            return
        if args.offset > 0:
            _say(f"Sleeping {args.offset}s more (--offset).", args)
            _SYSTEM_CLOCK.sleep(args.offset)
    except KeyboardInterrupt:
        # Non-zero, so `plexdo wait && ...` does not run what was meant to
        # follow a play that has not in fact ended.
        print("\nInterrupted before the play was over.", file=sys.stderr)
        sys.exit(130)


def _seconds_argument(text: str) -> float:
    """argparse type for an interval: a number of seconds above zero."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"not a number of seconds: {text!r}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be above 0 seconds, got {text}")
    return value


def _paused_argument(text: str) -> int:
    """argparse type for --paused: whole seconds, zero or more."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"not a whole number of seconds: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"cannot be negative, got {text}")
    return value


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the wait subparser."""
    parser = sub.add_parser(
        "wait", parents=parents,
        help="Sleep until a session's current play is over.",
        description=(
            "Sleep until a session's current play is over: the start of its "
            "end credits when the video has a credits marker, and its end "
            "otherwise. The wait also ends as soon as the video stops "
            "playing. Exits 0 once over, and 130 if interrupted, so "
            "`plexdo wait && ...` runs what follows only after the play."
        ),
    )
    parser.add_argument(
        "-s", "--session", dest="session_key", type=int, default=None,
        metavar="KEY",
        help=(
            "Follow the session with this sessionKey instead of the first "
            "one listed. Obtain it with status --section sessions."
        ),
    )
    parser.add_argument(
        "-r", "--rating-key", dest="rating_key", type=int, default=None,
        metavar="KEY",
        help=(
            "Wait for this video rather than whatever is playing. Without "
            "--session, whichever session plays it is followed. If it is not "
            "playing, the wait lasts until it starts (see --now)."
        ),
    )
    parser.add_argument(
        "-a", "--all", action="store_true", default=False,
        help=(
            "Wait for every play by every user, each judged as one play "
            "would be. Ends only when two polls an interval apart both find "
            "nothing left, so a play started meanwhile - autoplay included - "
            "is waited for too. Takes neither --session nor --rating-key."
        ),
    )
    parser.add_argument(
        "-i", "--interval", type=_seconds_argument, default=10.0,
        metavar="SECONDS",
        help="Seconds between polls, varied by up to 20%% either way "
             "(default: 10).",
    )
    parser.add_argument(
        "--fast-interval", type=_seconds_argument, default=1.0,
        metavar="SECONDS",
        help=(
            "Seconds between polls from 30 seconds before the end point on, "
            "likewise varied by up to 20%% (default: 1)."
        ),
    )
    parser.add_argument(
        "--no-credits", action="store_true", default=False,
        help="Ignore the end credits marker and wait for the video to end.",
    )
    parser.add_argument(
        "--offset", type=int, default=0, metavar="SECONDS",
        help=(
            "Signed seconds. Negative ends the wait that long before the "
            "credits marker, or the end; positive sleeps that long once the "
            "wait is over."
        ),
    )
    parser.add_argument(
        "--paused", type=_paused_argument, default=None, metavar="SECONDS",
        help=(
            "Count a play as over once its player has sat paused this many "
            "seconds, counted from the first poll that sees the pause; 0 "
            "ends it at the first sight of one."
        ),
    )
    parser.add_argument(
        "--now", action="store_true", default=False,
        help=(
            "With --rating-key: if that video is not playing, exit 0 at once "
            "instead of waiting for it to start."
        ),
    )


COMMANDS = {"wait": cmd_wait}

REQUIRES_PLEX = frozenset(COMMANDS)
