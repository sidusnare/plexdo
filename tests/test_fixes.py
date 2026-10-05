# SPDX-License-Identifier: GPL-3.0-or-later

"""Regressions: each test pins a bug that shipped, so it cannot come back."""

import argparse
import datetime
import json
import os
import xml.etree.ElementTree as ET

import pytest
from plexapi.exceptions import NotFound
from plexapi.video import Episode, Movie

from conftest import FakeItem, FakePlex
from plexdo.airdates import _date_label, prompt_for_date
from plexdo.commands import auth, copy, missing
from plexdo.constants import CONFIG_EXAMPLE
from plexdo.playlists import resolve_playlist
from plexdo.titles import fetch_show


def movie(**attributes):
    """A real plexapi Movie, built offline from XML."""
    attributes.setdefault("type", "movie")
    attributes.setdefault("ratingKey", "881")
    return Movie(None, ET.Element("Video", {k: str(v) for k, v in attributes.items()}))


def episode(**attributes):
    """A real plexapi Episode, built offline from XML."""
    attributes.setdefault("type", "episode")
    attributes.setdefault("ratingKey", "4180")
    return Episode(None, ET.Element("Video", {k: str(v) for k, v in attributes.items()}))


def answers(monkeypatch, *replies):
    """Feed input() these replies in turn, then end of input."""
    queue = list(replies)

    def fake_input(_prompt):
        if not queue:
            raise EOFError
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)


class Unknown:
    """A server that has no item at all."""

    def fetchItem(self, key):
        raise NotFound(f"no item {key}")


# --- build-chronological asks for a missing date, film or episode --------

def test_a_film_without_a_date_is_asked_for_one(monkeypatch):
    """This used to crash: the prompt read episode-only attributes."""
    answers(monkeypatch, "1995-12-15")
    assert prompt_for_date(movie(title="Heat", year=1995), None) == \
        datetime.datetime(1995, 12, 15)


def test_an_invalid_date_is_asked_for_again(monkeypatch, capsys):
    answers(monkeypatch, "15/12/1995", "1995-12-15")
    assert prompt_for_date(movie(title="Heat"), None).year == 1995
    assert "YYYY-MM-DD" in capsys.readouterr().out


def test_running_out_of_input_ends_cleanly(monkeypatch):
    """A script with no terminal must get a reason, not a traceback."""
    answers(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        prompt_for_date(movie(title="Heat", year=1995), None)
    assert "Heat (1995)" in str(exc.value)


def test_a_film_is_named_by_title_and_year():
    assert _date_label(movie(title="Heat", year=1995)) == "Heat (1995)"
    assert _date_label(movie(title="Heat")) == "Heat"


def test_an_episode_without_a_number_can_still_be_named():
    """seasonNumber or index missing used to crash the :02d format."""
    unnumbered = episode(title="Pilot", grandparentTitle="The Wire",
                         parentIndex=1)
    assert _date_label(unnumbered) == "The Wire S01E?? - Pilot"


# --- the config template is complete --------------------------------------

def test_the_template_keeps_its_per_user_heading():
    """A missing quote once turned this line into a Python comment."""
    assert ("# Per-user credentials, one section per user ID (see `plexdo\n"
            "# list-users`).") in CONFIG_EXAMPLE


# --- write-config-example never clobbers unasked -----------------------------

@pytest.fixture
def config(monkeypatch, tmp_path):
    """Point the command at a config path inside a temporary directory."""
    path = tmp_path / "etc" / "plexdo.ini"
    monkeypatch.setattr(auth, "CONFIG_PATH", path)
    return path


def write_example(**flags):
    args = argparse.Namespace(overwrite=False, dry_run=False)
    vars(args).update(flags)
    auth.cmd_write_config_example(None, args)


def test_an_existing_config_is_refused_and_left_alone(config):
    config.parent.mkdir()
    config.write_text("[plex]\nurl = http://mine\n")
    with pytest.raises(SystemExit) as exc:
        write_example()
    assert "--overwrite" in str(exc.value)
    assert config.read_text() == "[plex]\nurl = http://mine\n"


def test_overwrite_replaces_an_existing_config(config):
    config.parent.mkdir()
    config.write_text("old")
    write_example(overwrite=True)
    assert config.read_text() == CONFIG_EXAMPLE


def test_dry_run_writes_nothing(config):
    write_example(dry_run=True)
    assert not config.exists()


def test_dry_run_still_refuses_what_the_real_run_would(config):
    config.parent.mkdir()
    config.write_text("old")
    with pytest.raises(SystemExit):
        write_example(dry_run=True)


def test_a_new_config_is_written_private(config):
    write_example()
    assert config.read_text() == CONFIG_EXAMPLE
    if os.name != "nt":
        assert config.stat().st_mode & 0o777 == 0o600


# --- find-missing keeps machine-readable output parseable -----------------

def find_missing_args(fmt):
    return argparse.Namespace(format=fmt, seasons=None, all_shows=True,
                              show=None, library_id=None,
                              include_specials=False)


def test_no_gaps_is_an_empty_list_in_json(monkeypatch, capsys):
    monkeypatch.setattr(missing, "_scan_libraries", lambda plex, args: [])
    missing.cmd_find_missing(None, find_missing_args("json"))
    assert json.loads(capsys.readouterr().out) == []


def test_no_gaps_is_still_a_sentence_in_a_table(monkeypatch, capsys):
    monkeypatch.setattr(missing, "_scan_libraries", lambda plex, args: [])
    missing.cmd_find_missing(None, find_missing_args("table"))
    assert capsys.readouterr().out.strip() == "No gaps found."


# --- copy-playlist-to-user emits one document ------------------------------

class Source:
    """A playlist to copy from."""

    title = "Movie Night"

    def items(self):
        return [FakeItem(1, "A"), FakeItem(2, "B")]


def test_copy_to_user_is_a_single_json_document(monkeypatch, capsys):
    """The item list and the outcome used to be two documents in a row."""
    target = FakePlex()
    monkeypatch.setattr(copy, "server_for_user", lambda plex, uid: target)
    monkeypatch.setattr(copy, "resolve_playlist", lambda plex, name: Source())
    args = argparse.Namespace(
        format="json", dry_run=False, overwrite=False, source_user_id=0,
        source_playlist="Movie Night", user_id=7, dest="Movie Night",
    )
    copy.cmd_copy_playlist_to_user(None, args)
    record = json.loads(capsys.readouterr().out)
    assert (record["status"], record["playlist"]) == ("created", "Movie Night")
    assert [(name, len(items)) for name, items in target.created] == \
        [("Movie Night", 2)]


# --- unknown keys end with a message, not a traceback ----------------------

def test_an_unknown_playlist_ratingkey_is_a_clean_error():
    with pytest.raises(SystemExit) as exc:
        resolve_playlist(Unknown(), "9999")
    assert "9999" in str(exc.value)


def test_an_unknown_show_ratingkey_is_a_clean_error():
    with pytest.raises(SystemExit) as exc:
        fetch_show(Unknown(), 4102)
    assert "4102" in str(exc.value)
