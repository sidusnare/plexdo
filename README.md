<!--
SPDX-FileCopyrightText: 2026 SidusNare
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
-->

# plexdo

A command-line interface for Plex Media Server built on
[plexapi](https://github.com/pkkid/python-plexapi). It builds and copies
playlists, exports libraries to M3U or a static HTML photo gallery,
synchronises watched state between users, streams media to stdout, and manages
library scans.

## Install

```bash
pip install plexdo
```

From a source checkout:

```bash
git clone https://github.com/sidusnare/plexdo.git
cd plexdo
```

`make install` installs the package, the shell completions, and the man page
together:

```bash
make install                     # completion -> ~/.local/share/bash-completion/completions
make install PREFIX=/usr/local   # completion -> /usr/local/share/bash-completion/completions
make uninstall                   # removes both again
```

For development:

```bash
make develop                     # editable install with the dev extras
make check                       # lint, build, and validate the distribution
make help                        # all targets, and the completion path in use
```

Both `plexdo` and `plexdo` are installed as console scripts; they are the
same program.

## Getting started

```bash
plexdo write-config-example        # writes ~/.config/plexdo/config.yaml
plexdo login                       # prompts, saves a token in the keyring
plexdo libraries-list
```

`write-config-example --help` prints the exact template it would write. It
refuses to replace a config file that already exists unless given
`-o/--overwrite`, and `--dry-run` only says where it would write.

Coming from plexdo 1.x? Nothing to do: the first run of any command moves
`~/.local/etc/plexdo.ini` to `config.yaml`, and its passwords, PINs, and the
tokens from its token file into the keyring. The old file is renamed
`plexdo.ini.migrated` with the secrets taken out, and the token file is
deleted, so no secret is left in plaintext.

### Configuration

The files live where the platform expects them, following the XDG Base
Directory Specification on Linux, BSD, and macOS:

| | configuration | completion cache | secrets, without a keyring |
| --- | --- | --- | --- |
| Linux, BSD, macOS | `$XDG_CONFIG_HOME/plexdo/config.yaml` | `$XDG_CACHE_HOME/plexdo` | `$XDG_STATE_HOME/plexdo/secrets.json` |
| Windows | `%LOCALAPPDATA%\PlexDo\config.yaml` | `%LOCALAPPDATA%\PlexDo\Cache` | `%LOCALAPPDATA%\PlexDo\secrets.json` |

The XDG variables default to `~/.config`, `~/.cache`, and `~/.local/state`.
The configuration is YAML and holds no secret. `write-config-example` writes
every option with an explanation of what it means, the values it takes, and its
default:

```yaml
---
plex:
  url: "http://localhost:32400"      # the server; required
  # username: "you@example.com"      # the account `plexdo login` signs in as
  # cache_dir: "~/.cache/plexdo"     # the completion cache
  # secret_store: "auto"             # auto, keyring, or file
  # secrets_file: "~/.local/state/plexdo/secrets.json"
```

Values may contain environment variables as `$VAR` or `${VAR}`, and `~` for
your home directory. A name that is not set is left as literal text and warned
about, rather than failing later as a puzzling "no such file". An option plexdo
does not know is warned about by name, so a typo does not go unnoticed.

### Secrets

Tokens, passwords, and Plex Home PINs are kept in the system keyring: the
Secret Service (GNOME Keyring, KWallet) on Linux and BSD, the Keychain on macOS,
and Credential Manager on Windows. Each kind is one keyring entry under the
service `plexdo`. A token survives a reboot, so `plexdo login` is needed once.

Where there is no keyring, as on a headless server, secrets go in the
`secrets.json` above, created readable by your account alone, with a warning
that it is not encrypted. Set `secret_store: file` to use that file always -
on a machine whose keyring is locked when plexdo runs, as under cron - and to
silence the warning; `secret_store: keyring` refuses to fall back.

With `secret_store: file`, the secrets file holds saved passwords and PINs
only. Tokens are sessions and are kept apart from them, in
`$XDG_RUNTIME_DIR/plexdo/session.json`, or in a private directory of your own
under the temporary directory where there is no runtime directory. `plexdo
login` says on stderr where the session went. A session there does not
survive a reboot: run `plexdo login` again, which asks for nothing when the
password was saved. Tokens an earlier version left in the secrets file are
moved to the session file once.

A password is saved only if you ask: `plexdo login --save-password` keeps it
so plexdo can sign in again by itself once the token stops working. A
password or PIN in the configuration file is ignored, with a warning.

`plexdo write-secrets-example` writes an example of the secrets file as it is
under `secret_store: file`, with a placeholder password and PIN, to the path
`secrets_file` names in the configuration, readable by your account alone;
an existing file is replaced only with `-o/--overwrite`. When `secrets_file`
is not set, nothing is written: stderr says so, and the example is printed
to stdout instead.

### Multiple users

A Plex server refuses an admin-issued token for a user it has shared nothing
with, so acting on that user needs their own login. Add an entry for them under
`users`, keyed by their user ID (from `plexdo users-list`), and sign them in
once:

```yaml
users:
  99:
    username: "bob@example.com"
```

```bash
plexdo login --username bob@example.com --save-password
```

When a command hits a 401 for a user, three sources are tried in order:

1. the server-scoped token the admin can mint for them
2. a token already saved for them
3. a fresh login as their `users` entry, with the password `--save-password`
   kept

A token obtained by step 3 is saved, so the login happens once rather than on
every run.

`plexdo logout` signs every saved token out of plex.tv, so it stops working
wherever a copy of it might be, and removes it, with any password saved for the
account; `plexdo logout -u bob@example.com` does just that one, and is an error
if there is no such session. A token plex.tv already refuses is removed too.
One that could not be signed out, because plex.tv was unreachable, is kept so a
second run can finish, and the exit status is 1.

## Commands

Most commands are named for what they act on, then what they do to it:
`playlist-list`, `playlist-export`, `library-list`. `plexdo --help` lists
them in these groups, sorted by name within each:

| Group | Commands |
| --- | --- |
| Libraries and titles | `album-list`, `find-missing`, `libraries-list`, `library-list`, `metadata`, `search`, `show-list`, `titles-export` |
| Playlists | `playlist-build`, `playlist-clean`, `playlist-copy`, `playlist-export`, `playlist-list`, `playlist-remove`, `playlists-list` |
| Playback and watched state | `player-remote-play`, `read`, `show-watched-cp`, `wait` |
| Server | `rescan`, `status`, `users-list` |
| Account and configuration | `login`, `logout`, `set-pin`, `write-config-example`, `write-secrets-example` |

Every command accepts `-f/--format`, `-v/--verbose`, `--debug`,
`--debug-log PATH`, `--dry-run`, and `-V/--version`, and they may be given
either before or after the command name - `plexdo --json users-list` and
`plexdo users-list --json` are equivalent. Logging always goes to stderr, or
the debug log, so machine-readable output on stdout is safe to pipe.

### Debug log

`--debug-log PATH` appends the `--debug` output to a file instead of stderr,
and profiles the run. Every line starts with a Unix timestamp in nanoseconds,
and beside the debug logging the file records:

- each phase of the run - connecting, resolving arguments, the command - with
  its run time, CPU and memory, and the HTTP calls it made;
- every HTTP request, from plexdo or plexapi: method, URL, headers, status,
  sizes, and how long it waited;
- CPU and memory use every five seconds;
- at the end, totals for the run and cProfile's tables of function run times.

```bash
plexdo playlists-list 0 --debug-log ~/plexdo-debug.log
grep ' plexdo.http: recv ' ~/plexdo-debug.log    # every response and its wait
```

Tokens, passwords, PINs, cookies, and credential headers are redacted, on
stderr too, and bodies are never written. The file is created readable by
you alone; it still names your server, users, and titles, so treat it as
private.

### Output formats

```bash
plexdo libraries-list                  # aligned table (default)
plexdo libraries-list --json           # shorthand for -f json
plexdo -f yaml libraries-list
plexdo library-list 3 -f csv > titles.csv
plexdo users-list -f clixml            # PowerShell Import-Clixml
```

| format | notes |
| --- | --- |
| `table` | Default. Box-drawn and width-aligned, ASCII fallback on legacy consoles. |
| `json` | Non-ASCII escaped, so it prints on any console. |
| `yaml` | Strings are always quoted, so a title like `NO` or `1.10` stays a string rather than being reinterpreted as a boolean or a float. |
| `csv` | Header row plus one row per record, `\n` line endings. |
| `clixml` | PowerShell CLIXML with typed properties; pipe into `Import-Clixml`. |

`-V/--version` prints the installed version, which also appears in `--help`.

### Table width

Table output is fitted to your terminal: the widest column is truncated with
an ellipsis so a row stays on one line, and `--verbose` reports which columns
were narrowed.

```bash
plexdo library-list "TV Shows"           # fitted to the terminal
plexdo -W library-list "TV Shows"        # every character, however wide
plexdo library-list "TV Shows" > out.txt # redirected output is never truncated
```

Redirected output keeps every character, so piping to a file or to `grep` is
unaffected.

### Throttling

Some operations query once per item: walking every season of a show library,
applying watched state item by item, or reading each photo album. Past 50
items those are paced at `--throttle` seconds apart, 0.25 by default, so a
large run does not flood the server or trip its rate limiting. Smaller runs
are never paced.

```bash
plexdo --throttle 0 find-missing      # as fast as the server will answer
plexdo --throttle 1 find-missing      # gentler on a Raspberry Pi
```

When pacing kicks in it says so, with the expected duration:

```text
Pacing 500 requests 0.25s apart to go easy on the server; about 2m04s,
or --throttle 0 to disable.
```

Anywhere a **library** is required you may pass either the numeric library ID
or its title, so `plexdo library-list 3` and `plexdo library-list "TV Shows"`
are equivalent. The same applies to `--library-id` on `search` and `-l` on
`show-watched-cp`.

Anywhere a user is required you may pass either the numeric user ID or the
user's title, so `plexdo playlists-list 7` and `plexdo playlists-list Alice`
are equivalent. `0` always means the admin account. Titles match exactly first,
then case-insensitively. If a value is simultaneously one user's ID and another
user's title the ID wins, with a warning naming the user that was skipped; if
two users share a title the command aborts and asks for the numeric ID. The
identical rules apply to library IDs and titles.

### Listing and searching

| Command | Purpose |
| --- | --- |
| `libraries-list` | Library IDs, types, and titles |
| `library-list <library> [-t TYPE] [--filter F=V] [--category C]` | What a library holds, by type, filter, or folder |
| `album-list <rating_key>` | One album's tracks, photos, or clips, and how far through each you are |
| `find-missing <show> [-l L] [-A] [-s N,N]` | Seasons with gaps in their episode numbering |
| `show-list <rating_key> [--m3u P]` | Every episode of a show, specials skipped |
| `users-list` | User IDs, account types, titles, usernames, and emails |
| `playlists-list <user_id>` | A user's playlists |
| `playlist-list <user_id> <playlist\|ratingKey> [--m3u P]` | Items in one playlist |
| `metadata <rating_key> [-u FILE]` | Full metadata for one item, including its file paths; `-u` edits it from a JSON file |
| `search <user_id> <query> [--media-type T] [--library-id N]` | Search as a given user |

`library-list` lists one type of item. By default a movie library lists its
movies, a show library its shows, and a music or photo library its albums;
`-t/--type` names another, among those Plex serves for that kind of library
through `/library/sections/ID/all?type=`:

| Library | Types (default first) |
| --- | --- |
| movie | `movie`, `collection` |
| show | `show`, `season`, `episode`, `collection` |
| music | `album`, `artist`, `track`, `collection` |
| photo | `album`, `photo`, `clip` |

```bash
plexdo library-list "TV Shows"                 # the shows
plexdo library-list "TV Shows" -t episode      # every episode, with its show
plexdo library-list Music -t track             # every track
```

Any library can also be listed by folder, as its files are laid out on disk.
`-t folder` lists the folders at the top; `--path` opens one, as folder titles
separated by `/`, one request per level:

```bash
plexdo library-list Movies -t folder
plexdo library-list Movies --path "Films/Heat (1995)"
```

`--filter FIELD=VALUE` narrows a listing on any field the library can be
filtered by, as Plex's own filters can: `genre`, `collection`, `label`,
`contentRating`, `year`, `decade`, `studio`, and the rest. `!=` excludes, and
`>` and `<` compare a number or a date; quote those, or the shell reads them
as a redirection. Repeat it and every one must match.
`--category NAME` is short for `--filter genre=NAME`, and `--list-categories`
lists the genres there are:

```bash
plexdo library-list Movies --list-categories              # the genres
plexdo library-list Movies --category Crime --filter 'year>1990'
plexdo library-list "TV Shows" -t episode --filter 'genre!=Reality'
plexdo library-list Movies --filter 'addedAt>-30d'        # the last month
```

A field the library does not have is an error that lists those it does.

A table is kept compact, with columns to suit the type. A machine-readable
format carries **every field the server returned** for each item, and for a
show library nests each show's episodes under a `seasons` object:

```bash
plexdo library-list "TV Shows" -f json | jq '.[0].seasons | keys'
```

Nested objects such as media and their parts are expanded rather than printed
as object references, so a file name is at `media[].parts[].file`, and the
paths are repeated in a top-level `files` list:

```bash
plexdo library-list Movies -f json | jq -r '.[].files[]'
```

Note that `sourceURI` is **not** a file name. It is the remote server URI of an
item in someone else's playlist, and is null for anything on your own server.

Those fields are the ones present in the library listing; `metadata` is
the route to the full picture for a single item.

### Albums

`library-list` lists the albums of a music or photo library by default,
nested photo albums included. The table shows how many items each album
holds and how many have been played. A machine-readable format adds each
album's played state (`played`, `in progress`, or `unplayed`) and its
contents, every
track, photo, or clip with its own state, view count, and last-played time.
Anything part way through also carries `progress`, a percentage: for an
item, how far its resume point is into it; for an album, how much of its
running time has been played. Photos have no played state, so theirs is
null.

```bash
plexdo library-list Music                   # one row per album
plexdo library-list Music --json |          # albums part way through
    jq -r '.[] | select(.state == "in progress") |
        "\(.progress)% \(.title)"'
```

Played state is the connected account's own. The music table costs one
request; the other formats, and any photo library, open each album, one
request apiece, paced like the other per-item walks.

`album-list` shows a single album by its rating key: the album with its
state and progress, then one row per item. An item in progress shows its
resume point, length, and percentage:

```text
| # | ratingKey | track | title              | length | state       | progress            |
| 1 | 4128      | 1     | So What            | 9:22   | played      |                     |
| 2 | 4129      | 2     | Freddie Freeloader | 9:46   | in progress | 3:20 / 9:46 (34.1%) |
| 3 | 4130      | 3     | Blue in Green      | 5:37   | unplayed    |                     |
```

JSON and YAML carry the same record `library-list` gives for each album; CSV
and CLIXML, which cannot nest, carry one row per item.

### Finding gaps

```bash
plexdo find-missing "Breaking Bad"          # one show, by title
plexdo find-missing 1234                    # or by ratingKey
plexdo find-missing "The Wire" -s 1,3       # only these seasons
plexdo find-missing "The Wire" -l "TV Shows"
plexdo find-missing -A                      # every show, every library
plexdo find-missing -A -l "TV Shows"        # every show in one library
```

Reports the episode numbers missing between the start of a season and its
highest episode. A season that simply stops early is not reported, since an
unaired episode cannot be told from a missing one. Season 0 is skipped by
default because specials are numbered irregularly, though naming it with
`-s 0` includes it.

```text
┌──────────────┬───────────┬────────┬─────────┬──────────────┬──────┬─────────┐
│ show         │ ratingKey │ season │ missing │ missingCount │ have │ highest │
├──────────────┼───────────┼────────┼─────────┼──────────────┼──────┼─────────┤
│ Breaking Bad │ 1         │ 1      │ 5       │ 1            │ 6    │ 7       │
│ The Wire     │ 2         │ 1      │ 1, 2    │ 2            │ 3    │ 5       │
└──────────────┴───────────┴────────┴─────────┴──────────────┴──────┴─────────┘
```

### Building playlists

```bash
plexdo playlist-build -I "Mixed Run" 101 202       # round-robin across shows
plexdo playlist-build -C "By Air Date" 101 202     # date-sorted, shows and movies
plexdo playlist-build -R 0 "Source" "Shuffled"     # secrets-backed shuffle
plexdo playlist-build -A 0 "Mix" 55 56 57          # add items to a playlist
plexdo playlist-build -M 0 Mixed Shows Films --ratio 2:1  # two shows per film
```

`playlist-build` takes exactly one flag saying how to build, and with it what
the arguments are:

| Flag | Arguments | Builds |
| --- | --- | --- |
| `-I/--interleaved` | `NAME ratingKey...` | One episode of each show in turn |
| `-C/--chronological` | `NAME ratingKey...` | Shows and movies by original air date |
| `-R/--randomize` | `USER SOURCE DEST` | A shuffle of an existing playlist |
| `-A/--append` | `USER PLAYLIST ratingKey...` | Nothing new: adds items to an existing playlist |
| `-M/--merge` | `USER NAME FIRST SECOND` | Two existing playlists mixed at a ratio |

Playlists are always built fully in memory, validated, previewed, and then
created in exactly one API call. `--dry-run` stops after the preview.

Every command that takes an existing playlist accepts its **name or its
ratingKey** interchangeably. Every command that creates one takes
`-o/--overwrite`: without it a name collision is refused outright, leaving both
the existing playlist and the new one untouched; with it the existing playlist
is removed and replaced.

`-C` estimates missing air dates from the median interval between
neighbouring episodes in the same season, and prompts only when that is
impossible. A film with no release date is prompted for too. Without a
terminal to answer on, it stops and names the item that needs a date.

`-A` changes a playlist where it is, so it takes none of `-o`, `-u`, `-a`,
`--m3u`, and `-p`. Every ratingKey is looked up first, and nothing is added
unless all of them are found. Note the case: `-A` is `--append`, and `-a` is
`--all-users`.

`-M` mixes two playlists, taking items from each in turn at
`--ratio A:B`: A from the first, then B from the second. The default, 1:1,
alternates them. Each keeps its own order, and once one runs out the rest of
the other follows, so nothing is left out; `--verbose` says how many items
that is. `-s/--stop-short` stops there instead, so the whole result keeps the
ratio. `-U/--unique` skips an item already taken, and the next item of the
same playlist takes its place. `--ratio`, `-s`, and `-U` go only with `-M`.
It reads both playlists before writing, so either may also be the
destination:

```bash
plexdo playlist-build -M 0 Mix Mix "New Finds" --ratio 3:1 -o  # one new in four
plexdo playlist-build -M 0 Weekend Shows Films --ratio 2:1 -s -U  # ends with a film
```

#### Who the playlist is built for

Every `playlist-build` mode but `-A` takes `-u/--user` and
`-a/--all-users`. Without either, the playlist lands on the account the
items came from.

```bash
plexdo playlist-build -I "Mixed Run" 101 202 -u 7    # just for user 7
plexdo playlist-build -I "Mixed Run" 101 202 -u Bob  # a title works too
plexdo playlist-build -I "Mixed Run" 101 202 -a      # for everyone
```

With either flag the item list is printed once, and then one line per user as
that user completes, so a long run shows progress:

```text
Mixed Run (42 items)
┌───────┬───────────┬───────────────────────────┐
│ index │ ratingKey │ title                     │
└───────┴───────────┴───────────────────────────┘

  created  admin  (Mixed Run)
  created  Alice  (Mixed Run)
  skipped  Bob  ('Mixed Run' already exists (ratingKey 4120); --overwrite would replace it)
  skipped  Cara  (access denied (401) - no libraries are shared with 'Cara')
  failed   Dan  (500 Internal Server Error)
```

Nothing that goes wrong for one user ends the run. A name already taken is a
`skipped`, a user the server will not act for is a `skipped`, and anything
else is a `failed`; the remaining users are served either way. `-o/--overwrite`
turns the name collisions into `replaced`, and `--dry-run` reports what each
user would get without writing anything. In a machine-readable format the
outcomes come back as one record per user instead of the item list.

`-a` includes the admin account, since it is a user of the server too. `-u`
and `-a` are mutually exclusive.

### Copying and modifying

```bash
plexdo playlist-copy -T 0 "Mix" 7 "Mix" -o      # to one user
plexdo playlist-copy -A 0 "Mix"                 # to all; skips the source user
plexdo playlist-clean 0 "Mix"                   # drop what has been watched
plexdo playlist-remove 0 "Mix"
```

`playlist-clean` removes the watched entries and leaves the rest in their
existing order. It previews what it will drop, numbered by each entry's place
in the playlist as it stands, so the list lines up with what Plex shows rather
than renumbering around the gaps:

```text
┌───────┬───────────┬─────────────────────────────┬─────────┐
│ index │ ratingKey │ title                       │ state   │
├───────┼───────────┼─────────────────────────────┼─────────┤
│ 1     │ 55        │ The Wire - The Target       │ played  │
│ 4     │ 58        │ The Wire - Old Cases        │ played  │
└───────┴───────────┴─────────────────────────────┴─────────┘
```

A part-played item is kept, since it is the one you are in the middle of,
and so is one you have played before and are part way through again;
`--include-partial` drops those too, reported as `partial`. Watched state is
per-user, so the USER argument decides whose viewing history is consulted.
A smart playlist is refused - its contents come from a filter, not from its
entries - and `--dry-run` stops after the preview.

A user with no libraries shared to them cannot be acted on, even by the server
admin - Plex scopes each token to what that user can see. Commands targeting
one such user stop with an explanation; `playlist-copy --all` skips them
with a one-line warning and carries on.

`playlist-copy` takes exactly one of `-A/--all`, copying to every user the
server is shared with under the playlist's own title, and `-T/--to`, which
takes two more arguments: the user to copy to, and the title for the copy.
`-A` prints the item list once and then one line per user, since the list is
identical for everyone:

```text
Movie Night (3 items)
┌───────┬───────────┬───────────────────┐
│ index │ ratingKey │ title             │
└───────┴───────────┴───────────────────┘

  skipped  Fred  (source user)
  created  Alice  (Movie Night)
  created  Bob  (Movie Night admin copy)
  skipped  Cara  (both 'Movie Night' and 'Movie Night admin copy' already exist)
  skipped  Dan  (access denied (401) - no libraries are shared with 'Dan')
```

Lines appear as each user completes, so a long run shows progress. In a
machine-readable format the outcomes come back as one record per user.

Without `-o/--overwrite`, a copy that collides with both `Mix` and
`Mix admin copy` is skipped rather than overwriting anything.

### Watched-state sync

```bash
plexdo show-watched-cp 7 9 --dry-run     # always preview a full-library sync first
plexdo show-watched-cp 7 9 -1            # one-way: only user 9 is modified
plexdo show-watched-cp 7 9 -l 3          # a single library
plexdo show-watched-cp 7 9 --unwatch     # propagate unwatched instead
```

By default the most recent `lastViewedAt` wins. With `--unwatch`, an item
unwatched for either user is unwatched for both, and where both have progress
the earliest `lastViewedAt` wins.

Whether an item has been played and its resume point are both copied, as
they stand, so an item one user is watching again arrives played and part
way through. How many times it has been played is not copied.

`-t KEY` narrows the sync to one ratingKey. A movie, episode, or track is
compared by itself; a show or season stands for every episode in it, and an
artist or album for every track, each compared on its own:

```bash
plexdo show-watched-cp 7 9 -t 4102       # every episode of one show
```

### Exporting

```bash
plexdo playlist-export 0 "Mix" ~/mix.m3u
plexdo titles-export 3 ~/movies.m3u --sort date
plexdo titles-export 5 ~/photos.html --album "Iceland 2019"
```

M3U files contain **Plex server filesystem paths**, not HTTP URLs, so they are
meant to be read on or from the server's filesystem. Photo libraries export a
single self-contained HTML gallery instead.

Where the media is reached by a different route - an SMB share, another mount
point, a Windows drive letter - `-p/--prefix` swaps the server's library root
for one that makes sense there:

```bash
plexdo titles-export 3 ~/tv.m3u --prefix '\\NAS\media'
plexdo playlist-export 0 "Mix" ~/mix.m3u -p /Volumes/plex
plexdo titles-export 5 ~/photos.html -p smb://nas/pix
```

```text
/mnt/media/TV/Breaking Bad/S01E01.mkv   ->   \\NAS\media\Breaking Bad\S01E01.mkv
```

Separators follow the prefix, so a Windows prefix produces backslashes. Note
that the *library root* is what gets replaced, so one prefix maps every
library onto the same place; export each library separately if they are
mounted apart. A file below no known library root is appended whole, with one
warning. `--prefix` applies to `--m3u` on `playlist-build`, `playlist-list`,
and `show-list` too, and
to the photo gallery. Without it, exports keep the server's own paths.

### Streaming

```bash
plexdo read 12345 | mpv -
plexdo read 12345 > episode.mkv
```

On Linux with a display attached but no desktop environment, mpv can draw
straight to the console through the kernel modesetting driver, so playback
needs neither X nor Wayland:

```bash
plexdo read 12345 | mpv --vo=drm -
```

Run that from a virtual terminal rather than a terminal emulator, and make sure
your user can reach the DRM device (usually via the `video` group).

### Status

```bash
plexdo status                      # everything, as a set of tables
plexdo status --section sessions   # just one section
plexdo status -f json              # nested object, all sections
plexdo status --section tasks -f csv
```

Reports server identity (name, version, machine ID, platform, platform
version, last updated), active sessions with the sessionKey, library,
ratingKey, and the file each player has open, shared users, system accounts,
reachable addresses, library scans in progress, other background activity, and
scheduled maintenance tasks.

A section that cannot be read - reachable addresses need a plex.tv round trip,
for instance - is reported as a warning and left empty rather than losing the
whole report. `--format csv` and `--format clixml` are flat by nature and need
`--section`, since the eight sections have different shapes.

### Waiting for a play to end

```bash
plexdo wait && sudo systemctl restart plexmediaserver   # after the credits start
plexdo wait --no-credits                 # through the credits to the very end
plexdo wait --offset -120                # two minutes before the credits
plexdo wait --offset 60                  # a minute after the wait is over
plexdo wait -s 42                        # a particular session
plexdo wait -r 12345                     # until that video, once started, is over
plexdo wait -r 12345 --now               # ...or not at all, if it is not playing
plexdo wait --paused 600                 # a 10-minute pause counts as done
plexdo wait --all && sudo reboot         # everyone, including what starts meanwhile
```

`wait` sleeps until a session's current play is over and then exits 0, so
whatever follows `&&` runs once the viewer is done. By default it follows the
first session listed and waits for whatever that session is playing.

The play is over when playback reaches the start of the end credits, if Plex
has a credits marker for the video, or its end otherwise; `--no-credits`
ignores the marker. Where a film has two credits markers around a mid-credits
scene, the final one is used so the scene is not cut off. The wait also ends
the moment the video stops playing - the viewer quit, or autoplay moved on to
the next episode - wherever playback had got to.

It polls every 10 seconds (`-i`), then every second (`--fast-interval`) from
30 seconds before the end point on, so the end is caught within about a
second. Each delay varies by up to 20% either way. Every poll prints a line:

```text
Waiting for "The Wire - The Target" (Alice) to reach the credits at 55:40.
Alice | playing: The Wire - The Target | waiting for: The Wire - The Target | 55:00 / 58:12 | waited 0:00 | ~0:40 left
Alice | playing: The Wire - The Target | waiting for: The Wire - The Target | 55:15 / 58:12 | waited 0:10 | ~0:25 left
Alice | playing: The Wire - The Target | waiting for: The Wire - The Target | 55:30 / 58:12 paused | waited 0:11 | ~0:10 left
Alice | playing: The Wire - The Target | waiting for: The Wire - The Target | 55:41 / 58:12 reached | waited 0:12 | done
"The Wire - The Target" reached its end point.
```

With `-r`, a video that is not playing yet is waited for until it starts, and
each line says what the user is watching instead; `--now` exits 0 at once
rather than waiting. Without `-s`, `-r` follows whichever session plays the
video. `status --section sessions` lists the sessionKey `-s` takes.

In a machine-readable format every poll is one record - a line of JSON, a
YAML document, or a CSV row under a single header - flushed as it is written,
so a pipe sees each one immediately. CLIXML cannot be streamed and is refused;
from PowerShell, read the JSON a line at a time with `ConvertFrom-Json`.

`--paused SECONDS` counts a play as over once its player has sat paused that
long - someone fell asleep, or walked away. Plex does not say when a pause
began, so the count starts at the first poll that sees it; resuming starts it
again, and `0` ends the play at the first sight of a pause. While paused, the
estimate is the time the pause has left.

`--all` waits for every play by every user, each judged by the same rules:
its own credits or end, `--offset`, `--no-credits`, and `--paused`. Each poll
prints a line per session, and a session that disappears is reported once as
`stopped`. It ends only when two polls an interval apart both find nothing
left, so a play started in the meantime - an autoplayed next episode, or
someone new - is one more to wait for. Nothing playing at all still takes that
second look before exiting. `--all` takes neither `-s` nor `-r`.

A poll that fails is retried; five failures in a row end the wait with an
error. Interrupting it exits 130, so a command chained with `&&` does not run.

### Playing on a player

```bash
plexdo player-remote-play 10.20.0.40 881            # a film on the TV at that address
plexdo player-remote-play livingroom-tv.lan 881     # resolved here; the TV sees an IP
plexdo player-remote-play livingroom-tv.lan 881 --dry-run --json | jq '{account, fetchFrom}'
```

`player-remote-play` connects straight to a Plex player and tells it to start
playing an item at once, as casting from a Plex app on the same network does.
The player must allow remote control (*Advertise as player* in most Plex apps),
but the server need not know of it.

The player is addressed by IP only. Some players refuse a request whose Host
header carries a name, as a defence against DNS rebinding, so a host name is
resolved by plexdo and only the address goes on the wire; each address the
name has is tried until a player answers.

Each Plex app listens on its own port: 32500 for Android and Fire TV, 8324 for
Roku, 32433 for Plex HTPC, and others besides. Unless `--port` gives it, plexdo
asks the player over GDM, Plex's discovery protocol, and a player that does not
answer (GDM is IPv4 only, and firewalls may drop it) is tried on those common
ports in turn.

A player takes commands from an account it trusts, normally the one signed in
to it. The command is sent as plexdo's own account when that is the server's
admin or is signed in to the player; otherwise as the account from a `users`
entry that the player is signed in to; otherwise as plexdo's own account
anyway, with a warning.

The item is fetched as the account sending the command too, because the player
plays with the play queue and token of whoever fetched it and switches its own
user to match. When the server refuses an account's own token, as it does a
managed user's, the token the server issues for that user is used instead; when
it will have neither, `--player-user` is an error, and otherwise a warning says
the player will switch to plexdo's account.

`--player-user` names that account instead, by plex.tv user id, username, or
email, overriding all of the above, the admin shortcut included:

```bash
plexdo player-remote-play livingroom-tv.lan 881 --player-user bob@example.com
```

It must be plexdo's own account (`0` means it when plexdo is the admin, as
everywhere else), a member of plexdo's Plex Home, or have a `users` entry
signed in once with `plexdo login --username`; anything else is an error
rather than a quiet fallback to another account.

A Home member, including a managed user, which `users-list` shows as `home` or
`managed`, needs no password: plexdo switches into it through plex.tv, as a
Plex app's user switcher does. A managed user has no username or email, so name
it by id or by the name `users-list` shows:

```bash
plexdo player-remote-play livingroom-tv.lan 881 --player-user Clare
```

A member with a PIN needs it saved in the keyring, once, by its id:

```bash
plexdo set-pin 826699965
```

For anyone else, a `users` entry whose id or `username` is the value is used
directly; otherwise the entries are signed in one at a time and compared by
id, username, and email.

The player then fetches the item from the server, and the address it is given
has to work from the player's network, not plexdo's. Every address the server
has is a candidate - the configured `plex: url`, and each direct address
plex.tv lists - and the one most like the player's own address wins:

1. the same family, IPv4 for an IPv4 player and IPv6 for an IPv6 one;
2. the same scope, private (RFC 1918, ULA, carrier-grade NAT) or global;
3. the longest shared prefix, which picks the server's interface nearest
   the player on a routed network.

So a player on another routed private network gets the server's private
address nearest it, and a player at another IPv6 site, behind router ACLs
permitting direct connections, gets the server's global IPv6 address rather
than a ULA that would not be routed. Loopback, link-local, and relayed
addresses never qualify, and plex.tv addresses are sent by their `plex.direct`
names so https certificates check out. `--server-url` gives the address
outright when the networks are joined some way the ranking cannot see, such as
NAT. plexdo does not test the chosen address: from another segment, a test
would only say what plexdo can reach, not what the player can.

### Server management

```bash
plexdo rescan --status      # active scan jobs and progress
plexdo rescan 3             # scan one library for new files
plexdo rescan 3 --now       # cancel pending scans first
plexdo rescan --all         # scan every library
```

`rescan` with neither a library nor `--all` is an error that says to use
`--all`, so a library left off by mistake does not set the whole server
scanning.

## Shell completion

Completion is provided for **bash, zsh, fish, and PowerShell**. All four cover
user and library IDs *and* their titles, rating keys, playlist names and keys,
and photo album names, reading a 15-minute cache that the list commands
populate as a side effect. The cache is in `cache_dir` from the
configuration, or else `$XDG_CACHE_HOME/plexdo`, by default
`~/.cache/plexdo`. Numeric IDs are shown with the
title they belong to - `7  (Alice)`, `101  (Breaking Bad - Pilot)` - and only
the ID is inserted once you narrow to one. When a cache is stale it refreshes
in the background, so completion never blocks.

Playlists and photo album names are cached under every spelling of their
user or library - the ID, the title, and the word as you typed it - so
`plexdo playlist-list Alice <TAB>` completes as `plexdo playlist-list 7
<TAB>` does.

`make install` sets all three up for you. To manage them separately:

```bash
make install-completion                    # bash, zsh, and fish
make install-completion SHELLS="zsh fish"  # only the ones you want
make install-completion PREFIX=/usr/local  # system-wide instead of per-user
make uninstall-completion
```

| shell | default destination |
| --- | --- |
| bash | `~/.local/share/bash-completion/completions/plexdo` |
| zsh | `~/.local/share/zsh/site-functions/_plexdo` |
| fish | `~/.config/fish/completions/plexdo.fish` |
| PowerShell | `~/.local/share/powershell/Completions/plexdo.ps1` |

For zsh the directory must be in your `$fpath` before `compinit` runs:

```zsh
fpath=(~/.local/share/zsh/site-functions $fpath)
autoload -Uz compinit && compinit
```

Installing from PyPI rather than a checkout, the script ships as package data:

```bash
source "$(python3 -c 'import plexdo,pathlib;print(pathlib.Path(plexdo.__file__).parent/"data/plexdo.bash")')"
```

PowerShell has no drop-in completion directory, so dot-source the file from
your profile:

```powershell
New-Item -Type File -Force $PROFILE      # if you have no profile yet
Add-Content $PROFILE ". $HOME/.local/share/powershell/Completions/plexdo.ps1"
```

It needs no Python: PowerShell reads the cache with `ConvertFrom-Json`, and
completions carry the matching title as a tooltip.

The bash script needs no `bash-completion` package - only bash 4+ and
`python3`. The zsh and fish scripts likewise depend only on `python3`.

## Layout

```text
src/plexdo/
├── cli.py            argument parsing and dispatch
├── commands/         one module per command group, each exposing
│                     register(), COMMANDS, and REQUIRES_PLEX
├── config.py         the YAML configuration
├── secret_store.py   the system keyring, or a private file
├── tokens.py         saved tokens, passwords, and PINs
├── migrate.py        the one-time move from 1.x
├── console.py        JSON and box-drawn table output
├── accounts.py       per-user servers and account classification
├── playlists.py      playlist resolution and copy naming rules
├── airdates.py       air-date estimation
├── gallery.py        photo gallery generation
└── ...
```

Adding a command means adding a module under `commands/`, listing it in
`commands/__init__.py`, and naming the command in one of the `GROUPS` there,
which is where `--help` gets its grouping; `cli.py` needs no change.

## Development

```bash
pip install -e ".[dev]"
npm ci                     # markdownlint-cli2
make check                 # tests, every linter, the build
make derive                # after changing the version in pyproject.toml
```

The version is defined only in `pyproject.toml`; `make derive` writes it into
the man page and `sbom.spdx.json`, an SPDX 3.0 software bill of materials.

## Manual

A full man page ships with the project and is installed by `make install`:

```bash
man plexdo
man -l man/plexdo.1     # straight from a source checkout
```

It documents every command, the configuration file, where secrets are kept,
exit status, and the environment variables consulted.

Each command also has a detailed page of its own, covering every option, how
options conflict with or depend on one another, what each global option means
for that command, its output, and worked examples. They are written in
[scdoc](https://git.sr.ht/~sircmpwn/scdoc) source format under `man/`:
`plexdo-COMMAND.1.scd` for each command, and `plexdo-conventions.7.scd` for
what they share - naming users and libraries, output formats, path
rewriting, pacing, and exit status. With scdoc installed:

```bash
scdoc < man/plexdo-wait.1.scd | man -l -
for f in man/*.scd; do scdoc < "$f" > "${f%.scd}"; done   # build them all
```

The same pages are published to the [project wiki](https://github.com/sidusnare/plexdo/wiki),
one wiki page per command, kept in step with `main` by
`.github/workflows/wiki.yml`. `make wiki` builds them locally into
`build/wiki/`, and needs [pandoc](https://pandoc.org/) as well as scdoc.

## Platform support

Linux, macOS, and Windows are all supported.

| | notes |
| --- | --- |
| **Linux** | Reference platform. |
| **Python** | 3.11 through 3.14. |
| **macOS** | Completion scripts fall back to BSD `stat -f %m`, and the bash script avoids `mapfile` so it works with the bash 3.2 that macOS still ships. `make` uses only portable `install -d` / `install -m`. |
| **Windows** | Tables fall back to ASCII box characters when the console encoding cannot represent Unicode ones (a legacy cp1252 console would otherwise abort with `UnicodeEncodeError`), and characters a title contains but the console cannot render are substituted rather than crashing. POSIX permission checks and `chmod` are skipped, since Windows uses ACLs and `os.stat` reports a synthetic mode that would trip the check on every run. |

On Windows, `--password` scrubbing is best-effort: the `Py_GetArgcArgv` trick
that hides the value from `ps` has no Windows equivalent, so the value stays
visible in the process list; a warning says so. Use the interactive prompt
instead. Secrets go in Credential Manager, which Windows protects for your
account.

The bash, zsh, and fish completions all fall back to `python` where `python3`
is absent, which matters under Git Bash.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: `make develop`, then
`make check` before opening a pull request.

Security issues: see [SECURITY.md](SECURITY.md).

## Releasing

Tagging a `vX.Y.Z` release publishes to PyPI through Trusted Publishing; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Links

- Homepage and source: <https://github.com/sidusnare/plexdo>
- Issue tracker: <https://github.com/sidusnare/plexdo/issues>
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## License

GNU General Public License v3.0 or later - see [LICENSE](LICENSE).

This program is free software: you may redistribute and/or modify it under the
terms of the GPL as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version. It is distributed in the
hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
[LICENSE](LICENSE) file for details.

Note that this is a copyleft licence: derivative works and redistributions,
including modified versions, must also be released under the GPL-3.0-or-later.
