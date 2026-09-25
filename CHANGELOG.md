# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.1.25]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.25
[1.1.24]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.24
[1.1.23]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.23
[1.1.22]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.22
[1.1.18]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.18
[1.1.16]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.16
[1.1.6]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.6
