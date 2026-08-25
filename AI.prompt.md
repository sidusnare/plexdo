# AI.prompt.md

This file contains the complete prompt that regenerates this project from
scratch. It is the authoritative specification: when behaviour changes, update
this file in the same commit.

---

Build `plexdo`, an installable Python package providing a command-line
interface to Plex Media Server via the `plexapi` library, ready to publish to
PyPI. The console script is named `plexdo` (with `plexdo` as an alias).

## PROJECT LAYOUT

Use a src layout with setuptools and a PEP 621 `pyproject.toml`:

```
pyproject.toml          setuptools backend, PEP 621 metadata, pylint config
README.md  LICENSE  MANIFEST.in  requirements.txt  .gitignore  AI.prompt.md
completions/plexdo.bash
src/plexdo/
├── __init__.py         __version__
├── __main__.py         python -m plexdo
├── cli.py              _add_global_flags, build_parser, main
├── constants.py        DateInput, MediaItem, CONFIG_PATH, CACHE_DIR, LOG,
│                       PERMISSIVE_MODE_MASK, CONFIG_EXAMPLE
├── logs.py             configure_logging
├── config.py           check_file_permissions, config_optional, load_config,
│                       read_token, connect_plex
├── cache.py            write_cache
├── convert.py          parse_date, format_duration
├── console.py          output, clean_text, display_width, pad, rule,
│                       print_table, print_metadata
├── titles.py           display_title, fetch_show, non_special_episodes,
│                       shuffle_list, fetch_item
├── identify.py         resolve_identifier (shared by users and libraries)
├── sections.py         resolve_section, resolve_sections, library resolution
├── accounts.py         server_for_user, _find_user_by_id, _is_restricted,
│                       account_type
├── playlists.py        resolve_playlist, finalize_playlist,
│                       _resolve_dest_name, copy_playlist_to
├── m3u.py              write_m3u
├── photos.py           collect_photos, collect_library_items, photo_file_path
├── sorting.py          _alpha_sort_key, _date_sort_key, apply_sort
├── gallery.py          Spotlight.js HTML gallery
├── airdates.py         missing air-date estimation
├── security.py         argv scrubbing for --password
├── data/plexdo.bash   completion script shipped as package data
└── commands/
    ├── __init__.py     MODULES, register_all, build_registry
    ├── libraries.py    list-libraries, list-titles, list-show, export-titles
    ├── search.py       search
    ├── users.py        list-users
    ├── playlists.py    list-playlists, list-playlist, export-playlist,
    │                   remove-playlist, append-playlist
    ├── metadata.py     show-metadata
    ├── stream.py       read
    ├── rescan.py       rescan
    ├── build.py        build-interleaved, build-chronological, build-randomize
    ├── copy.py         copy-playlist-all-users, copy-playlist-to-user
    ├── watched.py      copy-watched
    └── auth.py         login, write-config-example
```

### Command module contract

Every module in `commands/` exposes exactly three names:

- `register(sub, parents)` - adds its subparsers to the top-level
  `add_subparsers` action, passing `parents=parents` on every `add_parser`
  call so each subcommand inherits the global flags
- `COMMANDS` - maps command name to handler
- `REQUIRES_PLEX` - the subset needing a connected server; `auth` has an empty
  frozenset because `login` and `write-config-example` run before a token exists

`commands/__init__.py` holds a `MODULES` tuple (whose order sets the order of
subcommands in `--help`), plus `register_all(sub)` and `build_registry()`
which merge the per-module tables. Adding a command means adding a module and
listing it in `MODULES`; `cli.py` never changes.

Shared logic must live in the core modules, not be duplicated across command
modules - pylint's `duplicate-code` check will catch it. In particular
`resolve_section` / `resolve_sections` and `fetch_item` exist because the
library-lookup and ratingKey-lookup blocks would otherwise be repeated across
four command modules.

### Packaging

`[project.scripts]` has the single entry `plexdo = "plexdo.cli:main"`. Dependencies are `PlexAPI>=4.15.10`
and `requests>=2.31`; `requires-python = ">=3.11"`. Ship the completion script
as package data via `[tool.setuptools.package-data]` so it can be located at
runtime through `plexdo.__file__`. `python -m build` must produce an sdist and
wheel that both pass `twine check`.

## CHARACTER SET

Source, completions, the man page, and the build files are **plain ASCII**.
Write `-` not an em or en dash, `->` not an arrow, `>=` not the inequality
sign, `...` not an ellipsis, and a straight `'` not a curly quote. This
applies to comments, docstrings, and user-facing message strings alike; a
warning printed to a terminal has no business containing an em dash.

Two deliberate exceptions, both about output rather than prose: `console.py`
holds the box-drawing glyphs as `\uXXXX` escapes, so the file itself stays
ASCII while the tables still draw; and the markdown docs keep literal box
characters where they reproduce what the program prints or draw a `tree`-style
directory listing.

## NAMING

A leading underscore means **module-private**. A helper another module imports
is package API and must not carry one - otherwise the convention says nothing
and every reader has to check. `clean_text`, `display_title`,
`server_for_user`, `write_m3u` and the rest are public for that reason; the
84 helpers that genuinely stay inside one module keep their underscore.

Names should say what they do: the text-cleaning helper is `clean_text`, not
`_cell`, because its job is stripping the stray carriage returns in Plex
metadata, not "being a cell".

Two functions where one will do is a smell worth removing - `mapper_for` and
`make_path_mapper` were merged, and a one-line alias for
`parse_date(ep.originallyAvailableAt)` was inlined.

## GENERAL REQUIREMENTS

- Python 3.11 through 3.14
- Fully type-annotate every function, parameter, and return type
- Must pass pylint >= 9.5 (target 10.0) across the whole package
- Follow the Google Python style guide; small, single-purpose functions
- No dead code, no duplicate logic, no unused variables, no global mutable state
- No bare `except`; broad excepts only where explicitly noted, each with `# pylint: disable=broad-except`

Two pylint traps to design around from the start:

- Splitting `register()` per command module keeps every parser builder well
  under the statement limit; do not centralise argparse in `cli.py`.
- `bar` is on pylint's disallowed-name blacklist. Name the vertical
  box-drawing character `vline`.

## IMPORTS

Each module imports only what it uses, ordered standard library, then
third-party (`requests`, `plexapi`), then first-party (`plexdo.*`) - pylint
enforces this grouping. The full set used across the package:

```python
import argparse, configparser, ctypes, datetime, getpass
import html as html_lib
import json, logging, secrets, statistics, sys, textwrap, unicodedata
from pathlib import Path
from typing import (Any, Dict, Iterator, List, NamedTuple, Optional,
                    Sequence, Tuple, Union)

import requests

from plexapi.audio import Track
from plexapi.photo import Photo
from plexapi.exceptions import BadRequest, NotFound, Unauthorized
from plexapi.myplex import MyPlexAccount, MyPlexUser
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show
```

## TYPE ALIASES AND CONSTANTS

```python
DateInput = Union[str, datetime.date, datetime.datetime, None]
MediaItem = Union[Episode, Movie, Track, Photo]

CONFIG_PATH          = Path("~/.local/etc/plexdo.ini").expanduser()
CACHE_DIR            = Path("~/.cache/plexdo").expanduser()
LOG                  = logging.getLogger("plexdo")
PERMISSIVE_MODE_MASK = 0o077
CONFIG_EXAMPLE       = "...the INI template, see below..."
```

## CONFIGURATION

`~/.local/etc/plexdo.ini`:

```ini
[plex]
url = http://localhost:32400
token_path = ~/usr/tmp/.fsec/plex_token

# Optional credentials used by `plexdo login`.
# The password is stored in plaintext, so keep this file mode 0600.
# Supplying --username on the command line ignores the password below.
# username = you@example.com
# password = your-plex-password
```

Expand `~` in all paths; read the token as UTF-8 and strip it; fail fast with a
clear `sys.exit` if either the config or the token file is missing, pointing at
`write-config-example`.

`CONFIG_EXAMPLE` must be a module-level constant, not a string inside the
writer function, because the `write-config-example` help output echoes it and
the two must never drift apart.

## SECURITY

### `check_file_permissions(path, label)`

Called at startup from `load_config()` (config file) and `read_token()` (token
file). Warns via `LOG.warning` if `st_mode & PERMISSIVE_MODE_MASK` is non-zero,
distinguishing "readable by group" from "readable by group and others", and
printing the literal `chmod 600 <path>` remedy. WARNING level so it shows
without `--verbose`; stderr so it never contaminates `--json`.

### `config_optional(cfg, key)`

Return a stripped optional `[plex]` value, or `None` when absent or empty.

## VERSIONING

The version is `major.minor.revision`. `__version__` in
`src/plexdo/__init__.py` and `version` in `pyproject.toml` must always agree.

**Increment the revision - the third field - every time a release archive is
produced.** Major and minor move only on explicit instruction, never
automatically because a change felt significant.

Note that the `Version="1.1.0.1"` attribute in the CLIXML output is a fixed
PowerShell schema constant and has nothing to do with this project's version;
it must never be bumped alongside it.

## GLOBAL FLAGS

Every command accepts `-f/--format`, `--json`, `-v/--verbose`, `--debug`,
`--dry-run`, and `-V/--version`, and they must work **either before or after
the command name**.

`--format` takes `table json yaml csv clixml` and writes to `dest="format"`.
`--json` is a `store_const` alias writing to that *same* destination, so there
is exactly one attribute for commands to consult and no possibility of the two
disagreeing; give it `default=argparse.SUPPRESS` so it never clobbers an
explicit `--format`. `-V/--version` uses `action="version"`, and the version
also appears in the parser description. All logging goes to
stderr only, so `--json` output on stdout is always clean.

Implement this with `_add_global_flags(parser, suppress=False)` called twice:
once on the top-level parser with ordinary `False` defaults, and once on an
`add_help=False` parent parser with `default=argparse.SUPPRESS`, which
`build_parser` passes to `register_all` and every subparser inherits via
`parents=`.

The SUPPRESS default is essential, not cosmetic. A subparser parses into its
own namespace and then copies **every** attribute onto the main namespace, so
ordinary `False` defaults on the inherited copies would silently clobber a flag
given before the subcommand - `plexdo --json list-users` would emit a table.
With SUPPRESS the attribute only exists when the flag was actually passed, so
whichever position it appears in wins and the other is left untouched.

## THROTTLING

`throttle.paced(items, args, what)` yields items, sleeping `--throttle`
seconds between them once the count passes `THROTTLE_THRESHOLD` (50). The
default is 0.25s; 0 disables it. The pause goes *between* elements, so n
items wait n-1 times, and a short run is never paced because the delay would
be latency for no benefit. Announce it once at info level with the expected
duration and how to turn it off.

Apply it wherever a loop makes one request per element and the count can
realistically exceed 50: the seasons walk in `list-titles`, `find-missing`,
applying watched state in `copy-watched`, `collect_photos` (one call per
album), and the per-user loop in `copy-playlist-all-users`. Functions that
need it take an optional `args`, since there is no global state to read it
from.

## OUTPUT

### `output(data, args)`
`--json` -> `json.dumps(data, default=str)`. Otherwise `print_table` for a
list-of-dicts, else plain `print`.

### `clean_text(value)`
`str(value).strip()`. Plex metadata contains stray `\r`, which makes a printed
row's trailing pad overwrite the start of the line and appear as a blank line
after every row. Every value that is measured or printed must pass through this.

### `display_width(text)`
Terminal display width, **not** `len()`. CJK glyphs (`east_asian_width` in
`W`/`F`) occupy two columns and combining marks occupy none, so a `len()`-padded
table drifts out of alignment on any library holding non-Latin titles. Pair it
with `_pad(text, width)` which replaces `ljust` everywhere.

Tables are fitted to the terminal. `table_limit(args)` returns the column
budget: `None` when `-W/--wide` is given **or when stdout is not a tty**,
since redirected output has no width to respect and truncating it would
corrupt a pipeline. `_fit_widths` shrinks the widest column repeatedly,
stopping at `MIN_COLUMN_WIDTH` and only then at the ellipsis itself, so a very
narrow terminal degrades instead of overflowing. Truncation is display-width
aware, and the columns narrowed are reported once at info level naming
`--wide`.

### `print_table(rows, limit=None)` / `print_metadata(record, limit=None)`
UTF-8 box-drawn tables using `┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ ─ │`, with a `_rule(widths, l, m, r)`
helper, column widths computed from `display_width`, and one space of padding
each side of every cell:

```
┌─────┬─────────┬─────────────────┐
│ id  │ type    │ title           │
├─────┼─────────┼─────────────────┤
│ 1   │ managed │ Kids Profile    │
└─────┴─────────┴─────────────────┘
```

## SHARED HELPERS

- `parse_date(value: DateInput) -> Optional[datetime]` - accepts `datetime`, `date`, `"%Y-%m-%d %H:%M:%S"`, `"%Y-%m-%d"`
- `display_title(item) -> str` - `Episode` -> `"grandparentTitle - title"`, everything else -> `item.title`. Use in every table, preview, M3U `#EXTINF`, and HTML alt/title
- `non_special_episodes(show)` - episodes with `seasonNumber > 0`
- `shuffle_list(lst)` - Fisher-Yates via `secrets.randbelow`
- `resolve_playlist(user_plex, identifier)` - try `int()` -> `fetchItem` (assert `isinstance(..., Playlist)`); else look up by title; `sys.exit` if absent

### Identifier resolution (users and libraries)

`identify.resolve_identifier(roster, value, kind, list_command)` implements the
rules once for both users and libraries; do not write the algorithm twice, or
pylint's `duplicate-code` check will flag it. The roster is a list of
`(numeric_id, title)` pairs, and `kind` / `list_command` only shape the
warnings and errors, so a library miss says "Library not found ... run
`plexdo list-libraries`" while a user miss names `list-users`.

Rules, in order:

- Titles match exactly first, then case-insensitively.
- More than one title match -> `sys.exit`, listing the colliding IDs.
- Numeric value that is a real ID -> use it; if it is *also* some other entry's
  title, warn naming the entry that was not selected.
- Numeric value that is not a real ID but *is* a title -> resolve by title.
- Numeric value matching nothing -> return unchanged so the downstream lookup
  produces the precise error.
- Non-numeric matching nothing -> `sys.exit` pointing at the list command.

The duplicate-title abort applies only when resolving *by title*; a numeric ID
is unambiguous and must still work on a server with two identically titled
entries.

### Library identifier resolution

Every argument naming a library accepts an ID or a title, so all six are plain
strings with `metavar="LIBRARY"` - never `type=int`. They are the positionals
of `list-titles`, `export-titles`, and `read`, the optional positional of
`rescan`, `--library-id` on `search`, and `-l/--library` on `copy-watched`.
All use the attribute name `library_id`.

`sections.resolve_library_arguments(plex, args)` runs from `cli.main` next to
the user resolver, rewriting `library_id` in place so handlers always receive
an int. It must return early when the attribute is absent *or None* - `rescan
--status` legitimately has no library - so those commands cost no extra API
call.

### User identifier resolution

Every argument naming a user accepts **either** a numeric user ID **or** the
user's title, so all such argparse arguments are plain strings with
`metavar="USER"` - never `type=int`.

`accounts.resolve_user_arguments(plex, args)` is called once from `cli.main`
after connecting and before dispatch, rewriting every attribute in
`USER_ID_ARGUMENTS = ("user_id", "user_a", "user_b", "source_user_id")` in
place. Handlers therefore always receive a plain int and need no changes.
Build the roster once per invocation so a two-user command costs one extra API
call, and skip the fetch entirely when no user argument is present.

`resolve_user_identifier(roster, value)` rules, where the roster is
`[(0, admin_title)] + [(id, title) for each shared user]`:

- Titles match exactly first, then case-insensitively.
- More than one title match -> `sys.exit`, listing the colliding IDs and asking
  for the numeric ID.
- Numeric value that is a real user ID -> use it. If it is *also* some other
  user's title, warn naming the user that was not selected.
- Numeric value that is not a real ID but *is* a title -> resolve by title.
- Numeric value matching nothing -> return it unchanged so the downstream
  lookup produces the precise error.
- Non-numeric value matching nothing -> `sys.exit` pointing at `list-users`.

Note the duplicate-title abort applies only when resolving *by title*; passing
a numeric ID is unambiguous and must still work on a server that happens to
have two identically titled users.

### `server_for_user(plex, user_id) -> PlexServer`

`user_id == 0` returns the admin `plex` object directly with no API call.
Otherwise call `user.get_token(plex.machineIdentifier)` and build a new
`PlexServer`. **Do not use `switchHomeUser()`** - it only works for Plex Home
and raises 401 for ordinary shared users. Every `user_id` help string must
document `0 = admin`.

## COMPLETION CACHE

The directory comes from `cache.cache_dir()`: `[plex] cache_dir` when set,
otherwise the platform default. The config is only consulted when the file
exists, so this works before `plexdo login` has ever run. The generated
template carries the platform default as a commented `cache_dir` line, and all
three completions resolve the same setting -- memoised on first use, since
reading the config through python at shell-startup time would be a noticeable
cost. Leaving the completions on a hardcoded path would let a custom
`cache_dir` silently disable tab completion.

`write_cache(name, data)` writes JSON atomically (`.tmp` then `Path.replace`)
into `CACHE_DIR`, silently swallowing `OSError`. Called as a side effect, before
`output()`, by: `list-libraries` -> `libraries.json`; `list-titles <id>` ->
`titles.<id>.json`; `list-users` -> `users.json`; `list-playlists <uid>` ->
`playlists.<uid>.json`.

## PLAYLISTS: LOOKUP AND CREATION

Every argument naming an **existing** playlist accepts a title or a ratingKey,
resolved through `resolve_playlist`; no command may call
`plex.playlist(name)` directly. That covers `list-playlist`,
`export-playlist`, `remove-playlist`, `append-playlist`, the source of
`build-randomize`, and the source of both copy commands.

Every command that **creates** a playlist takes `-o/--overwrite`:
`build-interleaved`, `build-chronological`, `build-randomize`, and the two
copy commands. `finalize_playlist` enforces it centrally - a name collision
without the flag exits reporting the existing ratingKey and making clear
nothing was created or removed, and the check happens **before** the preview
so a doomed run fails immediately rather than after a screen of output.

Because `finalize_playlist` performs the replacement, `copy_playlist_to` must
*not* delete as well: `_resolve_dest_name` only reports a replacement when
`--overwrite` was given, so both would be acting on the same condition.

## PLAYLIST BUILDING MODEL

Every build command must (1) fully construct the item list in memory,
(2) validate it is non-empty, (3) print a numbered preview via `display_title`,
(4) make exactly one `plex.createPlaylist(name, items=items)` call.
`finalize_playlist(plex, name, items, args)` enforces this and honours `--dry-run`.

## EXPORT PATH REWRITING

`paths.py` provides `mapper_for(plex, args)`, returning a
`Callable[[str], str]`. Without a prefix it returns `identity`, so the default
export keeps the server's paths and costs no extra API call; the library roots
are only fetched when a prefix is actually given.

The prefix replaces the **library root**, not an arbitrary leading substring,
so `library_roots()` collects `section.locations` from every section and sorts
them longest-first - otherwise a library nested inside another's tree matches
the wrong root. Rejoin using the prefix's own separator style, so a Windows
prefix yields backslashes throughout. A path under no known root is appended
whole and warned about exactly once, since spamming per file would drown the
export.

`write_m3u` and `write_gallery_html` take the mapper as an argument
defaulting to `identity`; they must not reach for `plex` themselves.

All seven export commands take `-p/--prefix`: `export-playlist`,
`export-titles`, and the five with `--m3u`. Register it through
`paths.add_prefix_argument(parser)` - repeating the help text inline in three
command modules trips pylint's `duplicate-code`.

## M3U EXPORT - `write_m3u(items, path)`

Plex **server filesystem paths only**, from `item.media[].parts[].file`. Skip
items with no path (no placeholder line); include every part of a multi-part
item. Duration is `item.duration` ms -> seconds, falling back to `-1`. The
`#EXTINF` title uses `display_title`.

```
#EXTM3U
#EXTINF:3600,Show Name - Episode Name
/server/path/to/file.mkv
```

## COMMANDS

### `list-libraries`
Columns `id`, `type`, `title`. Writes the libraries cache.

### `list-titles <library_id> [--album ALBUM]`
show/movie use `section.all()`; photo libraries use `collect_photos`. Columns
`ratingKey`, `title`. Writes `titles.<id>.json`. `--album` warns and is ignored
for non-photo libraries.

### `search <user_id> <query> [--media-type TYPE] [--library-id ID]`
Runs as the given user. Searches every library unless `--library-id` scopes it.
`--media-type` choices `movie show episode track photo album artist`, passed as
`libtype`. A per-library failure logs a warning and continues rather than
aborting. Columns `ratingKey`, `libraryId` (from `item.librarySectionID`),
`type`, `title`. Implement one `_search_in_section` helper and have
`_search_all_sections` call it - do not inline a second copy of the loop.

### `list-users`
Columns `id`, `type`, `title`; writes the users cache.

`account_type(user)` returns `managed` / `home` / `friend` / `shared`.
Note that plexapi exposes `restricted` as the **raw XML string**, not a bool, so
a plain truth test sees `"0"` as True and mislabels every account as managed.
`_is_restricted` must treat `""`, `"0"`, and `"false"` as false while still
accepting a real bool.

### `list-playlists <user_id>`
Columns `ratingKey`, `title`, `items`; writes the playlists cache.

### `list-playlist <user_id> <playlist|ratingKey> [--m3u PATH]`
Accepts either form via `resolve_playlist`. Columns `index`, `ratingKey`, `title`.

### `list-show <rating_key> [--m3u PATH]`
Fails fast if the item is not a `Show`. Columns `index`, `ratingKey`, `season`,
`episode`, `title`.

### `show-metadata <rating_key>`
Dispatch through a `_METADATA_BUILDERS` dict keyed on `item.type`, falling back
to the base builder. Base fields: `ratingKey, type, title, year, contentRating,
rating, duration` (ms -> `H:MM:SS` via `format_duration`), `addedAt, updatedAt,
summary`. Extra fields - `episode`: `show, season, episode, airDate, studio`;
`movie`: `studio, airDate, tagline, genres, directors`; `show`: `studio,
firstAired, seasons, episodes, genres, network`; `track`: `album, artist,
trackNumber`.

### `read <library_id> <rating_key>`
Streams a media file to stdout for redirection or piping:

```
plexdo read 3 12345 | mpv -
plexdo read 3 12345 > file.mkv
```

Validate that the item's `librarySectionID` matches `library_id`. Warn if the
item has multiple media/parts and stream only the first. Use
`requests.get(url, stream=True, timeout=30)` with 64 KB chunks written to
`sys.stdout.buffer`. Catch `BrokenPipeError` silently - that is the normal exit
when a player quits early - and `sys.exit` on `requests.HTTPError`. Warn to
stderr if stdout is a tty, then proceed. `--dry-run` prints title, server path,
and URL to stderr without streaming. Get the URL from
`plex.url(part.key, includeToken=True)`.

### `status [--section SECTION]`
Eight sections, in order: `server` (a single record: friendlyName, version,
machineIdentifier, platform, platformVersion, updatedAt, myPlexUsername,
myPlexSubscription), `sessions`, `users`, `accounts` (`plex.systemAccounts()`,
which is a different list from the shared users), `connections`, `scans`,
`activities`, `tasks` (`plex.butlerTasks()`).

`plex.activities` is a property, and it carries both library scanning and
other background work; split it on whether the `type` mentions scan/refresh/
library so "scans" and "background tasks" are separate sections.

Each section is collected in its own try/except so one failure costs a warning
rather than the report: `connections` needs a plex.tv round trip via
`account.resource(friendlyName).connections`, which a local-only or offline
server cannot do.

Table output prints every section with a heading, `(none)` when empty. JSON and
YAML emit one nested object. CSV and CLIXML are flat and cannot carry eight
differently shaped sections, so they require `--section` and exit with a clear
message naming the choices when it is missing.

### `rescan [library_id] [-s/--status] [-n/--now]`
`library_id` is `nargs="?"`; `sys.exit` if it is absent and `--status` was not given.

- `--status` / `-s`: read `plex.activities` - it is a **property, not a method**;
  calling it raises `TypeError: 'list' object is not callable`. Columns `type`,
  `title`, `subtitle`, `progress`, `uuid`; print "No active scan jobs." to stderr when empty.
- plain: `section.update()` (a file scan, not `refresh()` which only re-fetches metadata)
- `--now` / `-n`: first iterate every section calling `section.cancelUpdate()`,
  swallowing errors from already-idle sections, then `section.update()`. Both steps honour `--dry-run`.

### `build-interleaved <name> <ratingKey...> [--m3u PATH]`
Round-robin across shows using `non_special_episodes`.

### `build-chronological <name> <ratingKey...> [--m3u PATH]`
Shows and movies, season 0 skipped, globally sorted by resolved air date.

Missing-date resolution, implemented exactly:

1. Look only within the same season
2. Collect up to 6 previous and 6 next episodes that have dates, ordered by `episode.index`
3. Require >= 3 known dates (giving >= 2 intervals), else fall through to the prompt
4. Compute timedeltas between adjacent sorted dates
5. Require >= 2 intervals, else fall through
6. Take `statistics.median` of the interval seconds
7. Estimate from latest-previous (+median) and/or earliest-next (-median); average the timestamps when both exist
8. Otherwise prompt interactively for `YYYY-MM-DD`, offering the last resolved date as the example

### `build-randomize <user_id> <source> <dest> [--m3u PATH]`

`copy-playlist-all-users` prints the item list **once**, before the loop, and
passes `preview=False` to `copy_playlist_to` thereafter: the list is identical
for every user, so repeating it per user buries the report. Each user then
yields one line - `created`, `replaced`, `skipped`, `failed` - printed as it
completes so a long run shows progress, or one record per user in a
machine-readable format.

`finalize_playlist` returns `"created"` or `"replaced"` and `copy_playlist_to`
returns `(status, final_name, detail)` to make that possible. Because the
caller now surfaces the skip reason itself, the skip message inside
`copy_playlist_to` is `LOG.info`, not `LOG.warning` - leaving it as a warning
duplicates every skip on stderr.

### `copy-playlist-all-users <source_user_id> <source_playlist> [-o/--overwrite]`
Resolve the source through `server_for_user`, then copy to every user from
`account.users()`, **skipping the source user itself**. A failure for one user
logs a warning and the loop continues.

### `copy-playlist-to-user <source_user_id> <source_playlist> <user_id> <dest> [-o/--overwrite]`

Both copy commands share `_resolve_dest_name(user_plex, desired_name, force_overwrite)`,
returning `Optional[Tuple[str, bool]]` of `(final_name, delete_first)` or `None`
meaning skip:

| destination state | default | `-o` |
|---|---|---|
| nothing there | `Mix` | `Mix` |
| `Mix` exists | `Mix admin copy` | `Mix` (replaced) |
| `Mix` and `Mix admin copy` exist | **skip, warn, touch nothing** | `Mix` (replaced) |

`copy_playlist_to` takes a `target_label` argument so the skip warning names
the affected user - essential in the all-users loop, where the run continues.
The warning must name both conflicting titles and point at `--overwrite`.

### `copy-watched <user_a> <user_b> [-1/--one-way] [-l/--library ID] [-t/--title KEY] [--unwatch]`

Synchronises watched state and resume points between two users. Collects
`isPlayed`, `viewOffset`, and `lastViewedAt` for every item both users can see,
then writes the winning state onto the other user. Only the intersection of the
two users' visible ratingKeys is considered.

Scope: `--library` restricts to one section, `--title` to one ratingKey
(skipping the library scan entirely). Watch state lives on leaf items, so map
section type to leaf libtype - `movie`->`movie`, `show`->`episode`,
`artist`->`track` - and skip photo libraries, which have no watch state. Use
`section.all(libtype=...)`, **not** `section.search(...)`, which needs a
non-empty query and would silently return nothing.

Winner selection, `_select_winner(first, second, unwatch)` returning
`(winner, loser)` or `None`:

| situation | default | `--unwatch` |
|---|---|---|
| neither has data | skip | skip |
| states already match | skip | skip |
| exactly one has data | the one **with** data wins | the one **without** data wins |
| both have data | **latest** `lastViewedAt` wins | **earliest** `lastViewedAt` wins |

A `lastViewedAt` of `None` must never win: map it to `datetime.min` when the
latest wins and `datetime.max` when the earliest does. Because Plex rewrites
`viewOffset` continuously during playback, treat offsets within
`_OFFSET_TOLERANCE_MS` (10 s) as identical, or every run reports spurious changes.

`--one-way` drops any change whose target is the first user, so the first
user's state is never modified.

Actions are `markPlayed`, `setProgress`, or `markUnplayed`, computed before
applying so `--dry-run` can preview them. Print a preview table of
`ratingKey`, `title`, `action`, `target` and honour `--dry-run`. When nothing
needs changing, print "Watch state already in sync." to stderr (or `[]` for
`--json`). Note that plexapi renamed these methods (`markWatched` ->
`markPlayed`, `markUnwatched` -> `markUnplayed`), so call through a
`_call_first_method(item, names, *args)` helper that tries both spellings;
likewise read played state from `isPlayed`, then `isWatched`, then `viewCount`.

Register this subparser from its own `_register_copy_watched_subparser(sub)`
helper to keep both `build_parser` and the copy/mutation registrar under
pylint's statement limit. `-1` is a valid short option here: argparse
recognises that an option string looks like a negative number and stops
treating `-1` as a negative numeric positional.

### `export-playlist <user_id> <playlist> <path>`
`path` is a required positional. Rejects an empty playlist.

### `remove-playlist <user_id> <playlist>`

### `append-playlist <user_id> <playlist> <ratingKey...>`
Fetch each item, fail fast on an unknown key, preview, honour `--dry-run`, then
one `playlist.addItems(...)` call.

### `export-titles <library_id> <output_path> [--sort alpha|date|random] [--album ALBUM]`
`apply_sort` modes: `alpha` (episodes by `(grandparentTitle, seasonNumber, index)`,
others by title), `date` (`originallyAvailableAt` falling back to `addedAt`,
undated sorting last via `datetime.datetime.max`), `random`. Output is M3U for
show/movie libraries and an HTML gallery for photo libraries.

### `login [-u USER] [-p PASS] [-c CODE] [-2]`
Authenticate against plex.tv via `MyPlexAccount` and save the token to
`token_path` with mode 0600, creating parent directories. Distinguish
`Unauthorized` (bad credentials or 2FA required - say so) from `BadRequest`.
Verify the saved token by connecting to the configured URL; a failure warns
rather than aborting, since the token did save. Not in `COMMANDS_REQUIRING_PLEX`
- there is no token yet - but it still loads the config to learn where to write.
`--dry-run` authenticates without writing. `--json` emits
`{"token_path": ..., "verified": ...}` and never the token itself.

Credential precedence, `resolve_credentials(cfg, args)`:

| config | args | result |
|---|---|---|
| user + pass | - | ini user, ini pass |
| user + pass | `--username` | arg user, **prompt** (ini pass ignored) |
| user + pass | `--username --password` | arg user, arg pass |
| user + pass | `--password` | ini user, arg pass |
| user only | - | ini user, prompt |
| - | - | prompt both |
| - | `--username` | arg user, prompt |

The ini password is only ever used alongside the ini username; pairing a stored
password with a different username would be a silent credential mismatch.
Passwords are read with `getpass` and never echoed.

`--password` handling, run from `main()` immediately after logging is configured
and before any network call:

- `_overwrite_argv_memory(replacement)` rewrites the real argv block via
  `ctypes.pythonapi.Py_GetArgcArgv`, because `sys.argv` is only a copy and `ps`
  reads the original buffer. Best-effort, broadly guarded, degrading to a second warning.
- `_mask_argv_copy(secret)` redacts `sys.argv` so tracebacks cannot leak it,
  handling both `--password X` and `--password=X`.
- The warning must be blunt about what cannot be fixed: the password is already
  in shell history and was visible to `ps` during interpreter startup.

### `write-config-example`
Writes `CONFIG_EXAMPLE` to `CONFIG_PATH` with mode 0600, creating parent dirs.
Requires no Plex connection.

Its `--help` must print the exact template that would be written. This needs
`formatter_class=argparse.RawDescriptionHelpFormatter` so the epilog's newlines
survive - but that same formatter also stops argparse wrapping the description,
so pre-wrap the description with `textwrap.fill(..., width=78)` and indent the
epilog template with `textwrap.indent(CONFIG_EXAMPLE, "  ")`.

## PHOTO LIBRARIES

### `collect_photos(section, album=None)`
Walk `section.all()` to get album objects, then `palbum.photos()` on each -
mirroring how show libraries walk shows then episodes. **Do not use
`section.search(libtype="photo")`**: Plex requires a non-empty query string and
returns nothing for an empty one, so the library silently appears empty. When
`album` is given, match `palbum.title` case-insensitively at the album level and
`sys.exit` if nothing matches, suggesting `list-titles`.

### `collect_library_items(section, album=None)`
`show` -> walk `non_special_episodes`; `movie` -> `section.all()`; `photo` ->
`collect_photos`; anything else -> `sys.exit` listing the supported types.

## PHOTO GALLERY - `write_gallery_html(photos, output_path, library_title)`

A single self-contained HTML file using Spotlight.js from jsDelivr for the
lightbox. **No `plex` parameter and no Plex HTTP URLs anywhere in the output** -
every `href` and `src` is a server filesystem path from
`photo_file_path(photo)` (`photo.media[0].parts[0].file`, `None` on
`IndexError`/`AttributeError`). A photo with no resolvable path is skipped,
matching `write_m3u`.

Split into `_gallery_css()`, `_gallery_photo_anchor(photo)`,
`_gallery_album_section(album_name, photos)`, and `_group_photos_by_album(photos)`
to stay under pylint's local-variable limit.

Photos are grouped by `parentTitle` (falling back to `"Uncategorised"`) and
albums sorted alphabetically. Design: near-black `#0d0d0d` background, warm
amber `#a0835c` library title, muted small-caps album headings with counts,
192x192px cover-fit grid, `scale(1.06)` hover, `loading="lazy"` on every
thumbnail, and `prefers-reduced-motion` respected. Spotlight `data-title` is the
photo title and `data-description` the `originallyAvailableAt` date. For a
single-album export the gallery title is `"Library - Album"`.

## MAKEFILE

Provide a `Makefile` whose default target is `help`, listing every target and
printing the completion path currently in effect.

`install` runs `pip install .` and installs the completion; `uninstall` runs
`pip uninstall -y plexdo` and removes it; `develop` does an editable install
with the dev extras. Also provide `reinstall`, `install-completion`,
`uninstall-completion`, `build`, `lint`, `dist-check`, `check`, `clean`, and
`distclean`, and mark them all `.PHONY`.

The completion destination defaults to
`$(XDG_DATA_HOME)/bash-completion/completions` (falling back to
`~/.local/share`), switches to `$(PREFIX)/share/bash-completion/completions`
when `PREFIX` is set, and can be overridden outright via `COMPLETION_DIR`.
Honour `DESTDIR` for staged packaging builds. Respect `PYTHON`, `PIP`, and
`PIP_FLAGS` overrides.

Two safety points: `uninstall-completion` must test for the exact file before
removing it and say so when there is nothing to remove, rather than a blind
`rm -rf` on a user-supplied directory; and `uninstall` must prefix the pip call
with `-` so a package that is already absent does not fail the target.

## LICENSING

The project is GPL-3.0-or-later. `LICENSE` holds the complete GPL v3 text and
`pyproject.toml` declares the SPDX expression `license = "GPL-3.0-or-later"`
(a PEP 639 expression, so do not also add a deprecated `License ::` trove
classifier). Every source file carries an
`# SPDX-License-Identifier: GPL-3.0-or-later` tag; `__init__.py`, `__main__.py`,
and `cli.py` additionally carry the full copyright-and-warranty notice from the
GPL's "How to Apply These Terms" appendix. The README states the copyleft
obligation explicitly.

## PLATFORM SUPPORT

Linux, macOS, and Windows. Five portability rules, each guarding a failure
that is invisible when developing on Linux:

- **Console encoding.** `print_table` and `print_metadata` must select box
  glyphs via a `_box()` helper that test-encodes them against
  `sys.stdout.encoding` and falls back to ASCII `+-|`. A legacy Windows
  console is cp1252, which cannot encode U+2500, so the Unicode-only version
  raises `UnicodeEncodeError` and prints *nothing*. Route cell values through
  a `_printable()` helper that substitutes unencodable characters. Apply it
  only in the printers - never in `clean_text`, which feeds title matching, where
  mangling `Renee` to `Ren?e` would break comparisons against real Plex data.
  JSON output needs no equivalent: `json.dumps` escapes non-ASCII by default.
- **Default paths.** `constants.default_paths(is_windows, env)` returns the
  config path, cache directory, and default `token_path` for the platform.
  Windows has no XDG layout and a dotted directory in the user profile is not
  where a Windows user looks, so both live under `%LOCALAPPDATA%\PlexDo` and
  the token defaults to `%TEMP%\plexdo.token`, with `APPDATA` as a fallback.
  Take the flag and the environment as arguments rather than reading `os.name`
  inside, so the branch is testable from either platform. The three shell
  completions must resolve the same cache location, keying on `LOCALAPPDATA`,
  or completion silently stops working under Git Bash.
- **Permission checks.** `check_file_permissions` must return early when
  `os.name == "nt"`. Windows has no POSIX mode bits; `os.stat` synthesises
  `0o666`, so the check would fire on every run advising a `chmod` that cannot
  help. Guard the `chmod(0o600)` calls the same way.
- **Broken pipes.** After catching `BrokenPipeError` in the `read` command,
  `os.dup2` the null device onto stdout so the interpreter's final flush does
  not print "BrokenPipeError ignored" when the user quits the player.
- **macOS shell tooling.** macOS ships bash 3.2, which has no `mapfile` or
  `readarray`; fill `COMPREPLY` with a `while IFS= read -r` loop instead
  (redirecting into a function does not create a subshell, so the assignment
  survives). Use `stat -c %Y` with a `stat -f %m` fallback in all three
  completions, and restrict the Makefile to `install -d` / `install -m`, since
  `install -D` is GNU-only.
- **Interpreter name.** All three completions must fall back to `python` when
  `python3` is absent, as under Git Bash. In fish, guard `__plexdo_refresh` on
  the binary existing: fish reports an unknown command *before* the
  redirection applies, scribbling on the prompt mid-completion.

## TOKEN STORE AND MULTI-USER ACCESS

`token_path` holds a JSON object mapping username to token, handled by
`tokens.py` (`load_store`, `save_store`, `lookup`, `store_token`,
`admin_token`). Writes are atomic (temp file then `replace`) and mode 0600 on
POSIX.

Two compatibility points that are easy to miss:

- A file that is not JSON is a **pre-1.0.4 bare token**. Read it as
  `{ADMIN_KEY: contents}` rather than erroring, so an upgrade needs no manual
  step; the next write converts it.
- `ADMIN_KEY` is `"@admin"`. A reserved key is needed because `[plex]
  username` is optional, and `@` cannot occur in a Plex username so it cannot
  collide. `admin_token()` resolves in order: configured username, reserved
  key, then a store holding exactly one entry - which is what `login` with no
  configured username leaves behind.

The config file gains a section per user, named for the numeric user ID, each
holding `username` and `password`.

`accounts.server_for_user` tries three sources in order and returns the first
that connects, because a server refuses an admin-issued token for a user it
has shared nothing with:

1. `user.get_token(machineIdentifier)` - the admin-issued, server-scoped token
2. a token already in the store, under any of the candidate usernames
   (configured, then `user.username`, `user.email`, `user.title`)
3. `MyPlexAccount(username, password)` from the `[<user_id>]` section, whose
   `authenticationToken` is then **saved to the store** so the login happens
   once rather than every run

Each stage must return None rather than raising, so the next can be tried; a
stored token that has gone stale must fall through to a fresh login.
`UserAccessError` is raised only when all three fail.

Reading the config repeatedly would re-emit its permission warning once per
user in a loop, so expose a `cached_config()` memoised with
`functools.lru_cache(maxsize=1)` and use it everywhere the fallback path needs
the per-user sections.

## USER ACCESS FAILURES

A shared user with no libraries shared to them cannot be acted on at all, even
by the server admin: `user.get_token()` succeeds but the resulting
`PlexServer(...)` raises `plexapi.exceptions.Unauthorized`, carrying the
server's HTML error page in its message. Untreated this surfaces as a raw
traceback ending in a wall of HTML.

`accounts.server_for_user` must guard both `get_token()` and the `PlexServer`
construction, and a token that comes back empty, raising `UserAccessError`
with a plain-language explanation: the token was rejected, admin rights do not
override per-user scoping, and the fix is to share a library or pass 0. The
underlying exception goes to `LOG.debug` only, so the HTML never reaches the
user.

`UserAccessError` must be an ordinary `Exception`, **not** a `sys.exit`.
`copy-playlist-all-users` catches per-user failures and continues; `SystemExit`
derives from `BaseException` and would tear down the whole run on the first
inaccessible user. `cli.main` catches it around the dispatch and converts it to
a clean `sys.exit` for single-user commands.

It also carries a one-line `summary` attribute. The all-users loop logs that
rather than the full text, so skipping four users produces four lines instead
of twelve paragraphs.

## ERROR HANDLING

`sys.exit` with a clear message for: missing config, missing token, unknown
ratingKey, wrong media type, playlist not found, user not found, library ID not
found, unsupported library type, album not found.

## SHELL COMPLETION

Provide completions for **bash, zsh, fish, and PowerShell** in `completions/`, mirrored
into `src/plexdo/data/` as package data: `plexdo.bash`, `_plexdo` (zsh
`#compdef` convention), and `plexdo.fish`. All three share the same cache
strategy and cover the same values, and all three depend only on `python3` -
no `bash-completion` package, no external helpers.

### bash - `completions/plexdo.bash`

Must work **without** the `bash-completion` package: initialise from
`COMP_WORDS` / `COMP_CWORD` directly rather than `_init_completion`, and use
`compgen -f` rather than `_filedir`. Both are absent on many systems and produce
a `command not found` on every Tab press.

Caches live in `~/.cache/plexdo` with a 900-second TTL, checked via `stat`
portable across Linux (`-c %Y`) and macOS (`-f %m`). When a cache is stale or
missing, `_plexdo_bg_refresh` runs the relevant `plexdo` list command with
`>/dev/null 2>&1 &` and `disown`, so completion never blocks - stale results are
shown now and the next Tab sees fresh ones. `_plexdo_json_candidates cache field`
reads a cache with inline Python.

Helpers: `_plexdo_complete_user_id` (`0` plus cached IDs),
`_plexdo_complete_library_id`, `_plexdo_complete_rating_key` (merged from every
`titles.*.json`, chaining `list-libraries` -> per-library `list-titles` when
nothing is cached), `_plexdo_complete_playlist(uid)`,
`_plexdo_complete_playlist_id_or_name(uid)` (both ratingKeys and titles, for
`list-playlist`), `_plexdo_complete_album(library_id)` (unique album prefixes
split from `"Album - Photo Title"`), plus `_plexdo_find_cmd`,
`_plexdo_positional_count` (skipping `--m3u <value>` pairs), and
`_plexdo_nth_positional`.

| command | pos 0 | pos 1 | pos 2 | pos 3 | flags |
|---|---|---|---|---|---|
| `list-titles` | library_id | - | - | - | `--album` -> albums |
| `search` | user_id | free | - | - | `--media-type`, `--library-id` |
| `list-playlists` | user_id | - | - | - | - |
| `list-playlist` | user_id | playlist-id-or-name | - | - | `--m3u` -> file |
| `list-show` | rating_key | - | - | - | `--m3u` -> file |
| `show-metadata` | rating_key | - | - | - | - |
| `read` | library_id | rating_key | - | - | - |
| `rescan` | library_id | - | - | - | `-s/--status`, `-n/--now` |
| `build-interleaved` | free | rating_key... | - | - | `--m3u` -> file |
| `build-chronological` | free | rating_key... | - | - | `--m3u` -> file |
| `build-randomize` | user_id | playlist | free | - | `--m3u` -> file |
| `copy-playlist-all-users` | user_id | playlist | - | - | `-o/--overwrite` |
| `copy-playlist-to-user` | user_id | playlist | user_id | playlist | `-o/--overwrite` |
| `remove-playlist` | user_id | playlist | - | - | - |
| `export-playlist` | user_id | playlist | file path | - | - |
| `append-playlist` | user_id | playlist | rating_key... | - | - |
| `export-titles` | library_id | file path | - | - | `--sort`, `--album` -> albums |
| `copy-watched` | user_id | user_id | - | - | `-1`, `-l` -> libraries, `-t` -> ratingKeys, `--unwatch` |

Values that can contain spaces (library titles, user titles, playlist names)
must reach `COMPREPLY` as whole lines via the read-loop helper, **not** through
`compgen -W`, which word-splits `TV Shows` into two candidates.

Numeric IDs must be shown with their titles: `7  (Alice)`, `101  (Breaking Bad
- Pilot)`. bash cannot attach descriptions to completions, but it only
*inserts* a candidate once a single one remains - with several it merely lists
them and inserts their common prefix. `_plexdo_compreply_pairs` exploits that:
it lists the annotated forms while a choice remains and substitutes the bare
value the moment the choice collapses to one. Every annotated form begins with
its own value, so the common prefix bash inserts stays a valid prefix.

Distinguish what is *insertable* from what is merely *shown*: user and library
titles are insertable, because those arguments accept a title, but an item
title is not - `fetchItem` needs a numeric ratingKey, so a title there is
display only.

`_plexdo_complete_rating_key` merges keys from every `titles.*.json`, so it
must gather them all and render once; filling `COMPREPLY` inside the loop lets
a later library discard an earlier one's matches. Clear `COMPREPLY` on entry,
since bash does not reset it between invocations.

### PowerShell - `completions/plexdo.ps1`

`Register-ArgumentCompleter -Native -CommandName plexdo`. Needs no external
interpreter: `ConvertFrom-Json` reads the cache and the ini is parsed with a
line loop. Return `CompletionResult` objects so the ID is inserted while the
title shows as the tooltip, and quote values containing spaces.

Two PowerShell traps that parse cleanly and fail at runtime: a range of
`0..-1` **wraps** and yields the whole array, so stripping the word being
completed from a single-token list needs an explicit empty-array case; and a
parenthesised `if` is not a valid argument expression, so bind it to a
variable before passing it to a function.

### zsh - `completions/_plexdo`

Start with `#compdef plexdo plexdo`. Use `_arguments -C` with
`'1:command:_plexdo_commands'` and `'*::command argument:->subcmd'`, then a
`case ${words[1]}` dispatch. Note that under `*::` zsh **rebinds `words` so
that `words[1]` is the subcommand**, which the positional helper must assume.
Offer descriptions via `_describe`, and sanitise `:` out of description text
since `_describe` splits `value:description` on it.

### fish - `completions/plexdo.fish`

Use `complete -c plexdo -f` plus `-c plexdo` for the alias, gating each rule
on `__fish_seen_subcommand_from`. Fish has no positional-index primitive, so
write `__plexdo_positionals` / `__plexdo_at` / `__plexdo_nth` helpers that walk
`(commandline -opc)`, skipping flags and the values consumed by options that
take one (`--m3u`, `--album`, `--sort`, `--media-type`, `--library-id`, `-l`,
`-t`, `-u`, `-p`, `-c`). Global flags are registered without a subcommand
condition so they complete in either position. Emit `value\tdescription` pairs.
| `login` | - | - | - | - | `-u`, `-p`, `-c`, `-2` |

Register with `complete -F _plexdo_complete plexdo` and the same for `plex_do`.

## MAN PAGE

`man/plexdo.1`, in roff, mirrored into `src/plexdo/data/` as package data and
installed by `make install` to `$(MAN_DIR)/man1`. It must document every
command, the configuration and token formats, exit status, environment, files,
and worked examples, and must pass `groff -man -Tutf8 -ww -z` with no warnings.

The `.TH` line carries the version, which makes three places that can drift
apart. `make check-version` compares `__init__.py`, `pyproject.toml`, and the
man page and fails on any mismatch; it runs first in `make check`.

Two escapes to watch, both of which corrupt copy-pasteable examples if missed:

- A literal backslash is `\e`, so a UNC path in an example needs
  `\e\eNAS\emedia` to render as `\\NAS\media`.
- A literal apostrophe is `\(aq`, and a literal backtick is `\(ga`. groff
  remaps a bare `'` to a typographic right quote (U+2019) and a bare backtick
  to a left quote on many configurations - visible in PostScript output as the
  glyph `quoteright` rather than `quotesingle`. That silently breaks any
  shell-quoted example a reader tries to copy. Double quotes are *not*
  remapped and need no escape.

## PROJECT URLS

Homepage and source: `https://github.com/sidusnare/plexdo`
Issue tracker: `https://github.com/sidusnare/plexdo/issues`

These belong in `[project.urls]` (Homepage, Source, Issues), the README's
install and Links sections, and the man page's SEE ALSO and BUGS sections.
The repository, the distribution, the import package, the console script, the
man page, and the completion files all share the single name `plexdo`. The
project was once called `plex.do`; that name is retired and must not reappear
anywhere, including in the config path (`~/.local/etc/plexdo.ini`), the cache
directory (`~/.cache/plexdo`), or the completion filenames.

There is exactly one console script. An earlier `plex.do` entry point and a
`plex_do` completion alias existed only to work around the dot in the old
name; both are gone.

In the man page, write URLs as plain text with `.I`, not with the `.UR`/`.UE`
macros: those emit OSC-8 hyperlink escapes that duplicate the URL wherever the
page is piped through something that does not understand them.

## TESTS

`tests/` holds a pytest suite that must pass in `make check`. It covers the
project's own decision logic and never touches a network: the fixtures in
`conftest.py` stand in for plexapi objects.

What is worth testing, because a regression there is silent rather than loud:
the four output serialisers round-tripping through real parsers; table
alignment under double-width characters and the ASCII fallback for consoles
that cannot encode box glyphs; identifier resolution including the case where
a value is both one entry's ID and another's title; the playlist overwrite
guard performing no server calls when it refuses; watched-state winner
selection in both directions, including that an undated state never wins; path
rewriting picking the longest matching library root; the token store reading a
legacy bare-token file; and that global flags survive being given before the
subcommand.

Two behaviours the tests pin down that are easy to get backwards: two fully
played states need no sync at all, so a "latest wins" test must use states that
actually differ; and `format_duration(None)` is empty while
`format_duration(0)` is "0:00", because unknown and zero are different things.

## PUBLISHING CHECKLIST

Beyond the code: `py.typed` (the package is fully annotated, and without the
marker none of it reaches downstream users), `CHANGELOG.md`, `CONTRIBUTING.md`,
`SECURITY.md`, `.gitattributes`, a CI workflow covering Python 3.11-3.13 plus
a job that parses all three completions and lints the man page, and an AUTHORS
section in the man page.

Attribution is `SidusNare`, in `[project.authors]`, the GPL copyright line of
`__init__.py`, `__main__.py`, and `cli.py`, and the man page AUTHORS section.
No email is published; PEP 621 allows a name alone, and the address would be
public on PyPI.

## DELIVERABLES

1. The `plexdo` package under `src/`, laid out as above
2. `pyproject.toml` - PEP 621 metadata, both console scripts, package data, pylint config
3. `README.md` - install, configuration, every command group with examples, completion setup, layout
4. `man/plexdo.1` - the manual page
4. `LICENSE` - the full GNU GPL v3 text, `MANIFEST.in`, `requirements.txt`, `.gitignore`
5. `Makefile` - see below
6. `completions/plexdo.bash`, mirrored into `src/plexdo/data/`
7. `AI.prompt.md` - this file, at the top level of the project, containing the
   full prompt that regenerates the project including this requirement itself

Dead code and orphaned comments are checked with `vulture src/plexdo
--min-confidence 0` alongside pylint; both must come back empty. When a symbol
is renamed or removed, the sweep must include this file - a spec that still
describes the old API will regenerate it.

Verification: `make check` runs `check-version`, `smoke`, `pylint`, `build`,
and `twine check` in that order. The `smoke` target imports the package,
builds the full parser, and asserts every module in `MODULES` still exposes
`register()` and `COMMANDS` - pylint scores a module 10.00/10 even when an
edit has silently truncated that tail, which breaks every command in it.
`pylint src/plexdo` scores 10.00/10, `python -m build` succeeds,
`twine check dist/*` passes, and installing the wheel into a clean virtualenv
gives a working `plexdo` console script.
