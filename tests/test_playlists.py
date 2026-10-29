# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Playlist creation guards and the copy naming rules."""

import argparse

import pytest

from conftest import FakeItem, FakePlaylist, FakePlex
from plexdo.commands.build import (
    _concatenate,
    _merge,
    _parse_ratio,
)
from plexdo.commands.playlists import _watched_entries
from plexdo.playlists import _resolve_dest_name, finalize_playlist

ITEMS = [FakeItem(1, "A"), FakeItem(2, "B")]


def plex_with(*titles):
    return FakePlex(
        playlists=[FakePlaylist(t, 900 + i) for i, t in enumerate(titles)]
    )


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
    assert _resolve_dest_name(plex_with("Mix"), "Mix") == (
        "Mix admin copy",
        False,
    )


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
    return [
        (pos, item.title, label)
        for pos, item, label in _watched_entries(items, include_partial)
    ]


def test_played_entries_are_removed_and_the_rest_kept():
    items = [
        FakeItem(1, "A", viewCount=1),
        FakeItem(2, "B"),
        FakeItem(3, "C", viewCount=2),
    ]
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
    """The isPlayed flag of plexapi is authoritative; viewCount falls back."""
    items = [
        FakeItem(1, "A", isPlayed=False, viewCount=3),
        FakeItem(2, "B", isWatched=True, viewCount=0),
    ]
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


# --- build-merge: mixing two playlists at a ratio --------------------------


def merged(first, second, ratio=(1, 1), **flags):
    """Titles of the merge, in order, separated by spaces."""
    result = _merge(first, second, ratio, **flags)
    return " ".join(item.title for item in result.items)


def items(prefix, count):
    return [
        FakeItem(100 * ord(prefix) + n, f"{prefix}{n}") for n in range(count)
    ]


def test_one_to_one_alternates():
    assert merged(items("a", 3), items("b", 3)) == "a0 b0 a1 b1 a2 b2"


def test_a_ratio_takes_runs_of_each_in_turn():
    assert merged(items("a", 4), items("b", 2), (2, 1)) == "a0 a1 b0 a2 a3 b1"
    assert (
        merged(items("a", 2), items("b", 6), (1, 3))
        == "a0 b0 b1 b2 a1 b3 b4 b5"
    )


def test_the_rest_of_the_longer_playlist_follows():
    assert merged(items("a", 1), items("b", 3)) == "a0 b0 b1 b2"
    assert merged(items("a", 5), items("b", 1), (2, 1)) == "a0 a1 b0 a2 a3 a4"


def test_an_empty_side_leaves_the_other_as_it_was():
    assert merged([], items("b", 2)) == "b0 b1"
    assert merged(items("a", 2), [], (3, 2)) == "a0 a1"
    assert merged([], []) == ""


def test_repeats_are_kept():
    assert merged([A, B], [A, C]) == "A A B C"


@pytest.mark.parametrize(
    ("counts", "ratio", "ran_out", "unmixed"),
    [
        ((3, 3), (1, 1), None, 0),
        ((4, 2), (2, 1), None, 0),
        ((3, 2), (2, 1), None, 0),
        ((3, 1), (2, 1), 1, 1),
        ((1, 3), (1, 1), 0, 2),
        ((5, 1), (2, 1), 1, 3),
        ((0, 2), (1, 1), 0, 2),
    ],
)
def test_the_unmixed_tail_is_counted(counts, ratio, ran_out, unmixed):
    result = _merge(items("a", counts[0]), items("b", counts[1]), ratio)
    assert (result.ran_out, result.unmixed, result.left_out) == (
        ran_out,
        unmixed,
        0,
    )


def test_stop_short_ends_with_the_last_turn_both_took_part_in():
    assert merged(items("a", 1), items("b", 3), stop_short=True) == "a0 b0"
    assert (
        merged(items("a", 5), items("b", 1), (2, 1), stop_short=True)
        == "a0 a1 b0"
    )
    # A short last run still counts as taking part.
    assert (
        merged(items("a", 3), items("b", 3), (2, 1), stop_short=True)
        == "a0 a1 b0 a2 b1"
    )


def test_stop_short_counts_what_it_left_out():
    result = _merge(items("a", 5), items("b", 1), (2, 1), stop_short=True)
    assert (result.ran_out, result.unmixed, result.left_out) == (1, 0, 3)


def test_stop_short_changes_nothing_when_both_run_out_together():
    a, b = items("a", 4), items("b", 2)
    assert merged(a, b, (2, 1), stop_short=True) == merged(a, b, (2, 1))


def test_stop_short_with_an_empty_side_gives_nothing():
    assert merged([], items("b", 2), stop_short=True) == ""


def test_unique_passes_over_a_repeat_without_losing_its_place():
    """The next item of the same playlist takes the repeat's place."""
    assert merged([A, B], [A, C], unique=True) == "A C B"
    result = _merge([A, B], [A, C], (1, 1), unique=True)
    assert result.skipped == 1


def test_unique_matches_on_rating_key_and_within_one_playlist():
    first = [FakeItem(1, "A"), FakeItem(1, "A again"), FakeItem(2, "B")]
    second = [FakeItem(2, "B again"), C]
    assert merged(first, second, unique=True) == "A B again C"


def test_a_playlist_left_with_only_repeats_has_run_out():
    """The second has nothing new after B; the first's B and C go unread."""
    result = _merge([A, B, C], [A, B], (1, 1), unique=True, stop_short=True)
    assert [item.title for item in result.items] == ["A", "B"]
    assert (result.ran_out, result.left_out) == (1, 2)


@pytest.mark.parametrize(
    ("text", "ratio"), [("1:1", (1, 1)), ("3:2", (3, 2)), (" 10 : 1 ", (10, 1))]
)
def test_a_ratio_is_two_counts(text, ratio):
    assert _parse_ratio(text) == ratio


@pytest.mark.parametrize(
    "text", ["2", "2:0", "0:1", "1:2:3", "-1:1", "a:b", "1.5:1", "\u00b2:1"]
)
def test_a_bad_ratio_is_refused(text):
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_ratio(text)
