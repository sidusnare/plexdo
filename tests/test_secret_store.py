# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Where secrets are kept, the move from 1.x, and the commands saving them."""

import argparse
import json
import os
import stat

import pytest
import yaml
from keyring.backends import chainer, fail

from conftest import REAL_BACKEND
from plexdo import config, migrate, secret_store
from plexdo.commands import auth
from plexdo.constants import SECRETS_EXAMPLE
from plexdo.tokens import ADMIN_KEY, lookup, saved_password, saved_pin


class FakeKeyring:  # pylint: disable=too-few-public-methods
    """A keyring backend, as keyring.get_keyring() returns one."""

    name = "fake keyring"

    def __init__(self):
        self.entries = {}

    def get_password(self, service, kind):
        return self.entries.get((service, kind))

    def set_password(self, service, kind, text):
        self.entries[(service, kind)] = text

    def delete_password(self, service, kind):
        del self.entries[(service, kind)]


# --- choosing the store ------------------------------------------------------


def test_auto_uses_a_keyring_when_there_is_one(monkeypatch, tmp_path):
    ring = FakeKeyring()
    monkeypatch.setattr(secret_store.keyring, "get_keyring", lambda: ring)
    store = secret_store.open_store("auto", tmp_path / "s.json")
    store.write("tokens", '{"a": "t"}')
    assert ring.entries == {("plexdo", "tokens"): '{"a": "t"}'}
    assert "fake keyring" in store.describe()


@pytest.mark.parametrize("none", [fail.Keyring(), chainer.ChainerBackend()])
def test_auto_falls_back_to_the_file_with_a_warning(
    monkeypatch, tmp_path, caplog, none
):
    monkeypatch.setattr(chainer.ChainerBackend, "backends", [])
    monkeypatch.setattr(secret_store.keyring, "get_keyring", lambda: none)
    store = secret_store.open_store("auto", tmp_path / "s.json")
    assert isinstance(store, secret_store.FileStore)
    assert "unencrypted" in caplog.text


def test_keyring_insisted_on_without_one_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_store.keyring, "get_keyring", fail.Keyring)
    with pytest.raises(SystemExit) as exc:
        secret_store.open_store("keyring", tmp_path / "s.json")
    assert "secret_store: file" in str(exc.value)


def test_file_is_used_without_asking_the_keyring(monkeypatch, tmp_path, caplog):
    def no_asking():
        raise AssertionError("asked for a keyring despite secret_store: file")

    monkeypatch.setattr(secret_store.keyring, "get_keyring", no_asking)
    store = secret_store.open_store("file", tmp_path / "s.json")
    assert isinstance(store, secret_store.FileStore)
    assert "unencrypted" not in caplog.text


def test_the_configured_store_and_file_are_used(monkeypatch, tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        f"plex:\n  url: x\n  secret_store: file\n"
        f"  secrets_file: {tmp_path}/mine.json\n"
    )
    monkeypatch.setattr(secret_store, "CONFIG_PATH", path)
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    config.cached_config.cache_clear()
    REAL_BACKEND.cache_clear()
    try:
        store = REAL_BACKEND()
        assert store.path == tmp_path / "mine.json"
    finally:
        REAL_BACKEND.cache_clear()
        config.cached_config.cache_clear()


# --- the secrets file --------------------------------------------------------


def test_the_file_is_private_from_the_start(tmp_path):
    store = secret_store.FileStore(tmp_path / "deep" / "s.json")
    store.write("tokens", '{"a": "t"}')
    mode = stat.S_IMODE(os.stat(store.path).st_mode)
    assert mode & 0o077 == 0
    assert json.loads(store.path.read_text()) == {"tokens": {"a": "t"}}


def test_the_file_goes_with_its_last_secret(tmp_path):
    store = secret_store.FileStore(tmp_path / "s.json")
    store.write("tokens", '{"a": "t"}')
    store.write("pins", '{"1": "1234"}')
    store.remove("tokens")
    assert store.read("pins") == '{"1": "1234"}'
    store.remove("pins")
    assert not store.path.exists()


def test_a_corrupt_file_is_an_error_naming_it(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json")
    path.chmod(0o600)
    with pytest.raises(SystemExit) as exc:
        secret_store.FileStore(path).read("tokens")
    assert str(path) in str(exc.value)


def test_an_unreadable_saved_kind_reads_as_empty(secrets, caplog):
    secrets.write("tokens", "not json")
    assert secret_store.load("tokens") == {}
    assert "not readable" in caplog.text


# --- moving from plexdo 1.x --------------------------------------------------

LEGACY_INI = """\
[plex]
url = https://10-0-0-5.abc.plex.direct:32400
token_path = {token_path}
username = fred@example.com
password = fred-secret
cache_dir = /var/cache/plexdo

[99]
username = bob@example.com
password = bob-secret

[826699965]
pin = 4321
"""


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    """A plexdo 1.x INI file and token file, and nowhere yet for 2.x's."""
    token_path = tmp_path / "plex.token"
    token_path.write_text(
        json.dumps({"fred@example.com": "t-fred", "bob@example.com": "t-bob"})
    )
    ini = tmp_path / "etc" / "plexdo.ini"
    ini.parent.mkdir()
    ini.write_text(LEGACY_INI.format(token_path=token_path))
    new = tmp_path / "config" / "plexdo" / "config.yaml"
    monkeypatch.setattr(migrate, "CONFIG_PATH", new)
    monkeypatch.setattr(
        migrate, "PATHS", migrate.PATHS._replace(legacy_config=ini)
    )
    return ini, token_path, new


def test_everything_is_moved_across(legacy):
    ini, token_path, new = legacy
    migrate.migrate_legacy_config()
    assert yaml.safe_load(new.read_text()) == {
        "plex": {
            "url": "https://10-0-0-5.abc.plex.direct:32400",
            "username": "fred@example.com",
            "cache_dir": "/var/cache/plexdo",
        },
        "users": {99: {"username": "bob@example.com"}},
    }
    assert lookup("fred@example.com") == "t-fred"
    assert lookup("bob@example.com") == "t-bob"
    assert saved_password("fred@example.com") == "fred-secret"
    assert saved_password("bob@example.com") == "bob-secret"
    assert saved_pin(826699965) == "4321"
    assert not ini.exists() and not token_path.exists()


def test_no_secret_is_left_in_plaintext(legacy):
    ini, _, new = legacy
    migrate.migrate_legacy_config()
    aside = ini.with_name("plexdo.ini.migrated")
    for text in (aside.read_text(), new.read_text()):
        for secret in ("fred-secret", "bob-secret", "4321"):
            assert secret not in text
    assert "bob@example.com" in aside.read_text()


def test_the_migrated_config_explains_every_option(legacy):
    *_, new = legacy
    migrate.migrate_legacy_config()
    text = new.read_text()
    assert "# The Plex Media Server, as a URL. Required." in text
    assert "secret_store" in text


def test_a_legacy_bare_token_file_is_the_admin_token(legacy):
    _, token_path, _ = legacy
    token_path.write_text("legacy-token\n")
    migrate.migrate_legacy_config()
    assert lookup(ADMIN_KEY) == "legacy-token"


def test_secrets_already_saved_are_kept_over_the_old_ones(legacy):
    secret_store.save("tokens", {"fred@example.com": "t-newer"})
    migrate.migrate_legacy_config()
    assert lookup("fred@example.com") == "t-newer"
    assert lookup("bob@example.com") == "t-bob"


def test_nothing_happens_once_there_is_a_config(legacy):
    ini, _, new = legacy
    new.parent.mkdir(parents=True)
    new.write_text("plex:\n  url: x\n")
    migrate.migrate_legacy_config()
    assert ini.exists() and lookup("fred@example.com") is None


def test_the_migration_is_announced(legacy, caplog):
    migrate.migrate_legacy_config()
    assert "Moved the plexdo 1.x configuration" in caplog.text
    assert "2 token(s), 2 password(s), and 1 PIN(s)" in caplog.text


# --- login, set-pin, and write-config-example ------------------------------


@pytest.fixture
def signing_in(monkeypatch):
    """Login against a stand-in plex.tv that accepts any password."""
    signed_in = []

    class Account:  # pylint: disable=too-few-public-methods
        def __init__(self, username, password, **_):
            signed_in.append((username, password))
            self.authenticationToken = f"t-{username}"

    monkeypatch.setattr(auth, "MyPlexAccount", Account)
    monkeypatch.setattr(
        auth,
        "load_config",
        lambda: {"plex": {"url": "http://10.0.0.5:32400"}, "users": {}},
    )
    monkeypatch.setattr(auth, "_verify_token", lambda url, token: True)
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt: "typed-pw")
    return signed_in


def login(**options):
    auth.cmd_login(
        None,
        argparse.Namespace(
            **{
                "username": "bob@example.com",
                "password": None,
                "code": None,
                "two_factor": False,
                "remember_login": False,
                "dry_run": False,
                "format": "json",
                **options,
            }
        ),
    )


def test_login_saves_the_token_and_not_the_password(signing_in):
    login()
    assert lookup("bob@example.com") == "t-bob@example.com"
    assert saved_password("bob@example.com") is None
    assert signing_in == [("bob@example.com", "typed-pw")]


def test_save_password_keeps_it_for_the_next_sign_in(signing_in, monkeypatch):
    login(remember_login=True)
    assert saved_password("bob@example.com") == "typed-pw"
    monkeypatch.setattr(
        auth.getpass,
        "getpass",
        lambda prompt: pytest.fail("prompted despite a saved password"),
    )
    login()
    assert signing_in[-1] == ("bob@example.com", "typed-pw")


def test_login_dry_run_saves_nothing(signing_in, secrets):
    login(remember_login=True, dry_run=True)
    assert not secrets.entries


def set_pin(user_id=826699965, remove=False, dry_run=False):
    auth.cmd_set_pin(
        None,
        argparse.Namespace(
            user_id=user_id, remove=remove, dry_run=dry_run, format="table"
        ),
    )


def test_set_pin_saves_a_four_digit_pin(monkeypatch):
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt: "1234")
    set_pin()
    assert saved_pin(826699965) == "1234"
    set_pin(remove=True)
    assert saved_pin(826699965) is None


@pytest.mark.parametrize("typed", ["12", "abcd", "12345"])
def test_set_pin_refuses_what_is_not_a_pin(monkeypatch, typed):
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt: typed)
    with pytest.raises(SystemExit):
        set_pin()
    assert saved_pin(826699965) is None


def test_set_pin_dry_run_saves_nothing(monkeypatch):
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt: "1234")
    set_pin(dry_run=True)
    assert saved_pin(826699965) is None


# --- write-secrets-example ---------------------------------------------------


@pytest.fixture
def config_file(monkeypatch, tmp_path):
    """A config path inside a temporary directory, not yet written."""
    path = tmp_path / "config.yaml"
    monkeypatch.setattr(auth, "CONFIG_PATH", path)
    return path


def write_secrets_example(**flags):
    args = argparse.Namespace(overwrite=False, dry_run=False)
    vars(args).update(flags)
    auth.cmd_write_secrets_example(None, args)


@pytest.mark.parametrize("body", [None, "plex:\n  url: http://x\n"])
def test_with_no_secrets_file_set_the_example_is_printed(
    config_file, capsys, tmp_path, body
):
    """No config at all sets no secrets_file either."""
    if body is not None:
        config_file.write_text(body)
    before = sorted(tmp_path.iterdir())
    write_secrets_example()
    captured = capsys.readouterr()
    assert captured.out == SECRETS_EXAMPLE
    assert "secrets_file is not set" in captured.err
    assert str(config_file) in captured.err
    assert sorted(tmp_path.iterdir()) == before


def test_the_example_is_written_where_secrets_file_says(
    config_file, capsys, tmp_path
):
    target = tmp_path / "private" / "secrets.json"
    config_file.write_text(f"plex:\n  url: x\n  secrets_file: {target}\n")
    write_secrets_example()
    captured = capsys.readouterr()
    assert target.read_text() == SECRETS_EXAMPLE
    assert str(target) in captured.out
    assert captured.err == ""
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_an_existing_secrets_file_is_refused_and_left_alone(
    config_file, tmp_path
):
    target = tmp_path / "secrets.json"
    target.write_text('{"tokens": {"me": "real"}}')
    config_file.write_text(f"plex:\n  url: x\n  secrets_file: {target}\n")
    for flags in ({}, {"dry_run": True}):
        with pytest.raises(SystemExit) as exc:
            write_secrets_example(**flags)
        assert "--overwrite" in str(exc.value)
    assert target.read_text() == '{"tokens": {"me": "real"}}'


def test_overwrite_replaces_the_secrets_file_privately(config_file, tmp_path):
    target = tmp_path / "secrets.json"
    target.write_text("{}")
    target.chmod(0o644)
    config_file.write_text(f"plex:\n  url: x\n  secrets_file: {target}\n")
    write_secrets_example(overwrite=True)
    assert target.read_text() == SECRETS_EXAMPLE
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_write_secrets_example_dry_run_writes_nothing(
    config_file, capsys, tmp_path
):
    target = tmp_path / "secrets.json"
    config_file.write_text(f"plex:\n  url: x\n  secrets_file: {target}\n")
    write_secrets_example(dry_run=True)
    assert not target.exists()
    assert str(target) in capsys.readouterr().err


def test_the_example_is_a_secrets_file_the_store_can_read(tmp_path):
    """Its three kinds load, and its note survives a later save."""
    path = tmp_path / "secrets.json"
    path.write_text(SECRETS_EXAMPLE)
    path.chmod(0o600)
    store = secret_store.FileStore(path)
    for kind in ("tokens", "passwords", "pins"):
        entries = json.loads(store.read(kind))
        assert entries and all(isinstance(v, str) for v in entries.values())
    store.write("pins", '{"1": "1234"}')
    assert "_comment" in json.loads(path.read_text())
