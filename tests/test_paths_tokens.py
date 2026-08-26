# SPDX-License-Identifier: GPL-3.0-or-later

"""Export path rewriting and the on-disk token store."""

import argparse
import json

from conftest import FakePlex, FakeSection
from plexdo.paths import identity, mapper_for
from plexdo.tokens import ADMIN_KEY, admin_token, load_store, lookup, store_token

PLEX = FakePlex([
    FakeSection(1, "Movies", ["/mnt/media/Movies"]),
    FakeSection(3, "TV", ["/mnt/media/TV", "/mnt/media2/TV Extra"]),
])


def mapper(prefix):
    return mapper_for(PLEX, argparse.Namespace(prefix=prefix))


def test_no_prefix_is_the_identity_and_costs_no_lookup():
    assert mapper(None) is identity


def test_library_root_is_replaced_by_the_prefix():
    assert mapper("/Volumes/plex")("/mnt/media/TV/Show/S01E01.mkv") == \
        "/Volumes/plex/Show/S01E01.mkv"


def test_separators_follow_the_prefix_style():
    assert mapper(r"Z:\Media")("/mnt/media/TV/Show/ep.mkv") == r"Z:\Media\Show\ep.mkv"


def test_the_longest_matching_root_wins():
    """A library nested in another's tree must not match the shorter root."""
    assert mapper("/x")("/mnt/media2/TV Extra/Doc/ep.mkv") == "/x/Doc/ep.mkv"


def test_trailing_separator_on_the_prefix_is_tolerated():
    assert mapper("smb://nas/media/")("/mnt/media/TV/a.mkv") == "smb://nas/media/a.mkv"


def test_path_outside_any_library_is_kept_whole_and_warned_about(caplog):
    assert mapper("/x")("/srv/other/a.mkv") == "/x/srv/other/a.mkv"
    assert "library root" in caplog.text


# --- token store ---------------------------------------------------------

def test_absent_empty_and_corrupt_files_degrade_to_an_empty_store(tmp_path):
    assert load_store(tmp_path / "nope.json") == {}
    (tmp_path / "empty").write_text("")
    assert load_store(tmp_path / "empty") == {}
    (tmp_path / "arr.json").write_text("[1,2]")
    assert load_store(tmp_path / "arr.json") == {}


def test_a_legacy_bare_token_file_is_read_as_the_admin_token(tmp_path):
    legacy = tmp_path / "tok"
    legacy.write_text("legacy-token\n")
    assert load_store(legacy) == {ADMIN_KEY: "legacy-token"}
    assert admin_token(legacy, None) == "legacy-token"


def test_adding_a_user_converts_a_legacy_file_and_keeps_the_admin_token(tmp_path):
    legacy = tmp_path / "tok"
    legacy.write_text("legacy-token\n")
    store_token(legacy, "bob@example.com", "bob-token")
    data = json.loads(legacy.read_text())
    assert data == {ADMIN_KEY: "legacy-token", "bob@example.com": "bob-token"}


def test_stored_files_are_owner_only(tmp_path):
    path = tmp_path / "t.json"
    store_token(path, "a@b", "tok")
    assert path.stat().st_mode & 0o077 == 0


def test_lookup_returns_none_for_an_unknown_user(tmp_path):
    path = tmp_path / "t.json"
    store_token(path, "a@b", "tok")
    assert lookup(path, "nobody@x") is None


def test_admin_token_prefers_the_configured_username(tmp_path):
    path = tmp_path / "t.json"
    store_token(path, "fred@x", "fred-tok")
    store_token(path, "bob@x", "bob-tok")
    assert admin_token(path, "bob@x") == "bob-tok"


def test_admin_token_falls_back_to_a_single_entry_store(tmp_path):
    path = tmp_path / "t.json"
    store_token(path, "fred@x", "fred-tok")
    assert admin_token(path, None) == "fred-tok"


def test_admin_token_is_ambiguous_with_several_entries_and_no_username(tmp_path):
    path = tmp_path / "t.json"
    store_token(path, "a@x", "1")
    store_token(path, "b@x", "2")
    assert admin_token(path, None) is None
