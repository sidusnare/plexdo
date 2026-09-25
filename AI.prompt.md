# AI.prompt.md

This file is the complete prompt that regenerates this project from scratch,
and the authoritative specification for it. When behaviour changes, update
this file in the same commit.

Much of what follows is stated as a constraint with the reason attached. The
reasons matter: nearly every one records a bug that was shipped and then
found, and a regeneration that ignores them will reintroduce it.

---

Build `plexdo`, an installable Python package providing a command-line
interface to Plex Media Server via the `plexapi` library, ready to publish to
PyPI.

## IDENTITY

- Distribution, import package, console script, man page, and completion files
  all share the single name `plexdo`. The project was once called `plex.do`;
  that name is retired and must not appear anywhere.
- There is exactly one console script: `plexdo = "plexdo.cli:main"`.
- Homepage and source: `https://github.com/sidusnare/plexdo`
- Issues: `https://github.com/sidusnare/plexdo/issues`
- Author: `SidusNare`, in `[project.authors]`, the GPL copyright line of
  `__init__.py`, `__main__.py`, and `cli.py`, and the man page AUTHORS
  section. No email is published; PEP 621 allows a name alone.
- Licence: GPL-3.0-or-later. `LICENSE` holds the full text; `pyproject.toml`
  declares the SPDX expression and **no** `License ::` trove classifier, which
  modern setuptools rejects alongside it. Every source file carries an SPDX
  tag; the three entry-point modules carry the full notice.

## VERSIONING

`major.minor.revision`. `__version__` in `src/plexdo/__init__.py`, `version`
in `pyproject.toml`, and the `.TH` line of the man page must agree.

**Increment the revision every time a release archive is produced.** Major and
minor move only on explicit instruction, never because a change felt
significant. The `Version="1.1.0.1"` attribute in CLIXML output is a fixed
PowerShell schema constant and has nothing to do with this version.

## GENERAL REQUIREMENTS

- Python 3.11 through 3.14.
- Every function fully annotated; the package ships `py.typed`.
- pylint 10.00/10 across the package, and `vulture src/plexdo
  --min-confidence 0` empty. Scope vulture to `src`: test fixtures are
  consumed reflectively through `vars()`, so it cannot see their attributes
  being used.
- Google style, small single-purpose functions, no dead code, no duplicated
  logic, no global mutable state, no bare `except`.

### Naming

A leading underscore means **module-private**. A helper another module imports
is package API and must not carry one, or the convention says nothing.

**No two modules may define the same name.** The import tooling keeps one
entry per symbol, so a duplicate makes it inject a cross-module import that
silently shadows the local definition. That is how `records._scalar` came to
be overridden by `formats._scalar`, quietly disabling nested media expansion.
Name functions for what they do: `_cell_value` flattens a value for a tabular
cell, `_jsonable` preserves structure.

A constant referenced only by its own test is ceremony, not a source of truth;
assert the literal in the test instead.

### Character set

Source, completions, man page, and build files are **plain ASCII**. Write `-`
not an em dash, `->` not an arrow, `>=` not the inequality sign, `...` not an
ellipsis, a straight `'` not a curly quote. This applies to comments,
docstrings, and user-facing message strings alike: a warning printed to a
terminal has no business containing an em dash.

Two deliberate exceptions, both about output rather than prose: `console.py`
holds the box-drawing glyphs as `\uXXXX` escapes, so the file itself stays
ASCII while the tables still draw; and the markdown docs keep literal box
characters where they reproduce program output or draw a `tree`-style listing.

## LAYOUT

```
pyproject.toml  Makefile  README.md  LICENSE  MANIFEST.in  requirements.txt
CHANGELOG.md  CONTRIBUTING.md  SECURITY.md  AI.prompt.md  .gitignore
.gitattributes  .github/workflows/ci.yml
man/plexdo.1
completions/{plexdo.bash,_plexdo,plexdo.fish,plexdo.ps1}
tests/conftest.py + test_*.py
src/plexdo/
    __init__.py     __version__
    __main__.py     python -m plexdo
    cli.py          build_parser, main
    constants.py    windows_app_dir, default_paths, CONFIG_PATH,
                    DEFAULT_CACHE_DIR, DEFAULT_TOKEN_PATH, CONFIG_EXAMPLE, LOG
    logs.py         configure_logging
    config.py       load_config, cached_config, connect_plex, read_token,
                    token_store_path, config_optional, section_optional,
                    check_file_permissions
    tokens.py       load_store, save_store, lookup, store_token, admin_token
    cache.py        cache_dir, write_cache
    convert.py      parse_date, format_duration
    console.py      output, output_format, clean_text, table_limit,
                    print_table, print_metadata
    formats.py      to_json, to_yaml, to_csv, to_clixml, render
    records.py      loaded_fields, file_paths, release_date, summary_row,
                    cache_row, season_records
    identify.py     resolve_identifier
    accounts.py     server_for_user, account_type, resolve_user_arguments,
                    UserAccessError
    sections.py     resolve_section, resolve_sections,
                    resolve_library_arguments
    titles.py       display_title, fetch_item, fetch_show,
                    non_special_episodes, shuffle_list, item_is_played,
                    item_view_offset
    playlists.py    resolve_playlist, finalize_playlist, copy_playlist_to,
                    existing_playlist, preview_rows
    photos.py       collect_photos, collect_library_items, photo_file_path
    sorting.py      apply_sort
    m3u.py          write_m3u
    gallery.py      write_gallery_html
    paths.py        mapper_for, library_roots, add_prefix_argument
    airdates.py     resolve_episode_date and its helpers
    throttle.py     paced, throttle_delay
    security.py     scrub_password_argument
    data/           the four completions and the man page, as package data
    commands/       one module per group (see COMMANDS)
```

### Command module contract

Every module in `commands/` exposes exactly three names:

- `register(sub, parents)` adds its subparsers, passing `parents=parents` on
  every `add_parser` call so each inherits the global flags.
- `COMMANDS` maps command name to handler.
- `REQUIRES_PLEX` is the subset needing a server; `auth` has an empty
  frozenset because `login` and `write-config-example` run before a token
  exists.

`commands/__init__.py` holds a `MODULES` tuple whose order sets the order of
subcommands in `--help`, plus `register_all(sub, parents)` and
`build_registry()`. Adding a command means adding a module and listing it;
`cli.py` never changes.

## PLATFORM DEFAULTS

`constants.default_paths(is_windows, env)` returns the config path, cache
directory, and default `token_path`. Take the flag and environment as
arguments rather than reading `os.name` inside, so both branches are testable
from either platform: forcing `os.name` on Linux makes `pathlib` fail to build
a `WindowsPath`.

| | config | cache | token_path |
| --- | --- | --- | --- |
| Linux, macOS | `~/.local/etc/plexdo.ini` | `~/.cache/plexdo` | `$XDG_RUNTIME_DIR/.plex.token` |
| Windows | `%LOCALAPPDATA%\PlexDo\plexdo.ini` | `%LOCALAPPDATA%\PlexDo\Cache` | `%TEMP%\plexdo.token` |

`APPDATA` is the Windows fallback when `LOCALAPPDATA` is unset. All four shell
completions must resolve the same cache location, or completion silently stops
working under Git Bash.

## CONFIGURATION

```ini
[plex]
url = http://localhost:32400
token_path = $XDG_RUNTIME_DIR/.plex.token
# cache_dir = ~/.cache/plexdo
# username = you@example.com
# password = your-plex-password

[99]
username = bob@example.com
password = bobs-plex-password
```

- Construct the parser with `interpolation=None`: the default
  `BasicInterpolation` raises on a password containing `%` before the value
  can ever be used.
- Expand environment variables in every `[plex]` value with
  `os.path.expandvars`, which follows the platform (`%VAR%` on Windows,
  `$VAR` everywhere). An unset name is left literal, which would surface much
  later as a confusing "no such file", so warn about any name still present
  after expansion, in whichever spelling the platform accepts.
- `cache_dir` relocates the completion cache; the platform default appears
  commented out in the generated template.
- A section named for a numeric user ID holds that user's credentials.
- `cached_config()` is memoised with `lru_cache(maxsize=1)`: the fallback
  login path reaches per-user sections once per user in a loop, and re-reading
  would re-emit the permission warning each time.
- `check_file_permissions` warns when the config or token file is readable by
  group or other, at WARNING level so it shows without `--verbose` and on
  stderr so it never contaminates `--json`. Return early on `os.name == "nt"`:
  Windows has no POSIX mode bits and `os.stat` synthesises `0o666`, so the
  check would fire on every run advising a `chmod` that cannot help.

## TOKEN STORE AND MULTI-USER ACCESS

`token_path` holds a JSON object of username to token, handled by `tokens.py`.
Writes are atomic (temp file then `replace`) and mode 0600 on POSIX.

- A file that is not JSON is a **pre-1.0.4 bare token**. Read it as
  `{ADMIN_KEY: contents}` rather than erroring; the next write converts it.
- `ADMIN_KEY` is `"@admin"`. A reserved key is needed because `[plex]
  username` is optional, and `@` cannot occur in a Plex username.
  `admin_token()` resolves in order: configured username, reserved key, then a
  store holding exactly one entry.

`accounts.server_for_user(plex, user_id)` returns the admin server for
`user_id == 0`. Otherwise it tries three sources in order and returns the
first that connects, because a server refuses an admin-issued token for a user
it has shared nothing with:

1. `user.get_token(machineIdentifier)` (**never** `switchHomeUser()`, which
   only works for Plex Home and raises 401 for ordinary shared users)
2. a token already in the store, under any candidate username
3. `MyPlexAccount(username, password)` from the `[<user_id>]` section, whose
   token is then **saved** so the login happens once

Each stage returns None rather than raising, so the next is tried and a stale
stored token falls through to a fresh login. When all three fail, raise
`UserAccessError` explaining that admin rights do not override per-user
scoping and that a `[<user_id>]` section would fix it. It must be an ordinary
`Exception`, **not** a `sys.exit`: `copy-playlist-all-users` catches per-user
failures and continues, and `SystemExit` would tear down the whole run.
`cli.main` converts it to a clean exit for single-user commands. It carries a
one-line `summary` so a loop reports each skip in one line.

## IDENTIFIERS

`identify.resolve_identifier(roster, value, kind, list_command)` implements
the rules once for users, libraries, and shows. Do not write it three times.

- Titles match exactly first, then case-insensitively.
- More than one title match aborts, listing the colliding IDs.
- A numeric value that is a real ID wins; if it is *also* another entry's
  title, warn naming the entry not selected.
- A numeric value that is not a real ID but is a title resolves by title.
- A numeric value matching nothing is returned unchanged, so the downstream
  lookup produces the precise error.
- A non-numeric value matching nothing aborts, pointing at the list command.

The duplicate-title abort applies only when resolving by title; a numeric ID
is unambiguous and must still work on a server with two identically titled
entries.

Every argument naming a user or library accepts either form, so those argparse
arguments are plain strings with `metavar="USER"` or `"LIBRARY"` - never
`type=int`. `accounts.resolve_user_arguments` and
`sections.resolve_library_arguments` run from `cli.main` after connecting and
before dispatch, rewriting `user_id`, `user_a`, `user_b`, `source_user_id`,
and `library_id` in place, so handlers always receive an int. Build each
roster once per invocation, and skip the fetch when no such argument is
present.

## GLOBAL FLAGS

`-f/--format`, `--json`, `-v/--verbose`, `--debug`, `--dry-run`, `-W/--wide`,
`--throttle`, `-V/--version`. They must work **either before or after the
command name**.

Implement with `_add_global_flags(parser, suppress=False)` called twice: once
on the top-level parser with ordinary defaults, and once on an
`add_help=False` parent that every subparser inherits via `parents=`.

The SUPPRESS default is essential, not cosmetic. A subparser parses into its
own namespace and then copies **every** attribute onto the main one, so
ordinary defaults on the inherited copies would silently clobber a flag given
before the subcommand: `plexdo --json list-users` would print a table.

`--format` writes to `dest="format"`; `--json` is a `store_const` alias
writing to that same destination, so there is one attribute and no way for the
two to disagree. All logging goes to stderr only.

## OUTPUT

`output(data, args)` dispatches on `output_format(args)`, accepting **either**
a single record or a list so `show-metadata` and `list-titles` share the path.
No command reaches for `json.dumps` directly.

### Formats

| format | notes |
| --- | --- |
| `table` | box-drawn, width-aligned, fitted to the terminal |
| `json` | non-ASCII escaped, so it prints on any console |
| `yaml` | strings **always** double-quoted |
| `csv` | header row, `\n` line endings |
| `clixml` | PowerShell CLIXML with typed properties |

- YAML strings must always be quoted. Plain style would let YAML's type
  guessing turn a title of `NO`, `yes`, or `1.10` into a boolean or a float on
  the way back in. The emitter must be recursive, or nested sections
  serialise as stringified Python dicts.
- CLIXML emits typed elements (`<S>`, `<I32>`, `<B>`, `<Nil>`) inside `<MS>`,
  the first `<Obj>` carrying `<TN>` and later ones `<TNRef RefId="0" />`,
  which is what `Import-Clixml` expects.
- `formats._cell_value` flattens for CSV and CLIXML; `records._jsonable`
  preserves structure for the formats that can express it.

### Tables

- `clean_text(value)` is `str(value).strip()`. Plex metadata contains stray
  `\r`, which makes a printed row's trailing pad overwrite the start of the
  line and appear as a blank line after every row.
- `_display_width` uses `unicodedata.east_asian_width`, **not** `len()`: CJK
  glyphs occupy two columns and combining marks none, so a `len()`-padded
  table drifts out of alignment on any non-Latin title.
- `_box()` test-encodes the glyphs against `sys.stdout.encoding` and falls
  back to ASCII `+-|`. A legacy Windows console is cp1252, which cannot encode
  U+2500, and the Unicode-only version raises `UnicodeEncodeError` and prints
  *nothing*. `_printable()` substitutes unencodable cell characters. Apply it
  only in the printers, never in `clean_text`, which feeds title matching:
  mangling an accented name there would break comparisons against real Plex
  data.
- `table_limit(args)` returns the column budget, or `None` when `-W/--wide` is
  given **or stdout is not a tty** - truncating a pipeline would corrupt data
  going to a file or `grep`. `_fit_widths` shrinks the widest column
  repeatedly, stopping at `MIN_COLUMN_WIDTH` and only then at the ellipsis
  itself, so a very narrow terminal degrades rather than overflowing.
  Truncation is display-width aware; report the narrowed columns once at info
  level naming `--wide`.

## THROTTLING

`throttle.paced(items, args, what)` yields items, sleeping `--throttle`
seconds between them once the count passes `THROTTLE_THRESHOLD` (50). Default
0.25s; 0 disables. The pause goes *between* elements, so n items wait n-1
times, and a short run is never paced because the delay would be latency for
no benefit. Announce once at info level with the expected duration and how to
turn it off.

Apply wherever a loop makes one request per element and the count can exceed
50: the seasons walk in `list-titles`, `find-missing -A`, applying watched
state in `copy-watched`, removing entries in `clean-playlist`, reading each
source in `build-concatenated`, `collect_photos`, and the per-user loop in
`copy-playlist-all-users`. Functions needing it take an optional `args`.

## RECORDS

plexapi exposes `media`, `genres`, `directors`, `collections` and a dozen
others as `cached_data_property`. Those are **absent from `vars()`** until
something first accesses them, so reading only `vars()` reports a fraction of
the metadata and no file paths at all. Take the union of `vars(item)` and
`type(item)._cached_data_properties`.

Reading them must not cost requests, though:
`PlexPartialObject.__getattribute__` reloads whenever a value is `None` or
`[]` and the object is partial, which across a library is one round trip per
item. Set `item._autoReload = False` while reading and restore it afterwards;
that flag short-circuits the reload. Note plexapi returns underscore
attributes without reloading, so a test fake modelling this must explode only
for public names.

`records._media_versions` reads the XML plexapi already holds in `_data`
rather than the `media` property: it is always accurate, needs no reload
guard, and carries the `selected` flags that identify the version and part a
session is actually playing.

`_jsonable` expands nested plexapi objects to a depth of 2 rather than
`str()`-ing them, or `media` serialises as `<Media object at 0x...>` and the
file names appear nowhere. Cap the depth and guard `vars()` with `TypeError`,
since a self-referential object or one using `__slots__` would otherwise
recurse or raise. Reduce tag objects to their `.tag` and dates to text.

`records.file_paths(item)` is the **only** media traversal in the project:
M3U export, the photo gallery, `show-metadata`, and `loaded_fields` all use
it. An item may have several versions each with several parts, so it returns a
list. `loaded_fields` also lifts the paths to a top-level `files` key, because
they are otherwise three levels down.

`sourceURI` is not a file name: plexapi sets it from the `source` attribute,
the remote server URI of an item in another user's playlist, null for local
content.

## PLAYLISTS

Every argument naming an **existing** playlist accepts a title or a ratingKey
through `resolve_playlist`; no command may call `plex.playlist(name)`
directly.

Every build command constructs the list fully in memory, validates it is
non-empty, prints a numbered preview, and makes exactly one `createPlaylist`
call. `finalize_playlist` enforces this and returns `"created"` or
`"replaced"`.

Every creating command takes `-o/--overwrite`. A name collision without it
exits reporting the existing ratingKey and making clear nothing was created or
removed, and that check happens **before** the preview so a doomed run fails
immediately rather than after a screen of output.

`copy_playlist_to` returns `(status, final_name, detail)` and must **not**
delete: `_resolve_dest_name` only reports a replacement when `--overwrite` was
given, so `finalize_playlist` doing it too would be the same logic twice.
Without `--overwrite`, a taken name falls back to appending `" admin copy"`;
if that is taken too the target is skipped with a warning and nothing is
touched.

## COMMANDS

### Listing and searching

- `list-libraries` - columns `id`, `type`, `title`; writes the libraries cache.
- `list-titles LIBRARY [--album A]` - registered with
  `aliases=["list-library"]`. argparse reports whichever spelling was typed,
  so `COMMANDS` needs an entry for both, giving 27 registry entries for 26
  commands; the smoke test floor must allow for it. Table columns are
  `ratingKey`, `title`, `releaseDate`, `rating`, `studio`; a machine-readable
  format carries every listed field and, for a show library, nests each show's
  episodes under a `seasons` object keyed by season name. Always cache the
  minimal `ratingKey`/`title` rows whatever the caller asked to see.
- `list-show RATINGKEY [--m3u P] [-p PREFIX]` - fails fast if not a `Show`.
- `list-users` - `id`, `type`, `title`, `username`, `email`. `account_type`
  returns managed/home/friend/shared. plexapi exposes `restricted` as the raw
  XML **string**, so `"0"` is truthy and a naive check labels every account
  managed.
- `list-playlists USER`, `list-playlist USER PLAYLIST [--m3u P] [-p PREFIX]`.
- `show-metadata RATINGKEY` - type-specific builders via `_METADATA_BUILDERS`
  keyed on `item.type`, plus the file paths. A table names a lone file `file`
  and numbers several `file 1`, `file 2`; other formats carry a `files` list.
- `search USER QUERY [--media-type T] [--library-id L]` - per-library failures
  log a warning and continue.
- `find-missing SHOW [-l LIBRARY] [-A] [-s SEASONS] [--include-specials]` -
  names one show by default, resolved through `resolve_identifier`. `-A`
  sweeps every show and refuses a SHOW argument; `-s` takes one number or a
  comma list and applies only to a single show. For each season the run starts
  at 0 when an episode 0 exists and otherwise at 1, ending at the highest
  present. A season that simply **stops early is not a gap**: an unaired
  episode cannot be told from a missing one. Season 0 is skipped by default
  because specials are numbered irregularly, but `-s 0` overrides that, since
  asking for season 0 can only mean the specials.

### Building and copying

- `build-interleaved NAME RATINGKEY...` - round-robin across shows.
- `build-chronological NAME RATINGKEY...` - sorted by air date. A missing date
  is estimated from neighbours in the same season: collect up to 6 either
  side, require at least 3 known dates (so at least 2 intervals), take the
  median interval, estimate from latest-previous `+median` and earliest-next
  `-median`, averaging when both exist, and prompt only when that is
  impossible.
- `build-randomize USER SOURCE DEST` - Fisher-Yates via `secrets.randbelow`.
- `build-concatenated USER NAME PLAYLIST... [--unique]` - joins the sources
  end to end, keeping the order within each and the order they were named in.
  Read **every** source before writing anything, so naming a source as the
  destination works under `--overwrite`: the items are already in memory when
  the old playlist goes. Duplicates are kept by default - a concatenation is
  faithful, and Plex permits a repeat - while `--unique` keeps only an item's
  first appearance, matched on ratingKey rather than title, and reports how
  many it skipped. Warn about an empty source rather than passing over it: a
  typo that resolved to the wrong playlist looks exactly like a playlist that
  happens to be empty.
- `copy-playlist-all-users USER PLAYLIST` - skips the source user, prints the
  item list **once** before the loop and passes `preview=False` thereafter,
  then one line per user (`created`, `replaced`, `skipped`, `failed`) printed
  as it completes. Because the caller surfaces the skip reason, the message
  inside `copy_playlist_to` is `LOG.info`, not a warning that would duplicate
  every skip on stderr.
- `copy-playlist-to-user USER PLAYLIST USER DEST`.
- `append-playlist USER PLAYLIST RATINGKEY...`, `remove-playlist USER PLAYLIST`.
- `clean-playlist USER PLAYLIST [--include-partial]` - removes the watched
  entries and leaves the rest in their existing order. Preview first, then one
  `removeItems` call per entry so the loop is paced like any other per-item
  loop; the playlist item IDs come from the listing plexapi already holds, so
  the repeated calls cost nothing beyond the one DELETE each. Number the
  preview by each entry's place in the playlist **as it stands**, not within
  the removal list, so it lines up with what Plex shows. A part-played item is
  **kept** by default - it is the one being watched right now, not a watched
  one - and `--include-partial` drops it, labelled `partial` rather than
  `played`. Refuse a smart playlist: its contents come from a filter, and Plex
  answers a delete on one of its entries with a 400. Warn when every entry is
  going, since Plex drops a playlist that loses its last item.

### Watched state

`copy-watched USER USER [-1] [-l LIBRARY] [-t KEY] [--unwatch]`.
`_select_winner(first, second, unwatch)` returns `(winner, loser)` or None:

| situation | default | `--unwatch` |
| --- | --- | --- |
| neither has data, or states match | skip | skip |
| exactly one has data | the one **with** it wins | the one **without** it wins |
| both have data | **latest** `lastViewedAt` | **earliest** `lastViewedAt` |

A `lastViewedAt` of `None` must never win: map it to `datetime.min` when the
latest wins and `datetime.max` when the earliest does. Plex rewrites
`viewOffset` continuously during playback, so treat offsets within
`_OFFSET_TOLERANCE_MS` (10s) as identical, or every run reports spurious
changes. Two fully played states need no sync at all.

plexapi renamed these methods, so call through a helper trying both spellings
(`markPlayed`/`markWatched`, `markUnplayed`/`markUnwatched`) and read played
state from `isPlayed`, then `isWatched`, then `viewCount`. That read and the
resume-point read are `titles.item_is_played` and `titles.item_view_offset`,
because `clean-playlist` needs the same two and the rules must not be written
twice. All three attributes default to a bool or a number rather than None, so
reading them does not satisfy plexapi's reload condition.

Watch state lives on leaf items: map `movie`->`movie`, `show`->`episode`,
`artist`->`track`, and skip photo libraries. Use `section.all(libtype=...)`,
**not** `section.search(...)`, which needs a non-empty query.

### Exporting

- `export-playlist USER PLAYLIST PATH`, `export-titles LIBRARY PATH
  [--sort alpha|date|random] [--album A]`.
- M3U carries Plex server filesystem paths, `#EXTINF` seconds from
  `duration`/1000 with `-1` fallback, and skips items with no path.
- Photo libraries export a self-contained Spotlight.js gallery. **No Plex HTTP
  URLs anywhere in it**: both `href` and `src` are server filesystem paths.
- `-p/--prefix` on all eight export commands, registered through
  `paths.add_prefix_argument` - repeating the help text inline trips
  `duplicate-code`. `mapper_for(plex, args)` returns `identity` without a
  prefix, so the default costs no extra call. The prefix replaces the
  **library root**, so `library_roots()` sorts longest-first or a library
  nested in another's tree matches the wrong one. Rejoin using the prefix's
  own separator style. A path under no known root is appended whole and warned
  about exactly once.

### Photos

`collect_photos` walks `section.all()` (albums) then `palbum.photos()`.
**Never** `section.search(libtype="photo")`: Plex requires a non-empty query
string and returns nothing for an empty one, so the library appears empty.

### Streaming and server management

- `read LIBRARY RATINGKEY` - streams to `sys.stdout.buffer` in 64KB chunks via
  `requests.get(stream=True)`. Validate the item's `librarySectionID` matches.
  Catch `BrokenPipeError` silently and `os.dup2` the null device onto stdout,
  so the interpreter's final flush does not print "BrokenPipeError ignored"
  when the user quits the player. The epilog shows worked examples including
  `plexdo read 3 12345 | mpv --vo=drm -` for **Linux with a display attached
  but no desktop environment** - describe the condition, not the machine:
  "headless" contradicts having a screen, and the hardware could be a Pi, a
  kiosk, a sign, or an old laptop.
- `rescan [LIBRARY] [-s] [-n]` - `plex.activities` is a **property**, not a
  method. `section.update()` scans for files; `refresh()` only re-fetches
  metadata.
- `status [--section S]` - the sessions table carries `user`, `library`,
  `ratingKey`, `title`, `state`, `player`, `platform`, `address`, `progress`,
  and `file`. `records.playing_file` reports the file in use: a session marks
  the version and part being played with `selected`, which is the only way to
  tell them apart on a multi-version item, and nothing is marked when there is
  just one, so an empty selection means all of them. Eight sections: `server`, `sessions`, `users`,
  `accounts`, `connections`, `scans`, `activities`, `tasks`. Split
  `plex.activities` on whether the type mentions scan/refresh/library so scans
  and other background work are separate. Collect each section in its own
  try/except: `connections` needs a plex.tv round trip an offline server
  cannot make. CSV and CLIXML are flat and require `--section`.

### Setup

- `login [-u USER] [-p PASS] [-c CODE] [-2]` - password read with `getpass`.
  Credential precedence: `--username` uses that name and **ignores** the
  config password, since pairing a stored password with a different username
  would be a silent mismatch; otherwise the config username brings its
  password; `--password` always overrides. `--password` on the command line is
  scrubbed from the process title via `ctypes.pythonapi.Py_GetArgcArgv`
  (`sys.argv` is only a copy; `ps` reads the original buffer) and redacted
  from `sys.argv`, with a warning that is blunt about what cannot be fixed:
  the value is already in shell history and was visible during interpreter
  startup. On Windows the rewrite has no equivalent.
- `write-config-example` - writes `CONFIG_EXAMPLE`, mode 0600. Its `--help`
  prints the exact template, which needs `RawDescriptionHelpFormatter` for the
  epilog's newlines; that same formatter stops argparse wrapping the
  description, so pre-wrap it with `textwrap.fill(..., width=78)`.

## ERROR HANDLING

`sys.exit` with a clear message for: missing config or token, unknown
ratingKey, wrong media type, playlist or user or library not found,
unsupported library type, album not found, a refused name collision, a smart
playlist asked to give up an entry. No bare
`except`; the broad ones are in `_cancel_all_scans`, the per-user copy loop,
and per-section collection, each with a `# pylint: disable=broad-except`.

## PLATFORM SUPPORT

- **macOS** ships bash 3.2, which has no `mapfile`; fill `COMPREPLY` with a
  `while IFS= read -r` loop. Use `stat -c %Y` with a `stat -f %m` fallback.
  Restrict the Makefile to `install -d` / `install -m`; `install -D` is
  GNU-only.
- **Windows**: skip the POSIX permission check and `chmod`; the console
  encoding fallback above; `--password` scrubbing is best-effort only.
- All completions fall back to `python` when `python3` is absent, as under Git
  Bash.

## SHELL COMPLETION

Four scripts in `completions/`, mirrored into `src/plexdo/data/` as package
data. All cover the same values, read a 15-minute cache under the platform
cache directory (honouring `cache_dir`), and refresh a stale cache in the
background so completion never blocks.

Numeric IDs are shown with their titles. Distinguish what is *insertable* from
what is merely *shown*: user and library titles are insertable because those
arguments accept them, but an item title is not, since `fetchItem` needs a
numeric ratingKey.

- **bash** - no `bash-completion` package: initialise from `COMP_WORDS` and
  `COMP_CWORD`, use `compgen -f` not `_filedir`. Values that can contain
  spaces must reach `COMPREPLY` as whole lines via the read-loop helper, not
  through `compgen -W`, which splits `TV Shows` into two candidates. bash
  cannot attach descriptions, but it only *inserts* once a single candidate
  remains, so `_plexdo_compreply_pairs` lists annotated forms while a choice
  remains and substitutes the bare value when it collapses to one.
  `_plexdo_complete_rating_key` merges keys from every `titles.*.json`, so it
  must gather then render once and clear `COMPREPLY` on entry.
- **zsh** - `#compdef plexdo`, `_arguments -C` with `'*::arg:->subcmd'`. Note
  that under `*::` zsh **rebinds `words` so `words[1]` is the subcommand**.
  Sanitise `:` out of descriptions, since `_describe` splits on it.
- **fish** - no positional-index primitive, so walk `(commandline -opc)`,
  skipping options that consume a value. Guard the background refresh on the
  binary existing: fish reports an unknown command *before* redirection
  applies, scribbling on the prompt mid-completion.
- **PowerShell** - `Register-ArgumentCompleter -Native`. Needs no external
  interpreter: `ConvertFrom-Json` reads the cache. Return `CompletionResult`
  objects so the ID is inserted and the title shows as a tooltip. Two traps
  that parse cleanly and fail at runtime: a range of `0..-1` **wraps** and
  yields the whole array, and a parenthesised `if` is not a valid argument
  expression.

## MAN PAGE

`man/plexdo.1`, in roff, mirrored into `src/plexdo/data/`. Documents every
command, the configuration and token formats, exit status, environment, files,
and worked examples, and passes `groff -man -Tutf8 -ww -z` with no warnings.

Escapes that silently corrupt copy-pasteable examples: a literal backslash is
`\e`, a literal apostrophe is `\(aq`, and a backtick is `\(ga`. groff remaps a
bare `'` to a typographic right quote on many configurations. Double quotes
are not remapped. Write URLs as plain text with `.I`, not with `.UR`/`.UE`,
which emit OSC-8 escapes that duplicate the URL wherever the page is piped
through something that does not understand them.

## TESTS

`tests/` holds a pytest suite that must pass in `make check`. It covers the
project's own decision logic and never touches a network; `conftest.py`
provides one `FakeItem`, one `FakeMedia`, and friends. Do not define a second
mock for a concept that already has one.

Worth testing, because a regression there is silent rather than loud: the four
serialisers round-tripping through real parsers; table alignment under
double-width characters, the ASCII fallback, and fitting to a budget;
identifier resolution including the ID-versus-title collision; the overwrite
guard performing **no** server calls when it refuses; watched-state selection
in both directions and that an undated state never wins; which playlist entries
`clean-playlist` drops, and that it numbers them by their place in the
playlist rather than within the removal list; that concatenation preserves the
order given and that `--unique` matches on ratingKey; path rewriting
picking the longest matching root; the token store reading a legacy bare-token
file; that `loaded_fields` and `file_paths` never trigger a reload; and that
global flags survive being given before the subcommand.

Two behaviours easy to get backwards: two fully played states need no sync, so
a "latest wins" test must use states that actually differ; and
`format_duration(None)` is empty while `format_duration(0)` is `"0:00"`,
because unknown and zero are different things.

## BUILD

`make check` runs, in order: `check-version`, `check-assets`, `smoke`, `test`,
`lint`, `build`, `dist-check`.

- `check-version` compares the three places the version appears.
- `check-assets` verifies the four completions and the man page match their
  packaged mirrors, and that no source file contains non-ASCII. Editing the
  source copy and forgetting the mirror ships a stale asset in the wheel.
- `smoke` imports the package, builds the full parser, and asserts every
  module in `MODULES` still exposes `register()` and `COMMANDS`. pylint scores
  a module 10.00/10 even when an edit has truncated that tail, which breaks
  every command in it.

The Makefile also provides `install`, `uninstall`, `develop`, `reinstall`,
`install-man`, `uninstall-man`, `install-completion` and its four per-shell
targets, `clean`, and `distclean`, all `.PHONY`, with `help` as the default
target printing the paths in effect. Completion destinations default to the
XDG user locations, switch to `$(PREFIX)/share/...` when `PREFIX` is set, and
honour `DESTDIR`. `SHELLS` defaults to `bash zsh fish`; powershell is opt-in.
`uninstall-completion` tests for each exact file rather than removing a
directory, and `uninstall` prefixes pip with `-` so an already-absent package
still cleans up.

CI runs `make check` on Python 3.11 through 3.14, plus jobs that parse all
four completions and lint the man page.

**Every workflow declares `permissions`.** Without one, its jobs receive
whatever the repository default grants, which CodeQL flags as
`actions/missing-workflow-permissions` once per job. `contents: read` at the
top of the file is enough for anything that only builds and tests; a job
needing more raises it for itself, as the publish jobs do with
`id-token: write`.

Keep actions on their newest major: GitHub retires the Node runtime beneath
them periodically, so an old major first warns and eventually stops running.
Check `runs.using` in the action's own `action.yml` rather than trusting a
version number, and confirm the inputs still exist before jumping several
majors at once.

`publish.yml` uploads to PyPI through Trusted Publishing (OIDC), so no API
token exists to leak. It builds and verifies in one job, then publishes from a
second that raises only `id-token: write` and names a `pypi` environment,
which is where a deployment protection rule can be attached. Publishing runs
on a published GitHub release; `workflow_dispatch` offers TestPyPI for a
rehearsal, with `skip-existing` so a repeated dry run does not fail.

The release job must confirm the tag matches the packaged version. PyPI
uploads are immutable, so publishing `v1.2.3` from a tree carrying some other
version cannot be undone. Strip a leading `v` before comparing.

## DELIVERABLES

1. The `plexdo` package under `src/`, laid out as above
2. `pyproject.toml`, `Makefile`, `MANIFEST.in`, `requirements.txt`,
   `.gitignore`, `.gitattributes`
3. `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`
4. `man/plexdo.1`
5. `completions/` and its mirror in `src/plexdo/data/`
6. `tests/`
7. `.github/workflows/ci.yml`
8. `AI.prompt.md` - this file, containing the full prompt that regenerates the
   project including this requirement itself

Verification: `make check` passes, `vulture src/plexdo --min-confidence 0` is
empty, and installing the wheel into a clean virtualenv gives a working
`plexdo` console script.
