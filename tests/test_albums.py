# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""list-albums and list-album: albums, contents, played state, progress."""

import datetime
import json

import pytest

from plexdo.commands.albums import (
    IN_PROGRESS,
    PLAYED,
    UNPLAYED,
    album_record,
    album_summary,
    cmd_list_album,
    cmd_list_albums,
    content_record,
    item_rows,
    item_state,
    table_row,
)


class Node:
    """A plexapi object: its fields are plain attributes, as vars() reads."""

    TAG = "Track"

    def __init__(self, rating_key, title, **fields):
        self.ratingKey = rating_key
        self.title = title
        for name, value in fields.items():
            setattr(self, name, value)


class Track(Node):
    def __init__(self, rating_key, title, **fields):
        fields.setdefault("type", "track")
        fields.setdefault("viewCount", 0)
        fields.setdefault("viewOffset", 0)
        super().__init__(rating_key, title, **fields)


class Photo(Node):
    TAG = "Photo"

    def __init__(self, rating_key, title, **fields):
        super().__init__(rating_key, title, type="photo", **fields)


class Clip(Track):
    TAG = "Video"

    def __init__(self, rating_key, title, **fields):
        super().__init__(rating_key, title, type="clip", **fields)


class Album(Node):
    TAG = "Directory"

    def __init__(self, rating_key, title, children=(), **fields):
        super().__init__(rating_key, title, **fields)
        self.key = f"/library/metadata/{rating_key}"
        self._children = list(children)
        self._fetched = []

    def fetchItems(self, ekey):
        self._fetched.append(ekey)
        return list(self._children)


class Section:
    def __init__(self, stype, albums, title="Library"):
        self.type, self.title, self._albums = stype, title, albums

    def albums(self):
        return list(self._albums)

    def all(self):
        return list(self._albums)


class Library:
    def __init__(self, section):
        self.section = section

    def sectionByID(self, _key):
        return self.section


class Plex:
    def __init__(self, section):
        self.library = Library(section)


def run(section, capsys, fmt="json"):
    import argparse

    args = argparse.Namespace(library_id=1, format=fmt, throttle=0, wide=True)
    cmd_list_albums(Plex(section), args)
    out = capsys.readouterr().out
    return json.loads(out) if fmt == "json" else out


# --- one item -------------------------------------------------------------


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({"viewCount": 0, "viewOffset": 0}, UNPLAYED),
        ({"viewCount": 2, "viewOffset": 0}, PLAYED),
        ({"viewCount": 0, "viewOffset": 5000}, IN_PROGRESS),
        # Being played again: in progress, though played before.
        ({"viewCount": 1, "viewOffset": 5000}, IN_PROGRESS),
        ({"viewCount": 0}, UNPLAYED),
        ({}, None),  # a photo
    ],
)
def test_item_state(fields, expected):
    assert item_state(fields) == expected


def test_a_track_in_progress_has_its_resume_point_and_progress():
    track = Track(
        11,
        "Song",
        index=3,
        parentIndex=2,
        duration=200_000,
        viewOffset=50_000,
        grandparentTitle="Band",
        lastViewedAt=datetime.datetime(2026, 11, 1, 20, 30),
    )
    record = content_record(track, 1)
    assert record == {
        "index": 1,
        "ratingKey": 11,
        "type": "track",
        "disc": 2,
        "track": 3,
        "title": "Song",
        "artist": "Band",
        "duration": 200_000,
        "state": IN_PROGRESS,
        "played": False,
        "viewCount": 0,
        "lastViewedAt": "2026-11-01 20:30:00",
        "viewOffset": 50_000,
        "progress": 25.0,
        "files": [],
    }


def test_progress_is_null_unless_in_progress():
    played = content_record(Track(1, "A", duration=1000, viewCount=1), 1)
    fresh = content_record(Track(2, "B", duration=1000), 2)
    for record in (played, fresh):
        assert record["viewOffset"] is None
        assert record["progress"] is None
    assert played["played"] is True
    assert fresh["played"] is False


def test_a_track_artist_prefers_its_own_over_the_album_artist():
    track = Track(1, "A", originalTitle="Guest", grandparentTitle="Band")
    assert content_record(track, 1)["artist"] == "Guest"


def test_progress_without_a_duration_is_null():
    record = content_record(Track(1, "A", viewOffset=500), 1)
    assert record["state"] == IN_PROGRESS
    assert record["viewOffset"] == 500
    assert record["progress"] is None


def test_a_photo_has_no_played_state():
    record = content_record(Photo(5, "Beach", index=1), 1)
    assert record["state"] is None
    assert record["played"] is None
    assert record["viewCount"] is None
    assert record["track"] is None


# --- one album ------------------------------------------------------------


def album_of(*tracks, **fields):
    return Album(100, "Record", tracks, parentTitle="Band", **fields)


def test_an_album_with_everything_played_is_played():
    album = album_of(Track(1, "A", viewCount=1), Track(2, "B", viewCount=3))
    record = album_record(album, album._children, True)
    assert record["state"] == PLAYED
    assert record["played"] is True
    assert record["playedItems"] == 2
    assert record["inProgressItems"] == 0
    assert record["progress"] is None


def test_an_untouched_album_is_unplayed():
    album = album_of(Track(1, "A"), Track(2, "B"))
    record = album_record(album, album._children, True)
    assert record["state"] == UNPLAYED
    assert record["played"] is False
    assert record["progress"] is None


def test_a_part_played_album_is_in_progress_by_running_time():
    """One long track unplayed and a short one played is not half done."""
    album = album_of(
        Track(1, "Short", duration=100_000, viewCount=1),
        Track(2, "Long", duration=300_000),
    )
    record = album_record(album, album._children, True)
    assert record["state"] == IN_PROGRESS
    assert record["played"] is False
    assert record["playedItems"] == 1
    assert record["progress"] == 25.0


def test_a_resume_point_counts_towards_album_progress():
    album = album_of(
        Track(1, "A", duration=100_000, viewCount=1),
        Track(2, "B", duration=100_000, viewOffset=50_000),
    )
    record = album_record(album, album._children, True)
    assert record["state"] == IN_PROGRESS
    assert record["inProgressItems"] == 1
    assert record["progress"] == 75.0


def test_a_played_album_being_played_again_is_in_progress():
    album = album_of(
        Track(1, "A", duration=100_000, viewCount=1),
        Track(2, "B", duration=100_000, viewCount=1, viewOffset=20_000),
    )
    record = album_record(album, album._children, True)
    assert record["state"] == IN_PROGRESS
    assert record["playedItems"] == 2
    assert record["progress"] == 60.0


def test_album_fields_and_contents():
    album = album_of(
        Track(1, "A", duration=1000, index=1),
        Track(2, "B", duration=2000, index=2),
        year=1999,
    )
    record = album_record(album, album._children, True)
    assert record["ratingKey"] == 100
    assert record["artist"] == "Band"
    assert record["title"] == "Record"
    assert record["year"] == 1999
    assert record["items"] == 2
    assert record["duration"] == 3000
    assert [r["title"] for r in record["contents"]] == ["A", "B"]
    assert [r["index"] for r in record["contents"]] == [1, 2]


def test_album_last_viewed_falls_back_to_its_latest_item():
    album = album_of(
        Track(1, "A", lastViewedAt=datetime.datetime(2026, 1, 1)),
        Track(2, "B", lastViewedAt=datetime.datetime(2026, 3, 1)),
    )
    record = album_record(album, album._children, True)
    assert record["lastViewedAt"] == "2026-03-01 00:00:00"


def test_a_photo_album_has_no_played_state_or_artist():
    album = Album(7, "Trip", [Photo(1, "a"), Photo(2, "b")])
    record = album_record(album, album._children, False)
    assert record["artist"] is None
    assert record["state"] is None
    assert record["played"] is None
    assert record["playedItems"] is None
    assert record["items"] == 2


def test_photos_do_not_count_against_the_clips_in_an_album():
    album = Album(7, "Trip", [Photo(1, "a"), Clip(2, "b", viewCount=1)])
    record = album_record(album, album._children, False)
    assert record["state"] == PLAYED
    assert record["playedItems"] == 1


def test_every_album_record_carries_every_key():
    """CSV takes its header from the first record."""
    music = album_record(album_of(Track(1, "A")), [Track(1, "A")], True)
    photo = album_record(Album(7, "Trip"), [], False)
    assert list(music) == list(photo)
    assert photo["state"] is None and photo["items"] == 0


# --- the table ------------------------------------------------------------


def test_a_music_table_row_uses_the_listing_counts():
    album = album_of(leafCount=12, viewedLeafCount=3, year=2001)
    assert table_row(album, None, True) == {
        "ratingKey": 100,
        "artist": "Band",
        "title": "Record",
        "year": 2001,
        "items": 12,
        "played": 3,
    }


def test_a_photo_table_row_has_no_artist_and_counts_its_contents():
    album = Album(7, "Trip", [Photo(1, "a"), Clip(2, "b", viewCount=1)])
    assert table_row(album, album._children, False) == {
        "ratingKey": 7,
        "title": "Trip",
        "year": "",
        "items": 2,
        "played": 1,
    }


def test_a_photo_only_album_shows_no_played_count():
    album = Album(7, "Trip", [Photo(1, "a")])
    assert table_row(album, album._children, False)["played"] == ""


# --- the command ----------------------------------------------------------


def test_music_json_reads_each_album_once(capsys):
    first = album_of(Track(1, "A", viewCount=1))
    second = Album(200, "Other", [Track(2, "B")], parentTitle="Band")
    rows = run(Section("artist", [first, second]), capsys)
    assert [r["title"] for r in rows] == ["Record", "Other"]
    assert [r["state"] for r in rows] == [PLAYED, UNPLAYED]
    assert first._fetched == ["/library/metadata/100/children"]
    assert second._fetched == ["/library/metadata/200/children"]


def test_a_music_table_reads_no_album(capsys):
    album = album_of(Track(1, "A"), leafCount=1, viewedLeafCount=0)
    out = run(Section("artist", [album]), capsys, fmt="table")
    assert "Record" in out and "Band" in out
    assert album._fetched == []


def test_nested_photo_albums_follow_their_parent(capsys):
    inner = Album(2, "Day 1", [Photo(20, "p")])
    outer = Album(1, "Trip", [Photo(10, "q"), inner])
    later = Album(3, "Home", [])
    rows = run(Section("photo", [outer, later]), capsys)
    assert [r["title"] for r in rows] == ["Trip", "Day 1", "Home"]
    # A nested album is not part of its parent's contents.
    assert [c["title"] for c in rows[0]["contents"]] == ["q"]


def test_an_list_albumsed_at_the_top_and_nested_is_listed_once(capsys):
    inner = Album(2, "Day 1", [Photo(20, "p")])
    outer = Album(1, "Trip", [inner])
    rows = run(Section("photo", [outer, inner]), capsys)
    assert [r["title"] for r in rows] == ["Trip", "Day 1"]


@pytest.mark.parametrize("stype", ["movie", "show"])
def test_other_libraries_are_refused(stype, capsys):
    with pytest.raises(SystemExit, match="music or photo library"):
        run(Section(stype, [], title="Films"), capsys)


def test_an_empty_library_lists_nothing(capsys):
    assert run(Section("artist", []), capsys) == []


def test_the_command_takes_a_library_by_id_or_title():
    from plexdo.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["list-albums", "Music"]).library_id == "Music"
    assert parser.parse_args(["list-albums", "4", "--json"]).format == "json"


# --- list-album -----------------------------------------------------------


class ItemPlex:
    """A server holding these items, fetched by ratingKey."""

    def __init__(self, *items):
        self.items = {int(item.ratingKey): item for item in items}

    def fetchItem(self, key):
        from plexapi.exceptions import NotFound

        try:
            return self.items[int(key)]
        except KeyError:
            raise NotFound(key) from None


def show(item, capsys, fmt="json"):
    import argparse

    args = argparse.Namespace(
        rating_key=int(item.ratingKey), format=fmt, wide=True
    )
    cmd_list_album(ItemPlex(item), args)
    out = capsys.readouterr().out
    return json.loads(out) if fmt == "json" else out


def music_album(*tracks, **fields):
    fields.setdefault("type", "album")
    return Album(100, "Record", tracks, parentTitle="Band", **fields)


def test_json_is_the_list_albums_record(capsys):
    album = music_album(
        Track(1, "A", duration=100_000, viewCount=1),
        Track(2, "B", duration=100_000, viewOffset=25_000),
    )
    record = show(album, capsys)
    assert record == json.loads(
        json.dumps(album_record(album, album._children, True))
    )
    assert record["state"] == IN_PROGRESS
    assert record["progress"] == 62.5
    assert record["contents"][1]["progress"] == 25.0
    assert album._fetched == ["/library/metadata/100/children"]


def test_csv_carries_one_row_per_item(capsys):
    album = music_album(Track(1, "A"), Track(2, "B"))
    out = show(album, capsys, fmt="csv").splitlines()
    assert out[0].startswith("index,ratingKey,type,disc,track,title")
    assert len(out) == 3


def test_the_table_shows_the_album_then_its_items(capsys):
    album = music_album(
        Track(1, "Opener", index=1, duration=200_000, viewCount=1),
        Track(2, "Closer", index=2, duration=200_000, viewOffset=50_000),
        year=1999,
    )
    out = show(album, capsys, fmt="table")
    assert out.index("Record") < out.index("Opener") < out.index("Closer")
    assert "1 of 2" in out
    assert "0:50 / 3:20 (25.0%)" in out


def test_a_photo_is_not_an_album(capsys):
    with pytest.raises(SystemExit, match="not an album"):
        show(Photo(5, "Beach"), capsys)


def test_a_show_is_not_an_album(capsys):
    """Shows are Directory elements too; only the type tells them apart."""
    with pytest.raises(SystemExit, match="not an album .it is a show"):
        show(Album(9, "Series", type="show"), capsys)


def test_a_missing_album_is_reported(capsys):
    import argparse

    args = argparse.Namespace(rating_key=404, format="json", wide=True)
    with pytest.raises(SystemExit, match="not found: 404"):
        cmd_list_album(ItemPlex(), args)


def test_nested_photo_albums_are_not_contents(capsys):
    album = Album(
        1,
        "Trip",
        [Photo(10, "a"), Album(2, "Day 1", type="photo")],
        type="photo",
    )
    record = show(album, capsys)
    assert [c["title"] for c in record["contents"]] == ["a"]
    summary = album_summary(record, 1)
    assert summary["nested albums"] == "1, listed by list-albums"


def test_the_summary_shows_only_what_applies():
    photos = album_record(
        Album(1, "Trip", type="photo"), [Photo(10, "a")], False
    )
    summary = album_summary(photos, 0)
    assert list(summary) == ["ratingKey", "title", "items"]

    album = music_album(
        Track(1, "A", duration=60_000, viewCount=1),
        Track(2, "B", duration=60_000, viewOffset=30_000),
        year=2001,
    )
    summary = album_summary(album_record(album, album._children, True), 0)
    assert summary["artist"] == "Band"
    assert summary["year"] == 2001
    assert summary["length"] == "2:00"
    assert summary["state"] == IN_PROGRESS
    assert summary["played"] == "1 of 2"
    assert summary["in progress"] == 1
    assert summary["progress"] == "75.0%"


def rows_of(*tracks):
    album = music_album(*tracks)
    return item_rows(album_record(album, album._children, True))


def test_item_rows_on_one_disc_show_bare_track_numbers():
    rows = rows_of(
        Track(1, "A", index=1, parentIndex=1, duration=61_000, viewCount=1),
        Track(2, "B", index=2, parentIndex=1, duration=5_000, viewOffset=1_000),
    )
    assert rows[0] == {
        "#": 1,
        "ratingKey": 1,
        "track": 1,
        "title": "A",
        "length": "1:01",
        "state": PLAYED,
        "progress": "",
        "last played": "",
    }
    assert rows[1]["progress"] == "0:01 / 0:05 (20.0%)"
    assert "artist" not in rows[0]


def test_item_rows_across_discs_carry_the_disc():
    rows = rows_of(
        Track(1, "A", index=9, parentIndex=1),
        Track(2, "B", index=1, parentIndex=2),
    )
    assert [r["track"] for r in rows] == ["1-09", "2-01"]


def test_item_rows_name_the_artist_only_on_a_compilation():
    assert "artist" not in rows_of(Track(1, "A", grandparentTitle="Band"))[0]
    rows = rows_of(
        Track(1, "A", grandparentTitle="Band"),
        Track(2, "B", originalTitle="Guest"),
    )
    assert [r["artist"] for r in rows] == ["Band", "Guest"]


def test_item_rows_of_photos_have_no_played_columns():
    album = Album(1, "Trip", [Photo(10, "a")], type="photo")
    rows = item_rows(album_record(album, album._children, False))
    assert rows == [{"#": 1, "ratingKey": 10, "title": "a", "length": ""}]


def test_list_album_takes_a_rating_key():
    from plexdo.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["list-album", "100"]).rating_key == 100
    with pytest.raises(SystemExit):
        parser.parse_args(["list-album", "Record"])
