plexdo-list-titles(1) "plexdo" "User Commands"

# NAME

plexdo-list-titles, plexdo-list-library - list the titles in a library

# SYNOPSIS

*plexdo list-titles* _LIBRARY_ [*--album* _ALBUM_] [_GLOBAL OPTIONS_]

*plexdo list-library* _LIBRARY_ [*--album* _ALBUM_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Lists what a library holds: its films, its shows, its artists, or, for a
photo library, its photos. *list-library* is another name for the same
command; the two behave identically.

How much each entry carries depends on the output format. The table is kept
compact, five columns per title. Every machine-readable format carries every
field the server returned for each title, the paths of its files, and, for a
show library, the show's seasons and episodes as well. Collecting those
episodes means walking the whole library a show at a time, so a large show
library takes noticeably longer in a machine-readable format than as a
table.

A photo library is read album by album. Its photos are listed rather than its
albums; *--album* narrows the listing to one album.

The ratingKey and title of every entry are also written to the shell
completion cache, whatever the output format, so that completing a
_ratingKey_ argument offers these titles afterwards.

# ARGUMENTS

_LIBRARY_
	The library to list, by numeric ID or by title, as
	*plexdo-list-libraries*(1) shows them. See *plexdo-conventions*(7) for
	how a title is matched.

# OPTIONS

*--album* _ALBUM_
	Photo libraries only: list only the photos in the album titled
	_ALBUM_. The title is matched ignoring case. An album that is not found
	is an error, and nothing is listed.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	*table* shows five columns; every other format carries the full record
	described under *OUTPUT*, and for a show library walks every show's
	seasons to include its episodes.

*-W*, *--wide*
	Never truncate the table; long titles and studio names are what would
	otherwise shrink.

*--throttle* _SECONDS_
	Paces the album walk of a photo library, and the season walk of a show
	library in a machine-readable format, once either has more than 50
	albums or shows. *0* turns pacing off.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection and, for a show library in a
	machine-readable format, how many shows are being walked; *--debug*
	adds the cache write.

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--album* applies only to a photo library. Given for any other kind of
  library it is ignored with a warning, and the whole library is listed.
- With *--album*, an album name that matches no album is an error, even
  though the library itself was found.
- The output format decides how much is fetched: only a machine-readable
  format walks the seasons of a show library, and only then does
  *--throttle* pace that walk.

# OUTPUT

As a table, one row per title:

*ratingKey*
	The title's ratingKey, which commands taking a _ratingKey_ accept.

*title*
	The title as Plex shows it.

*releaseDate*
	The original release or air date, or the year alone when that is all
	the server has.

*rating*
	The critic or audience rating, when there is one.

*studio*
	The studio, when there is one.

In any other format each record carries every field the server listed for
the title, sorted by name, plus:

*files*
	The server-side paths of every file behind the title: several when
	there are several versions or parts.

*releaseDate*
	As in the table.

*seasons*
	Show libraries only: an object keyed by season name, each holding one
	record per episode with that episode's fields and files.

# EXIT STATUS

*0* on success. *1* when _LIBRARY_ is not found or is ambiguous, or when
*--album* names an album the library does not have. See
*plexdo-conventions*(7).

# EXAMPLES

List the shows in a library named by its title:

```
plexdo list-titles "TV Shows"
```

The same library by its ID, through the other name of the command:

```
plexdo list-library 2
```

List the photos in one album of a photo library; the album name is matched
ignoring case:

```
plexdo list-titles Photos --album "summer 2024"
```

Export the full record for every film, then print the path of every file:

```
plexdo list-titles Movies --json > movies.json
jq -r '.[].files[]' movies.json
```

Collect every show with its seasons and episodes as YAML. On a fast local
network, *--throttle 0* removes the pause between shows:

```
plexdo list-titles "TV Shows" -f yaml --throttle 0 > shows.yaml
```

Count the episodes of each show:

```
plexdo list-titles "TV Shows" --json |
    jq -r '.[] | "\\(.title): \\([.seasons[] | length] | add)"'
```

# SEE ALSO

*plexdo-list-libraries*(1), *plexdo-list-show*(1), *plexdo-export-titles*(1),
*plexdo-show-metadata*(1), *plexdo-conventions*(7), *plexdo*(1)
