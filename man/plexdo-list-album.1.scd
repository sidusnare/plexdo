plexdo-list-album(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-list-album - show what is in one album, and how far through it you are

# SYNOPSIS

*plexdo list-album* _ratingKey_ [_GLOBAL OPTIONS_]

# DESCRIPTION

Shows one music or photo album: first the album itself, with its played
state and progress, then every track, photo, or clip in it, in order, each
with its own played state, and with where it stands when it is part way
through.

Played state is kept by Plex for each account, and what is shown is the
state of the account plexdo is connected as. *PLAYED STATE* in
*plexdo-list-albums*(1) says what *played*, *in progress*, and *unplayed*
mean, and how progress is worked out, for an item and for an album.

An album inside a photo album is not one of its items. It is left out, and
the table's summary says how many there are; *plexdo-list-albums*(1) lists
them, and *list-album* shows any one of them by its own ratingKey.

The album and its contents take two requests in all, whatever its size.

# ARGUMENTS

_ratingKey_
	The album's ratingKey, as *plexdo-list-albums*(1) shows it. Anything
	that is not an album, such as a track, an artist, or a show, is
	refused.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	*table* shows the album, then its items, as described under *OUTPUT*.
	*json* and *yaml* carry the album as one record with its items nested
	in it. *csv* and *clixml* hold one value per column, so they carry the
	item records alone, one row per item.

*-W*, *--wide*
	Never truncate the tables; titles are what would otherwise shrink.

*--throttle* _SECONDS_
	No effect: there is never more than one album to open.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection, and how many nested albums were
	left out.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OUTPUT

As a table, the album first, showing only what applies to it:
*ratingKey*, *artist* (a music album), *title*, *year*, *items*, *nested
albums*, *length*, *state*, *played* (as _N_ of _M_), *in progress* (how
many items are), *progress*, and *last played*. A photo album holding photos
alone has no played state, so the lines from *state* on are left out.

Then one row per item:

*#*
	The item's position in the album, from 1.

*ratingKey*
	The item's ratingKey, which commands taking a _ratingKey_ accept.

*track*
	The track number; on an album of several discs, the disc as well, as
	*2-03*. Shown for a music album.

*title*
	The item's title.

*artist*
	The track artist. Shown only when some track's artist is not the
	album's, as on a compilation.

*length*
	The item's running time.

*state*
	*played*, *in progress*, or *unplayed*; empty for a photo.

*progress*
	For an item in progress, its resume point, its length, and how far
	that is into it, as *3:20 / 9:46 (34.1%)*; otherwise empty.

*last played*
	The date it was last played.

The *state*, *progress*, and *last played* columns are left out for an album
of photos alone.

In JSON and YAML, the album is one record, the same record
*plexdo-list-albums*(1) gives for each album, with its items under
*contents*: see *OUTPUT* in that page for every field. In CSV and CLIXML,
each row is one of those item records.

# EXIT STATUS

*0* on success, including for an empty album. *1* when _ratingKey_ is not
found, or is not an album. *2* when _ratingKey_ is not a whole number. See
*plexdo-conventions*(7).

# EXAMPLES

Show an album, with how far through it you are:

```
plexdo list-album 4127
```

Find an album's ratingKey first, then show it:

```
plexdo list-albums Music | grep "Kind of Blue"
plexdo list-album 4127
```

The tracks part way through, and where each stands:

```
plexdo list-album 4127 --json |
    jq -r '.contents[] | select(.state == "in progress") |
        "\\(.title): \\(.progress)%"'
```

Every track as a CSV row:

```
plexdo list-album 4127 -f csv > tracks.csv
```

# SEE ALSO

*plexdo-list-albums*(1), *plexdo-show-metadata*(1), *plexdo-copy-watched*(1),
*plexdo-conventions*(7), *plexdo*(1)
