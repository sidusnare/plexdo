plexdo-copy-playlist-to-user(1) "plexdo" "User Commands"

# NAME

plexdo-copy-playlist-to-user - copy a playlist from one user to another

# SYNOPSIS

*plexdo copy-playlist-to-user* _SOURCE_USER_ _PLAYLIST_ _USER_ _DEST_ [*-o*]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Copies one of _SOURCE_USER_'s playlists to _USER_'s account under the title
_DEST_. The copy holds the same items in the same order; the original is
left as it was. Copying a smart playlist copies the items it holds now, as
an ordinary playlist.

When _DEST_ is already taken on _USER_'s account, the copy falls back to
_DEST_ followed by *admin copy*, and when that is taken too, nothing is
copied and the command reports the copy as skipped. *-o* instead replaces
the playlist titled _DEST_.

The items are listed before the copy is created, and the outcome is
reported on one line afterwards.

# ARGUMENTS

_SOURCE_USER_
	Whose playlist to copy, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist to copy, by title or ratingKey. A value made only of
	digits is always taken as a ratingKey.

_USER_
	Who receives the copy, by numeric user ID or title; *0* is the admin
	account. It may be the same as _SOURCE_USER_, to duplicate a playlist
	under another title.

_DEST_
	The title for the copy.

# OPTIONS

*-o*, *--overwrite*
	Replace a playlist already titled _DEST_ on _USER_'s account, instead
	of falling back to _DEST_ followed by *admin copy*.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table shows the item list and then the outcome line. A
	machine-readable format carries the outcome record alone, as one
	document, as *plexdo-copy-playlist-all-users*(1) does.

*-W*, *--wide*
	Never truncate the item table; titles are what would shrink.

*--throttle* _SECONDS_
	No effect: the copy is a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the title the copy is made under, whether it
	replaces anything, and why a skipped copy was skipped.

*--dry-run*
	Decide the title, list the items, and stop without creating or
	replacing anything. The outcome line says what would have happened.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- Without *-o*, a taken _DEST_ falls back to _DEST_ followed by *admin
  copy*; if that is taken too, the copy is skipped and nothing is created
  or removed.
- With *-o*, _DEST_ is always used, replacing any playlist of that title,
  and the *admin copy* fallback never applies.

# OUTPUT

As a table, the items, with *index*, *ratingKey*, and *title*, and then the
outcome. In any other format, the outcome alone:

*user*, *id*
	The receiving user's numeric ID, as text and as a number.

*status*
	*created*, *replaced*, or *skipped*.

*playlist*
	The title the copy was created under.

*detail*
	Why it was skipped, when it was.

As a table, the outcome is a single line:

```
  created  7  (Movie Night admin copy)
```

# EXIT STATUS

*0* on success, including when the copy is skipped because both titles are
taken. *1* when either user or the playlist is not found, when the playlist
is empty, or when either user has nothing shared and cannot be acted on.
See *plexdo-conventions*(7).

# EXAMPLES

Copy the admin account's playlist to Alice under the same title:

```
plexdo copy-playlist-to-user 0 "Movie Night" Alice "Movie Night"
```

Copy it again later, replacing her copy rather than creating a second:

```
plexdo copy-playlist-to-user 0 "Movie Night" Alice "Movie Night" -o
```

Copy one user's playlist to another, by IDs and ratingKey:

```
plexdo copy-playlist-to-user 7 9104 9 "From Alice"
```

Duplicate a playlist on the same account under a new title:

```
plexdo copy-playlist-to-user 0 Mix 0 "Mix (backup)"
```

# SEE ALSO

*plexdo-copy-playlist-all-users*(1), *plexdo-build-randomize*(1),
*plexdo-list-playlists*(1), *plexdo-conventions*(7), *plexdo*(1)
