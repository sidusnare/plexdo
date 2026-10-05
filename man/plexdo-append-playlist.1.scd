plexdo-append-playlist(1) "plexdo" "User Commands"

# NAME

plexdo-append-playlist - add items to the end of an existing playlist

# SYNOPSIS

*plexdo append-playlist* _USER_ _PLAYLIST_ _ratingKey_... [_GLOBAL OPTIONS_]

# DESCRIPTION

Adds one or more items to the end of one of _USER_'s playlists, in the order
given. Every _ratingKey_ is looked up first, as _USER_ sees the server, and
the items are added only when all of them are found: one unknown key means
nothing is added at all.

The items to be added are listed before they are added. An item already in
the playlist is added again rather than skipped, since Plex allows a playlist
to hold the same item more than once.

A smart playlist's contents come from its filter, so Plex refuses to add
items to one.

# ARGUMENTS

_USER_
	Whose playlist it is, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist, by title or ratingKey. A value made only of digits is
	always taken as a ratingKey.

_ratingKey_...
	One or more items to add, by ratingKey, as *plexdo-list-titles*(1),
	*plexdo-list-show*(1), or *plexdo-search*(1) report them. Each must be
	something _USER_ can see.

# OPTIONS

None beyond the global options.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the list of items to be added.

*-W*, *--wide*
	Never truncate the table; titles are what would shrink.

*--throttle* _SECONDS_
	No effect: the items are looked up one request each, without pacing,
	and added in a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports how many items are being added, and when they
	have been.

*--dry-run*
	Look up every item, fail as usual if any is not found, list them, and
	stop without adding anything.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None: the command takes no options of its own.

# OUTPUT

The items to be added, one record each:

*index*
	Its position among the items being added, from 1; not its position
	in the playlist.

*ratingKey*
	Its ratingKey.

*title*
	Its title; an episode's is shown as *Show - Episode*.

# EXIT STATUS

*0* on success. *1* when _USER_ or _PLAYLIST_ is not found, when any
_ratingKey_ is not found (in which case nothing is added), or when _USER_
has nothing shared and cannot be acted on. See *plexdo-conventions*(7).

# EXAMPLES

Add three episodes to a playlist:

```
plexdo append-playlist 0 Mix 4180 4181 4182
```

Preview the addition without making it:

```
plexdo append-playlist 0 Mix 4180 4181 4182 --dry-run
```

Add every episode of a show, specials excepted, to another user's playlist:

```
plexdo append-playlist Alice "The Wire" \\
    $(plexdo list-show 4102 --json | jq -r '.[].ratingKey')
```

# SEE ALSO

*plexdo-list-playlist*(1), *plexdo-clean-playlist*(1),
*plexdo-build-concatenated*(1), *plexdo-conventions*(7), *plexdo*(1)
