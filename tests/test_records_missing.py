# SPDX-License-Identifier: GPL-3.0-or-later

"""Listing records and episode-gap detection."""

import datetime

import pytest

from conftest import FakeItem, FakeMedia
from plexdo.commands.missing import episode_gaps
from plexdo.records import loaded_fields, release_date, summary_row


class Tag:
    """A plexapi tag object, as genres and directors are."""

    def __init__(self, tag):
        self.tag = tag


Item = FakeItem


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
    """These five are what the man page and README promise."""
    row = summary_row(Item(year=1999, rating=8.1, studio="A24"))
    assert tuple(row) == ("ratingKey", "title", "releaseDate", "rating", "studio")


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


def test_loaded_fields_disables_reload_while_reading():
    """Across a library, one reload per item would be one request per item."""
    class Exploding(Item):
        """Public attribute access explodes, as a reload would.

        plexapi returns underscore attributes without reloading, so those
        stay readable here too.
        """

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            raise AssertionError(f"reload triggered for {name}")
    item = Exploding()
    item._autoReload = True
    assert loaded_fields(item)["title"] == "A Title"
    assert item._autoReload is True          # restored afterwards


# --- file paths ----------------------------------------------------------

from plexdo.records import file_paths


def test_a_single_file_is_reported():
    assert file_paths(Item(media=[FakeMedia("/mnt/a.mkv")])) == ["/mnt/a.mkv"]


def test_every_part_of_every_version_is_reported():
    item = Item(media=[FakeMedia("/mnt/cd1.avi", "/mnt/cd2.avi"), FakeMedia("/mnt/hd.mkv")])
    assert file_paths(item) == ["/mnt/cd1.avi", "/mnt/cd2.avi", "/mnt/hd.mkv"]


def test_a_container_with_no_media_yields_nothing():
    """A show's files belong to its episodes, not to the show."""
    assert file_paths(Item(media=[])) == []
    assert file_paths(Item()) == []


def test_parts_without_a_path_are_skipped():
    assert file_paths(Item(media=[FakeMedia(None, "/mnt/b.mkv")])) == ["/mnt/b.mkv"]


def test_file_paths_does_not_trigger_a_reload():
    class Exploding(Item):
        """Public attribute access explodes, as a reload would.

        plexapi returns underscore attributes without reloading, so those
        stay readable here too.
        """

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            raise AssertionError(f"reload triggered for {name}")
    assert file_paths(Exploding()) == []


# --- nested media in listing records -------------------------------------

def test_media_is_expanded_rather_than_repr_d():
    """A repr like '<Media object at 0x...>' carries nothing."""
    fields = loaded_fields(Item(media=[FakeMedia("/mnt/a.mkv")]))
    assert fields["media"][0]["parts"][0]["file"] == "/mnt/a.mkv"
    assert "object at 0x" not in str(fields["media"])


def test_expansion_carries_the_surrounding_media_detail():
    """The point of expanding is the codec and size data, not just the path."""
    version = loaded_fields(Item(media=[FakeMedia("/mnt/a.mkv")]))["media"][0]
    assert version["videoResolution"] == "1080"
    assert version["parts"][0]["container"] == "mkv"
    assert version["parts"][0]["size"] == 100


def test_the_file_paths_are_also_surfaced_at_the_top_level():
    fields = loaded_fields(Item(media=[FakeMedia("/mnt/a.mkv")]))
    assert fields["files"] == ["/mnt/a.mkv"]


def test_no_files_key_when_the_item_has_no_media():
    assert "files" not in loaded_fields(Item())


def test_private_attributes_of_nested_objects_are_skipped():
    fields = loaded_fields(Item(media=[FakeMedia("/mnt/a.mkv")]))
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


# --- find-missing arguments ----------------------------------------------

from plexdo.commands.missing import _wanted, parse_seasons


@pytest.mark.parametrize("text,expected", [
    ("1", {1}), ("1,3,5", {1, 3, 5}), (" 2 , 4 ", {2, 4}), ("0", {0}),
])
def test_season_lists_are_parsed(text, expected):
    assert parse_seasons(text) == expected


@pytest.mark.parametrize("text", ["x", "1,,x", "", "  "])
def test_a_bad_season_list_is_refused(text):
    with pytest.raises(SystemExit):
        parse_seasons(text)


def test_season_zero_is_skipped_by_default():
    assert _wanted(0, None, False) is False
    assert _wanted(1, None, False) is True


def test_include_specials_brings_season_zero_back():
    assert _wanted(0, None, True) is True


def test_naming_a_season_overrides_the_specials_default():
    """Asking for --season 0 can only mean the specials."""
    assert _wanted(0, {0}, False) is True
    assert _wanted(1, {0}, False) is False


def test_a_named_season_list_selects_only_those():
    assert _wanted(3, {1, 3}, False) is True
    assert _wanted(2, {1, 3}, False) is False


# --- the file a player has open ------------------------------------------

from plexdo.records import playing_file


class SelPart:
    def __init__(self, file, selected=False):
        self.file, self.selected = file, selected


class SelMedia:
    def __init__(self, *parts, selected=False):
        self.parts, self.selected = list(parts), selected


def test_a_single_version_needs_no_selection():
    item = Item(media=[SelMedia(SelPart("/mnt/a.mkv"))])
    assert playing_file(item) == "/mnt/a.mkv"


def test_the_selected_version_wins_over_the_first():
    """A 4K and a 1080p copy: report the one actually being played."""
    item = Item(media=[SelMedia(SelPart("/mnt/4k.mkv")),
                       SelMedia(SelPart("/mnt/1080.mkv"), selected=True)])
    assert playing_file(item) == "/mnt/1080.mkv"


def test_the_selected_part_wins_within_a_version():
    item = Item(media=[SelMedia(SelPart("/mnt/cd1.avi"),
                                SelPart("/mnt/cd2.avi", selected=True))])
    assert playing_file(item) == "/mnt/cd2.avi"


def test_an_item_with_no_media_reports_nothing():
    assert playing_file(Item(media=[])) == ""
    assert playing_file(Item()) == ""


def test_playing_file_does_not_trigger_a_reload():
    class Exploding(Item):
        """Public attribute access explodes, as a reload would.

        plexapi returns underscore attributes without reloading, so those
        stay readable here too.
        """

        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            raise AssertionError(f"reload triggered for {name}")
    assert playing_file(Exploding()) == ""


# --- reading real plexapi object shapes ----------------------------------

import xml.etree.ElementTree as ET


class Lazy:
    """A plexapi-shaped object: XML in _data, media as a lazy property.

    plexapi moved media, genres and a dozen others to cached_data_property,
    which is absent from vars() until first accessed, so anything reading
    only vars() sees nothing.
    """

    _cached_data_properties = {"media"}

    def __init__(self, xml):
        self._data = ET.fromstring(xml)
        self._autoReload = True
        self.ratingKey = 101
        self.title = "Blade Runner 2049"

    @property
    def media(self):
        raise AssertionError("read from _data, not the lazy property")


TWO_VERSIONS = """<Video ratingKey="101" title="Blade Runner 2049">
  <Media id="1" videoResolution="4k" selected="0">
    <Part id="11" file="/mnt/4k.mkv" selected="0"/>
  </Media>
  <Media id="2" videoResolution="1080" selected="1">
    <Part id="12" file="/mnt/1080.mkv" selected="1"/>
  </Media>
</Video>"""

NO_MEDIA = '<Directory ratingKey="1" title="Breaking Bad" type="show"/>'


def test_file_paths_reads_a_real_object_shape():
    assert file_paths(Lazy(TWO_VERSIONS)) == ["/mnt/4k.mkv", "/mnt/1080.mkv"]


def test_playing_file_reads_a_real_object_shape():
    assert playing_file(Lazy(TWO_VERSIONS)) == "/mnt/1080.mkv"


def test_a_container_with_no_media_element_yields_nothing():
    assert file_paths(Lazy(NO_MEDIA)) == []
    assert playing_file(Lazy(NO_MEDIA)) == ""
