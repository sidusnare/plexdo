# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist creation guards and the copy naming rules."""

import pytest

from conftest import FakeItem, FakePlaylist, FakePlex
from plexdo.commands.build import _concatenate
from plexdo.commands.playlists import _watched_entries
from plexdo.playlists import _resolve_dest_name, finalize_playlist

ITEMS = [FakeItem(1, "A"), FakeItem(2, "B")]


def plex_with(*titles):
    return FakePlex(playlists=[FakePlaylist(t, 900 + i) for i, t in enumerate(titles)])


def test_empty_playlist_is_refused(args):
    with pytest.raises(SystemExit):
        finalize_playlist(FakePlex(), "Mix", [], args)


def test_creates_when_the_name_is_free(args):
    plex = plex_with()
    assert finalize_playlist(plex, "Mix", ITEMS, args) == "created"
    assert plex.created == [("Mix", ITEMS)]


def test_name_collision_without_overwrite_creates_and_deletes_nothing(args):
    plex = plex_with("Mix")
    with pytest.raises(SystemExit) as exc:
        finalize_playlist(plex, "Mix", ITEMS, args)
    assert "--overwrite" in str(exc.value)
    assert plex.created == []
    assert not plex.playlists()[0].deleted


def test_overwrite_replaces_the_existing_playlist(args):
    args.overwrite = True
    plex = plex_with("Mix")
    assert finalize_playlist(plex, "Mix", ITEMS, args) == "replaced"
    assert plex.playlists()[0].deleted
    assert plex.created == [("Mix", ITEMS)]


def test_dry_run_touches_nothing(args):
    args.overwrite, args.dry_run = True, True
    plex = plex_with("Mix")
    finalize_playlist(plex, "Mix", ITEMS, args)
    assert plex.created == [] and not plex.playlists()[0].deleted


# --- copy destination naming --------------------------------------------

def test_free_name_is_used_as_is():
    assert _resolve_dest_name(plex_with(), "Mix") == ("Mix", False)


def test_taken_name_falls_back_to_admin_copy():
    assert _resolve_dest_name(plex_with("Mix"), "Mix") == ("Mix admin copy", False)


def test_both_names_taken_means_skip_rather_than_clobber():
    assert _resolve_dest_name(plex_with("Mix", "Mix admin copy"), "Mix") is None


def test_overwrite_targets_the_plain_name_and_reports_a_replacement():
    plex = plex_with("Mix", "Mix admin copy")
    assert _resolve_dest_name(plex, "Mix", True) == ("Mix", True)


def test_overwrite_on_an_empty_destination_is_not_a_replacement():
    assert _resolve_dest_name(plex_with(), "Mix", True) == ("Mix", False)


# --- clean-playlist: which entries count as watched ----------------------

def labelled(items, include_partial=False):
    """(position, title, label) for the entries a clean run would remove."""
    return [(pos, item.title, label)
            for pos, item, label in _watched_entries(items, include_partial)]


def test_played_entries_are_removed_and_the_rest_kept():
    items = [FakeItem(1, "A", viewCount=1), FakeItem(2, "B"),
             FakeItem(3, "C", viewCount=2)]
    assert labelled(items) == [(1, "A", "played"), (3, "C", "played")]


def test_positions_are_the_playlists_own_numbering():
    """The preview must point at what Plex shows, not renumber the gaps."""
    items = [FakeItem(1, "A"), FakeItem(2, "B"), FakeItem(3, "C", viewCount=1)]
    assert labelled(items) == [(3, "C", "played")]


def test_a_resume_point_is_kept_by_default():
    """Part-played is what the user is in the middle of, not watched."""
    assert labelled([FakeItem(1, "A", viewOffset=90_000)]) == []


def test_include_partial_removes_a_resume_point():
    items = [FakeItem(1, "A", viewOffset=90_000), FakeItem(2, "B")]
    assert labelled(items, True) == [(1, "A", "partial")]


def test_is_played_beats_a_stale_view_count():
    """plexapi's isPlayed is authoritative; viewCount is only the fallback."""
    items = [FakeItem(1, "A", isPlayed=False, viewCount=3),
             FakeItem(2, "B", isWatched=True, viewCount=0)]
    assert labelled(items) == [(2, "B", "played")]


def test_an_untouched_playlist_yields_nothing_to_remove():
    assert labelled([FakeItem(1, "A"), FakeItem(2, "B")]) == []


# --- build-concatenated: joining sources end to end ----------------------

def joined(sources, unique=False):
    """Titles of the concatenation, in order."""
    return [item.title for item in _concatenate(sources, unique)]


A, B, C = FakeItem(1, "A"), FakeItem(2, "B"), FakeItem(3, "C")


def test_sources_are_joined_in_the_order_given():
    assert joined([("one", [A, B]), ("two", [C])]) == ["A", "B", "C"]
    assert joined([("two", [C]), ("one", [A, B])]) == ["C", "A", "B"]


def test_duplicates_are_kept_by_default():
    """Plex allows a repeat, and a plain concatenation is faithful."""
    assert joined([("one", [A, B]), ("two", [B, C])]) == ["A", "B", "B", "C"]


def test_unique_keeps_the_first_appearance_only():
    assert joined([("one", [A, B]), ("two", [B, C])], True) == ["A", "B", "C"]


def test_unique_also_collapses_a_repeat_inside_one_source():
    assert joined([("one", [A, B, A])], True) == ["A", "B"]


def test_an_item_is_identified_by_rating_key_not_title():
    """Two playlists hold separate objects for the same item."""
    same = [("one", [FakeItem(1, "A")]), ("two", [FakeItem(1, "A again")])]
    assert joined(same, True) == ["A"]


def test_empty_sources_contribute_nothing():
    assert joined([("one", []), ("two", [A]), ("three", [])]) == ["A"]
