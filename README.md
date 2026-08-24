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
plexdo write-config-example        # writes ~/.local/etc/plexdo.ini (mode 0600)
plexdo login                       # prompts, saves a token to token_path
plexdo list-libraries
```

`write-config-example --help` prints the exact template it would write.

### Configuration

The configuration file lives where the platform expects it:

| | configuration | completion cache | default `token_path` |
| --- | --- | --- | --- |
| Linux, macOS | `~/.local/etc/plexdo.ini` | `~/.cache/plexdo` | `$XDG_RUNTIME_DIR/.plex.token` |
| Windows | `%LOCALAPPDATA%\PlexDo\plexdo.ini` | `%LOCALAPPDATA%\PlexDo\Cache` | `%TEMP%\plexdo.token` |

`cache_dir` in the `[plex]` section moves the completion cache anywhere you
like; the platform default is written into the template as a comment, and the
shell completions read the same setting.

`plexdo write-config-example` writes to the right one for you, and its
`--help` prints the exact template, with the notes that apply to your
platform.

```ini
[plex]
url = http://localhost:32400

# Values may contain environment variables as $VAR or ${VAR}, and ~ for your
# home directory. XDG_RUNTIME_DIR is a private, user-only tmpfs on most Linux
# systems, which suits a secret -- but it is cleared at logout, so you will
# need to run `plexdo login` again after each reboot. Point token_path
# somewhere persistent if you would rather not.
token_path = $XDG_RUNTIME_DIR/.plex.token

# Optional credentials used by `plexdo login`.
# The password is stored in plaintext, so keep this file mode 0600.
# Supplying --username on the command line ignores the password below.
# username = you@example.com
# password = your-plex-password
```

### Multiple users

A Plex server refuses an admin-issued token for a user it has shared nothing
with, so acting on that user needs their own credentials. Add a section named
for their user ID (from `plexdo list-users`):

```ini
[99]
username = bob@example.com
password = bobs-plex-password
```

When a command hits a 401 for a user, three sources are tried in order:

1. the server-scoped token the admin can mint for them
2. a token already saved in the token file
3. a fresh login with the credentials in their `[<user_id>]` section

A token obtained by step 3 is written back to the token file, so the login
happens once rather than on every run.

### The token file

`token_path` holds a JSON object of username to token:

```json
{
  "@admin": "xxxxxxxxxxxxxxxxxxxx",
  "bob@example.com": "yyyyyyyyyyyyyyyyyyyy"
}
```

`@admin` is the reserved key used when no `[plex] username` is set; `@` cannot
appear in a Plex username, so it never collides with a real one. The file is
written atomically with mode 0600. A file from an earlier version holding a
single bare token is read as the admin token and converted to JSON on the next
write - no manual migration needed.

Environment variables are expanded in every value. A name that is not set is
left as literal text and warned about, rather than failing later as a puzzling
"no such file". `%` needs no escaping - interpolation is disabled, so a
password may contain one freely.

Both the config file and the token file are checked at startup and a warning is
printed if either is readable by group or other.

## Commands

Every command accepts `-f/--format`, `-v/--verbose`, `--debug`, `--dry-run`,
and `-V/--version`, and they may be given either before or after the command
name - `plexdo --json list-users` and `plexdo list-users --json` are
equivalent. Logging always goes to stderr, so machine-readable output on stdout
is safe to pipe.

### Output formats

```bash
plexdo list-libraries                  # aligned table (default)
plexdo list-libraries --json           # shorthand for -f json
plexdo -f yaml list-libraries
plexdo list-titles 3 -f csv > titles.csv
plexdo list-users -f clixml            # PowerShell Import-Clixml
```

| format | notes |
| --- | --- |
| `table` | Default. Box-drawn and width-aligned, ASCII fallback on legacy consoles. |
| `json` | Non-ASCII escaped, so it prints on any console. |
| `yaml` | Strings are always quoted, so a title like `NO` or `1.10` stays a string rather than being reinterpreted as a boolean or a float. |
| `csv` | Header row plus one row per record, `\n` line endings. |
| `clixml` | PowerShell CLIXML with typed properties; pipe into `Import-Clixml`. |

`-V/--version` prints the installed version, which also appears in `--help`.

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

```
Pacing 500 requests 0.25s apart to go easy on the server; about 2m04s,
or --throttle 0 to disable.
```
Anywhere a **library** is required you may pass either the numeric library ID
or its title, so `plexdo list-titles 3` and `plexdo list-titles "TV Shows"`
are equivalent. The same applies to `--library-id` on `search` and `-l` on
`copy-watched`.

Anywhere a user is required you may pass either the numeric user ID or the
user's title, so `plexdo list-playlists 7` and `plexdo list-playlists Alice`
are equivalent. `0` always means the admin account. Titles match exactly first,
then case-insensitively. If a value is simultaneously one user's ID and another
user's title the ID wins, with a warning naming the user that was skipped; if
two users share a title the command aborts and asks for the numeric ID. The
identical rules apply to library IDs and titles.

### Listing and searching

| Command | Purpose |
| --- | --- |
| `list-libraries` | Library IDs, types, and titles |
| `list-titles <library> [--album A]` | Titles in a library (alias: `list-library`) |
| `find-missing [library] [--include-specials]` | Seasons with gaps in their episode numbering |
| `list-show <rating_key> [--m3u P]` | Every episode of a show, specials skipped |
| `list-users` | User IDs, account types, and titles |
| `list-playlists <user_id>` | A user's playlists |
| `list-playlist <user_id> <playlist\|ratingKey> [--m3u P]` | Items in one playlist |
| `show-metadata <rating_key>` | Full metadata for one item |
| `search <user_id> <query> [--media-type T] [--library-id N]` | Search as a given user |

`list-titles` shows the rating key, title, release date, rating, and studio as
a table. A machine-readable format carries **every field the server returned**
for each item, and for a show library nests each show's episodes under a
`seasons` object:

```bash
plexdo list-titles "TV Shows" -f json | jq '.[0].seasons | keys'
```

Those fields are the ones present in the library listing; `show-metadata` is
the route to the full picture for a single item.

### Finding gaps

```bash
plexdo find-missing                 # every show library
plexdo find-missing "TV Shows"      # one library
plexdo find-missing --include-specials
```

Reports the episode numbers missing between the start of a season and its
highest episode. A season that simply stops early is not reported, since an
unaired episode cannot be told from a missing one. Season 0 is skipped by
default, because specials are numbered irregularly.

```
┌──────────────┬───────────┬────────┬─────────┬──────────────┬──────┬─────────┐
│ show         │ ratingKey │ season │ missing │ missingCount │ have │ highest │
├──────────────┼───────────┼────────┼─────────┼──────────────┼──────┼─────────┤
│ Breaking Bad │ 1         │ 1      │ 5       │ 1            │ 6    │ 7       │
│ The Wire     │ 2         │ 1      │ 1, 2    │ 2            │ 3    │ 5       │
└──────────────┴───────────┴────────┴─────────┴──────────────┴──────┴─────────┘
```

### Building playlists

```bash
plexdo build-interleaved "Mixed Run" 101 202       # round-robin across shows
plexdo build-chronological "By Air Date" 101 202   # date-sorted, shows and movies
plexdo build-randomize 0 "Source" "Shuffled"       # secrets-backed shuffle
```

Playlists are always built fully in memory, validated, previewed, and then
created in exactly one API call. `--dry-run` stops after the preview.

Every command that takes an existing playlist accepts its **name or its
ratingKey** interchangeably. Every command that creates one takes
`-o/--overwrite`: without it a name collision is refused outright, leaving both
the existing playlist and the new one untouched; with it the existing playlist
is removed and replaced.

`build-chronological` estimates missing air dates from the median interval
between neighbouring episodes in the same season, and prompts only when that is
impossible.

### Copying and modifying

```bash
plexdo copy-playlist-to-user 0 "Mix" 7 "Mix" -o
plexdo copy-playlist-all-users 0 "Mix"          # skips the source user
plexdo append-playlist 0 "Mix" 55 56 57
plexdo remove-playlist 0 "Mix"
```

A user with no libraries shared to them cannot be acted on, even by the server
admin - Plex scopes each token to what that user can see. Commands targeting
one such user stop with an explanation; `copy-playlist-all-users` skips them
with a one-line warning and carries on.

`copy-playlist-all-users` prints the item list once and then one line per
user, since the list is identical for everyone:

```
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
plexdo copy-watched 7 9 --dry-run     # always preview a full-library sync first
plexdo copy-watched 7 9 -1            # one-way: only user 9 is modified
plexdo copy-watched 7 9 -l 3          # a single library
plexdo copy-watched 7 9 --unwatch     # propagate unwatched instead
```

By default the most recent `lastViewedAt` wins. With `--unwatch`, an item
unwatched for either user is unwatched for both, and where both have progress
the earliest `lastViewedAt` wins.

### Exporting

```bash
plexdo export-playlist 0 "Mix" ~/mix.m3u
plexdo export-titles 3 ~/movies.m3u --sort date
plexdo export-titles 5 ~/photos.html --album "Iceland 2019"
```

M3U files contain **Plex server filesystem paths**, not HTTP URLs, so they are
meant to be read on or from the server's filesystem. Photo libraries export a
single self-contained HTML gallery instead.

Where the media is reached by a different route - an SMB share, another mount
point, a Windows drive letter - `-p/--prefix` swaps the server's library root
for one that makes sense there:

```bash
plexdo export-titles 3 ~/tv.m3u --prefix '\\NAS\media'
plexdo export-playlist 0 "Mix" ~/mix.m3u -p /Volumes/plex
plexdo export-titles 5 ~/photos.html -p smb://nas/pix
```

```
/mnt/media/TV/Breaking Bad/S01E01.mkv   ->   \\NAS\media\Breaking Bad\S01E01.mkv
```

Separators follow the prefix, so a Windows prefix produces backslashes. Note
that the *library root* is what gets replaced, so one prefix maps every
library onto the same place; export each library separately if they are
mounted apart. A file below no known library root is appended whole, with one
warning. `--prefix` applies to `--m3u` on the build and list commands too, and
to the photo gallery. Without it, exports keep the server's own paths.

### Streaming

```bash
plexdo read 3 12345 | mpv -
plexdo read 3 12345 > episode.mkv
```

On Linux with a display attached but no desktop environment, mpv can draw
straight to the console through the kernel modesetting driver, so playback
needs neither X nor Wayland:

```bash
plexdo read 3 12345 | mpv --vo=drm -
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
version, last updated), active sessions, shared users, system accounts,
reachable addresses, library scans in progress, other background activity, and
scheduled maintenance tasks.

A section that cannot be read - reachable addresses need a plex.tv round trip,
for instance - is reported as a warning and left empty rather than losing the
whole report. `--format csv` and `--format clixml` are flat by nature and need
`--section`, since the eight sections have different shapes.

### Server management

```bash
plexdo rescan --status      # active scan jobs and progress
plexdo rescan 3             # scan one library for new files
plexdo rescan 3 --now       # cancel pending scans first
```

## Shell completion

Completion is provided for **bash, zsh, fish, and PowerShell**. All three cover user and library IDs
*and* their titles, rating keys, playlist names and keys, and photo album
names, reading a 15-minute cache under `~/.cache/plexdo` that the list
commands populate as a side effect. Numeric IDs are shown with the title they
belong to - `7  (Alice)`, `101  (Breaking Bad - Pilot)` - and only the ID is
inserted once you narrow to one. When a cache is stale it refreshes in the
background, so completion never blocks.

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

```
src/plexdo/
├── cli.py            argument parsing and dispatch
├── commands/         one module per command group, each exposing
│                     register(), COMMANDS, and REQUIRES_PLEX
├── config.py         config, token, and permission checks
├── console.py        JSON and box-drawn table output
├── accounts.py       per-user servers and account classification
├── playlists.py      playlist resolution and copy naming rules
├── airdates.py       air-date estimation
├── gallery.py        photo gallery generation
└── ...
```

Adding a command means adding a module under `commands/` and listing it in
`commands/__init__.py`; `cli.py` needs no change.

## Development

```bash
pip install -e ".[dev]"
pylint src/plexdo          # expected: 10.00/10
python -m build            # sdist + wheel
```

## Manual

A full man page ships with the project and is installed by `make install`:

```bash
man plexdo
man -l man/plexdo.1     # straight from a source checkout
```

It documents every command, the configuration and token file formats, exit
status, and the environment variables consulted.

## Platform support

Linux, macOS, and Windows are all supported.

| | notes |
| --- | --- |
| **Linux** | Reference platform. |
| **Python** | 3.11 through 3.14. |
| **macOS** | Completion scripts fall back to BSD `stat -f %m`, and the bash script avoids `mapfile` so it works with the bash 3.2 that macOS still ships. `make` uses only portable `install -d` / `install -m`. |
| **Windows** | Tables fall back to ASCII box characters when the console encoding cannot represent Unicode ones (a legacy cp1252 console would otherwise abort with `UnicodeEncodeError`), and characters a title contains but the console cannot render are substituted rather than crashing. POSIX permission checks and `chmod` are skipped, since Windows uses ACLs and `os.stat` reports a synthetic mode that would trip the check on every run. |

Two caveats specific to Windows. `%TEMP%` is per-user but is not protected by
file permissions and Windows may clear it, so protecting the token file is your
responsibility there: `chmod` cannot restrict it, so place it somewhere your
user account alone can read. And `--password` scrubbing is best-effort - the
`Py_GetArgcArgv` trick that hides the value from `ps` has no Windows
equivalent, so the value stays visible in the process list; a warning says so.
Use the config file or the interactive prompt instead.

The bash, zsh, and fish completions all fall back to `python` where `python3`
is absent, which matters under Git Bash.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: `make develop`, then
`make check` before opening a pull request.

Security issues: see [SECURITY.md](SECURITY.md).

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
