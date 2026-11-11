plexdo-library-list(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-library-list - list what a library holds, by type or by folder

# SYNOPSIS

*plexdo library-list* _LIBRARY_ [*-t* _TYPE_] [*--filter* _FIELD_=_VALUE_]...
\[*--category* _CATEGORY_]... [_GLOBAL OPTIONS_]

*plexdo library-list* _LIBRARY_ [*-t* _TYPE_] *--list-categories*
\[_GLOBAL OPTIONS_]

*plexdo library-list* _LIBRARY_ *-t folder* [*--path* _PATH_]
\[_GLOBAL OPTIONS_]

*plexdo library-list* _LIBRARY_ *--album* _ALBUM_ [_GLOBAL OPTIONS_]

# DESCRIPTION

Lists what a library holds, of one type: its films, its shows, their
episodes, its albums, and so on. By default a movie library lists its
movies, a show library its shows, and a music or photo library its albums;
*-t* names another type, among those the library's kind can hold.

*--filter* narrows the listing to what matches, on any field the library
can be filtered by, as Plex's own filters can: a genre, a collection, a
label, a content rating, a year. *--category* is a genre, and
*--list-categories* lists the genres there are. See *FILTERS*.

Or lists the library by folder, as its files are laid out on disk, one
folder at a time: *-t folder* lists the folders at the top of the library,
and *--path* opens one of them, or one inside it.

How much each entry carries depends on the output format. The table is kept
compact. Every machine-readable format carries every field the server
returned, the paths of the files, for a show library the show's seasons and
episodes as well, and for an album its played state, progress, and
contents. Collecting episodes or album contents means opening each show or
album in turn, so a large library takes noticeably longer in a
machine-readable format than as a table.

The ratingKey and title of every entry of the library's default listing are
also written to the shell completion cache, whatever the output format, so
that completing a _ratingKey_ argument offers these titles afterwards, and
completing *--album* offers a photo library's albums. Another type, or a
folder, is not cached, so what completion offers does not change with
whatever was listed last.

# TYPES

Each type is one Plex serves for that kind of library, through
_/library/sections/ID/all?type=_. The first is the default.

[[ *Library*
:< *Types*
|  movie
:  *movie*, *collection*
|  show
:  *show*, *season*, *episode*, *collection*
|  music
:  *album*, *artist*, *track*, *collection*
|  photo
:  *album*, *photo*, *clip*

Any library can also be listed as *folder*, through
_/library/sections/ID/folder_. Naming a type the library cannot hold is an
error naming those it can.

*album* in a photo library is a photo album. Albums are walked as
*NESTED ALBUMS* describes, so an album inside another is listed, just after
the album holding it. *photo* lists every photo in the library, wherever it
is filed, and *clip* every video.

# FILTERS

*--filter* _FIELD_=_VALUE_ lists only the items whose _FIELD_ is _VALUE_.
The fields are those the library offers for the type listed, the same as
Plex's own filters, and the server checks them: a field the library does
not have is an error that lists those it does. The common ones:

[[ *Field*
:< *Matches*
|  genre
:  a genre, as *--list-categories* lists them
|  collection
:  a collection, by title
|  label
:  a label
|  contentRating
:  a rating such as *PG-13*
|  year, decade
:  a year, or a decade as its first year, *1990*
|  studio, network, director, actor, country
:  as Plex records them
|  unwatched
:  *1* for what you have not finished, *0* for what you have

A genre, a collection, or any other tag is matched against the names the
library has, ignoring case, so *genre=drama* finds Drama; a text field such
as *title* matches what contains the value. Other operators:
_FIELD_!=_VALUE_ excludes, and _FIELD_>_VALUE_ and _FIELD_<_VALUE_ compare a
number or a date, such as *year>1990* or *addedAt>-30d*, added in the last
30 days. Quote a filter holding *>*, *<*, or *!*, as in *--filter
'year>1990'*: to the shell, the first two redirect, and the last may recall
a command from history.

Give *--filter* more than once and every one must match. *--category* _NAME_
is *--filter genre=*_NAME_, and may be repeated, and given with *--filter*,
in the same way.

The filtering is the server's, so it applies to the type listed: with *-t
episode*, *genre=Crime* is the episodes of crime shows. Filtering the albums
of a photo library lists the albums the server matches, without walking into
the albums inside them.

*--list-categories* lists the genres the library's items of the type listed
are filed under, in place of the items. A type with no genres, such as
photos, is an error saying so.

# FOLDERS

*-t folder* lists the folders at the top of the library: the folders the
library was added from, as Plex knows them. *--path* names a folder to open
instead, as folder titles from the top separated by */*, as in
*TV/The Wire/Season 1*. Each title is matched exactly, or failing that
ignoring case, and each level costs one request. A folder that is not there
is an error naming the folders there are.

A folder lists its subfolders, then the items it holds directly: a film or
a track, or a show or an album when the folder is one. A subfolder has no
ratingKey; its *path* is what *--path* takes to open it.

# NESTED ALBUMS

A photo library is walked depth first: each album is opened, and the albums
found inside it are opened in turn. An album met a second time is passed
over, so one the server shows both at the top level and inside another is
listed once, and albums that contain one another cannot keep the walk going
for ever. Nesting is followed 16 albums deep; anything deeper is left out,
with a warning naming where the walk stopped. *--album*, and
*plexdo-titles-export*(1), walk a photo library the same way.

# PLAYED STATE

An album's played state is that of the account plexdo is connected as, as
Plex keeps it per account.

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

# ARGUMENTS

_LIBRARY_
	The library to list, by numeric ID or by title, as
	*plexdo-libraries-list*(1) shows them. See *plexdo-conventions*(7) for
	how a title is matched.

# OPTIONS

*-t*, *--type* _TYPE_
	What to list: one of the types under *TYPES*, or *folder*. The
	default depends on the library, as *TYPES* shows.

*--filter* _FIELD_=_VALUE_
	List only what matches. Repeatable: every one must match. See
	*FILTERS*.

*--category* _CATEGORY_
	Short for *--filter genre=*_CATEGORY_. Repeatable.

*--list-categories*
	List the categories, genres, of the type listed, in place of the
	items.

*--path* _PATH_
	The folder to list, as folder titles from the top of the library
	separated by */*. Implies *-t folder*.

*--album* _ALBUM_
	Photo libraries only: list the photos in the album titled _ALBUM_,
	wherever it is nested, and in the albums inside it. The title is
	matched ignoring case. Implies *-t photo*. An album that is not
	found is an error, and nothing is listed.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	*table* shows the compact rows under *OUTPUT*; every other format
	carries the full records. CSV and CLIXML hold one value per column,
	so an album's contents and a show's seasons are flattened to text
	there; use JSON or YAML to read them.

*-W*, *--wide*
	Never truncate the table; long titles are what would otherwise
	shrink.

*--throttle* _SECONDS_
	Paces the album walk of a photo library, the reading of each music
	album's contents in a machine-readable format, and the season walk of
	a show library in one, once any has more than 50 albums or shows.
	*0* turns pacing off.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection, how many albums a library holds,
	and when shows or albums are being opened; *--debug* adds the cache
	write.

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

- *-t* must name a type the library can hold, or *folder*.
- *--path* goes only with *-t folder*, or with no *-t*, which it then
  implies; with another type it is a usage error.
- *--filter*, *--category*, and *--list-categories* go with any type but
  *folder*, and not with *--album*. *--list-categories* takes no
  *--filter* or *--category*.
- A filtered listing is not written to the completion cache.
- *--album* goes only with *-t photo*, or with no *-t*, which it then
  implies, and not with *--path*. Given for a library other than a photo
  library it is ignored with a warning, and the default listing is shown.
- With *--album*, an album name that matches no album is an error, even
  though the library itself was found.
- The output format decides how much is fetched: only a machine-readable
  format walks the seasons of a show library or opens each music album,
  and only then does *--throttle* pace that.

# OUTPUT

As a table, one row per entry, with the columns that suit the type:

*movie*, *show*, *artist*
	*ratingKey*, *title*, *releaseDate* (the original release or air
	date, or the year alone), *rating*, and *studio*.

*season*
	*ratingKey*, *show*, *season* (its number), *title*, and *date*.

*episode*
	*ratingKey*, *show*, *season*, *episode* (the numbers), then as for a
	movie.

*track*
	*ratingKey*, *artist* (the track's own, or else the album's),
	*album*, *track* (its number), *title*, and *date*.

*photo*, *clip*
	*ratingKey*, *title*, and *date*.

*collection*
	*ratingKey*, *title*, and *items*, how many it holds.

*album*
	*ratingKey*, *artist* (music only), *title*, *year*, *items* (how many
	tracks, photos, and clips it holds; nested albums have rows of their
	own), and *played* (how many of those have been played to the end,
	empty for an album of photos alone). A music library's table costs
	one request, whatever its size.

*folder*
	*type* (*folder* for a subfolder, or the item's type), *ratingKey*
	(none for a subfolder), *title*, and *path* (for a subfolder, what
	*--path* takes to open it).

*--list-categories* lists one record per genre, *category*, its name.

In any other format, a folder listing carries those same four fields, and
every other type one record per entry with every field the server listed
for it, sorted by name, plus:

*files*
	The server-side paths of every file behind the entry: several when
	there are several versions or parts.

*releaseDate*
	As in the table.

*seasons*
	Shows only: an object keyed by season name, each holding one record
	per episode with that episode's fields and files.

An album's record is different, the same record *plexdo-album-list*(1)
gives:

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

Every album record carries every key, null where it does not apply.

# EXIT STATUS

*0* on success, including an empty listing. *1* when _LIBRARY_ is not found
or is ambiguous, when *-t* names a type the library cannot hold, when a
filter names a field the library does not have or a value of the wrong
kind, when *--path* names a folder that is not there, or when *--album*
names an album the library does not have. *2* when *--path* or *--album* is
given with a type it does not go with, or both are given, when a filter is
not written as _FIELD_=_VALUE_, or when *--filter*, *--category*, or
*--list-categories* is given with an option it does not go with. See
*plexdo-conventions*(7).

# EXAMPLES

List the shows in a library named by its title, then every episode:

```
plexdo library-list "TV Shows"
plexdo library-list "TV Shows" -t episode
```

The albums of a music library, with how many tracks of each have been
played:

```
plexdo library-list Music
```

The albums part way through, and how far:

```
plexdo library-list Music --json |
    jq -r '.[] | select(.state == "in progress") |
        "\\(.progress)%  \\(.artist) - \\(.title)"'
```

Every track with a resume point, and where it is:

```
plexdo library-list Music --json |
    jq -r '.[].contents[] | select(.viewOffset) |
        "\\(.title): \\(.viewOffset / 1000 | floor)s (\\(.progress)%)"'
```

The albums of a photo library, nested ones included, then the photos in one
of them; the album name is matched ignoring case:

```
plexdo library-list Photos
plexdo library-list Photos --album "summer 2024"
```

The crime dramas, and the films of the 1990s rated PG-13:

```
plexdo library-list "TV Shows" --category Crime --category Drama
plexdo library-list Movies --filter decade=1990 --filter contentRating=PG-13
```

The genres a music library's albums are filed under:

```
plexdo library-list Music --list-categories
```

Walk a library's folders, a level at a time:

```
plexdo library-list Movies -t folder
plexdo library-list Movies --path "Films/Heat (1995)"
```

Export the full record for every film, then print the path of every file:

```
plexdo library-list Movies --json > movies.json
jq -r '.[].files[]' movies.json
```

Count the episodes of each show. On a fast local network, *--throttle 0*
removes the pause between shows:

```
plexdo library-list "TV Shows" --json --throttle 0 |
    jq -r '.[] | "\\(.title): \\([.seasons[] | length] | add)"'
```

# SEE ALSO

*plexdo-libraries-list*(1), *plexdo-album-list*(1), *plexdo-show-list*(1),
*plexdo-titles-export*(1), *plexdo-metadata*(1), *plexdo-conventions*(7),
*plexdo*(1)
