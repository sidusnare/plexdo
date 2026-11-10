plexdo-playlist-copy(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-playlist-copy - copy a playlist from one user to another, or to all

# SYNOPSIS

*plexdo playlist-copy* *-A* _USER_ _PLAYLIST_ [*-o*] [_GLOBAL OPTIONS_]

*plexdo playlist-copy* *-T* _USER_ _PLAYLIST_ _TO_USER_ _DEST_ [*-o*]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Copies one of _USER_'s playlists to other accounts. Exactly one of *-A* and
*-T* says to whom. A copy holds the same items in the same order; the
original is left as it was. Copying a smart playlist copies the items it
holds now, as an ordinary playlist.

On an account where the copy's title is already taken, the copy falls back
to the title followed by *admin copy*, and when that is taken too, nothing
is copied there and the copy is reported as skipped. *-o* instead replaces
the playlist of that title.

# MODES

*-A*, *--all*
	Copy to every user the server is shared with, as
	*plexdo-users-list*(1) lists them, each copy under the playlist's own
	title. The admin account is not among them, and _USER_ is skipped,
	since the playlist is already theirs. The item list is printed once,
	since it is the same for everyone, and then one line per user as each
	completes, so a long run shows progress:

```
Movie Night (3 items)
(the numbered item list)

  skipped  Fred  (source user)
  created  Alice  (Movie Night)
  created  Bob  (Movie Night admin copy)
  skipped  Cara  (both 'Movie Night' and 'Movie Night admin copy' already
           exist; use --overwrite to replace)
  skipped  Dan  (access denied (401) - no libraries are shared with 'Dan')
```

	Each line is a single line; one is wrapped above only to fit this
	page. Nothing that goes wrong for one user stops the others: a user
	the server will not act for is *skipped*, and any other error is
	*failed*.

*-T*, *--to*
	Copy to the one account _TO_USER_, under the title _DEST_. This is
	the way to give a playlist to the admin account. The items are listed
	before the copy is created, and the outcome is reported on one line
	afterwards:

```
  created  7  (Movie Night admin copy)
```

# ARGUMENTS

_USER_
	Whose playlist to copy, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist to copy, by title or ratingKey. A value made only of
	digits is always taken as a ratingKey.

_TO_USER_ (*-T*)
	Who receives the copy, by numeric user ID or title; *0* is the admin
	account. It may be the same as _USER_, to duplicate a playlist under
	another title.

_DEST_ (*-T*)
	The title for the copy.

*-A* takes _USER_ and _PLAYLIST_ alone, and *-T* all four. The arguments may
come before or after the options, but not either side of one.

# OPTIONS

*-o*, *--overwrite*
	On each receiving account, replace a playlist already titled like the
	copy, instead of falling back to the title followed by *admin copy*.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table shows the item list and then the outcome lines. A
	machine-readable format carries the outcome alone, as one document:
	one record per user under *-A*, and a single record under *-T*.

*-W*, *--wide*
	Never truncate the item table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces *-A* when there are more than 50 users. *0* turns pacing off.
	No effect under *-T*, which is a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the title each copy is made under, whether it
	replaces anything, and why a skipped copy was skipped; *--debug* adds
	the full error behind each *failed*.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	Decide each title and outcome, list the items, print the outcome
	lines, and stop without creating or replacing anything.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-A* and *-T* are mutually exclusive, and one is required.
- Without *-o*, a taken title falls back to the title followed by *admin
  copy*; if that is taken too, the copy is skipped and nothing is created
  or removed on that account.
- With *-o*, the title is always used, replacing any playlist of that
  title, and the *admin copy* fallback never applies.

# OUTPUT

As a table, the items, with *index*, *ratingKey*, and *title*, and then the
outcome lines. In any other format, the outcome alone, per receiving user:

*user*, *id*
	Under *-A*, the user's title and numeric ID. Under *-T*, the numeric
	ID, as text and as a number.

*status*
	*created*, *replaced*, *skipped*, or, under *-A*, *failed*.

*playlist*
	The title the copy was created under.

*detail*
	Why the user was skipped or failed: the source user, both titles
	taken, no access, or the server's error.

# EXIT STATUS

*0* on success: under *-A*, once every user has been tried, even when some
were skipped or failed, and under *-T*, including when the copy is skipped
because both titles are taken. *1* when a user or the playlist is not found,
when the playlist is empty, or when _USER_ or _TO_USER_ has
nothing shared and cannot be acted on. *2* for a usage error: neither or
both of *-A* and *-T*, or the wrong number of arguments for the one given.
See *plexdo-conventions*(7).

# EXAMPLES

Give every user a copy of the admin account's playlist:

```
plexdo playlist-copy -A 0 "Movie Night"
```

Push an updated version, replacing everyone's earlier copy:

```
plexdo playlist-copy -A 0 "Movie Night" -o
```

See who would get what, without copying:

```
plexdo playlist-copy -A 0 "Movie Night" --dry-run
```

Share one user's playlist with everyone else, and list who failed:

```
plexdo playlist-copy -A Alice "Road Trip" --json |
    jq -r '.[] | select(.status == "failed") | "\\(.user): \\(.detail)"'
```

Copy the admin account's playlist to Alice under the same title, replacing
her earlier copy:

```
plexdo playlist-copy -T 0 "Movie Night" Alice "Movie Night" -o
```

Copy one user's playlist to another, by IDs and ratingKey:

```
plexdo playlist-copy -T 7 9104 9 "From Alice"
```

Duplicate a playlist on the same account under a new title:

```
plexdo playlist-copy -T 0 Mix 0 "Mix (backup)"
```

# SEE ALSO

*plexdo-playlist-build*(1), *plexdo-playlists-list*(1),
*plexdo-users-list*(1), *plexdo-conventions*(7), *plexdo*(1)
