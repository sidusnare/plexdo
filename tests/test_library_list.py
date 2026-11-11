# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""library-list: what each kind of library lists, by type and by folder."""

import argparse
import json
import xml.etree.ElementTree as ET

import pytest
from plexapi.exceptions import NotFound

from conftest import FakeItem
from plexdo.cli import build_parser, parse_arguments
from plexdo.commands import libraries
from plexdo.commands.libraries import (
    FOLDER,
    LIST_TYPES,
    TYPE_CHOICES,
    cmd_list_titles,
    parse_filter,
)


class Section:
    """A library that records what it was asked to list."""

    def __init__(self, stype, items=(), key=3, title="Library", error=None):
        self.type, self.key, self.title = stype, key, title
        self._items = list(items)
        self._error = error
        self.asked = []
        self.filtered = []

    def all(self, libtype=None, filters=None):
        self.asked.append(libtype)
        if filters is not None:
            self.filtered.append(filters)
            if self._error:
                raise self._error
        return list(self._items)

    def search(self, libtype=None, filters=None):
        self.asked.append(("search", libtype))
        self.filtered.append(filters)
        return list(self._items)

    def listFilterChoices(self, field, libtype=None):
        self.asked.append(("choices", field, libtype))
        if self._error:
            raise self._error
        return [Choice("Crime"), Choice("Drama")]


class Choice:
    def __init__(self, title):
        self.title, self.key = title, title.lower()

    def albums(self):
        self.asked.append("albums")
        return []


class Plex:
    """A server holding one library, and folders as XML."""

    def __init__(self, section, folders=None):
        self.library = self
        self._section = section
        self._folders = folders or {}
        self.queried = []

    def sectionByID(self, _key):
        return self._section

    def query(self, key):
        self.queried.append(key)
        return ET.fromstring(self._folders[key])


@pytest.fixture
def cache(monkeypatch):
    """What library-list writes to the completion cache, by name."""
    written = {}
    monkeypatch.setattr(
        libraries,
        "write_cache",
        lambda name, rows: written.update({name: rows}),
    )
    monkeypatch.setattr(libraries, "write_word_caches", lambda *a: None)
    return written


def run(plex, capsys, fmt="json", **options):
    args = argparse.Namespace(
        library_id=3,
        format=fmt,
        throttle=0,
        wide=True,
        list_type=None,
        path=None,
        album=None,
        filters=None,
        categories=None,
        list_categories=False,
    )
    vars(args).update(options)
    cmd_list_titles(plex, args)
    out = capsys.readouterr().out
    return json.loads(out) if fmt == "json" else out


# --- defaults ----------------------------------------------------------------


@pytest.mark.parametrize(
    "stype,default", [("movie", "movie"), ("show", "show")]
)
def test_a_video_library_lists_its_top_level_by_default(
    stype, default, cache, capsys
):
    section = Section(stype, [FakeItem(1, "One")])
    run(Plex(section), capsys, fmt="table")
    assert section.asked == [default]
    assert cache == {"titles.3": [{"ratingKey": 1, "title": "One"}]}


@pytest.mark.parametrize("stype", ["artist", "photo"])
def test_music_and_photos_list_albums_by_default(stype):
    assert LIST_TYPES[stype][0] == "album"


def test_every_type_is_offered_and_folder_besides():
    listed = {kind for kinds in LIST_TYPES.values() for kind in kinds}
    assert set(TYPE_CHOICES) == listed | {FOLDER}


# --- a type named ------------------------------------------------------------


@pytest.mark.parametrize(
    "stype,kind",
    [
        ("movie", "collection"),
        ("show", "season"),
        ("show", "episode"),
        ("artist", "artist"),
        ("artist", "track"),
        ("photo", "photo"),
        ("photo", "clip"),
    ],
)
def test_a_type_is_asked_of_the_all_endpoint(stype, kind, cache, capsys):
    section = Section(stype, [FakeItem(1, "One")])
    rows = run(Plex(section), capsys, list_type=kind)
    assert section.asked == [kind]
    assert rows[0]["ratingKey"] == 1
    # The cache holds the default listing only, so it stays steady.
    assert cache == {}


@pytest.mark.parametrize(
    "stype,kind", [("movie", "episode"), ("show", "track"), ("photo", "movie")]
)
def test_a_type_the_library_cannot_hold_is_refused(stype, kind, capsys):
    section = Section(stype, title="Films")
    with pytest.raises(SystemExit) as exc:
        run(Plex(section), capsys, list_type=kind)
    message = str(exc.value)
    assert f"holds no {kind} items" in message
    assert ", ".join((*LIST_TYPES[stype], FOLDER)) in message
    assert section.asked == []


def test_an_episode_row_says_which_show_and_season(capsys):
    episode = FakeItem(
        5, "Pilot", grandparentTitle="The Wire", parentIndex=1, index=1
    )
    row = run(
        Plex(Section("show", [episode])),
        capsys,
        fmt="table",
        list_type="episode",
    )
    assert "The Wire" in row and "Pilot" in row


def test_a_track_row_says_which_artist_and_album(capsys):
    track = FakeItem(
        7,
        "So What",
        grandparentTitle="Miles Davis",
        parentTitle="Kind of Blue",
        index=1,
    )
    out = run(
        Plex(Section("artist", [track])), capsys, fmt="table", list_type="track"
    )
    assert "Miles Davis" in out and "Kind of Blue" in out


def test_a_machine_readable_listing_carries_every_field(capsys):
    film = FakeItem(1, "Heat", studio="Warner", year=1995)
    rows = run(Plex(Section("movie", [film])), capsys)
    assert rows[0]["studio"] == "Warner"
    assert rows[0]["releaseDate"] == "1995"


# --- --album -----------------------------------------------------------------


def test_album_lists_photos_through_the_album_walk(monkeypatch, capsys):
    walked = []
    monkeypatch.setattr(
        libraries,
        "collect_photos",
        lambda section, album, args: walked.append(album) or [FakeItem(9, "p")],
    )
    section = Section("photo")
    rows = run(Plex(section), capsys, album="Trip")
    assert walked == ["Trip"]
    assert section.asked == []
    assert rows[0]["ratingKey"] == 9


def test_album_is_ignored_with_a_warning_outside_a_photo_library(
    caplog, capsys
):
    section = Section("movie", [FakeItem(1, "Heat")])
    run(Plex(section), capsys, album="Trip")
    assert section.asked == ["movie"]
    assert "only applicable to photo libraries" in caplog.text


# --- folders -----------------------------------------------------------------


TOP = """<MediaContainer>
  <Directory key="/library/sections/3/folder?parent=11" title="TV"/>
  <Directory key="/library/sections/3/folder?parent=12" title="Films"/>
</MediaContainer>"""
TV = """<MediaContainer>
  <Directory key="/library/sections/3/folder?parent=21" title="The Wire"/>
  <Video ratingKey="77" type="movie" title="Loose File"/>
</MediaContainer>"""
WIRE = """<MediaContainer>
  <Directory ratingKey="4102" type="show" title="The Wire"
             key="/library/metadata/4102/children"/>
</MediaContainer>"""
FOLDERS = {
    "/library/sections/3/folder": TOP,
    "/library/sections/3/folder?parent=11": TV,
    "/library/sections/3/folder?parent=21": WIRE,
}


def test_the_top_folders_are_listed_with_the_path_to_open_each(capsys):
    plex = Plex(Section("show"), FOLDERS)
    rows = run(plex, capsys, list_type="folder")
    assert rows == [
        {"type": "folder", "ratingKey": None, "title": "TV", "path": "TV"},
        {
            "type": "folder",
            "ratingKey": None,
            "title": "Films",
            "path": "Films",
        },
    ]
    assert plex.queried == ["/library/sections/3/folder"]


def test_a_path_opens_one_folder_at_a_time(capsys):
    plex = Plex(Section("show"), FOLDERS)
    rows = run(plex, capsys, path="tv/The Wire")
    assert rows == [
        {"type": "show", "ratingKey": 4102, "title": "The Wire", "path": None}
    ]
    assert plex.queried == list(FOLDERS)


def test_a_folder_holding_folders_and_items_lists_both(capsys):
    rows = run(Plex(Section("show"), FOLDERS), capsys, path="TV")
    assert [(r["type"], r["title"], r["path"]) for r in rows] == [
        ("folder", "The Wire", "TV/The Wire"),
        ("movie", "Loose File", None),
    ]


def test_a_folder_that_is_not_there_names_what_is(capsys):
    with pytest.raises(SystemExit) as exc:
        run(Plex(Section("show"), FOLDERS), capsys, path="TV/Lost")
    assert "No folder 'Lost' in 'TV'" in str(exc.value)
    assert "'The Wire'" in str(exc.value)


def test_an_item_is_not_a_folder_to_open(capsys):
    with pytest.raises(SystemExit) as exc:
        run(Plex(Section("show"), FOLDERS), capsys, path="TV/Loose File")
    assert "No folder 'Loose File'" in str(exc.value)


def test_folders_need_no_cache(cache, capsys):
    run(Plex(Section("show"), FOLDERS), capsys, list_type="folder")
    assert cache == {}


# --- the command line --------------------------------------------------------


@pytest.mark.parametrize(
    "argv,attrs",
    [
        (["library-list", "TV"], {"list_type": None, "path": None}),
        (["library-list", "TV", "-t", "episode"], {"list_type": "episode"}),
        (["library-list", "TV", "--path", "A/B"], {"path": "A/B"}),
        (["library-list", "Pix", "--album", "Trip"], {"album": "Trip"}),
    ],
)
def test_library_list_parses(argv, attrs):
    args = parse_arguments(build_parser(), argv)
    for name, value in attrs.items():
        assert getattr(args, name) == value


@pytest.mark.parametrize(
    "argv,said",
    [
        (["-t", "show", "--path", "TV"], "--path lists a folder"),
        (["-t", "album", "--album", "Trip"], "--album lists photos"),
        (["--album", "Trip", "--path", "TV"], "cannot be used together"),
        (["-t", "person"], "invalid choice"),
    ],
)
def test_options_that_do_not_go_together_exit_2(argv, said, capsys):
    with pytest.raises(SystemExit) as exc:
        parse_arguments(build_parser(), ["library-list", "TV", *argv])
    assert exc.value.code == 2
    assert said in capsys.readouterr().err


@pytest.mark.parametrize(
    "old,new", [("missing-find", "find-missing"), ("show-metadata", "metadata")]
)
def test_the_renamed_commands(old, new):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([old, "1"])
    assert parser.parse_args([new, "1"]).command == new


# --- --filter, --category, --list-categories --------------------------------


@pytest.mark.parametrize(
    "text,parsed",
    [
        ("genre=Drama", ("genre", "Drama")),
        ("genre!=Horror", ("genre!", "Horror")),
        ("year>1990", ("year>>", "1990")),
        ("year<2000", ("year<<", "2000")),
        ("title=A=B", ("title", "A=B")),
        ("collection= Marvel ", ("collection", "Marvel")),
    ],
)
def test_a_filter_is_a_field_an_operator_and_a_value(text, parsed):
    assert parse_filter(text) == parsed


@pytest.mark.parametrize("text", ["Drama", "=Drama", "genre=", "1x=y", "g e=x"])
def test_what_is_not_a_filter_is_refused(text):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_filter(text)


def test_one_filter_goes_to_the_server_as_it_is(cache, capsys):
    section = Section("movie", [FakeItem(1, "Heat")])
    run(Plex(section), capsys, filters=[("genre", "Crime")])
    assert section.filtered == [{"genre": "Crime"}]
    assert section.asked == ["movie"]
    # A filtered listing is not the library's default one, so not cached.
    assert cache == {}


def test_several_filters_must_all_hold(capsys):
    section = Section("movie", [FakeItem(1, "Heat")])
    run(
        Plex(section),
        capsys,
        filters=[("year>>", "1990")],
        categories=["Crime", "Drama"],
    )
    assert section.filtered == [
        {"and": [{"year>>": "1990"}, {"genre": "Crime"}, {"genre": "Drama"}]}
    ]


def test_category_is_a_genre_filter(capsys):
    section = Section("show", [FakeItem(1, "The Wire")])
    run(Plex(section), capsys, categories=["Crime"], list_type="episode")
    assert section.filtered == [{"genre": "Crime"}]
    assert section.asked == ["episode"]


def test_a_music_library_filters_its_albums_on_the_server(capsys):
    section = Section("artist", [])
    run(Plex(section), capsys, fmt="table", categories=["Jazz"])
    assert section.asked == [("search", "album")]
    assert section.filtered == [{"genre": "Jazz"}]


def test_a_photo_library_filters_photoalbums(capsys):
    section = Section("photo", [])
    run(Plex(section), capsys, filters=[("label", "Trip")])
    assert section.asked == [("search", "photoalbum")]


def test_a_field_the_library_has_not_is_a_message(capsys):
    """Plexapi names the fields there are; that is what is worth showing."""
    error = NotFound(
        'Unknown filter field "genr" for libtype "movie". Available filter '
        "fields: ['genre', 'year']"
    )
    section = Section("movie", error=error, title="Films")
    with pytest.raises(SystemExit) as exc:
        run(Plex(section), capsys, filters=[("genr", "Crime")])
    message = str(exc.value)
    assert message.startswith("Cannot filter library 'Films': Unknown filter")
    assert "['genre', 'year']" in message


def test_list_categories_lists_the_genres_of_the_type(capsys):
    section = Section("show")
    rows = run(Plex(section), capsys, list_categories=True, list_type="episode")
    assert rows == [{"category": "Crime"}, {"category": "Drama"}]
    assert section.asked == [("choices", "genre", "episode")]


def test_a_photo_librarys_albums_are_photoalbums_to_the_server(capsys):
    section = Section("photo")
    run(Plex(section), capsys, list_categories=True)
    assert section.asked == [("choices", "genre", "photoalbum")]


def test_a_type_with_no_categories_says_so(capsys):
    section = Section(
        "photo", error=NotFound('Unknown filter field "genre"'), title="Pix"
    )
    with pytest.raises(SystemExit) as exc:
        run(Plex(section), capsys, list_categories=True, list_type="photo")
    assert "Cannot filter library 'Pix'" in str(exc.value)


@pytest.mark.parametrize(
    "argv,attrs",
    [
        (["--filter", "genre=Drama"], {"filters": [("genre", "Drama")]}),
        (
            ["--filter", "year>1990", "--filter", "genre!=Horror"],
            {"filters": [("year>>", "1990"), ("genre!", "Horror")]},
        ),
        (["--category", "Drama"], {"categories": ["Drama"]}),
        (["--list-categories", "-t", "episode"], {"list_categories": True}),
    ],
)
def test_the_narrowing_options_parse(argv, attrs):
    args = parse_arguments(build_parser(), ["library-list", "TV", *argv])
    for name, value in attrs.items():
        assert getattr(args, name) == value


@pytest.mark.parametrize(
    "argv,said",
    [
        (["--filter", "Drama"], "expected FIELD=VALUE"),
        (["--category", "Drama", "-t", "folder"], "cannot go with a folder"),
        (["--filter", "genre=x", "--path", "TV"], "cannot go with a folder"),
        (["--category", "x", "--album", "Trip"], "cannot go with --album"),
        (["--list-categories", "--category", "x"], "takes no --filter"),
    ],
)
def test_narrowing_options_that_do_not_go_together_exit_2(argv, said, capsys):
    with pytest.raises(SystemExit) as exc:
        parse_arguments(build_parser(), ["library-list", "TV", *argv])
    assert exc.value.code == 2
    assert said in capsys.readouterr().err
