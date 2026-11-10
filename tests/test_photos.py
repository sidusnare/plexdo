# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Walking a photo library: nested albums, loops, and how deep to go."""

import pytest

from plexdo import photos
from plexdo.photos import MAX_ALBUM_DEPTH, collect_photos, walk_photo_albums


class Photo:
    TAG = "Photo"

    def __init__(self, key, kind="photo"):
        self.ratingKey, self.type, self.title = key, kind, f"p{key}"


class Album:
    TAG = "Directory"

    def __init__(self, key, title, *children):
        self.ratingKey, self.title, self.type = key, title, "photo"
        self.key = f"/library/metadata/{key}"
        self.children = list(children)
        self.opened = 0

    def fetchItems(self, _path):
        self.opened += 1
        return self.children


class Section:
    title, type = "Pictures", "photo"

    def __init__(self, *albums):
        self._albums = list(albums)

    def all(self):
        return self._albums


def keys(found):
    return [photo.ratingKey for photo in found]


def test_photos_in_nested_albums_are_collected():
    """They were left out: only an album's own photos were read."""
    inner = Album(11, "Day 2", Photo(3), Photo(4))
    outer = Album(10, "Trip", Photo(1), inner, Photo(2))
    assert keys(collect_photos(Section(outer))) == [1, 2, 3, 4]


def test_a_clip_in_an_album_is_not_a_photo():
    album = Album(10, "Trip", Photo(1), Photo(2, kind="clip"))
    assert keys(collect_photos(Section(album))) == [1]


def test_an_album_filter_takes_the_albums_inside_it_too():
    inner = Album(11, "Day 2", Photo(3))
    outer = Album(10, "Trip", Photo(1), inner)
    other = Album(20, "Home", Photo(9))
    section = Section(outer, other)
    assert keys(collect_photos(section, "trip")) == [1, 3]
    assert keys(collect_photos(section, "Day 2")) == [3]


def test_an_album_that_is_not_there_is_an_error():
    with pytest.raises(SystemExit) as exc:
        collect_photos(Section(Album(10, "Trip", Photo(1))), "Nope")
    assert "'Nope' not found" in str(exc.value)


def test_an_empty_album_is_found_and_holds_nothing():
    assert collect_photos(Section(Album(10, "Trip")), "Trip") == []


def test_albums_that_contain_one_another_are_walked_once():
    """A loop on the server must not become one here."""
    first = Album(10, "A", Photo(1))
    second = Album(11, "B", Photo(2), first)
    first.children.append(second)
    visits = walk_photo_albums(Section(first))
    assert [v.album.ratingKey for v in visits] == [10, 11]
    assert (first.opened, second.opened) == (1, 1)


def test_an_album_listed_at_the_top_and_inside_another_is_listed_once():
    inner = Album(11, "Day 2", Photo(3))
    outer = Album(10, "Trip", inner)
    visits = walk_photo_albums(Section(outer, inner))
    assert [v.album.ratingKey for v in visits] == [10, 11]


def test_each_visit_carries_the_titles_of_the_albums_around_it():
    inner = Album(11, "Day 2")
    visits = walk_photo_albums(Section(Album(10, "Trip", inner)))
    assert [v.titles for v in visits] == [("Trip",), ("Trip", "Day 2")]


def test_nesting_is_followed_only_so_deep(caplog):
    """Distinct albums all the way down: the loop check cannot stop it."""
    deepest = Album(1000, "bottom", Photo(1))
    album = deepest
    for key in range(999, 999 - (MAX_ALBUM_DEPTH + 3), -1):
        album = Album(key, f"level {key}", album)
    visits = walk_photo_albums(Section(album))
    assert len(visits) == MAX_ALBUM_DEPTH
    assert deepest.opened == 0
    assert f"more than {MAX_ALBUM_DEPTH} deep" in caplog.text


def test_a_library_within_the_limit_says_nothing(caplog):
    walk_photo_albums(Section(Album(10, "Trip", Album(11, "Day 2"))))
    assert "deep" not in caplog.text


def test_the_walk_is_what_the_album_commands_use():
    from plexdo.commands import albums

    assert albums.walk_photo_albums is photos.walk_photo_albums
