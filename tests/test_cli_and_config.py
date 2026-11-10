# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Argument parsing, config handling, and the command registry."""

from pathlib import Path

import pytest

from plexdo import __version__
from plexdo.cli import build_parser, parse_arguments
from plexdo.commands import GROUPS, MODULES, build_registry
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
        "write-secrets-example",
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
        [flag, "yaml", "users-list"] if flag == "-f" else [flag, "users-list"]
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
        ["users-list", flag, "yaml"] if flag == "-f" else ["users-list", flag]
    )
    assert getattr(parser.parse_args(argv), attr) == value


@pytest.mark.parametrize(
    "argv",
    [
        ["--debug-log", "run.log", "users-list"],
        ["users-list", "--debug-log", "run.log"],
    ],
)
def test_debug_log_works_before_or_after_the_command(parser, argv):
    assert parser.parse_args(argv).debug_log == "run.log"
    assert parser.parse_args(["users-list"]).debug_log is None


def test_a_flag_given_before_the_command_is_not_clobbered_by_the_subparser(
    parser,
):
    """The subparser copies its whole namespace over; SUPPRESS prevents that."""
    assert (
        parser.parse_args(["--json", "show-watched-cp", "7", "9"]).format
        == "json"
    )


def test_users_and_libraries_accept_titles_not_just_numbers(parser):
    assert parser.parse_args(["playlists-list", "Alice"]).user_id == "Alice"
    assert (
        parser.parse_args(["library-list", "TV Shows"]).library_id == "TV Shows"
    )


def test_minus_one_parses_as_the_one_way_flag_not_a_negative_number(parser):
    assert (
        parser.parse_args(["show-watched-cp", "7", "9", "-1"]).one_way is True
    )


def test_build_merge_keeps_minus_u_for_the_target_user(parser):
    """-U is --unique; -u stays --user, as on every build command."""
    args = parser.parse_args(
        ["merge-build", "0", "Mix", "a", "b", "-s", "-U", "-u", "7"]
    )
    assert args.stop_short and args.unique
    assert args.dest_user_id == "7"
    default = parser.parse_args(["merge-build", "0", "Mix", "a", "b"])
    assert default.ratio == (1, 1)


@pytest.mark.parametrize(
    "command", ["playlist-build", "merge-build", "playlist-copy"]
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
        "playlist-list",
        "show-list",
        "playlist-export",
        "titles-export",
        "playlist-build",
        "merge-build",
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
    assert paths.secrets_file == WIN_APP / "secrets.json"
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
        paths.secrets_file
        == Path("~/.local/state/plexdo/secrets.json").expanduser()
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
    assert paths.secrets_file == Path("/s/plexdo/secrets.json")


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


# --- the completion cache, by ID and by word ---------------------------------


def test_a_cache_key_is_the_word_with_what_a_file_name_cannot_hold_replaced():
    from plexdo.cache import cache_key

    assert cache_key(7) == "7"
    assert cache_key("TV Shows") == "TV Shows"
    assert cache_key('a/b\\c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


_COMPLETIONS = Path(__file__).resolve().parents[1] / "completions"

# How each shell is asked for the cache name of the word in its last argument.
_SHELL_KEY = {
    "bash": [
        "bash",
        "-c",
        'source "$1"; _plexdo_word_key "$2"',
        "x",
        str(_COMPLETIONS / "plexdo.bash"),
    ],
    "zsh": [
        "zsh",
        "-fc",
        # All but the last line, which runs the completion itself.
        'eval "$(sed \'$d\' "$1")" 2>/dev/null; _plexdo_word_key "$2"',
        "x",
        str(_COMPLETIONS / "_plexdo"),
    ],
    "fish": [
        "fish",
        "--no-config",
        "-c",
        "source $argv[1]; __plexdo_word_key $argv[2]",
        str(_COMPLETIONS / "plexdo.fish"),
    ],
}


@pytest.mark.parametrize("shell", sorted(_SHELL_KEY))
@pytest.mark.parametrize(
    "word", ["7", "TV Shows", 'a/b\\c:d*e?f"g<h>i|j', "Kids' Films"]
)
def test_each_completion_names_the_word_cache_as_plexdo_does(shell, word):
    """A script that names the file differently never finds it."""
    import shutil
    import subprocess

    from plexdo.cache import cache_key

    if shutil.which(shell) is None:
        pytest.skip(f"{shell} is not installed")
    done = subprocess.run(
        [*_SHELL_KEY[shell], word],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={"HOME": "/nonexistent", "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )
    assert done.stdout.rstrip("\n") == cache_key(word)


def test_word_caches_are_written_once_per_spelling(tmp_path, configured):
    from plexdo import cache

    configured(f"plex:\n  url: x\n  cache_dir: {tmp_path}/c\n")
    rows = [{"ratingKey": 1, "title": "Mix"}]
    cache.write_word_caches(
        "playlists", ["7", "alice", "Alice", None, ""], rows
    )
    written = sorted(p.name for p in (tmp_path / "c").iterdir())
    assert written == [
        "playlists-by-word.7.json",
        "playlists-by-word.Alice.json",
        "playlists-by-word.alice.json",
    ]


def test_resolving_an_argument_remembers_every_spelling():
    import argparse

    from plexdo.identify import argument_words, remember_words

    args = argparse.Namespace(user_id=7)
    assert argument_words(args, "user_id") == ["7"]
    remember_words(args, "user_id", " alice ", [(0, "admin"), (7, "Alice")], 7)
    assert argument_words(args, "user_id") == ["7", "alice", "Alice"]
    assert argument_words(args, "library_id") == []


def test_listing_playlists_files_them_by_id_and_by_word(
    tmp_path, configured, monkeypatch
):
    """Completion holding "Alice" found nothing in a cache named for 7."""
    import argparse

    from plexdo.commands import playlists

    configured(f"plex:\n  url: x\n  cache_dir: {tmp_path}/c\n")

    class Playlist:
        ratingKey, title, leafCount = 900, "Mix", 3

    class Server:
        def playlists(self):
            return [Playlist()]

    monkeypatch.setattr(playlists, "server_for_user", lambda p, uid: Server())
    args = argparse.Namespace(
        format="json",
        user_id=7,
        argument_words={"user_id": ["7", "alice", "Alice"]},
    )
    playlists.cmd_list_playlists(None, args)
    written = sorted(p.name for p in (tmp_path / "c").iterdir())
    assert written == [
        "playlists-by-word.7.json",
        "playlists-by-word.Alice.json",
        "playlists-by-word.alice.json",
        "playlists.7.json",
    ]


# --- the renamed and merged commands ---------------------------------------


def test_library_list_takes_a_library_and_an_album(parser):
    args = parser.parse_args(["library-list", "My Photos", "--album", "Trip"])
    assert (args.command, args.library_id, args.album) == (
        "library-list",
        "My Photos",
        "Trip",
    )


@pytest.mark.parametrize(
    "gone",
    [
        "list-titles",
        "list-library",
        "list-users",
        "build-concatenated",
        "build-interleaved",
        "append-playlist",
        "copy-playlist-to-user",
        "copy-watched",
    ],
)
def test_the_old_command_names_are_gone(parser, gone):
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([gone])
    assert exc.value.code == 2


def test_every_command_is_listed_in_exactly_one_help_group():
    grouped = [name for _, names in GROUPS for name in names]
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == set(build_registry()[0])


def test_help_lists_the_commands_grouped_and_sorted(parser):
    text = parser.format_help()
    listed = [
        line.split()[0]
        for line in text.splitlines()
        if line.startswith("  ") and line[2:3].isalpha()
    ]
    expected = [name for _, names in GROUPS for name in sorted(names)]
    assert listed == expected
    for title, _ in GROUPS:
        assert f"\n{title}:\n" in text


def test_a_command_lists_the_global_options_last_and_apart(parser):
    command = parser._subparsers._group_actions[0].choices["library-list"]
    text = command.format_help()
    assert text.index("\noptions:") < text.index("\nglobal options:")
    assert "[global options]" in command.format_usage()
    assert "--debug-log" not in command.format_usage()


def test_the_global_options_are_sorted_by_name(parser):
    group = next(
        g for g in parser._action_groups if g.title == "global options"
    )
    names = [a.option_strings[-1].lstrip("-") for a in group._group_actions]
    assert names == sorted(names)


# --- playlist-build: one command, four modes -------------------------------


@pytest.mark.parametrize(
    "flag,mode",
    [
        ("-I", "interleaved"),
        ("--interleaved", "interleaved"),
        ("-C", "chronological"),
        ("--chronological", "chronological"),
    ],
)
def test_playlist_build_from_rating_keys(parser, flag, mode):
    args = parse_arguments(parser, ["playlist-build", flag, "Mix", "12", "34"])
    assert (args.mode, args.name, args.rating_keys) == (mode, "Mix", [12, 34])


@pytest.mark.parametrize("flag", ["-R", "--randomize"])
def test_playlist_build_randomize_takes_user_source_dest(parser, flag):
    args = parse_arguments(
        parser, ["playlist-build", flag, "Alice", "Queue", "Shuffled", "-o"]
    )
    assert (args.mode, args.user_id, args.source, args.dest) == (
        "randomize",
        "Alice",
        "Queue",
        "Shuffled",
    )
    assert args.overwrite


@pytest.mark.parametrize("flag", ["-A", "--append"])
def test_playlist_build_append_takes_user_playlist_keys(parser, flag):
    args = parse_arguments(parser, ["playlist-build", flag, "0", "Queue", "7"])
    assert (args.mode, args.user_id, args.playlist, args.rating_keys) == (
        "append",
        "0",
        "Queue",
        [7],
    )


def test_minus_a_is_all_users_and_minus_capital_a_is_append(parser):
    args = parse_arguments(parser, ["playlist-build", "-I", "Mix", "1", "-a"])
    assert (args.mode, args.all_users) == ("interleaved", True)


@pytest.mark.parametrize(
    "argv",
    [
        ["Mix", "12"],  # no mode
        ["-I", "-C", "Mix", "12"],  # two modes
        ["-I", "Mix"],  # no ratingKey
        ["-I", "Mix", "twelve"],  # not a ratingKey
        ["-R", "0", "Queue"],  # no DEST
        ["-R", "0", "Queue", "Shuffled", "extra"],
        ["-A", "0", "Queue"],  # nothing to append
        ["-A", "0", "Queue", "7", "-o"],  # nothing to overwrite
        ["-A", "0", "Queue", "7", "-a"],
        ["-A", "0", "Queue", "7", "-u", "3"],
        ["-A", "0", "Queue", "7", "--m3u", "out.m3u"],
    ],
)
def test_playlist_build_usage_errors_exit_2(parser, argv, capsys):
    with pytest.raises(SystemExit) as exc:
        parse_arguments(parser, ["playlist-build", *argv])
    assert exc.value.code == 2
    assert "usage: plexdo playlist-build" in capsys.readouterr().err


# --- playlist-copy: to all, or to one --------------------------------------


@pytest.mark.parametrize("flag", ["-A", "--all"])
def test_playlist_copy_to_all(parser, flag):
    args = parse_arguments(parser, ["playlist-copy", flag, "0", "Queue", "-o"])
    assert (args.copy_to, args.source_user_id, args.source_playlist) == (
        "all",
        "0",
        "Queue",
    )
    assert args.overwrite


@pytest.mark.parametrize("flag", ["-T", "--to"])
def test_playlist_copy_to_one(parser, flag):
    args = parse_arguments(
        parser, ["playlist-copy", flag, "0", "Queue", "Alice", "Hers"]
    )
    assert (args.copy_to, args.user_id, args.dest) == ("one", "Alice", "Hers")
    assert (args.source_user_id, args.source_playlist) == ("0", "Queue")


@pytest.mark.parametrize(
    "argv",
    [
        ["0", "Queue"],  # neither -A nor -T
        ["-A", "-T", "0", "Queue"],
        ["-A", "0", "Queue", "Alice"],  # --all names no target
        ["-T", "0", "Queue"],  # --to needs both
        ["-T", "0", "Queue", "Alice"],
        ["-T", "0", "Queue", "Alice", "Hers", "extra"],
    ],
)
def test_playlist_copy_usage_errors_exit_2(parser, argv, capsys):
    with pytest.raises(SystemExit) as exc:
        parse_arguments(parser, ["playlist-copy", *argv])
    assert exc.value.code == 2
    assert "usage: plexdo playlist-copy" in capsys.readouterr().err
