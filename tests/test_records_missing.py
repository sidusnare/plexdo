# SPDX-License-Identifier: GPL-3.0-or-later

"""Listing records and episode-gap detection."""

import datetime

import pytest

from plexdo.commands.missing import episode_gaps
from plexdo.records import SUMMARY_FIELDS, loaded_fields, release_date, summary_row


class Tag:
    def __init__(self, tag):
        self.tag = tag


class Item:
    def __init__(self, **kw):
        self.ratingKey = kw.pop("ratingKey", 1)
        self.title = kw.pop("title", "A Title")
        for key, value in kw.items():
            setattr(self, key, value)
        self._server = object()          # private, must not be reported


@pytest.mark.parametrize("numbers,expected", [
    ([1, 2, 3], []),
    ([1, 2, 4], [3]),
    ([3, 4, 5], [1, 2]),
    ([0, 1, 3], [2]),
    ([1], []),
    ([], []),
    ([1, 4, 5, 9], [2, 3, 6, 7, 8]),
])
def test_episode_gaps(numbers, expected):
    assert episode_gaps(numbers) == expected


def test_a_season_stopping_early_is_not_a_gap():
    """An unaired episode cannot be told from a missing one."""
    assert episode_gaps([1, 2, 3]) == []


def test_episode_zero_starts_the_run_at_zero():
    assert episode_gaps([0, 2]) == [1]
    assert episode_gaps([2, 3]) == [1]


# --- records -------------------------------------------------------------

def test_summary_row_has_exactly_the_documented_columns():
    row = summary_row(Item(year=1999, rating=8.1, studio="A24"))
    assert tuple(row) == SUMMARY_FIELDS


def test_release_date_prefers_the_full_date_over_the_year():
    assert release_date(Item(originallyAvailableAt="2008-01-20", year=2007)) \
        == "2008-01-20"


def test_release_date_falls_back_to_the_year():
    assert release_date(Item(year=1999)) == "1999"


def test_release_date_is_empty_when_neither_is_known():
    assert release_date(Item()) == ""


def test_loaded_fields_skips_private_attributes():
    assert "_server" not in loaded_fields(Item())


def test_loaded_fields_reduces_tag_objects_to_their_names():
    assert loaded_fields(Item(genres=[Tag("Drama"), Tag("Crime")]))["genres"] \
        == ["Drama", "Crime"]


def test_loaded_fields_renders_dates_as_text():
    fields = loaded_fields(Item(addedAt=datetime.datetime(2024, 3, 5, 12, 30)))
    assert fields["addedAt"] == "2024-03-05 12:30:00"


def test_loaded_fields_reads_only_what_is_already_present():
    """Attribute access on a partial plexapi object triggers a reload."""
    class Exploding(Item):
        def __getattr__(self, name):     # only called for missing attributes
            raise AssertionError(f"reload triggered for {name}")
    assert loaded_fields(Exploding())["title"] == "A Title"


# --- file paths ----------------------------------------------------------

from plexdo.records import file_paths


class Part:
    def __init__(self, file):
        self.file = file


class Media:
    def __init__(self, *files):
        self.parts = [Part(f) for f in files]


def test_a_single_file_is_reported():
    assert file_paths(Item(media=[Media("/mnt/a.mkv")])) == ["/mnt/a.mkv"]


def test_every_part_of_every_version_is_reported():
    item = Item(media=[Media("/mnt/cd1.avi", "/mnt/cd2.avi"), Media("/mnt/hd.mkv")])
    assert file_paths(item) == ["/mnt/cd1.avi", "/mnt/cd2.avi", "/mnt/hd.mkv"]


def test_a_container_with_no_media_yields_nothing():
    """A show's files belong to its episodes, not to the show."""
    assert file_paths(Item(media=[])) == []
    assert file_paths(Item()) == []


def test_parts_without_a_path_are_skipped():
    assert file_paths(Item(media=[Media(None, "/mnt/b.mkv")])) == ["/mnt/b.mkv"]


def test_file_paths_does_not_trigger_a_reload():
    class Exploding(Item):
        def __getattr__(self, name):
            raise AssertionError(f"reload triggered for {name}")
    assert file_paths(Exploding()) == []


# --- nested media in listing records -------------------------------------

class PartFull:
    def __init__(self, file):
        self.file, self.size, self.container = file, 100, "mkv"
        self._server = object()


class MediaFull:
    def __init__(self, *files):
        self.parts = [PartFull(f) for f in files]
        self.videoResolution = "1080"


def test_media_is_expanded_rather_than_repr_d():
    """A repr like '<Media object at 0x...>' carries nothing."""
    fields = loaded_fields(Item(media=[MediaFull("/mnt/a.mkv")]))
    assert fields["media"][0]["parts"][0]["file"] == "/mnt/a.mkv"
    assert "object at 0x" not in str(fields["media"])


def test_the_file_paths_are_also_surfaced_at_the_top_level():
    fields = loaded_fields(Item(media=[MediaFull("/mnt/a.mkv")]))
    assert fields["files"] == ["/mnt/a.mkv"]


def test_no_files_key_when_the_item_has_no_media():
    assert "files" not in loaded_fields(Item())


def test_private_attributes_of_nested_objects_are_skipped():
    fields = loaded_fields(Item(media=[MediaFull("/mnt/a.mkv")]))
    assert "_server" not in fields["media"][0]["parts"][0]


def test_a_self_referential_object_does_not_recurse_forever():
    class Loop:
        def __init__(self):
            self.name = "x"
            self.parent = self
    loaded_fields(Item(loop=Loop()))          # must simply return


def test_an_object_without_a_dict_falls_back_to_text():
    class Slotted:
        __slots__ = ()
    assert isinstance(loaded_fields(Item(thing=Slotted()))["thing"], str)
