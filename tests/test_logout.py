# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""logout: signing tokens out at plex.tv and removing them from the store."""

import argparse
import json

import pytest
from plexapi.exceptions import Unauthorized
from requests import ConnectionError as RequestsConnectionError

from plexdo import secret_store
from plexdo.commands import auth
from plexdo.tokens import load_store, save_password, saved_password


class SignOutRecorder:
    """Stands in for MyPlexAccount, recording which tokens sign out.

    A token in `invalid` is refused as plex.tv refuses a dead one, when the
    account is first loaded; one in `unreachable` fails as a network would.
    """

    def __init__(self, invalid=(), unreachable=()):
        self.invalid, self.unreachable = set(invalid), set(unreachable)
        self.signed_out = []

    def __call__(self, token):
        if token in self.invalid:
            raise Unauthorized("(401) unauthorized")
        recorder = self

        class Account:  # pylint: disable=too-few-public-methods
            def signout(self):
                if token in recorder.unreachable:
                    raise RequestsConnectionError("plex.tv unreachable")
                recorder.signed_out.append(token)

        return Account()


@pytest.fixture
def store(secrets):
    """A secret store holding three sessions."""
    secret_store.save(
        "tokens",
        {"@admin": "t-admin", "alice@example.com": "t-alice", "bob": "t-bob"},
    )
    return secrets


def logout(monkeypatch, recorder, username=None, fmt="table", dry_run=False):
    monkeypatch.setattr(auth, "MyPlexAccount", lambda token: recorder(token))
    auth.cmd_logout(
        None, argparse.Namespace(username=username, format=fmt, dry_run=dry_run)
    )


def test_every_session_is_signed_out_and_the_empty_entry_removed(
    store, monkeypatch, capsys
):
    recorder = SignOutRecorder()
    logout(monkeypatch, recorder)
    assert sorted(recorder.signed_out) == ["t-admin", "t-alice", "t-bob"]
    assert "tokens" not in store.entries
    assert "plexdo login" in capsys.readouterr().out


def test_a_signed_out_users_saved_password_goes_too(store, monkeypatch):
    """Kept, it would sign the account straight back in on the next run."""
    save_password("alice@example.com", "pw-alice")
    save_password("bob", "pw-bob")
    logout(monkeypatch, SignOutRecorder(), username="alice@example.com")
    assert saved_password("alice@example.com") is None
    assert saved_password("bob") == "pw-bob"


def test_one_user_is_signed_out_and_the_rest_kept(store, monkeypatch):
    recorder = SignOutRecorder()
    logout(monkeypatch, recorder, username="alice@example.com")
    assert recorder.signed_out == ["t-alice"]
    assert load_store() == {"@admin": "t-admin", "bob": "t-bob"}


def test_a_user_matches_ignoring_case(store, monkeypatch):
    recorder = SignOutRecorder()
    logout(monkeypatch, recorder, username="Alice@Example.com")
    assert recorder.signed_out == ["t-alice"]


def test_a_user_not_in_the_file_is_an_error_and_signs_out_nobody(
    store, monkeypatch
):
    recorder = SignOutRecorder()
    with pytest.raises(SystemExit) as exc:
        logout(monkeypatch, recorder, username="carol")
    assert "carol" in str(exc.value) and "alice@example.com" in str(exc.value)
    assert recorder.signed_out == []
    assert len(load_store()) == 3


def test_a_token_plex_tv_already_refuses_is_removed(store, monkeypatch):
    recorder = SignOutRecorder(invalid={"t-bob"})
    logout(monkeypatch, recorder, username="bob")
    assert "bob" not in load_store()


def test_a_failed_sign_out_keeps_that_token_and_exits_1(
    store, monkeypatch, capsys
):
    recorder = SignOutRecorder(unreachable={"t-bob"})
    with pytest.raises(SystemExit) as exc:
        logout(monkeypatch, recorder, fmt="json")
    assert "1 session(s)" in str(exc.value)
    # The others are gone; the one still valid is kept for another try.
    assert load_store() == {"bob": "t-bob"}
    records = {
        r["user"]: r["status"] for r in json.loads(capsys.readouterr().out)
    }
    assert records == {
        "@admin": "signed out",
        "alice@example.com": "signed out",
        "bob": "failed",
    }


def test_a_token_filed_twice_is_signed_out_once(store, monkeypatch):
    secret_store.save(
        "tokens", {"@admin": "t-same", "alice@example.com": "t-same"}
    )
    recorder = SignOutRecorder()
    logout(monkeypatch, recorder)
    assert recorder.signed_out == ["t-same"]
    assert "tokens" not in store.entries


def test_dry_run_signs_out_nothing_and_keeps_the_tokens(
    store, monkeypatch, capsys
):
    recorder = SignOutRecorder()
    logout(monkeypatch, recorder, dry_run=True)
    assert recorder.signed_out == []
    assert len(load_store()) == 3
    assert "would sign out" in capsys.readouterr().out


def test_nothing_stored_is_not_an_error(store, monkeypatch, capsys):
    store.entries.clear()
    logout(monkeypatch, SignOutRecorder(), fmt="json")
    assert json.loads(capsys.readouterr().out) == []
