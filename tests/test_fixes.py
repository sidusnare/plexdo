# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Regressions: each test pins a bug that shipped, so it cannot come back."""

import argparse
import datetime
import json
import os
import xml.etree.ElementTree as ET

import pytest
import requests
from plexapi.exceptions import BadRequest, NotFound, Unauthorized
from plexapi.video import Episode, Movie, Show

from conftest import FakeItem, FakePlaylist, FakePlex
from plexdo import cli, photos
from plexdo.airdates import _date_label, prompt_for_date
from plexdo.commands import (
    auth,
    build,
    copy,
    missing,
    playlists,
    rescan,
    search,
    users,
)
from plexdo.constants import CONFIG_EXAMPLE
from plexdo.playlists import resolve_playlist
from plexdo.titles import as_rating_key, fetch_show


def movie(**attributes):
    """A real plexapi Movie, built offline from XML."""
    attributes.setdefault("type", "movie")
    attributes.setdefault("ratingKey", "881")
    return Movie(
        None, ET.Element("Video", {k: str(v) for k, v in attributes.items()})
    )


def episode(**attributes):
    """A real plexapi Episode, built offline from XML."""
    attributes.setdefault("type", "episode")
    attributes.setdefault("ratingKey", "4180")
    return Episode(
        None, ET.Element("Video", {k: str(v) for k, v in attributes.items()})
    )


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


# --- playlist-build -C asks for a missing date, film or episode --------


def test_a_film_without_a_date_is_asked_for_one(monkeypatch):
    """This used to crash: the prompt read episode-only attributes."""
    answers(monkeypatch, "1995-12-15")
    assert prompt_for_date(
        movie(title="Heat", year=1995), None
    ) == datetime.datetime(1995, 12, 15)


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
    """SeasonNumber or index missing used to crash the :02d format."""
    unnumbered = episode(
        title="Pilot", grandparentTitle="The Wire", parentIndex=1
    )
    assert _date_label(unnumbered) == "The Wire S01E?? - Pilot"


# --- the config template is complete --------------------------------------


def test_the_template_keeps_its_users_heading():
    """A missing quote once turned this line into a Python comment."""
    prose = " ".join(line.lstrip("# ") for line in CONFIG_EXAMPLE.splitlines())
    assert (
        "Other plex.tv accounts plexdo may act as, keyed by user id as "
        "`plexdo users-list` shows it."
    ) in prose


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


# --- missing-find keeps machine-readable output parseable -----------------


def find_missing_args(fmt):
    return argparse.Namespace(
        format=fmt,
        seasons=None,
        all_shows=True,
        show=None,
        library_id=None,
        include_specials=False,
    )


def test_no_gaps_is_an_empty_list_in_json(monkeypatch, capsys):
    monkeypatch.setattr(missing, "_scan_libraries", lambda plex, args: [])
    missing.cmd_find_missing(None, find_missing_args("json"))
    assert json.loads(capsys.readouterr().out) == []


def test_no_gaps_is_still_a_sentence_in_a_table(monkeypatch, capsys):
    monkeypatch.setattr(missing, "_scan_libraries", lambda plex, args: [])
    missing.cmd_find_missing(None, find_missing_args("table"))
    assert capsys.readouterr().out.strip() == "No gaps found."


# --- playlist-copy --to emits one document ----------------------------------


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
        format="json",
        dry_run=False,
        overwrite=False,
        copy_to="one",
        source_user_id=0,
        source_playlist="Movie Night",
        user_id=7,
        dest="Movie Night",
    )
    copy.cmd_playlist_copy(None, args)
    record = json.loads(capsys.readouterr().out)
    assert (record["status"], record["playlist"]) == ("created", "Movie Night")
    assert [(name, len(items)) for name, items in target.created] == [
        ("Movie Night", 2)
    ]


# --- unknown keys end with a message, not a traceback ----------------------


def test_an_unknown_playlist_ratingkey_is_a_clean_error():
    with pytest.raises(SystemExit) as exc:
        resolve_playlist(Unknown(), "9999")
    assert "9999" in str(exc.value)


def test_an_unknown_show_ratingkey_is_a_clean_error():
    with pytest.raises(SystemExit) as exc:
        fetch_show(Unknown(), 4102)
    assert "4102" in str(exc.value)


# --- a request that fails ends with a message, not a traceback -------------


@pytest.mark.parametrize(
    "error,expected",
    [
        (
            requests.exceptions.ConnectionError("Connection refused"),
            "Could not reach Plex: Connection refused",
        ),
        (
            requests.exceptions.ReadTimeout("timed out"),
            "did not answer in time",
        ),
        (Unauthorized("(401) unauthorized\n<html>page</html>"), "plexdo login"),
        (BadRequest("(400) bad_request"), "Plex refused the request: (400)"),
    ],
)
def test_a_failed_request_is_a_clean_exit(monkeypatch, error, expected):
    def fail(_args):
        raise error

    monkeypatch.setattr(cli, "_run", fail)
    with pytest.raises(SystemExit) as exc:
        cli.main(["libraries-list"])
    message = str(exc.value)
    assert expected in message
    assert "<html>" not in message


def test_a_token_in_a_failed_url_is_not_shown(monkeypatch):
    def fail(_args):
        raise requests.exceptions.ConnectionError(
            "GET /library/parts/1/file.mkv?X-Plex-Token=sekrit-token-value"
        )

    monkeypatch.setattr(cli, "_run", fail)
    with pytest.raises(SystemExit) as exc:
        cli.main(["libraries-list"])
    assert "sekrit-token-value" not in str(exc.value)


# --- search: a library that cannot hold the type is not a failure ----------


class SearchSection:
    """A library that finds what it is given, or fails."""

    def __init__(self, title, stype, hits=(), error=None):
        self.title, self.type, self.key = title, stype, 1
        self._hits, self._error = list(hits), error
        self.asked = []

    def search(self, query, **kwargs):
        self.asked.append((query, kwargs))
        if self._error:
            raise self._error
        return self._hits


class SearchPlex:
    def __init__(self, *sections):
        self.library = self
        self._sections = list(sections)

    def sections(self):
        return self._sections

    def sectionByID(self, library_id):
        return self._sections[library_id]


def search_run(monkeypatch, plex, **options):
    monkeypatch.setattr(search, "server_for_user", lambda admin, uid: plex)
    args = argparse.Namespace(
        format="json", user_id=0, query="wire", media_type=None, library_id=None
    )
    vars(args).update(options)
    search.cmd_search(None, args)


def test_a_library_of_another_type_is_not_asked(monkeypatch, caplog, capsys):
    """Each used to answer "Unknown libtype", reported as a failed search."""
    movies = SearchSection("Movies", "movie", error=NotFound("Unknown libtype"))
    shows = SearchSection("TV", "show", hits=[FakeItem(5, "The Wire")])
    search_run(monkeypatch, SearchPlex(movies, shows), media_type="episode")
    assert not movies.asked
    assert shows.asked == [("wire", {"libtype": "episode"})]
    assert "failed" not in caplog.text
    assert json.loads(capsys.readouterr().out)[0]["ratingKey"] == 5


def test_a_failure_is_not_mentioned_when_something_was_found(
    monkeypatch, caplog, capsys
):
    broken = SearchSection("Old", "movie", error=RuntimeError("boom"))
    fine = SearchSection("Movies", "movie", hits=[FakeItem(5, "Wired")])
    search_run(monkeypatch, SearchPlex(broken, fine))
    assert "Search failed" not in caplog.text
    assert len(json.loads(capsys.readouterr().out)) == 1


def test_search_failed_is_said_when_nothing_came_back(
    monkeypatch, caplog, capsys
):
    broken = SearchSection("Old", "movie", error=RuntimeError("boom\nmore"))
    empty = SearchSection("Movies", "movie")
    search_run(monkeypatch, SearchPlex(broken, empty))
    assert "Search failed in library 'Old': boom" in caplog.text
    assert "more" not in caplog.text
    assert json.loads(capsys.readouterr().out) == []


def test_a_named_library_that_cannot_hold_the_type_is_an_error(monkeypatch):
    movies = SearchSection("Movies", "movie")
    with pytest.raises(SystemExit) as exc:
        search_run(
            monkeypatch, SearchPlex(movies), media_type="episode", library_id=0
        )
    assert "holds no episode items" in str(exc.value)
    assert not movies.asked


# --- playlist-build --append refuses a smart playlist cleanly --------------


class SmartPlaylist:
    title, smart = "Recently Added", True

    def addItems(self, items):
        raise BadRequest("Cannot add items to a smart playlist.")


def test_appending_to_a_smart_playlist_is_a_clean_error(monkeypatch):
    """Plexapi raised BadRequest, which reached the user as a traceback."""
    fetched = []

    class Server:
        def fetchItem(self, key):
            fetched.append(key)
            return FakeItem(key, "X")

    monkeypatch.setattr(build, "server_for_user", lambda plex, uid: Server())
    monkeypatch.setattr(
        build, "resolve_playlist", lambda plex, name: SmartPlaylist()
    )
    args = argparse.Namespace(
        format="json",
        dry_run=False,
        user_id=0,
        playlist="Recently Added",
        rating_keys=[5],
    )
    with pytest.raises(SystemExit) as exc:
        build._append(None, args)
    assert "is smart" in str(exc.value)
    assert not fetched


# --- rescan: an empty list, every library, and a rehearsal that speaks -----


class ScanSection:
    def __init__(self, key, title):
        self.key, self.title, self.updated = key, title, 0

    def update(self):
        self.updated += 1

    def cancelUpdate(self):
        pass


class ScanPlex:
    def __init__(self, *sections, activities=()):
        self.library, self.activities = self, list(activities)
        self._sections, self.updated_all = list(sections), 0

    def sections(self):
        return self._sections

    def sectionByID(self, library_id):
        return next(s for s in self._sections if s.key == library_id)

    def update(self):
        self.updated_all += 1


def rescan_run(plex, **options):
    args = argparse.Namespace(
        format="table",
        dry_run=False,
        status=False,
        now=False,
        all_libraries=False,
        library_id=None,
    )
    vars(args).update(options)
    rescan.cmd_rescan(plex, args)


def test_rescan_status_with_nothing_running_is_an_empty_document(capsys):
    """It printed prose in every format, which breaks whatever parses it."""
    rescan_run(ScanPlex(), status=True, format="json")
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert captured.err == ""
    rescan_run(ScanPlex(), status=True)
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "No active scan jobs.\n")


def test_rescan_all_asks_the_server_once_for_every_library(capsys):
    plex = ScanPlex(ScanSection(1, "Movies"), ScanSection(2, "TV"))
    rescan_run(plex, all_libraries=True)
    assert plex.updated_all == 1
    assert [s.updated for s in plex.sections()] == [0, 0]
    assert "all 2 libraries" in capsys.readouterr().out


def test_rescan_of_one_library_scans_only_it():
    movies, shows = ScanSection(1, "Movies"), ScanSection(2, "TV")
    plex = ScanPlex(movies, shows)
    rescan_run(plex, library_id=2)
    assert (movies.updated, shows.updated, plex.updated_all) == (0, 1, 0)


@pytest.mark.parametrize(
    "options,said",
    [
        ({"library_id": 1}, "would rescan library 'Movies'"),
        ({"all_libraries": True}, "would rescan all 1 libraries"),
        (
            {"library_id": 1, "now": True},
            "would cancel every pending scan, then rescan library 'Movies'",
        ),
    ],
)
def test_a_rescan_rehearsal_says_what_it_would_do(capsys, options, said):
    """It said nothing without --verbose, like a run with nothing to do."""
    section = ScanSection(1, "Movies")
    plex = ScanPlex(section)
    rescan_run(plex, dry_run=True, **options)
    assert said in capsys.readouterr().err
    assert (section.updated, plex.updated_all) == (0, 0)


@pytest.mark.parametrize(
    "argv,said",
    [
        (["rescan"], "use --all to rescan every library"),
        (["rescan", "Movies", "--all"], "give a library or --all, not both"),
    ],
)
def test_rescan_needs_a_library_or_all_and_not_both(argv, said, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.parse_arguments(cli.build_parser(), argv)
    assert exc.value.code == 2
    assert said in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv", [["rescan", "-a"], ["rescan", "Movies"], ["rescan", "-s"]]
)
def test_rescan_accepts_a_library_all_or_status(argv):
    assert cli.parse_arguments(cli.build_parser(), argv).command == "rescan"


# --- playlist-remove: a rehearsal that speaks -------------------------------


def test_a_removal_rehearsal_names_the_playlist_and_keeps_it(
    monkeypatch, capsys
):
    target = FakePlaylist("Old Mix", 9104)
    monkeypatch.setattr(playlists, "server_for_user", lambda plex, uid: None)
    monkeypatch.setattr(playlists, "resolve_playlist", lambda plex, n: target)
    args = argparse.Namespace(
        format="table", dry_run=True, user_id=0, playlist="9104"
    )
    playlists.cmd_remove_playlist(None, args)
    captured = capsys.readouterr()
    assert "would delete playlist 'Old Mix' (ratingKey 9104)" in captured.err
    assert not target.deleted
    args.dry_run = False
    playlists.cmd_remove_playlist(None, args)
    assert target.deleted
    assert "Deleted playlist: 'Old Mix'" in capsys.readouterr().out


# --- playlist-list --m3u and playlist-export write through one function ----


class Listed:
    title = "Mix"

    def items(self):
        return [FakeItem(1, "A")]


@pytest.mark.parametrize(
    "command", [playlists.cmd_list_playlist, playlists.cmd_export_playlist]
)
def test_both_ways_to_an_m3u_share_the_writer(monkeypatch, command, capsys):
    written = []
    monkeypatch.setattr(playlists, "server_for_user", lambda plex, uid: None)
    monkeypatch.setattr(playlists, "resolve_playlist", lambda plex, n: Listed())
    monkeypatch.setattr(
        playlists,
        "_export_m3u",
        lambda plex, items, path, args: written.append((len(items), path)),
    )
    args = argparse.Namespace(
        format="json", user_id=0, playlist="Mix", m3u="out.m3u", prefix=None
    )
    command(None, args)
    assert written == [(1, "out.m3u")]


# --- a ratingKey is ASCII digits, and nothing else ---------------------------


@pytest.mark.parametrize(
    "word", ["1_000", "+7", " 12 ", "-5", "\u0663", "12a", "", "1.0"]
)
def test_what_int_would_take_but_is_no_rating_key(word):
    """A playlist called 1_000 was looked up as ratingKey 1000."""
    assert as_rating_key(word) is None


def test_ascii_digits_are_a_rating_key():
    assert as_rating_key("0042") == 42
    assert as_rating_key(9104) == 9104


def test_a_playlist_titled_like_a_number_is_found_by_title():
    class Server:
        def playlist(self, title):
            return f"playlist {title}"

        def fetchItem(self, key):
            pytest.fail("a title was fetched as a ratingKey")

    assert resolve_playlist(Server(), "1_000") == "playlist 1_000"


# --- missing-find: a ratingKey needs no list of every show -------------------


class KeyedShow(Show):
    """A real Show, so isinstance holds, built without a server."""

    def __init__(self, key, title):  # pylint: disable=super-init-not-called
        self.__dict__.update(ratingKey=key, title=title)


class ShowSection:
    type, title, key = "show", "TV", 2

    def __init__(self, shows, namesakes=()):
        self._shows, self._namesakes = list(shows), list(namesakes)
        self.listed = 0
        self.searched = []

    def all(self):
        self.listed += 1
        return self._shows

    def search(self, **kwargs):
        self.searched.append(kwargs)
        return self._namesakes


class ShowPlex:
    def __init__(self, section, items):
        self.library, self._section, self._items = self, section, items

    def sections(self):
        return [self._section]

    def fetchItem(self, key):
        if key not in self._items:
            raise NotFound(key)
        return self._items[key]


def test_a_show_named_by_key_is_fetched_without_listing_the_library():
    wire = KeyedShow(4102, "The Wire")
    section = ShowSection([wire])
    found = missing.resolve_show(ShowPlex(section, {4102: wire}), "4102", None)
    assert found is wire
    assert section.listed == 0
    assert section.searched == [{"title": "4102", "libtype": "show"}]


def test_a_show_titled_like_the_key_is_still_warned_about(caplog):
    """24 is a ratingKey and a show; the key wins, and it is said."""
    by_key, by_title = KeyedShow(24, "Lost"), KeyedShow(900, "24")
    section = ShowSection([by_key, by_title], namesakes=[by_title])
    plex = ShowPlex(section, {24: by_key, 900: by_title})
    assert missing.resolve_show(plex, "24", None) is by_key
    assert "both a show ratingKey and the title of show 900" in caplog.text


def test_a_number_that_is_no_shows_key_may_be_a_title():
    titled = KeyedShow(900, "1923")
    section = ShowSection([titled])
    plex = ShowPlex(section, {900: titled, 1923: FakeItem(1923, "A Film")})
    assert missing.resolve_show(plex, "1923", None) is titled
    assert section.listed == 1


# --- titles-export paces its walk of a show library -------------------------


def test_exporting_a_show_library_is_paced(monkeypatch):
    """One request per show, and it was the one such loop left unpaced."""
    seen = []

    def recording(items, args, what="requests"):
        seen.append((len(items), what))
        return iter(items)

    class Shows:
        type, title = "show", "TV"

        def all(self):
            return ["a", "b", "c"]

    monkeypatch.setattr(photos, "paced", recording)
    monkeypatch.setattr(photos, "non_special_episodes", lambda show: [show])
    assert photos.collect_library_items(Shows()) == ["a", "b", "c"]
    assert seen == [(3, "shows")]


# --- users-list shows what its documentation says ---------------------------


def test_users_list_carries_username_and_email(monkeypatch, capsys):
    """The man page promised five fields; the command printed three."""

    class User:
        id, title, username, email = 7, "Alice", "alice", "a@example.com"
        restricted, home, friend = "0", True, False

    class Plex:
        def myPlexAccount(self):
            return self

        def users(self):
            return [User()]

    monkeypatch.setattr(users, "write_cache", lambda name, rows: None)
    users.cmd_list_users(Plex(), argparse.Namespace(format="json"))
    assert json.loads(capsys.readouterr().out) == [
        {
            "id": 7,
            "type": "home",
            "title": "Alice",
            "username": "alice",
            "email": "a@example.com",
        }
    ]


def test_status_and_users_list_show_the_same_rows():
    from plexdo import accounts
    from plexdo.commands import status

    assert status._SECTIONS["users"][1] is accounts.user_rows
    assert users.user_rows is accounts.user_rows


# --- read takes a ratingKey alone --------------------------------------------


def test_read_takes_no_library():
    """A ratingKey is unique on the server; the library only got in the way."""
    args = cli.build_parser().parse_args(["read", "12345"])
    assert args.rating_key == 12345
    assert not hasattr(args, "library_id")
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["read", "3", "12345"])


# --- playlist-build says what each mode takes --------------------------------


def test_missing_build_arguments_are_explained(capsys):
    """It said only that ARG was required."""
    with pytest.raises(SystemExit) as exc:
        cli.parse_arguments(cli.build_parser(), ["playlist-build", "-I", "Mix"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "-I and -C take NAME ratingKey" in err
    assert "-R takes USER SOURCE DEST" in err
    assert "required: ARG" not in err
