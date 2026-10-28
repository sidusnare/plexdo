# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Export path rewriting and the saved tokens, passwords, and PINs."""

import argparse

from conftest import FakePlex, FakeSection
from plexdo import tokens
from plexdo.paths import identity, mapper_for
from plexdo.tokens import (
    ADMIN_KEY,
    admin_token,
    load_store,
    lookup,
    store_token,
)

PLEX = FakePlex(
    [
        FakeSection(1, "Movies", ["/mnt/media/Movies"]),
        FakeSection(3, "TV", ["/mnt/media/TV", "/mnt/media2/TV Extra"]),
    ]
)


def mapper(prefix):
    return mapper_for(PLEX, argparse.Namespace(prefix=prefix))


def test_no_prefix_is_the_identity_and_costs_no_lookup():
    assert mapper(None) is identity


def test_library_root_is_replaced_by_the_prefix():
    assert (
        mapper("/Volumes/plex")("/mnt/media/TV/Show/S01E01.mkv")
        == "/Volumes/plex/Show/S01E01.mkv"
    )


def test_separators_follow_the_prefix_style():
    assert (
        mapper(r"Z:\Media")("/mnt/media/TV/Show/ep.mkv")
        == r"Z:\Media\Show\ep.mkv"
    )


def test_the_longest_matching_root_wins():
    """A library nested in another's tree must not match the shorter root."""
    assert mapper("/x")("/mnt/media2/TV Extra/Doc/ep.mkv") == "/x/Doc/ep.mkv"


def test_trailing_separator_on_the_prefix_is_tolerated():
    assert (
        mapper("smb://nas/media/")("/mnt/media/TV/a.mkv")
        == "smb://nas/media/a.mkv"
    )


def test_path_outside_any_library_is_kept_whole_and_warned_about(caplog):
    assert mapper("/x")("/srv/other/a.mkv") == "/x/srv/other/a.mkv"
    assert "library root" in caplog.text


# --- saved tokens, passwords, and PINs -------------------------------------


def test_nothing_saved_is_an_empty_store():
    assert load_store() == {}
    assert lookup("anyone") is None


def test_adding_a_token_keeps_the_others():
    store_token(ADMIN_KEY, "admin-token")
    store_token("bob@example.com", "bob-token")
    assert load_store() == {
        ADMIN_KEY: "admin-token",
        "bob@example.com": "bob-token",
    }


def test_tokens_are_one_entry_in_the_store(secrets):
    """Every token is filed in one entry.

    A keyring cannot list what it holds, and logout must read them back
    whole.
    """
    store_token("a@b", "tok")
    store_token("c@d", "tok2")
    assert list(secrets.entries) == ["tokens"]


def test_admin_token_prefers_the_configured_username():
    store_token("fred@x", "fred-tok")
    store_token("bob@x", "bob-tok")
    assert admin_token("bob@x") == "bob-tok"


def test_admin_token_falls_back_to_a_single_entry_store():
    store_token("fred@x", "fred-tok")
    assert admin_token(None) == "fred-tok"


def test_admin_token_is_ambiguous_with_several_entries_and_no_username():
    store_token("a@x", "1")
    store_token("b@x", "2")
    assert admin_token(None) is None


def test_the_last_token_forgotten_removes_the_entry(secrets):
    store_token("a@x", "1")
    assert tokens.forget_tokens(["a@x"]) == 0
    assert "tokens" not in secrets.entries


def test_passwords_are_filed_by_username_apart_from_tokens(secrets):
    tokens.save_password("bob@x", "pw")
    assert tokens.saved_password("bob@x") == "pw"
    assert tokens.saved_password("carol@x") is None
    assert lookup("bob@x") is None
    assert tokens.forget_passwords(["bob@x", "nobody"]) == 1
    assert "passwords" not in secrets.entries


def test_a_pin_is_saved_and_removed_by_user_id():
    tokens.save_pin(826699965, "1234")
    assert tokens.saved_pin(826699965) == "1234"
    tokens.save_pin(826699965, None)
    assert tokens.saved_pin(826699965) is None
