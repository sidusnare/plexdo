plexdo-export-playlist(1) "plexdo" "User Commands"

# NAME

plexdo-export-playlist - write a playlist to an M3U file

# SYNOPSIS

*plexdo export-playlist* _USER_ _PLAYLIST_ _PATH_ [*-p* _PREFIX_]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Writes one of _USER_'s playlists, in playlist order, to an M3U file holding
the server's own file paths, for a player that can read those files
directly. *plexdo-list-playlist*(1) *--m3u* does the same while also listing
the items.

Each entry carries the item's length in seconds (*-1* when unknown), its
title, and the path of its file. An item with several files has an entry per
file, and one with none is left out.

# ARGUMENTS

_USER_
	Whose playlist it is, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist, by title or ratingKey. A value made only of digits is
	always taken as a ratingKey.

_PATH_
	The M3U file to write. A leading *~* is expanded. An existing file is
	replaced without asking.

# OPTIONS

*-p*, *--prefix* _PREFIX_
	Rewrite every path so the server's library root is replaced by
	_PREFIX_. See *REWRITING EXPORTED PATHS* in *plexdo-conventions*(7).

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	No effect: the command writes a file rather than records, and prints
	one plain line naming it in any format.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect: the playlist is read in a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports how many items are exported, and where; *--debug*
	adds the library roots used by *--prefix*.

*--dry-run*
	No effect: nothing on the server changes, and the file is still
	written.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None beyond *--prefix* applying to every path written.

# OUTPUT

The file at _PATH_, and one line on standard output:

```
Exported 12 items to: /home/fred/movie-night.m3u
```

# EXIT STATUS

*0* on success. *1* when _USER_ or _PLAYLIST_ is not found, when the playlist
is empty, or when _USER_ has nothing shared and cannot be acted on. See
*plexdo-conventions*(7).

# EXAMPLES

Export a playlist by title:

```
plexdo export-playlist 0 "Movie Night" ~/movie-night.m3u
```

Export another user's playlist by ratingKey:

```
plexdo export-playlist Alice 9104 alice.m3u
```

Export for a Windows player reaching the film library through a share:

```
plexdo export-playlist 0 "Movie Night" night.m3u -p '\\\\NAS\\movies'
```

Export every one of the admin account's playlists, one file each:

```
plexdo list-playlists 0 --json | jq -r '.[].ratingKey' |
    while read -r key; do
        plexdo export-playlist 0 "$key" "playlist-$key.m3u"
    done
```

# SEE ALSO

*plexdo-list-playlist*(1), *plexdo-list-playlists*(1),
*plexdo-export-titles*(1), *plexdo-conventions*(7), *plexdo*(1)
