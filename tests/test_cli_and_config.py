# SPDX-License-Identifier: GPL-3.0-or-later

"""Argument parsing, config handling, and the command registry."""

import pytest

from plexdo import __version__
from plexdo.cli import build_parser
from plexdo.commands import MODULES, build_registry


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


def test_only_login_and_config_bootstrap_run_without_a_server():
    handlers, needs_plex = build_registry()
    assert set(handlers) - needs_plex == {"login", "write-config-example"}


@pytest.mark.parametrize("flag,attr,value", [
    ("--json", "format", "json"),
    ("-f", "format", "yaml"),
    ("-v", "verbose", True),
    ("--dry-run", "dry_run", True),
])
def test_global_flags_work_before_the_command(parser, flag, attr, value):
    argv = [flag, "yaml", "list-users"] if flag == "-f" else [flag, "list-users"]
    assert getattr(parser.parse_args(argv), attr) == value


@pytest.mark.parametrize("flag,attr,value", [
    ("--json", "format", "json"),
    ("-f", "format", "yaml"),
    ("-v", "verbose", True),
    ("--dry-run", "dry_run", True),
])
def test_global_flags_work_after_the_command(parser, flag, attr, value):
    argv = ["list-users", flag, "yaml"] if flag == "-f" else ["list-users", flag]
    assert getattr(parser.parse_args(argv), attr) == value


def test_a_flag_given_before_the_command_is_not_clobbered_by_the_subparser(parser):
    """The subparser copies its whole namespace over; SUPPRESS prevents that."""
    assert parser.parse_args(["--json", "copy-watched", "7", "9"]).format == "json"


def test_users_and_libraries_accept_titles_not_just_numbers(parser):
    assert parser.parse_args(["list-playlists", "Alice"]).user_id == "Alice"
    assert parser.parse_args(["list-titles", "TV Shows"]).library_id == "TV Shows"


def test_minus_one_parses_as_the_one_way_flag_not_a_negative_number(parser):
    assert parser.parse_args(["copy-watched", "7", "9", "-1"]).one_way is True


@pytest.mark.parametrize("command", [
    "build-interleaved", "build-chronological", "build-randomize",
    "copy-playlist-all-users", "copy-playlist-to-user",
])
def test_every_creating_command_offers_overwrite(parser, command):
    action = {a.dest for p in [parser._subparsers._group_actions[0].choices[command]]
              for a in p._actions}
    assert "overwrite" in action


@pytest.mark.parametrize("command", [
    "list-playlist", "list-show", "export-playlist", "export-titles",
    "build-interleaved", "build-chronological", "build-randomize",
])
def test_every_export_command_offers_a_path_prefix(parser, command):
    dests = {a.dest for a in
             parser._subparsers._group_actions[0].choices[command]._actions}
    assert "prefix" in dests


def test_version_flag_reports_the_package_version(parser, capsys):
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])
    assert __version__ in capsys.readouterr().out


# --- configuration -------------------------------------------------------

def write_config(tmp_path, body):
    path = tmp_path / "plexdo.ini"
    path.write_text(body)
    path.chmod(0o600)
    return path


def test_environment_variables_are_expanded(tmp_path, monkeypatch):
    from plexdo import config
    cfg_path = write_config(tmp_path, "[plex]\nurl = http://$HOST:32400\n")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_path)
    monkeypatch.setenv("HOST", "media.lan")
    assert config.load_config().get("plex", "url") == "http://media.lan:32400"


def test_an_unset_variable_is_left_literal_and_warned_about(
    tmp_path, monkeypatch, caplog
):
    from plexdo import config
    cfg_path = write_config(tmp_path, "[plex]\ntoken_path = $NOPE_UNSET/t\n")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_path)
    monkeypatch.delenv("NOPE_UNSET", raising=False)
    assert "$NOPE_UNSET" in config.load_config().get("plex", "token_path")
    assert "NOPE_UNSET" in caplog.text


def test_a_password_may_contain_a_percent_sign(tmp_path, monkeypatch):
    """Default interpolation would raise before the value could be used."""
    from plexdo import config
    cfg_path = write_config(tmp_path, "[plex]\npassword = p%ss w0rd\n")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_path)
    assert config.load_config().get("plex", "password") == "p%ss w0rd"


def test_a_group_readable_config_is_warned_about(tmp_path, monkeypatch, caplog):
    from plexdo import config
    cfg_path = write_config(tmp_path, "[plex]\nurl = x\n")
    cfg_path.chmod(0o644)
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_path)
    config.load_config()
    assert "SECURITY" in caplog.text


# --- platform defaults ---------------------------------------------------

from pathlib import Path

from plexdo.constants import default_paths, windows_app_dir

WIN_ENV = {"LOCALAPPDATA": r"C:\Users\me\AppData\Local", "TEMP": r"C:\Temp"}


def test_windows_config_lives_under_localappdata():
    config, _, _ = default_paths(True, WIN_ENV)
    assert config == Path(r"C:\Users\me\AppData\Local") / "PlexDo" / "plexdo.ini"


def test_windows_cache_lives_beside_the_config():
    _, cache, _ = default_paths(True, WIN_ENV)
    assert cache == Path(r"C:\Users\me\AppData\Local") / "PlexDo" / "Cache"


def test_windows_token_defaults_to_the_temp_directory():
    _, _, token = default_paths(True, WIN_ENV)
    assert token == r"%TEMP%\plexdo.token"


def test_windows_falls_back_to_appdata_when_localappdata_is_unset():
    assert windows_app_dir({"APPDATA": r"C:\Roaming"}) == Path(r"C:\Roaming") / "PlexDo"


def test_windows_survives_neither_variable_being_set():
    assert windows_app_dir({}).name == "PlexDo"


def test_posix_defaults_are_unchanged():
    config, cache, token = default_paths(False, {})
    assert config == Path("~/.local/etc/plexdo.ini").expanduser()
    assert cache == Path("~/.cache/plexdo").expanduser()
    assert token == "$XDG_RUNTIME_DIR/.plex.token"


def test_the_config_template_names_the_platforms_token_path():
    from plexdo.constants import CONFIG_EXAMPLE, DEFAULT_TOKEN_PATH
    assert f"token_path = {DEFAULT_TOKEN_PATH}" in CONFIG_EXAMPLE


# --- configurable cache directory ---------------------------------------

def test_cache_dir_defaults_to_the_platform_location(tmp_path, monkeypatch):
    from plexdo import cache
    monkeypatch.setattr(cache, "CONFIG_PATH", tmp_path / "absent.ini")
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", tmp_path / "default")
    assert cache.cache_dir() == tmp_path / "default"


def test_cache_dir_is_overridden_by_the_config(tmp_path, monkeypatch):
    from plexdo import cache, config
    cfg = write_config(tmp_path, f"[plex]\nurl = x\ncache_dir = {tmp_path}/mine\n")
    monkeypatch.setattr(cache, "CONFIG_PATH", cfg)
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    config.cached_config.cache_clear()
    assert cache.cache_dir() == tmp_path / "mine"
    config.cached_config.cache_clear()


def test_cache_dir_expands_environment_variables(tmp_path, monkeypatch):
    from plexdo import cache, config
    cfg = write_config(tmp_path, "[plex]\nurl = x\ncache_dir = $MYCACHE/sub\n")
    monkeypatch.setenv("MYCACHE", str(tmp_path / "envbased"))
    monkeypatch.setattr(cache, "CONFIG_PATH", cfg)
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    config.cached_config.cache_clear()
    assert cache.cache_dir() == tmp_path / "envbased" / "sub"
    config.cached_config.cache_clear()


def test_write_cache_creates_the_configured_directory(tmp_path, monkeypatch):
    from plexdo import cache, config
    cfg = write_config(tmp_path, f"[plex]\nurl = x\ncache_dir = {tmp_path}/made\n")
    monkeypatch.setattr(cache, "CONFIG_PATH", cfg)
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    config.cached_config.cache_clear()
    cache.write_cache("users", [{"id": 1}])
    assert (tmp_path / "made" / "users.json").exists()
    config.cached_config.cache_clear()


def test_the_template_documents_the_default_cache_dir():
    from plexdo.constants import CONFIG_EXAMPLE, DEFAULT_CACHE_DIR
    assert f"# cache_dir = {DEFAULT_CACHE_DIR}" in CONFIG_EXAMPLE


# --- command alias -------------------------------------------------------

def test_list_library_is_an_alias_for_list_titles(parser):
    assert parser.parse_args(["list-library", "3"]).library_id == "3"
    assert parser.parse_args(["list-library", "3"]).command == "list-library"


def test_both_spellings_dispatch_to_the_same_handler():
    """argparse reports the spelling typed, so the alias needs its own entry."""
    handlers, needs_plex = build_registry()
    assert handlers["list-library"] is handlers["list-titles"]
    assert {"list-titles", "list-library"} <= needs_plex


def test_the_alias_accepts_the_same_options(parser):
    args = parser.parse_args(["list-library", "My Photos", "--album", "Trip"])
    assert (args.library_id, args.album) == ("My Photos", "Trip")
