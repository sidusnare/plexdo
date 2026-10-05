plexdo-build-concatenated(1) "plexdo" "User Commands"

# NAME

plexdo-build-concatenated - join several playlists end to end into a new one

# SYNOPSIS

*plexdo build-concatenated* _USER_ _NAME_ _PLAYLIST_... [*--unique*] [*-o*]
\[*--m3u* _PATH_ [*-p* _PREFIX_]] [*-u* _TARGET_ | *-a*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Joins several of _USER_'s playlists end to end into a new playlist titled
_NAME_: all of the first, then all of the second, and so on, each keeping
its own order. The playlists joined are left as they were.

Every playlist is read before anything is written, so a playlist may be both
joined and replaced: naming one of the sources as _NAME_ with *-o* appends
the others to it.

By default the result keeps any item that appears more than once, as a
plain concatenation should and as Plex permits; *--unique* keeps only each
item's first appearance. An empty playlist among the sources is reported
with a warning, since a mistyped name that matched the wrong playlist looks
exactly like one that happens to be empty, and contributes nothing.

The whole list is built before anything is created, then shown as a
numbered preview, and the playlist is created in a single request. Nothing is
created when every source is empty.

By default _NAME_ is created on _USER_'s own account. *-u* creates it for
another user instead, and *-a* for every user. See *USERS* below.

# ARGUMENTS

_USER_
	Whose playlists are joined, by numeric user ID or title; *0* is the
	admin account. See *plexdo-conventions*(7).

_NAME_
	The title of the new playlist.

_PLAYLIST_...
	One or more playlists, by title or ratingKey, in the order they should
	appear. A value made only of digits is always taken as a ratingKey. The
	same playlist may be named more than once, and appears that many times.

# OPTIONS

*--unique*
	Skip an item an earlier playlist already contributed, so an item
	appearing in two playlists is listed once, where it first appeared.
	Items are matched by ratingKey rather than title, so two episodes
	sharing a title are both kept. A repeat within one playlist is skipped
	too.

*-o*, *--overwrite*
	Replace an existing playlist titled _NAME_. Without it, a taken name is
	refused: see *OPTION INTERACTIONS*.

*--m3u* _PATH_
	Also write the joined items to an M3U file at _PATH_, replacing any file
	already there. A leading *~* is expanded. Each entry carries the item's
	length in seconds (*-1* when unknown), its title, and the path of its
	file.

*-p*, *--prefix* _PREFIX_
	Rewrite the paths written by *--m3u* so the server's library root is
	replaced by _PREFIX_. See *REWRITING EXPORTED PATHS* in
	*plexdo-conventions*(7).

*-u*, *--user* _TARGET_
	Create _NAME_ for this user rather than for _USER_, by numeric user ID
	or title; *0* is the admin account. The playlists are still read from
	_USER_.

*-a*, *--all-users*
	Create _NAME_ for every user on the server, the admin account included.
	The playlists are still read from _USER_.

# USERS

With *-u* or *-a*, the joined list is printed once, followed by one line per
user as each completes: *created*, *replaced*, *skipped* (the title is taken,
or the server will not act for that user), or *failed*. Nothing that goes
wrong for one user stops the others.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the preview. With *-u* or *-a*, a machine-readable
	format carries one record per user instead: *user*, *id*, *status*,
	*playlist*, and *detail*.

*-W*, *--wide*
	Never truncate the preview table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces the reading of the playlists when more than 50 are named, and
	*-a* when there are more than 50 users. *0* turns pacing off.

*-v*, *--verbose*; *--debug*
	*--verbose* reports each playlist's size as it is read, how many
	repeats *--unique* skipped, the size of the result, its creation or
	replacement, and under *-a* how many users were served.

*--dry-run*
	Read, join, and preview, check _NAME_ as usual, and stop without
	creating or replacing anything. Under *-u* or *-a*, each user's line
	says what would have happened. *--m3u* still writes its file.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-u* and *-a* are mutually exclusive; giving both is an error.
- _USER_ always names where the playlists are read from; *-u* and *-a* only
  change where _NAME_ is created.
- Without *-o*, a playlist already titled _NAME_ is refused. On _USER_'s
  account, the default, that is an error, reported before the preview, and
  nothing is created or removed. Under *-u* or *-a* it makes that user
  *skipped*, and the others carry on.
- *-o* replaces the existing playlist, which may be one of the sources:
  every source is read first, so its items are not lost.
- *--unique* applies across all the sources together, and within each.
- *--prefix* only changes the paths written by *--m3u*; without *--m3u* it
  has no effect.
- *--m3u* is written once, whichever users the playlist is created for,
  and is written under *--dry-run* too.

# EXIT STATUS

*0* on success. Under *-u* or *-a*, *0* even when some users were skipped or
failed; their lines say so. *1* when _USER_ or any _PLAYLIST_ is not found,
when every source is empty, when _USER_ has nothing shared and cannot be
acted on, or when _NAME_ is taken without *-o* on _USER_'s account. *2* when
*-u* and *-a* are both given. See *plexdo-conventions*(7).

# EXAMPLES

Join two playlists into a new one:

```
plexdo build-concatenated 0 "Season Run" "Part 1" "Part 2"
```

Append one playlist to another, in place:

```
plexdo build-concatenated 0 Mix Mix "New Finds" -o
```

Merge two overlapping playlists without repeats, checking the result first:

```
plexdo build-concatenated 0 Favourites "Alice's picks" "Bob's picks" \\
    --unique --dry-run
```

Join playlists by ratingKey, and give the result to every user:

```
plexdo build-concatenated 0 "Holiday Films" 9001 9017 9022 -a
```

Read the playlists from Alice's account and create the result on Bob's:

```
plexdo build-concatenated Alice "From Alice" "Road Trip" "Comfort TV" \\
    -u Bob
```

# SEE ALSO

*plexdo-append-playlist*(1), *plexdo-build-randomize*(1),
*plexdo-list-playlists*(1), *plexdo-conventions*(7), *plexdo*(1)
