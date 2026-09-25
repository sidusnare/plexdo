# SPDX-License-Identifier: GPL-3.0-or-later

"""Creating one playlist for many users: targets, and surviving a bad one."""

import pytest

from conftest import FakeItem, FakePlaylist, FakePlex
from plexdo.accounts import UserAccessError
from plexdo.fanout import _create_for_one, _targets, report_line, run_per_user
from plexdo.playlists import create_for_user

ITEMS = [FakeItem(1, "A"), FakeItem(2, "B")]
ROSTER = [(0, "admin"), (3, "Alice"), (5, "Bob")]


@pytest.fixture
def target_args(args):
    """The global flags plus the two target flags, both unset."""
    args.dest_user_id, args.all_users, args.throttle = None, False, 0
    return args


@pytest.fixture
def roster(monkeypatch):
    """Stand in for the one plex.tv round trip the roster costs."""
    monkeypatch.setattr("plexdo.fanout.user_roster", lambda plex: list(ROSTER))


def raising(exc):
    """A server_for_user that always fails the way exc describes."""
    def fail(plex, user_id):
        raise exc
    return fail


# --- choosing the targets ------------------------------------------------

def test_neither_flag_means_the_account_the_items_came_from(target_args):
    """None keeps every build command's existing behaviour, and costs no call."""
    assert _targets(None, target_args) is None


def test_all_users_targets_the_whole_roster(target_args, roster):
    target_args.all_users = True
    assert _targets(object(), target_args) == ROSTER


def test_a_single_user_is_labelled_from_the_roster(target_args, roster):
    target_args.dest_user_id = 5
    assert _targets(object(), target_args) == [(5, "Bob")]


def test_an_unknown_user_falls_back_to_its_id(target_args, roster):
    """server_for_user raises the precise error; labelling must not pre-empt it."""
    target_args.dest_user_id = 42
    assert _targets(object(), target_args) == [(42, "42")]


# --- one bad user must not end the run -----------------------------------

def test_an_unreachable_user_is_skipped_rather_than_fatal(target_args, monkeypatch):
    monkeypatch.setattr(
        "plexdo.fanout.server_for_user",
        raising(UserAccessError("chapter and verse", "nothing is shared")),
    )
    record = _create_for_one(None, (7, "Cara"), "Mix", ITEMS, target_args)
    assert record["status"] == "skipped"
    assert record["detail"] == "nothing is shared"
    assert record["playlist"] == ""


def test_any_other_failure_is_recorded_as_failed(target_args, monkeypatch):
    monkeypatch.setattr(
        "plexdo.fanout.server_for_user", raising(RuntimeError("500 from Plex")),
    )
    record = _create_for_one(None, (9, "Dan"), "Mix", ITEMS, target_args)
    assert (record["status"], record["detail"]) == ("failed", "500 from Plex")


def test_the_run_continues_past_a_failing_user(target_args):
    def action(target):
        status = "failed" if target[0] == 3 else "created"
        return {"user": target[1], "id": target[0], "status": status,
                "playlist": "Mix", "detail": ""}

    records = run_per_user(ROSTER, ("Mix", ITEMS), target_args, action)
    assert [r["status"] for r in records] == ["created", "failed", "created"]


def test_a_report_line_names_the_user_and_the_reason():
    line = report_line({"user": "Bob", "id": 5, "status": "skipped",
                        "playlist": "", "detail": "already exists"})
    assert "skipped" in line and "Bob" in line and "already exists" in line


# --- per-user creation reports instead of exiting ------------------------

def test_a_taken_name_is_a_skip_and_touches_nothing(args):
    """A sys.exit here would end a run that still has other users to serve."""
    plex = FakePlex(playlists=[FakePlaylist("Mix")])
    status, detail = create_for_user(plex, "Mix", ITEMS, args)
    assert status == "skipped"
    assert "--overwrite" in detail
    assert plex.created == [] and not plex.playlists()[0].deleted


def test_overwrite_lets_a_per_user_create_replace(args):
    args.overwrite = True
    plex = FakePlex(playlists=[FakePlaylist("Mix")])
    assert create_for_user(plex, "Mix", ITEMS, args) == ("replaced", "")
    assert plex.created == [("Mix", ITEMS)]
    assert plex.playlists()[0].deleted


def test_a_free_name_is_created(args):
    plex = FakePlex()
    assert create_for_user(plex, "Mix", ITEMS, args) == ("created", "")
    assert plex.created == [("Mix", ITEMS)]
