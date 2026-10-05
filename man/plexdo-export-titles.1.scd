plexdo-export-titles(1) "plexdo" "User Commands"

# NAME

plexdo-export-titles - export a whole library to an M3U file or photo gallery

# SYNOPSIS

*plexdo export-titles* _LIBRARY_ _PATH_ [*--sort* *alpha*|*date*|*random*]
\[*--album* _ALBUM_] [*-p* _PREFIX_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Writes everything in a library to one file at _PATH_, replacing any file
already there. What is written depends on the kind of library:

*show*
	An M3U playlist of every episode of every show. Specials, season 0,
	are left out.

*movie*
	An M3U playlist of every film.

*photo*
	A single HTML page showing every photo as a gallery, grouped by album,
	with each photo's title and date as its caption. Clicking a photo opens
	it in a full-screen viewer.

Music libraries are not supported.

Both kinds of file refer to the media by the paths the Plex server itself
uses, never by Plex HTTP URLs, so they work wherever those paths can be
read: on the server, or anywhere *--prefix* makes them valid. An M3U entry
carries the item's length in seconds (*-1* when unknown), its title, and its
path; an item with several files gets an entry per file, and an item with no
file is left out, in the gallery too.

The gallery page loads its viewer, Spotlight.js, from the jsDelivr content
network when it is opened, so viewing it needs an internet connection; the
photos themselves are never fetched from anywhere but their paths.

# ARGUMENTS

_LIBRARY_
	The library to export, by numeric ID or by title. See
	*plexdo-conventions*(7).

_PATH_
	The file to write: an M3U playlist for a show or movie library, an HTML
	page for a photo library. A leading *~* is expanded. An existing file
	is replaced without asking.

# OPTIONS

*--sort* *alpha*|*date*|*random*
	The order of the entries. Default *alpha*.

	*alpha*: episodes by show title, then season, then episode number, so
	each show stays together in airing order; films and photos by title.

	*date*: by original air or release date, falling back to the date the
	item was added to Plex, which suits photos without a date taken.
	Items with neither come last.

	*random*: shuffled, using the operating system's secure random source
	rather than a predictable generator.

*--album* _ALBUM_
	Photo libraries only: export only the album titled _ALBUM_, matched
	ignoring case. The album's title is added to the gallery's heading.

*-p*, *--prefix* _PREFIX_
	Rewrite every path so the server's library root is replaced by
	_PREFIX_. See *REWRITING EXPORTED PATHS* in *plexdo-conventions*(7).

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	No effect: the command writes a file rather than records. A successful
	M3U export prints one plain line naming the file, in any format.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	Paces the album walk of a photo library when it has more than 50
	albums. *0* turns pacing off. Show and movie libraries are not paced.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the library read, the number of items and the sort
	order, and the file written; *--debug* adds the library roots used by
	*--prefix* and every photo skipped for having no file.

*--dry-run*
	No effect: nothing on the server changes, and the file is still
	written.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--album* applies only to a photo library. For a show or movie library it
  is ignored with a warning, and the whole library is exported.
- With *--album*, an album name that matches no album is an error, and no
  file is written.
- *--sort date* places undated items last, so a library with few dates comes
  out mostly in arbitrary order; *alpha* is the predictable choice.
- *--prefix* rewrites the paths in a gallery exactly as in an M3U file.

# OUTPUT

The file at _PATH_. After an M3U export, one line on standard output:

```
Exported 1432 items to: /home/fred/tv.m3u
```

A gallery is reported only at *--verbose* level.

# EXIT STATUS

*0* on success. *1* when _LIBRARY_ is not found or is ambiguous, when it is a
music library, when it holds nothing to export, or when *--album* names an
album that does not exist. See *plexdo-conventions*(7).

# EXAMPLES

Export every episode of every show, alphabetically by show:

```
plexdo export-titles "TV Shows" ~/tv.m3u
```

Export the films in release order:

```
plexdo export-titles Movies ~/movies.m3u --sort date
```

A shuffled film playlist for a player on a machine that mounts the library
at _/mnt/media/movies_ rather than the server's _/srv/media/movies_:

```
plexdo export-titles Movies shuffle.m3u --sort random -p /mnt/media/movies
```

The same for a Windows player reaching the library through a share; note
the quoting, which keeps the backslashes intact:

```
plexdo export-titles Movies movies.m3u --prefix '\\\\NAS\\movies'
```

Turn one photo album into a gallery, oldest photo first:

```
plexdo export-titles Photos ~/summer.html --album "Summer 2024" --sort date
```

A gallery of the whole photo library, with the paths rewritten so a browser
on another machine can open the files from its own mount:

```
plexdo export-titles Photos photos.html -p /mnt/photos
```

# SEE ALSO

*plexdo-list-titles*(1), *plexdo-list-show*(1), *plexdo-export-playlist*(1),
*plexdo-conventions*(7), *plexdo*(1)
