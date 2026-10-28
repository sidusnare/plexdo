# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Resolving a user or library by numeric ID or by title."""

import pytest

from plexdo.identify import resolve_identifier

# Library 3 is titled "TV Shows"; library 9 is *titled* "3", so "3" is
# simultaneously one entry's ID and another's title.
ROSTER = [(1, "Movies"), (3, "TV Shows"), (5, "My Photos"), (9, "3")]
DUPES = [(1, "Media"), (2, "Media")]


def r(value, roster=ROSTER):
    return resolve_identifier(roster, value, "library", "list-libraries")


def test_numeric_id_resolves_to_itself():
    assert r("1") == 1


def test_title_resolves_to_its_id():
    assert r("TV Shows") == 3


def test_title_match_is_case_insensitive_as_a_fallback():
    assert r("movies") == 1


def test_exact_title_match_beats_a_case_insensitive_one():
    roster = [(1, "Media"), (2, "media")]
    assert resolve_identifier(roster, "media", "library", "x") == 2


def test_id_wins_when_a_value_is_both_an_id_and_another_entrys_title(caplog):
    assert r("3") == 3
    assert "9" in caplog.text


def test_numeric_value_that_is_only_a_title_resolves_by_title():
    assert (
        resolve_identifier([(1, "Movies"), (9, "3")], "3", "library", "x") == 9
    )


def test_unknown_numeric_id_passes_through_for_the_caller_to_report():
    assert r("77") == 77


def test_duplicate_titles_abort():
    with pytest.raises(SystemExit) as exc:
        resolve_identifier(DUPES, "Media", "library", "list-libraries")
    assert "1, 2" in str(exc.value)


def test_duplicate_titles_do_not_block_an_unambiguous_numeric_id():
    assert resolve_identifier(DUPES, "1", "library", "x") == 1


def test_unknown_title_aborts_naming_the_listing_command():
    with pytest.raises(SystemExit) as exc:
        r("Nothing")
    assert "list-libraries" in str(exc.value)


def test_messages_name_the_kind_being_resolved():
    with pytest.raises(SystemExit) as exc:
        resolve_identifier([(0, "Fred")], "Ghost", "user", "list-users")
    assert "User not found" in str(exc.value)
