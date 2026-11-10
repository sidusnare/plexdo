plexdo-albums-list(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-albums-list - list the albums in a library, with what you have played

# SYNOPSIS

*plexdo albums-list* _LIBRARY_ [_GLOBAL OPTIONS_]

# DESCRIPTION

Lists every album in a music or photo library. In a photo library that
includes albums inside other albums, each listed just after the album that
holds it. Any other kind of library has no albums and is refused.

The table is kept compact: one row per album, saying how many items it
holds and how many of them have been played. Every machine-readable format
carries the album's played state and progress as well, and its contents in
order: each track, photo, or clip, with its own played state, and its
progress when it is part way through.

Played state is kept by Plex for each account, and what is shown is the
state of the account plexdo is connected as.

# ARGUMENTS

_LIBRARY_
	The library to list, by numeric ID or by title, as
	*plexdo-libraries-list*(1) shows them. See *plexdo-conventions*(7) for
	how a title is matched.

# PLAYED STATE

A track or a video clip is *played* once it has been played to the end,
*in progress* while it has a resume point, and *unplayed* otherwise. A
resume point wins: a played track being played again is in progress. A
photo cannot be played, so its state is null.

An album is *played* when all its tracks and clips are, *unplayed* when none
is played or in progress, and *in progress* otherwise. An album of photos
alone has no state.

Progress is a percentage, given only for what is in progress and null
otherwise. For an item it is how far the resume point is into it. For an
album it is how much of its running time has been played, a played item
counting in full and one in progress up to its resume point, so an album of
a long track and a short one is not half done when only the short one has
been played.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	*table* shows one row per album; every other format carries the full
	record described under *OUTPUT*. CSV and CLIXML hold one value per
	column, so there the contents are flattened to text; use JSON or YAML
	to read them.

*-W*, *--wide*
	Never truncate the table; long titles and artist names are what would
	otherwise shrink.

*--throttle* _SECONDS_
	Paces the requests that open each album, once there are more than 50.
	*0* turns pacing off.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection, how many albums the library holds,
	and when their contents are being read.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- The output format decides how much is fetched. A music library's table
  takes its counts from the album listing, one request in all. Every other
  format opens each album to read its contents, one request per album. A
  photo library is always opened album by album, since that is the only
  way to find the albums nested inside others.
- *--throttle* paces only the requests that open albums, so it has no
  effect on a music library's table.

# OUTPUT

As a table, one row per album:

*ratingKey*
	The album's ratingKey, which commands taking a _ratingKey_ accept.

*artist*
	Music libraries only: the album artist.

*title*, *year*
	The album's title, and its year when the server has one.

*items*
	How many tracks, photos, and clips it holds. Nested albums are not
	counted: they have rows of their own.

*played*
	How many of those have been played to the end. Empty for an album of
	photos alone.

In any other format, one record per album:

*ratingKey*, *artist*, *title*, *year*
	As in the table; *artist* is null in a photo library.

*items*, *duration*
	The number of items, and their total running time in milliseconds,
	null when none has one.

*state*, *played*
	The album's state, as under *PLAYED STATE*, and whether that is
	*played*. Both are null for an album of photos alone.

*playedItems*, *inProgressItems*
	How many of its tracks and clips are played, and how many are in
	progress. An item played before and being played again counts in both.

*lastViewedAt*
	When the album was last played, or else the latest time any of its
	items was.

*progress*
	As under *PLAYED STATE*.

*contents*
	One record per item, in album order:

	*index*
		The item's position in the album, from 1.

	*ratingKey*, *type*, *title*
		The item, and whether it is a *track*, *photo*, or *clip*.

	*disc*, *track*
		Tracks only: the disc and track numbers.

	*artist*
		Tracks only: the track artist, or else the album artist.

	*duration*
		Its length in milliseconds.

	*state*, *played*, *viewCount*, *lastViewedAt*
		Its state, as under *PLAYED STATE*; whether it has been played
		to the end at least once; how many times; and when last. All
		null for a photo.

	*viewOffset*, *progress*
		The resume point in milliseconds, and how far that is into the
		item as a percentage. Both null unless it is in progress.

	*files*
		The server-side paths of the files behind it.

Every record carries every key, null where it does not apply.

# EXIT STATUS

*0* on success, including for a library with no albums. *1* when _LIBRARY_
is not found or is ambiguous, or is neither a music nor a photo library.
See *plexdo-conventions*(7).

# EXAMPLES

List the albums of a music library, with how many tracks of each have been
played:

```
plexdo albums-list Music
```

Every album with its tracks and their played state, as JSON:

```
plexdo albums-list Music --json > albums.json
```

The albums part way through, and how far:

```
plexdo albums-list Music --json |
    jq -r '.[] | select(.state == "in progress") |
        "\\(.progress)%  \\(.artist) - \\(.title)"'
```

Every track with a resume point, and where it is:

```
plexdo albums-list Music --json |
    jq -r '.[].contents[] | select(.viewOffset) |
        "\\(.title): \\(.viewOffset / 1000 | floor)s (\\(.progress)%)"'
```

The albums of a photo library, nested ones included:

```
plexdo albums-list Photos
```

# SEE ALSO

*plexdo-album-list*(1), *plexdo-libraries-list*(1), *plexdo-library-list*(1),
*plexdo-show-watched-cp*(1), *plexdo-show-metadata*(1), *plexdo-conventions*(7),
*plexdo*(1)
