<!--
SPDX-FileCopyrightText: 2026 SidusNare
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
-->

# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.1.0] - 2026-11-12

`metadata` can now edit an item, from the JSON it prints. Everything in
4.1.0-rc.1 is here, unchanged.

### Added

- `metadata -u FILE` (`--update`) edits an item's metadata from a JSON file
  shaped like `metadata --json`, or from standard input with `-`. Keys left
  out, and keys matching the server, are left alone. A changed value for a
  field that cannot be edited stops the command with nothing changed and
  every offending key named. Changes go in one request and are locked
  against agent refreshes, and `--dry-run` lists them instead.

### Fixed

- `metadata` no longer gives a show, season, or album an empty `files`
  list in JSON and the other structured formats; like the table, it leaves
  the files out when the item has none of its own.

### Security

- The Markdown linter used in development is markdownlint-cli2 0.24.1,
  whose markdownlint 0.42.1 brings re2js 2.9.1 and with it the fix for
  GHSA-gg6h-894w-4m9c, without forcing any version. The low-severity KaTeX
  advisory remains, as before; plexdo does not ship KaTeX.
- Values CodeQL mistook for secrets because of their names are renamed:
  the secrets file example is `STORE_FILE_EXAMPLE`, and what
  `secret_store.load` builds is `entries`. Nothing sensitive was printed:
  the example holds placeholders, and `logout` prints account names, not
  tokens.

## [4.0.0] - 2026-11-11

These changes are incompatible with 3.x, hence the MAJOR release:
`albums-list` and `merge-build` are folded into `library-list` and
`playlist-build`, two commands are renamed, and `library-list` lists a
music or photo library's albums by default.

### Changed

- **Breaking:** `library-list` on a music or photo library lists its
  albums by default, where it listed a music library's artists and a photo
  library's photos. `-t artist` and `-t photo` list those.
- `library-list -t TYPE` (`--type`) lists any type Plex serves for the
  library's kind: `movie` and `collection` in a movie library; `show`,
  `season`, `episode`, and `collection` in a show library; `album`,
  `artist`, `track`, and `collection` in a music library; `album`,
  `photo`, and `clip` in a photo library. A movie library lists its movies
  by default and a show library its shows, as before. Table columns suit
  the type: an episode shows its show and numbers, a track its artist and
  album.
- `library-list -t folder` lists a library by folder, as its files are
  laid out on disk, and `--path A/B` opens a folder within it.
- `library-list --filter FIELD=VALUE` lists only what matches, on any field
  the library can be filtered by, such as `genre`, `collection`, `label`,
  `contentRating`, or `year`; `!=` excludes, and `>` and `<` compare.
  Repeated, every one must match. `--category NAME` is short for
  `--filter genre=NAME`, and `--list-categories` lists the genres there
  are.
- `library-list --album` implies `-t photo`, and its completion offers the
  album titles whole; one with " - " in its title was cut short.
- **Breaking:** `missing-find` is renamed `find-missing`, and
  `show-metadata` is renamed `metadata`. The old names are not kept.
- **Breaking:** `merge-build` is folded into `playlist-build` as
  `-M/--merge`: `merge-build USER NAME FIRST SECOND` is now
  `playlist-build -M USER NAME FIRST SECOND`, with `--ratio`, `-s`, and `-U`
  as before. Those three are refused with any other mode.

### Removed

- **Breaking:** `albums-list`. `library-list` lists a music or photo
  library's albums by default, with the same table and the same records.
- **Breaking:** `merge-build`, now `playlist-build --merge`.

## [3.0.0] - 2026-11-10

These changes are incompatible with 2.x, hence the MAJOR release: commands
are renamed, some are merged or removed, and `read` takes a ratingKey alone.
The old command names are not kept as aliases. 3.0.0 takes the place of
2.1.0, which stopped at its release candidate: everything in 2.1.0-rc.1 is
here, under the new command names.

### Added

- `write-secrets-example [-o]` writes an example secrets file, with a
  placeholder entry for each kind of secret, to the path `plex:
  secrets_file` names, readable by your account alone. When `secrets_file`
  is not set, nothing is written: stderr says so, and the example is printed
  to stdout. An existing file is replaced only with `-o/--overwrite`.
- `albums-list LIBRARY` lists the albums of a music or photo library, nested
  photo albums included, with how many items each holds and how many have
  been played. A machine-readable format adds each album's played state and
  progress, and its contents: every track, photo, or clip with its own
  played state, view count, last-played time, and, when part way through,
  its resume point and progress.
- `album-list RATINGKEY` shows one album: the album with its played state
  and progress, then each track, photo, or clip, with its own state and,
  when part way through, its resume point, length, and percentage.

### Changed

- **Breaking:** commands are now named for what they act on, then what they
  do to it. The old names are gone, not kept as aliases, so scripts and
  shell history need updating:

  | Before | Now |
  | --- | --- |
  | `list-libraries` | `libraries-list` |
  | `list-titles`, `list-library` | `library-list` |
  | `list-show` | `show-list` |
  | `export-titles` | `titles-export` |
  | `find-missing` | `missing-find` |
  | `list-users` | `users-list` |
  | `list-playlists` | `playlists-list` |
  | `list-playlist` | `playlist-list` |
  | `export-playlist` | `playlist-export` |
  | `remove-playlist` | `playlist-remove` |
  | `clean-playlist` | `playlist-clean` |
  | `build-interleaved` | `playlist-build --interleaved` (`-I`) |
  | `build-chronological` | `playlist-build --chronological` (`-C`) |
  | `build-randomize` | `playlist-build --randomize` (`-R`) |
  | `append-playlist` | `playlist-build --append` (`-A`) |
  | `build-merge` | `merge-build` |
  | `copy-playlist-all-users` | `playlist-copy --all` (`-A`) |
  | `copy-playlist-to-user` | `playlist-copy --to` (`-T`) |
  | `copy-watched` | `show-watched-cp` |

  `search`, `show-metadata`, `read`, `rescan`, `status`, `wait`,
  `player-remote-play`, `login`, `logout`, `set-pin`, and
  `write-config-example` keep their names.
- `playlist-build` and `playlist-copy` take the arguments the commands they
  replace took, after a flag saying which of them is meant; exactly one such
  flag is required. `playlist-build --append` changes a playlist where it
  is, so it refuses `-o`, `-u`, `-a`, `--m3u`, and `-p`.
- `plexdo --help` lists the commands in five groups, sorted by name within
  each, in place of one flat list in no particular order. Each command's
  `--help` lists the global options in a group of their own, sorted and
  last, and its usage line names the command's own arguments followed by
  `[global options]` instead of spelling all nine out. Summaries and
  argument names are consistent across commands.
- With `plex: secret_store` set to `file`, session tokens are kept apart
  from saved passwords and PINs. The secrets file holds passwords and PINs
  only; tokens go in `$XDG_RUNTIME_DIR/plexdo/session.json`, or in a
  private directory of your own under the temporary directory where there
  is no runtime directory, and `login` says on stderr where that is. Such
  a session does not survive a reboot: run `plexdo login` again then,
  which asks for nothing when the password was saved. Tokens already in
  the secrets file are moved across once, so upgrading signs nobody out.
  `auto` and `keyring` are unchanged.
- `write-secrets-example` writes the secrets file in that form, with a
  placeholder password and PIN and no token.
- `show-watched-cp` copies whether an item has been played and its resume
  point, both as they stand, so an item one user is watching again arrives
  played and part way through. The number of plays is not copied. The
  `action` field joins its steps with `+`, as in `markPlayed+setProgress`,
  and has a new value, `clearProgress`.
- `show-watched-cp -t KEY` given a show or season synchronises every
  episode in it, and given an artist or album every track, each on its
  own. A ratingKey with no watched state, such as a photo, is an error.
- `playlist-clean` keeps an item that was played before and is part way
  through again, as it keeps any item with a resume point;
  `--include-partial` removes it.
- `search --media-type` searches only the libraries that can hold that
  type, and naming a library that cannot is an error. A library that could
  not be searched is reported only when the search found nothing at all.
- `library-list` and `titles-export` on a photo library include the photos
  of albums nested inside other albums, and `--album` matches an album
  wherever it is nested and takes the albums inside it. Nesting is
  followed 16 albums deep, in `albums-list` too.
- Shell completion caches playlists and photo album names under every
  spelling of their user or library, as `playlists-by-word.WORD.json` and
  `titles-by-word.WORD.json`, beside the caches named for the numeric ID.
- `login` in a machine-readable format adds `passwordStore`.
- **Breaking:** `read` takes a ratingKey alone, as `read RATINGKEY`. The
  library it used to require first only had to match the item, and is
  gone.
- `rescan --all` (`-a`) scans every library. `rescan` naming neither a
  library nor `--all` now says to use `--all`, and is a usage error, exit
  2 where it was 1.
- `users-list` shows each user's `username` and `email` as well, the same
  records as `status --section users`.
- `rescan --dry-run` and `playlist-remove --dry-run` say on stderr what
  they would do; they said nothing without `--verbose`.
  `playlist-remove` names the playlist by its title, however it was given.
- `missing-find` given a ratingKey fetches the show outright, without
  first listing every show in every library.
- `titles-export` paces its walk of a show library, as every other
  per-item loop is paced.

### Removed

- **Breaking:** `build-concatenated`. `merge-build` mixes two playlists into
  one, and `playlist-build --append` adds items to one.
- **Breaking:** `list-titles`, whose alias `list-library` became
  `library-list`, the one name for it now.

### Fixed

- zsh completion offers `-p`/`--prefix` again: its option had been written
  in a form zsh does not expand, so it was never offered.
- A request that fails, because the server cannot be reached, does not
  answer in time, refuses the saved token, or refuses the request, ends
  with a message saying which and what to do, not a traceback.
- `show-watched-cp --unwatch` clears a resume point on an item one user was
  only part way through. It listed the change and made none, on every run.
- `playlist-build --append` refuses a smart playlist with a message; it
  ended in a traceback.
- `write-secrets-example` no longer writes a placeholder token. With
  `secret_store: file`, one left beside a real token made every command
  report that there was no admin token.
- `rescan --status` with nothing running prints an empty list in a
  machine-readable format; it printed a sentence in every format.
- `playlist-build` given too few arguments says what each mode takes; it
  said only that `ARG` was required.
- A playlist whose title reads as a number to Python but is not a
  ratingKey, such as `1_000` or `+7`, is found by its title. Only ASCII
  digits are taken as a ratingKey.
- Shell completion finds its cache again: all four scripts read
  `cache_dir` from the 1.x configuration file and assumed `~/.cache`, so a
  configured `cache_dir` or `XDG_CACHE_HOME` left completion with nothing
  to offer.
- Playlists, and photo album names, complete after a user or library given
  by title; they completed only after a numeric ID.

## [2.1.0-rc.1] - 2026-10-29

The first release candidate for 2.1.0. On PyPI this version is
`2.1.0rc1`, the PEP 440 spelling of the same pre-release.

### Added

- `build-merge USER NAME FIRST SECOND [--ratio A:B]` mixes two playlists
  into a new one, taking A items from the first, then B from the second, in
  turn; the default is 1:1. Once one runs out, the rest of the other
  follows, or with `-s/--stop-short` is left out. `-U/--unique` lists an
  item in both playlists once. It takes the same `-o`, `--m3u`, `-p`, `-u`,
  and `-a` as the other build commands.
- `build-concatenated` takes `-U` as short for `--unique`.
- `--debug-log PATH`, on every command, appends the debug output to a file
  instead of stderr, each line starting with a Unix timestamp in
  nanoseconds, with the run profiled: the run time of each phase and, from
  cProfile, of each function; every HTTP request with its headers, status,
  sizes, and wait; and CPU and memory use every five seconds. Secrets are
  redacted in it. The file is created with mode 0600.

### Security

- Log output on stderr is redacted too: a token in a URL that a library
  logs at `--debug`, such as urllib3's request line, or quotes in an error,
  is replaced by `***`, as is any saved token or password wherever it
  appears.

## [2.0.3] - 2026-10-28

### Security

- The Markdown linter used in development is markdownlint-cli2 0.24.0, whose
  own dependencies include the fixed markdown-it, js-yaml, and smol-toml, in
  place of 2.0.1's forcing those versions under an older release. One
  low-severity KaTeX advisory remains in that tree with no fixed release in
  reach; markdownlint never calls KaTeX, and plexdo does not ship it.

### Fixed

- Publishing a release installs the linters `make check` runs before running
  it. Without them, no release since 2.0.0-rc.1 could be published to PyPI.

## [2.0.2] - 2026-10-28

### Changed

- Values that are not secrets, such as the secrets file's path, a count of
  removed passwords, and the `--save-password` flag, are no longer named as
  if they were, so code scanning (CodeQL's clear-text logging check) no
  longer reports their logging as a leak. Nothing a user sees changes; no
  secret was ever logged.

## [2.0.1] - 2026-10-28

### Security

- The Markdown linter used in development, markdownlint-cli2, is held to
  fixed versions of four of its dependencies, which had denial-of-service
  and prototype-pollution vulnerabilities: markdown-it 14.3.3, js-yaml
  4.3.2, smol-toml 1.9.0, and KaTeX 0.18.2. plexdo itself never used them,
  and installing plexdo does not install them.

## [2.0.0] - 2026-10-28

These changes are incompatible with 1.x, hence the MAJOR release; the first
run of any command moves a 1.x setup across by itself, as **Changed**
describes. Nothing has changed since 2.0.0-rc.1.

### Changed

- **Breaking:** the configuration is a YAML file,
  `$XDG_CONFIG_HOME/plexdo/config.yaml` (by default
  `~/.config/plexdo/config.yaml`; `%LOCALAPPDATA%\PlexDo\config.yaml` on
  Windows), replacing `~/.local/etc/plexdo.ini`. `[plex]` becomes `plex:`,
  and a `[<user id>]` section becomes an entry under `users:`. Every option
  is explained in the file `write-config-example` writes. A mistyped
  option is now reported by name instead of being silently ignored.
- **Breaking:** tokens, passwords, and Plex Home PINs are kept in the system
  keyring: the Secret Service on Linux and BSD, the Keychain on macOS, and
  Credential Manager on Windows. Where there is no keyring, as on a headless
  machine, they go in `$XDG_STATE_HOME/plexdo/secrets.json`, readable by your
  account alone, with a warning that it is not encrypted. Tokens now survive
  a reboot, so `plexdo login` is no longer needed after each one.
- **Breaking:** the first run finding a 1.x INI file and no YAML file moves
  everything across: the options into `config.yaml`, and every token,
  password, and PIN into the keyring. The INI file is then renamed
  `plexdo.ini.migrated`, with its secrets removed, and the token file is
  deleted, so no secret is left in plaintext.
- **Breaking:** `login` no longer reads a password from the configuration.
  It prompts, or uses one saved by an earlier `login --save-password`. Its
  JSON output has `user`, `store`, `verified`, and `passwordSaved` in place
  of `token_path` and `verified`.
- **Breaking:** a per-user entry needs only a `username`. Sign it in once
  with `plexdo login --username <name>`; its token is then used as before.
- **Breaking:** `player-remote-play --player-user` takes a Plex Home
  member's PIN from `set-pin` rather than from a `pin` in the configuration.
- `logout` also removes the saved passwords of the accounts it signs out,
  since a saved password would otherwise sign the account straight back
  in.
- The completion cache honours `XDG_CACHE_HOME`.

### Added

- `set-pin USER_ID [--remove]` saves a Plex Home member's PIN in the
  keyring, prompting for it, or removes it.
- `login --save-password` saves the password in the keyring alongside the
  token, so plexdo can sign in again by itself once the token stops
  working.
- `plex: secret_store` chooses where secrets are kept: `auto`, the default,
  `keyring`, or `file`, for a machine whose keyring is locked when plexdo
  runs, as under cron. `plex: secrets_file` moves that file.
- `sbom.spdx.json`, a software bill of materials in SPDX 3.0.

### Removed

- **Breaking:** the `token_path` option, and passwords and PINs in the
  configuration file. One found there is ignored with a warning.

### Fixed

- `LICENSE` is the exact text of the GNU GPL version 3 as gnu.org publishes
  it.
- Bash completion offers a file name containing a space as one name, not
  one per word.
- Bash completion of `login --` offers login's own options, not only the
  global ones.

## [2.0.0-rc.1] - 2026-10-28

The release candidate for 2.0.0, with the changes listed there. On PyPI
this version is `2.0.0rc1`, the PEP 440 spelling of the same pre-release.

## [1.1.29] - 2026-10-22

### Fixed

- The `player-remote-play` tests for Plex Home members no longer read the
  `plexdo.ini` of whoever runs them, so they pass where there is none, as
  on CI, and a PIN in a real config cannot change their outcome.

## [1.1.28] - 2026-10-15

### Added

- `logout [-u USERNAME]` signs the saved tokens out of plex.tv, invalidating
  them, and removes them from the token file: every one by default, or the
  one saved under `-u`, which is an error when the file has no such name. A
  token plex.tv already refuses is removed too; one that could not be signed
  out is kept for another try, and the exit status is 1. A token file left
  empty is deleted.
- `player-remote-play HOST ratingKey` connects directly to a Plex player and
  tells it to start playing an item. A host name is resolved by plexdo and
  only the IP address is sent, since some players refuse a Host header
  carrying a name as a defence against DNS rebinding; each address is tried
  until a player answers. Each Plex app listens on its own port, so unless
  `--port` gives it the player is asked over GDM (UDP 32412), and one that
  does not answer is tried on the common apps' ports: 32500 (Android, Fire
  TV), 8324 (Roku), 32433 (Plex HTPC), 3005 (Plex Home Theater), skipping
  any that take no TCP connection within two seconds. The command is sent as
  plexdo's own account when it is the server's admin or is signed in to the
  player, otherwise as an account from a `[<user_id>]` section that is
  signed in to the player, and otherwise as plexdo's own anyway, with a
  warning. `--player-user` names the account instead, by plex.tv user id,
  username, or email, or a managed user's name. It may be plexdo's own
  account; a member of plexdo's Plex Home, managed users included, which
  plexdo switches into without a password (a PIN-protected member takes
  `pin` from its `[<user_id>]` section); or an account with a
  `[<user_id>]` section. Anything else is an error.
- The player is told to fetch from whichever of the server's addresses is
  most like its own - the configured URL and every direct address plex.tv
  lists, ranked by family, then private or global scope, then the longest
  shared prefix - so a player on another routed private network, or at
  another IPv6 site behind router ACLs, gets an address it can reach.
  Loopback, link-local, and relayed addresses never qualify, and plex.tv
  addresses go by their `plex.direct` names so https certificates check out.
  `--server-url` gives the address outright, and the output shows the one
  chosen.

### Fixed

- plexapi's informational messages, such as `Failed to parse "" to
  datetime`, no longer reach stderr without `-v`: plexapi sets its own
  logger to INFO, and the stderr handler now filters by the level asked
  for.

## [1.1.27] - 2026-10-05

### Added

- A detailed manual page for every command, in scdoc source format under
  `man/`: `plexdo-COMMAND.1.scd` for each command, covering every option,
  which options conflict with or depend on one another, what each global
  option does for that command, its output, its exit status, and worked
  examples; and `plexdo-conventions.7.scd` for what the commands share. The
  sources ship in the sdist.
- `write-config-example -o/--overwrite`. Without it, an existing config file
  is now refused rather than replaced.
- The command pages are published to the project wiki, one page each, by
  `.github/workflows/wiki.yml` whenever one changes on `main`, and built on
  pull requests to catch a page that does not compile. `make wiki` builds
  them locally, with scdoc and pandoc. Pages written on the wiki by hand are
  left alone.

### Fixed

- `build-chronological` crashed on any film without a release date: the date
  prompt read episode-only attributes. It now asks for a film's date just as
  it does an episode's, names an episode with no number as `S01E??` rather
  than crashing on it too, and stops with an explanation instead of a
  traceback when there is no terminal to answer on.
- The config template lost its "Per-user credentials" heading, so that
  paragraph began mid-sentence: the line had no opening quote and was read as
  a Python comment.
- `write-config-example` replaced an existing config file without asking, and
  ignored `--dry-run`, writing the file anyway. It now refuses an existing
  file without `--overwrite`, and a dry run writes nothing.
- `find-missing` printed `No gaps found.` as plain text in every format,
  breaking `--json` and the other machine-readable formats; they now get an
  empty list.
- `copy-playlist-to-user` wrote two documents to a machine-readable stream,
  the item list and then the outcome; it now writes the outcome alone.
- An unknown numeric playlist, or an unknown ratingKey given to `list-show`,
  `build-interleaved`, or `build-chronological`, ended in a Python traceback
  rather than a message.
- The manual page gave exit status 1 for an argument that cannot be parsed,
  which exits 2, and said `rescan -s` lists scan jobs when it lists all of the
  server's background activity.

## [1.1.26] - 2026-10-05

### Added

- `wait` sleeps until a session's current play is over, then exits 0, so
  `plexdo wait && ...` runs once the viewer is done. It follows the first
  session listed by default, or `-s/--session`, and waits for what that
  session is playing, or `-r/--rating-key`. The play is over at the start of
  the end credits when Plex has a credits marker - the final one, after any
  mid-credits scene - and at the end otherwise; `--no-credits` ignores the
  marker. It is also over the moment the video stops playing. A negative
  `--offset` ends the wait that many seconds early; a positive one sleeps that
  long afterwards. Polls come every 10 seconds (`-i/--interval`), then every
  second (`--fast-interval`) from 30 seconds before the end point, each
  varied by up to 20%, and every poll reports the user, what is playing, the
  video waited for, the position, the time waited, and the time left. A video
  not yet playing is waited for until it starts, or with `--now` not at all.
  `--paused SECONDS` counts a play as over once it has sat paused that long.
  `-a/--all` waits for every play by every user, and ends only when two polls
  an interval apart find nothing left, so a play started meanwhile - autoplay
  included - is waited for too.
  Machine-readable formats stream one record per poll; CLIXML, which cannot
  be streamed, is refused. Failed polls are retried, and an interrupt exits
  130.
- The `status` sessions table carries each session's `sessionKey`, which
  `wait --session` takes.

## [1.1.25] - 2026-09-24

### Added

- All four build commands (`build-interleaved`, `build-chronological`,
  `build-randomize`, `build-concatenated`) take `-u/--user` to create the
  playlist for one named user and `-a/--all-users` to create it for every user
  on the server, the admin account included. Without either the playlist lands
  where it always has, on the account the items came from. With either, the
  item list is printed once and each user then reports a single line as it
  completes: `created`, `replaced`, `skipped`, or `failed`. Nothing that goes
  wrong for one user ends the run - a name already taken and a user the server
  will not act for are both skips - and a machine-readable format returns one
  record per user.

### Changed

- `finalize_playlist` now shares its write step with a new non-fatal
  `create_for_user`, which reports a refused name collision instead of calling
  `sys.exit`; a SystemExit would have torn down a run that still had other
  users to serve, for the same reason `UserAccessError` is an ordinary
  exception.
- The per-user loop that prints the item list once and then one line per user
  moved to the new `fanout` module, so the build commands and
  `copy-playlist-all-users` share it rather than each keeping a copy.

## [1.1.24] - 2026-09-24

### Added

- `build-concatenated USER NAME PLAYLIST... [--unique]` joins several
  playlists end to end into one new playlist, keeping the order within each
  and the order they were named in. Every source is read before anything is
  written, so a source may also be the destination under `-o/--overwrite`.
  Duplicates are kept by default, a plain concatenation being faithful and
  Plex permitting a repeat; `--unique` keeps only an item's first appearance,
  matched on ratingKey, and reports how many it skipped. An empty source is
  reported rather than passed over, since a typo that resolved to the wrong
  playlist otherwise looks exactly like a playlist that happens to be empty.

## [1.1.23] - 2026-09-19

### Added

- `clean-playlist USER PLAYLIST [--include-partial]` removes the watched
  entries from a playlist and leaves the rest in their existing order. The
  removals are previewed first, numbered by each entry's place in the playlist
  as it stands rather than renumbered around the gaps, and `--dry-run` stops
  there. A part-played item is kept by default, being the one the user is in
  the middle of; `--include-partial` drops those too. A smart playlist is
  refused, its contents coming from a filter rather than from its entries.

### Changed

- The played-state and resume-point reads that `copy-watched` used privately
  are now `titles.item_is_played` and `titles.item_view_offset`, shared with
  `clean-playlist` rather than written twice.

## [1.1.22] - 2026-08-27

### Fixed

- File paths were reported as empty everywhere: the `status` sessions column,
  `show-metadata`, the `files` key in machine-readable `list-titles`, M3U
  export, and the photo gallery. plexapi exposes `media` as a
  `cached_data_property`, which is absent from `vars()` until first accessed,
  and the traversal read only `vars()`. It now reads the XML plexapi already
  holds in `_data`, which is both accurate and free.
- `list-titles` in a machine-readable format was reporting a fraction of the
  metadata for the same reason: a Movie has 18 lazy properties, including
  genres, directors, and collections. They are now read with plexapi's
  auto-reload disabled, so a field that happens to be empty costs no HTTP
  request.

## [1.1.21] - 2026-08-27

### Fixed

- `ci.yml` declared no `permissions`, so its three jobs received the
  repository default token; CodeQL reported one warning per job. It now grants
  `contents: read`, which is all a build and test run needs.

## [1.1.20] - 2026-08-27

### Changed

- Workflow actions moved to their current majors, off the deprecated node20
  runtime: `actions/checkout@v7`, `actions/setup-python@v7`,
  `actions/upload-artifact@v7`, `actions/download-artifact@v8`. The PyPI
  publish action is a composite and has no Node runtime to deprecate.

## [1.1.19] - 2026-08-27

### Added

- The `status` sessions table now carries the library ID, the ratingKey, and
  the file the player actually has open. For an item with several versions or
  parts, the one Plex marks as selected is reported rather than the first.

## [1.1.18] - 2026-08-14

### Changed

- Release notes in `CONTRIBUTING.md` now record that the publish workflow
  triggers on a published release rather than a pushed tag, and suggest
  `git config tag.sort version:refname` so `v1.1.16` no longer sorts before
  `v1.1.6`.

## [1.1.17] - 2026-08-14

### Added

- `.github/workflows/publish.yml`: publishes to PyPI through Trusted
  Publishing, so no API token is stored. It reruns `make check`, refuses to
  publish when the release tag does not match the packaged version, and
  offers a manual TestPyPI rehearsal.

## [1.1.16] - 2026-08-14

### Changed

- `AI.prompt.md` regenerated from the current code rather than edited in
  place. The previous version had drifted: the `find-missing` section had been
  deleted by an earlier edit and `list-titles` still described an interface
  three revisions old. The new one is checked against the registry and the
  module list, is a third shorter, and states each constraint with the reason
  attached.

## [1.1.15] - 2026-08-14

### Changed

- `find-missing` now names a show by default, by title or ratingKey, rather
  than sweeping every library. `-A/--all` restores the sweep, `-l/--library`
  narrows either, and `-s/--season` takes one season or a comma-separated
  list for a single show. Naming season 0 with `-s 0` includes the specials
  without needing `--include-specials`.
- Show lookup uses the same precedence as every other identifier: a numeric
  value is a ratingKey, titles match exactly before case-insensitively, and an
  ambiguous title aborts rather than guessing.

## [1.1.14] - 2026-08-14

### Fixed

- `records.py` carried a stray `from plexdo.formats import _scalar` that
  shadowed its own function of the same name, so nested media were flattened
  to text instead of expanded. Both are now named for what they do:
  `formats._cell_value` flattens for CSV and CLIXML, `records._jsonable`
  preserves structure.

### Changed

- Test fixtures consolidated: one `FakeItem` and one `FakeMedia` in
  `conftest.py` replace four near-duplicate mock classes.
- Removed `SUMMARY_FIELDS`, a constant referenced only by its own test.

## [1.1.13] - 2026-08-14

### Fixed

- `list-titles` in a machine-readable format printed media as object
  references (`<Media object at 0x...>`), so file names appeared nowhere.
  Nested objects are now expanded, putting the name at
  `media[].parts[].file`, and the paths are repeated in a top-level `files`
  list. `sourceURI` was never a file name: it is the remote server URI of an
  item in another user's playlist and is null for local content.

## [1.1.12] - 2026-08-14

### Added

- `show-metadata` reports the server-side path of every file backing an item.
  A table names a lone file `file` and numbers them when there are several; a
  machine-readable format carries them as a `files` list.

### Changed

- The media traversal behind M3U export, photo galleries, and this new field
  is now one shared `records.file_paths` rather than three copies.

## [1.1.11] - 2026-08-14

### Added

- Table output is fitted to the terminal: the widest column is truncated with
  an ellipsis so a row stays on one line, and the columns narrowed are
  reported at INFO level. `-W/--wide` disables it, and redirected output is
  never truncated.

## [1.1.10] - 2026-08-14

### Added

- Global `--throttle SECONDS` (default 0.25) paces operations that issue one
  request per item once there are more than 50 of them: the seasons walk in
  `list-titles`, `find-missing`, applying watched state in `copy-watched`,
  reading photo albums, and copying to every user. Pass 0 to disable. Smaller
  runs are never paced, since the delay would be latency for no benefit.

## [1.1.9] - 2026-08-14

### Added

- `find-missing` reports seasons whose episode numbering has holes, across
  every show library or one named library. Season 0 is skipped unless
  `--include-specials` is given.
- `list-titles` now shows release date, rating, and studio alongside the
  rating key and title in table output.
- A machine-readable format carries every field the library listing returned
  for each item, and for a show library nests each show's episodes under a
  `seasons` object keyed by season name.

### Notes

- Listing records are built from the attributes plexapi has already loaded.
  Reading a missing attribute triggers a reload, which would mean one HTTP
  request per item across a whole library, so the listing reports what the
  server sent and `show-metadata` remains the route to the full picture for a
  single item.

## [1.1.8] - 2026-08-14

### Changed

- Reworded the `read` help, manual page, and README to describe the condition
  (a display attached, no desktop environment) rather than calling the machine
  a headless server, which is both self-contradictory and an assumption about
  its role.

## [1.1.7] - 2026-08-14

### Added

- `list-library` as an alias for `list-titles`, recognised by all four shell
  completions.
- The `read` command's help now shows worked examples, including
  `mpv --vo=drm -` for playing on Linux with a display but no desktop
  environment, which needs neither X nor Wayland.

## [1.1.6] - 2026-08-14

### Added

- PowerShell completion (`completions/plexdo.ps1`), covering the same values
  as the other shells. It uses no external interpreter, reading the cache with
  `ConvertFrom-Json`, and shows the matching title as a tooltip beside each ID.
  Install with `make install-completion SHELLS="bash zsh fish powershell"`,
  then dot-source it from your profile.

## [1.1.5] - 2026-08-14

### Added

- `cache_dir` in the `[plex]` section relocates the completion cache. The
  platform default appears commented out in the generated config template, and
  all three shell completions read the setting so a custom location does not
  silently break tab completion.

## [1.1.4] - 2026-08-14

### Changed

- Native Windows defaults: the configuration file is now
  `%LOCALAPPDATA%\PlexDo\plexdo.ini`, the completion cache
  `%LOCALAPPDATA%\PlexDo\Cache`, and `token_path` defaults to
  `%TEMP%\plexdo.token`. Linux and macOS are unchanged.
- The config template and its unresolved-variable warning follow the platform,
  accepting and reporting `%VAR%` on Windows as well as `$VAR`.
- All three shell completions read the Windows cache location when
  `LOCALAPPDATA` is set, so completion keeps working under Git Bash.

## [1.1.3] - 2026-08-14

### Added

- Declared support for Python 3.14, and added it to the CI matrix. The suite,
  the CLI, and the build were verified against CPython 3.14.4.

### Fixed

- Suppressed a `no-value-for-parameter` false positive that newer astroid
  raises for `ctypes.c_int()`, so pylint stays at 10.00/10 on 3.14.

## [1.1.2] - 2026-08-14

### Changed

- Attribution set to SidusNare in the package metadata, the GPL notices, and
  the manual page, replacing the "plexdo contributors" placeholder.

## [1.1.1] - 2026-08-14

### Added

- Test suite (126 tests) covering output formats, table alignment and encoding
  fallback, identifier resolution, playlist guards, watched-state selection,
  path rewriting, the token store, config handling, and the command registry.
- `py.typed` marker, so the package's complete type annotations are visible to
  downstream users (PEP 561).
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.gitattributes`.
- Continuous integration across Python 3.11-3.13.
- `make test`, wired into `make check`.
- AUTHORS section in the manual page.

## [1.1.0] - 2026-08-14

### Changed

- **Renamed the project from `plex.do` to `plexdo` throughout.** The console
  script, man page, completion files, configuration file, and cache directory
  all use the new name.
  - The configuration file moves from `~/.local/etc/plex.do.ini` to
    `~/.local/etc/plexdo.ini`. Rename it by hand; nothing reads the old path.
  - The completion cache moves to `~/.cache/plexdo` and regenerates itself.
- The second console script (`plex.do`) and the `plex_do` completion alias are
  gone; there is one command, `plexdo`.

## [1.0.15] - 2026-08-14

### Added

- Project homepage and issue tracker URLs in the package metadata, README, and
  manual page.

### Changed

- Source, completions, manual page, and build files are plain ASCII.
- `check-assets` verifies the packaged copies of the completions and manual
  page match their sources, and that no source file contains non-ASCII.

## [1.0.14] and earlier

Iterative development: the single-file script became a package, gaining
multi-user token handling, watched-state synchronisation, a status report,
photo galleries, YAML/CSV/CLIXML output, shell completions for bash, zsh, and
fish, a manual page, and packaging for PyPI. See the commit history.

[Unreleased]: https://github.com/sidusnare/plexdo/compare/v4.1.0...HEAD
[4.1.0]: https://github.com/sidusnare/plexdo/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/sidusnare/plexdo/compare/v3.0.0...v4.0.0
[3.0.0]: https://github.com/sidusnare/plexdo/compare/v2.0.3...v3.0.0
[2.1.0-rc.1]: https://github.com/sidusnare/plexdo/compare/v2.0.3...v2.1.0-rc.1
[2.0.3]: https://github.com/sidusnare/plexdo/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/sidusnare/plexdo/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/sidusnare/plexdo/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/sidusnare/plexdo/compare/v1.1.29...v2.0.0
[2.0.0-rc.1]: https://github.com/sidusnare/plexdo/compare/v1.1.29...v2.0.0-rc.1
[1.1.29]: https://github.com/sidusnare/plexdo/compare/v1.1.28...v1.1.29
[1.1.28]: https://github.com/sidusnare/plexdo/compare/v1.1.27...v1.1.28
[1.1.27]: https://github.com/sidusnare/plexdo/compare/v1.1.26...v1.1.27
[1.1.26]: https://github.com/sidusnare/plexdo/compare/v1.1.25...v1.1.26
[1.1.25]: https://github.com/sidusnare/plexdo/compare/v1.1.24...v1.1.25
[1.1.24]: https://github.com/sidusnare/plexdo/compare/v1.1.23...v1.1.24
[1.1.23]: https://github.com/sidusnare/plexdo/compare/v1.1.22...v1.1.23
[1.1.22]: https://github.com/sidusnare/plexdo/compare/v1.1.21...v1.1.22
[1.1.21]: https://github.com/sidusnare/plexdo/compare/v1.1.20...v1.1.21
[1.1.20]: https://github.com/sidusnare/plexdo/compare/v1.1.19...v1.1.20
[1.1.19]: https://github.com/sidusnare/plexdo/compare/v1.1.18...v1.1.19
[1.1.18]: https://github.com/sidusnare/plexdo/compare/v1.1.17...v1.1.18
[1.1.17]: https://github.com/sidusnare/plexdo/compare/v1.1.16...v1.1.17
[1.1.16]: https://github.com/sidusnare/plexdo/compare/v1.1.15...v1.1.16
[1.1.15]: https://github.com/sidusnare/plexdo/compare/v1.1.14...v1.1.15
[1.1.14]: https://github.com/sidusnare/plexdo/compare/v1.1.13...v1.1.14
[1.1.13]: https://github.com/sidusnare/plexdo/compare/v1.1.12...v1.1.13
[1.1.12]: https://github.com/sidusnare/plexdo/compare/v1.1.11...v1.1.12
[1.1.11]: https://github.com/sidusnare/plexdo/compare/v1.1.10...v1.1.11
[1.1.10]: https://github.com/sidusnare/plexdo/compare/v1.1.9...v1.1.10
[1.1.9]: https://github.com/sidusnare/plexdo/compare/v1.1.8...v1.1.9
[1.1.8]: https://github.com/sidusnare/plexdo/compare/v1.1.7...v1.1.8
[1.1.7]: https://github.com/sidusnare/plexdo/compare/v1.1.6...v1.1.7
[1.1.6]: https://github.com/sidusnare/plexdo/compare/v1.1.5...v1.1.6
[1.1.5]: https://github.com/sidusnare/plexdo/compare/v1.1.4...v1.1.5
[1.1.4]: https://github.com/sidusnare/plexdo/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/sidusnare/plexdo/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/sidusnare/plexdo/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/sidusnare/plexdo/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/sidusnare/plexdo/compare/v1.0.15...v1.1.0
[1.0.15]: https://github.com/sidusnare/plexdo/releases/tag/v1.0.15
