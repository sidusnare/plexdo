plexdo-clean-playlist(1) "plexdo" "User Commands"

# NAME

plexdo-clean-playlist - remove the watched items from a playlist

# SYNOPSIS

*plexdo clean-playlist* _USER_ _PLAYLIST_ [*--include-partial*]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Removes from one of _USER_'s playlists every item _USER_ has watched,
leaving the rest in their existing order. Watched state belongs to each user,
so _USER_ decides both whose playlist is cleaned and whose viewing history
counts.

An item counts as watched when Plex marks it fully played. An item that is
only part played, with a resume point, is kept: it is the one being watched
right now. *--include-partial* removes those too.

The items to be removed are listed first, each numbered by its place in the
playlist as it stands, so the numbers line up with what Plex shows rather
than running 1, 2, 3 through the removals. When every item is watched, a
warning says the playlist will be left empty; Plex removes a playlist once
its last item is gone.

A smart playlist is refused: its contents come from its filter, not from
entries that could be removed.

# ARGUMENTS

_USER_
	Whose playlist, and whose watched state, by numeric user ID or title;
	*0* is the admin account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist, by title or ratingKey. A value made only of digits is
	always taken as a ratingKey.

# OPTIONS

*--include-partial*
	Also remove items that are only part played, which are otherwise kept.
	They are listed with the state *partial* rather than *played*.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the list of items to be removed. When nothing is
	watched, a table prints a note on standard error instead, and a
	machine-readable format prints an empty list.

*-W*, *--wide*
	Never truncate the table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces the removal when more than 50 items are being removed, since
	each removal is a request of its own. *0* turns pacing off.

*-v*, *--verbose*; *--debug*
	*--verbose* reports how many items were removed and how many remain,
	and when nothing was watched.

*--dry-run*
	List the items that would be removed, warn if the playlist would be
	left empty, and stop without removing anything.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None beyond *--include-partial* widening what counts as watched.

# OUTPUT

The items to be removed, one record each:

*index*
	The item's position in the playlist before anything is removed.

*ratingKey*
	Its ratingKey.

*title*
	Its title; an episode's is shown as *Show - Episode*.

*state*
	*played*, or *partial* for a part-played item removed under
	*--include-partial*.

# EXIT STATUS

*0* on success, whether or not anything was removed. *1* when _USER_ or
_PLAYLIST_ is not found, when the playlist is smart, or when _USER_ has
nothing shared and cannot be acted on. See *plexdo-conventions*(7).

# EXAMPLES

See what would go, then clean the playlist:

```
$ plexdo clean-playlist 0 "The Wire" --dry-run
+-------+-----------+-----------------------+--------+
| index | ratingKey | title                 | state  |
+-------+-----------+-----------------------+--------+
| 1     | 4180      | The Wire - The Target | played |
| 4     | 4183      | The Wire - Old Cases  | played |
+-------+-----------+-----------------------+--------+
$ plexdo clean-playlist 0 "The Wire"
```

Clean another user's playlist by their own viewing, removing what they are
part way through as well:

```
plexdo clean-playlist Alice "Road Trip" --include-partial
```

Clean every playlist a user has. A smart playlist among them is refused and
the loop moves on:

```
plexdo list-playlists Alice --json | jq -r '.[].ratingKey' |
    while read -r key; do plexdo clean-playlist Alice "$key"; done
```

# SEE ALSO

*plexdo-list-playlist*(1), *plexdo-append-playlist*(1),
*plexdo-copy-watched*(1), *plexdo-conventions*(7), *plexdo*(1)
