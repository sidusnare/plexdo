plexdo-remove-playlist(1) "plexdo" "User Commands"

# NAME

plexdo-remove-playlist - delete a playlist from a user's account

# SYNOPSIS

*plexdo remove-playlist* _USER_ _PLAYLIST_ [_GLOBAL OPTIONS_]

# DESCRIPTION

Deletes one of _USER_'s playlists. Only the playlist goes: the films,
episodes, and tracks it held are untouched, and so is any other user's copy
of it.

There is no confirmation prompt, and Plex has no way to undo the deletion.
Use *--dry-run* to check which playlist a title or ratingKey resolves to
first.

# ARGUMENTS

_USER_
	Whose playlist it is, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist, by title or ratingKey. A value made only of digits is
	always taken as a ratingKey.

# OPTIONS

None beyond the global options.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	No effect: the command prints one plain line in any format.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect: the deletion is a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the playlist being removed, and under *--dry-run*
	that the deletion was skipped.

*--dry-run*
	Find the playlist, fail as usual if it cannot be found, and stop
	without deleting it. Nothing is printed on standard output; add
	*--verbose* to see what would have been removed.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None: the command takes no options of its own.

# OUTPUT

One line naming the playlist as it was given:

```
Deleted playlist: 'Movie Night'
```

# EXIT STATUS

*0* on success. *1* when _USER_ or _PLAYLIST_ is not found, when _PLAYLIST_
is a ratingKey belonging to something other than a playlist, or when _USER_
has nothing shared and cannot be acted on. See *plexdo-conventions*(7).

# EXAMPLES

Check what would be removed, then remove it:

```
plexdo remove-playlist 0 "Old Mix" --dry-run --verbose
plexdo remove-playlist 0 "Old Mix"
```

Remove one of another user's playlists by ratingKey, which is unambiguous
even if they have two playlists of the same title:

```
plexdo remove-playlist Alice 9104
```

# SEE ALSO

*plexdo-list-playlists*(1), *plexdo-clean-playlist*(1),
*plexdo-copy-playlist-all-users*(1), *plexdo-conventions*(7), *plexdo*(1)
