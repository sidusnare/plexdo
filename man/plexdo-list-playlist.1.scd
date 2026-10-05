plexdo-list-playlist(1) "plexdo" "User Commands"

# NAME

plexdo-list-playlist - list the items in one playlist, optionally writing an M3U

# SYNOPSIS

*plexdo list-playlist* _USER_ _PLAYLIST_ [*--m3u* _PATH_ [*-p* _PREFIX_]]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Lists the items of one of _USER_'s playlists, numbered in playlist order.

With *--m3u*, the same items are also written to an M3U playlist that holds
the server's own file paths, for a player that can read those files
directly. *plexdo-export-playlist*(1) writes the M3U without the listing.

# ARGUMENTS

_USER_
	Whose playlist it is, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist, by title or ratingKey, as *plexdo-list-playlists*(1)
	shows them. A value made only of digits is always taken as a ratingKey.

# OPTIONS

*--m3u* _PATH_
	Also write the items to an M3U file at _PATH_, replacing any file
	already there. A leading *~* is expanded. Each entry carries the item's
	length in seconds (*-1* when unknown), its title, and the path of its
	file; an item with several files has an entry per file, and one with
	none is left out.

*-p*, *--prefix* _PREFIX_
	Rewrite the paths written by *--m3u* so the server's library root is
	replaced by _PREFIX_. See *REWRITING EXPORTED PATHS* in
	*plexdo-conventions*(7).

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the item list. The M3U file is unaffected.

*-W*, *--wide*
	Never truncate the table; titles are what would shrink.

*--throttle* _SECONDS_
	No effect: the items come back in a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection and the M3U written; *--debug* adds
	how the user's connection was made and the library roots used by
	*--prefix*.

*--dry-run*
	No effect: nothing on the server changes, and *--m3u* still writes its
	file.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--prefix* only changes the paths written by *--m3u*. Without *--m3u* it
  is accepted and has no effect.
- *--m3u* replaces an existing file at _PATH_ without asking.

# OUTPUT

One record per item:

*index*
	Its position in the playlist, from 1.

*ratingKey*
	Its ratingKey.

*title*
	Its title; an episode's is shown as *Show - Episode*.

# EXIT STATUS

*0* on success. *1* when _USER_ or _PLAYLIST_ is not found, when _PLAYLIST_
is a ratingKey belonging to something other than a playlist, or when _USER_
has nothing shared and cannot be acted on. See *plexdo-conventions*(7).

# EXAMPLES

List a playlist by title:

```
plexdo list-playlist 0 "Movie Night"
```

The same playlist by its ratingKey:

```
plexdo list-playlist 0 9001
```

List another user's playlist and keep an M3U copy of it:

```
plexdo list-playlist Alice "Road Trip" --m3u ~/road-trip.m3u
```

Write the M3U of a film playlist for a machine that mounts the film
library's folder at _/mnt/movies_. The prefix replaces each item's library
root, so a playlist mixing several libraries would put them all under the
one prefix:

```
plexdo list-playlist 0 "Movie Night" --m3u night.m3u -p /mnt/movies
```

# SEE ALSO

*plexdo-list-playlists*(1), *plexdo-export-playlist*(1),
*plexdo-clean-playlist*(1), *plexdo-conventions*(7), *plexdo*(1)
