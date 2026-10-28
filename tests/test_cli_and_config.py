# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Argument parsing, config handling, and the command registry."""

from pathlib import Path

import pytest

from plexdo import __version__
from plexdo.cli import build_parser
from plexdo.commands import MODULES, build_registry
from plexdo.constants import default_paths, windows_app_dir


@pytest.fixture(scope="module")
def parser():
    return build_parser()


def test_every_command_module_exposes_the_registry_contract():
    for module in MODULES:
        assert hasattr(module, "register")
        assert module.COMMANDS
        assert isinstance(module.REQUIRES_PLEX, frozenset)


def test_registry_has_no_duplicate_command_names():
    names = [n for m in MODULES for n in m.COMMANDS]
    assert len(names) == len(set(names))


def test_only_the_account_and_config_commands_run_without_a_server():
    handlers, needs_plex = build_registry()
    assert set(handlers) - needs_plex == {
        "login",
        "logout",
        "set-pin",
        "write-config-example",
    }


@pytest.mark.parametrize(
    "flag,attr,value",
    [
        ("--json", "format", "json"),
        ("-f", "format", "yaml"),
        ("-v", "verbose", True),
        ("--dry-run", "dry_run", True),
    ],
)
def test_global_flags_work_before_the_command(parser, flag, attr, value):
    argv = (
        [flag, "yaml", "list-users"] if flag == "-f" else [flag, "list-users"]
    )
    assert getattr(parser.parse_args(argv), attr) == value


@pytest.mark.parametrize(
    "flag,attr,value",
    [
        ("--json", "format", "json"),
        ("-f", "format", "yaml"),
        ("-v", "verbose", True),
        ("--dry-run", "dry_run", True),
    ],
)
def test_global_flags_work_after_the_command(parser, flag, attr, value):
    argv = (
        ["list-users", flag, "yaml"] if flag == "-f" else ["list-users", flag]
    )
    assert getattr(parser.parse_args(argv), attr) == value


def test_a_flag_given_before_the_command_is_not_clobbered_by_the_subparser(
    parser,
):
    """The subparser copies its whole namespace over; SUPPRESS prevents that."""
    assert (
        parser.parse_args(["--json", "copy-watched", "7", "9"]).format == "json"
    )


def test_users_and_libraries_accept_titles_not_just_numbers(parser):
    assert parser.parse_args(["list-playlists", "Alice"]).user_id == "Alice"
    assert (
        parser.parse_args(["list-titles", "TV Shows"]).library_id == "TV Shows"
    )


def test_minus_one_parses_as_the_one_way_flag_not_a_negative_number(parser):
    assert parser.parse_args(["copy-watched", "7", "9", "-1"]).one_way is True


@pytest.mark.parametrize(
    "command",
    [
        "build-interleaved",
        "build-chronological",
        "build-randomize",
        "copy-playlist-all-users",
        "copy-playlist-to-user",
    ],
)
def test_every_creating_command_offers_overwrite(parser, command):
    action = {
        a.dest
        for p in [parser._subparsers._group_actions[0].choices[command]]
        for a in p._actions
    }
    assert "overwrite" in action


@pytest.mark.parametrize(
    "command",
    [
        "list-playlist",
        "list-show",
        "export-playlist",
        "export-titles",
        "build-interleaved",
        "build-chronological",
        "build-randomize",
    ],
)
def test_every_export_command_offers_a_path_prefix(parser, command):
    dests = {
        a.dest
        for a in parser._subparsers._group_actions[0].choices[command]._actions
    }
    assert "prefix" in dests


def test_version_flag_reports_the_package_version(parser, capsys):
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])
    assert __version__ in capsys.readouterr().out


# --- configuration -------------------------------------------------------


def write_config(tmp_path, body):
    path = tmp_path / "config.yaml"
    path.write_text(body)
    return path


@pytest.fixture
def load(tmp_path, monkeypatch):
    """Load a config file with this body, as plexdo would."""
    from plexdo import config

    def loader(body):
        monkeypatch.setattr(config, "CONFIG_PATH", write_config(tmp_path, body))
        return config.load_config()

    return loader


def test_environment_variables_are_expanded(load, monkeypatch):
    monkeypatch.setenv("HOST", "media.lan")
    cfg = load("plex:\n  url: http://$HOST:32400\n")
    assert cfg["plex"]["url"] == "http://media.lan:32400"


def test_an_unset_variable_is_left_literal_and_warned_about(
    load, monkeypatch, caplog
):
    monkeypatch.delenv("NOPE_UNSET", raising=False)
    cfg = load("plex:\n  url: x\n  cache_dir: $NOPE_UNSET/c\n")
    assert "$NOPE_UNSET" in cfg["plex"]["cache_dir"]
    assert "NOPE_UNSET" in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        "plex:\n  url: x\n  password: hunter2\n",
        "plex:\n  url: x\nusers:\n  99:\n    username: bob\n    password: pw\n",
        "plex:\n  url: x\nusers:\n  99:\n    pin: '1234'\n",
    ],
)
def test_a_secret_in_the_config_is_ignored_and_warned_about(load, caplog, body):
    """Secrets belong in the keyring; the file must never hold one."""
    cfg = load(body)
    assert "hunter2" not in repr(cfg) and "pw" not in repr(cfg.get("users"))
    assert "1234" not in repr(cfg)
    assert "keyring" in caplog.text


def test_an_unknown_option_is_warned_about_by_name(load, caplog):
    cfg = load("plex:\n  url: x\n  urll: y\n")
    assert "urll" not in cfg["plex"] and "'urll'" in caplog.text


@pytest.mark.parametrize(
    "body, said",
    [
        ("plex: [unclosed\n", "not valid YAML"),
        ("- a list\n", "mapping"),
        ("plex:\n  url: x\nusers:\n  bob:\n    username: bob\n", "user id"),
        ("plex:\n  url: x\n  secret_store: vault\n", "secret_store"),
        ("plex:\n  url: [a, b]\n", "single value"),
    ],
)
def test_a_malformed_config_is_an_error_saying_what_is_wrong(load, body, said):
    with pytest.raises(SystemExit) as exc:
        load(body)
    assert said in str(exc.value)


def test_users_entries_are_keyed_by_id_as_text(load):
    from plexdo.config import configured_users, user_option

    cfg = load(
        "plex:\n  url: x\nusers:\n  99:\n    username: bob\n"
        "  '100':\n    username: carol\n"
    )
    assert configured_users(cfg) == [(99, "bob"), (100, "carol")]
    assert user_option(cfg, 99, "username") == "bob"
    assert user_option(cfg, 7, "username") is None


def test_an_empty_file_is_a_config_with_nothing_set(load):
    assert load("") == {"plex": {}, "users": {}}


def test_a_missing_config_says_how_to_make_one(tmp_path, monkeypatch):
    from plexdo import config

    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "absent.yaml")
    with pytest.raises(SystemExit) as exc:
        config.load_config()
    assert "write-config-example" in str(exc.value)


def test_a_config_without_a_url_is_an_error_where_it_is_needed():
    from plexdo.connection import server_url

    with pytest.raises(SystemExit) as exc:
        server_url({"plex": {}, "users": {}})
    assert "plex: url" in str(exc.value)


# --- platform defaults ---------------------------------------------------

WIN_ENV = {"LOCALAPPDATA": r"C:\Users\me\AppData\Local", "TEMP": r"C:\Temp"}
WIN_APP = Path(r"C:\Users\me\AppData\Local") / "PlexDo"


def test_windows_keeps_everything_under_localappdata():
    paths = default_paths(True, WIN_ENV)
    assert paths.config == WIN_APP / "config.yaml"
    assert paths.cache == WIN_APP / "Cache"
    assert paths.secrets == WIN_APP / "secrets.json"
    assert paths.legacy_config == WIN_APP / "plexdo.ini"


def test_windows_falls_back_to_appdata_when_localappdata_is_unset():
    assert (
        windows_app_dir({"APPDATA": r"C:\Roaming"})
        == Path(r"C:\Roaming") / "PlexDo"
    )


def test_windows_survives_neither_variable_being_set():
    assert windows_app_dir({}).name == "PlexDo"


def test_posix_defaults_follow_the_xdg_base_directories():
    paths = default_paths(False, {})
    assert paths.config == Path("~/.config/plexdo/config.yaml").expanduser()
    assert paths.cache == Path("~/.cache/plexdo").expanduser()
    assert (
        paths.secrets == Path("~/.local/state/plexdo/secrets.json").expanduser()
    )
    assert paths.legacy_config == Path("~/.local/etc/plexdo.ini").expanduser()


def test_the_xdg_variables_move_each_directory():
    paths = default_paths(
        False,
        {
            "XDG_CONFIG_HOME": "/c",
            "XDG_CACHE_HOME": "/k",
            "XDG_STATE_HOME": "/s",
        },
    )
    assert paths.config == Path("/c/plexdo/config.yaml")
    assert paths.cache == Path("/k/plexdo")
    assert paths.secrets == Path("/s/plexdo/secrets.json")


def test_a_relative_xdg_variable_is_ignored_as_the_specification_says():
    paths = default_paths(False, {"XDG_CONFIG_HOME": "relative/dir"})
    assert paths.config == Path("~/.config/plexdo/config.yaml").expanduser()


# --- the template ----------------------------------------------------------


def test_the_template_is_valid_yaml_setting_only_the_url():
    import yaml

    from plexdo.config import parse_config
    from plexdo.constants import CONFIG_EXAMPLE

    assert yaml.safe_load(CONFIG_EXAMPLE) == {
        "plex": {"url": "http://localhost:32400"}
    }
    assert parse_config(CONFIG_EXAMPLE)["plex"] == {
        "url": "http://localhost:32400"
    }


def test_the_template_shows_every_option_with_its_default():
    from plexdo.config import _PLEX_OPTIONS, _USER_OPTIONS
    from plexdo.constants import (
        CONFIG_EXAMPLE,
        DEFAULT_CACHE_DIR,
        DEFAULT_SECRETS_FILE,
    )

    for option in _PLEX_OPTIONS + _USER_OPTIONS:
        assert f"{option}:" in CONFIG_EXAMPLE, option
    assert f"Default: {DEFAULT_CACHE_DIR}" in CONFIG_EXAMPLE
    assert f"Default: {DEFAULT_SECRETS_FILE}" in CONFIG_EXAMPLE
    assert 'Default: "auto"' in CONFIG_EXAMPLE


def test_values_are_quoted_so_any_text_survives():
    import yaml

    from plexdo.constants import config_text

    text = config_text(
        url="http://h:1/#x", username="a: b #c", users=[(99, "bob@example.com")]
    )
    assert yaml.safe_load(text) == {
        "plex": {"url": "http://h:1/#x", "username": "a: b #c"},
        "users": {99: {"username": "bob@example.com"}},
    }


# --- configurable cache directory ---------------------------------------


def test_cache_dir_defaults_to_the_platform_location(tmp_path, monkeypatch):
    from plexdo import cache

    monkeypatch.setattr(cache, "CONFIG_PATH", tmp_path / "absent.yaml")
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", tmp_path / "default")
    assert cache.cache_dir() == tmp_path / "default"


@pytest.fixture
def configured(tmp_path, monkeypatch):
    """Make this the configuration every module reads."""
    from plexdo import cache, config

    def use(body):
        path = write_config(tmp_path, body)
        monkeypatch.setattr(cache, "CONFIG_PATH", path)
        monkeypatch.setattr(config, "CONFIG_PATH", path)
        config.cached_config.cache_clear()

    yield use
    config.cached_config.cache_clear()


def test_cache_dir_is_overridden_by_the_config(tmp_path, configured):
    from plexdo import cache

    configured(f"plex:\n  url: x\n  cache_dir: {tmp_path}/mine\n")
    assert cache.cache_dir() == tmp_path / "mine"


def test_cache_dir_expands_environment_variables(
    tmp_path, monkeypatch, configured
):
    from plexdo import cache

    monkeypatch.setenv("MYCACHE", str(tmp_path / "envbased"))
    configured("plex:\n  url: x\n  cache_dir: $MYCACHE/sub\n")
    assert cache.cache_dir() == tmp_path / "envbased" / "sub"


def test_write_cache_creates_the_configured_directory(tmp_path, configured):
    from plexdo import cache

    configured(f"plex:\n  url: x\n  cache_dir: {tmp_path}/made\n")
    cache.write_cache("users", [{"id": 1}])
    assert (tmp_path / "made" / "users.json").exists()


# --- command alias -------------------------------------------------------


def test_list_library_is_an_alias_for_list_titles(parser):
    assert parser.parse_args(["list-library", "3"]).library_id == "3"
    assert parser.parse_args(["list-library", "3"]).command == "list-library"


def test_both_spellings_dispatch_to_the_same_handler():
    """The argparse error names the spelling typed: aliases need an entry."""
    handlers, needs_plex = build_registry()
    assert handlers["list-library"] is handlers["list-titles"]
    assert {"list-titles", "list-library"} <= needs_plex


def test_the_alias_accepts_the_same_options(parser):
    args = parser.parse_args(["list-library", "My Photos", "--album", "Trip"])
    assert (args.library_id, args.album) == ("My Photos", "Trip")
