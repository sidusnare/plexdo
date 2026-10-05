plexdo-build-randomize(1) "plexdo" "User Commands"

# NAME

plexdo-build-randomize - shuffle a playlist into a new one

# SYNOPSIS

*plexdo build-randomize* _USER_ _SOURCE_ _DEST_ [*-o*] [*--m3u* _PATH_
\[*-p* _PREFIX_]] [*-u* _TARGET_ | *-a*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Shuffles one of _USER_'s playlists into a new playlist titled _DEST_,
leaving _SOURCE_ as it was. The shuffle draws on the operating system's
secure random source rather than a predictable generator, so every order is
equally likely, and running the command again gives a different order.

The whole list is built before anything is created, then shown as a
numbered preview, and the playlist is created in a single request. Nothing is
created when _SOURCE_ is empty.

By default _DEST_ is created on _USER_'s own account, beside _SOURCE_. *-u*
creates it for another user instead, and *-a* for every user. See *USERS*
below.

# ARGUMENTS

_USER_
	Whose playlist _SOURCE_ is, by numeric user ID or title; *0* is the
	admin account. See *plexdo-conventions*(7).

_SOURCE_
	The playlist to shuffle, by title or ratingKey. A value made only of
	digits is always taken as a ratingKey.

_DEST_
	The title of the new playlist. It may not be _SOURCE_'s own title
	without *-o*, and with *-o* the source is replaced by its own shuffle.

# OPTIONS

*-o*, *--overwrite*
	Replace an existing playlist titled _DEST_. Without it, a taken name is
	refused: see *OPTION INTERACTIONS*.

*--m3u* _PATH_
	Also write the shuffled items to an M3U file at _PATH_, replacing any
	file already there. A leading *~* is expanded. Each entry carries the
	item's length in seconds (*-1* when unknown), its title, and the path of
	its file.

*-p*, *--prefix* _PREFIX_
	Rewrite the paths written by *--m3u* so the server's library root is
	replaced by _PREFIX_. See *REWRITING EXPORTED PATHS* in
	*plexdo-conventions*(7).

*-u*, *--user* _TARGET_
	Create _DEST_ for this user rather than for _USER_, by numeric user ID
	or title; *0* is the admin account. _SOURCE_ is still read from
	_USER_.

*-a*, *--all-users*
	Create _DEST_ for every user on the server, the admin account included.
	_SOURCE_ is still read from _USER_.

# USERS

With *-u* or *-a*, the shuffled list is printed once, followed by one line
per user as each completes: *created*, *replaced*, *skipped* (the title is
taken, or the server will not act for that user), or *failed*. Nothing that
goes wrong for one user stops the others. Every user gets the same order,
since the shuffle happens once.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the preview. With *-u* or *-a*, a machine-readable
	format carries one record per user instead: *user*, *id*, *status*,
	*playlist*, and *detail*.

*-W*, *--wide*
	Never truncate the preview table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces *-a* when there are more than 50 users. *0* turns pacing off.
	Otherwise no effect.

*-v*, *--verbose*; *--debug*
	*--verbose* reports how many items were shuffled, the creation or
	replacement, and under *-a* how many users were served.

*--dry-run*
	Shuffle and preview, check _DEST_ as usual, and stop without creating
	or replacing anything. Under *-u* or *-a*, each user's line says what
	would have happened. *--m3u* still writes its file.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-u* and *-a* are mutually exclusive; giving both is an error.
- _USER_ always names where _SOURCE_ is read from; *-u* and *-a* only change
  where _DEST_ is created.
- Without *-o*, a playlist already titled _DEST_ is refused. On _USER_'s
  account, the default, that is an error, reported before the preview, and
  nothing is created or removed. Under *-u* or *-a* it makes that user
  *skipped*, and the others carry on.
- *-o* replaces the existing playlist, which may be _SOURCE_ itself: the
  items are read before anything is removed, so shuffling a playlist in
  place works.
- *--prefix* only changes the paths written by *--m3u*; without *--m3u* it
  has no effect.
- *--m3u* is written once, whichever users the playlist is created for,
  and is written under *--dry-run* too.

# EXIT STATUS

*0* on success. Under *-u* or *-a*, *0* even when some users were skipped or
failed; their lines say so. *1* when _USER_ or _SOURCE_ is not found, when
_SOURCE_ is empty, when _USER_ has nothing shared and cannot be acted on, or
when _DEST_ is taken without *-o* on _USER_'s account. *2* when *-u* and *-a*
are both given. See *plexdo-conventions*(7).

# EXAMPLES

Shuffle a playlist into a new one:

```
plexdo build-randomize 0 "Movie Night" "Movie Night (shuffled)"
```

Reshuffle the same destination each week, replacing last week's order:

```
plexdo build-randomize 0 "Movie Night" "Movie Night (shuffled)" -o
```

Shuffle a playlist in place:

```
plexdo build-randomize 0 Mix Mix -o
```

Shuffle the admin account's playlist and give the result to Alice:

```
plexdo build-randomize 0 "Movie Night" "Shuffled for you" -u Alice
```

Give every user the same shuffled order of a family playlist:

```
plexdo build-randomize 0 Family "Family (shuffled)" -a -o
```

# SEE ALSO

*plexdo-build-concatenated*(1), *plexdo-copy-playlist-to-user*(1),
*plexdo-list-playlists*(1), *plexdo-conventions*(7), *plexdo*(1)
