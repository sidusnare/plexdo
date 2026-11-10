plexdo-show-watched-cp(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-show-watched-cp - sync watched state and resume points of two users

# SYNOPSIS

*plexdo show-watched-cp* _USER_ _USER_ [*-1*] [*-l* _LIBRARY_ | *-t* _KEY_]
\[*--unwatch*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Compares what two users have watched, item by item, and brings them into
line: what one has watched is marked watched for the other, and a resume
point one has is given to the other. By default both users can be changed;
*-1* only ever changes the second.

Two things are copied for each item, as they stand: whether it has been
played, and its resume point. An item played before and part way through
again has both, and both are copied. How many times it has been played is
not: the count is each user's own.

Watched state belongs to individual films, episodes, and tracks, so those are
what is compared, across every library both users can see that holds them.
Photo libraries have no watched state and are skipped. Only items both users
can see are compared.

The planned changes are listed first, then made.

## Which state wins

For each item:

- Neither user has watched or started it, or both are in the same state:
  nothing changes. The same state means the same played flag and the same
  resume point; two resume points within 10 seconds of each other count as
  the same, since Plex moves a resume point continuously during playback.
- Only one user has watched or started it: that user's state is copied to
  the other. With *--unwatch* it goes the other way: the unwatched state is
  copied to the user who had watched it.
- Both have watched or started it, differently: the more recent viewing
  wins. With *--unwatch* the earlier one does. A viewing with no recorded
  date never wins.

Applying a state means marking the item watched or unwatched where the two
differ on that, then setting or clearing its resume point, so that the
losing user's state matches the winner's in both. Under *--unwatch*, an item
one user is only part way through loses its resume point too.

# ARGUMENTS

_USER_ _USER_
	The two users, each by numeric user ID or title; *0* is the admin
	account. They must differ. With *-1*, the first is only read and the
	second is the one changed. See *plexdo-conventions*(7).

# OPTIONS

*-1*, *--one-way*
	Only ever change the second user. Where the first user's state would
	lose, nothing happens rather than the first user changing.

*-l*, *--library* _LIBRARY_
	Compare only this library, by numeric ID or title.

*-t*, *--title* _KEY_
	Compare only what this ratingKey names. A film, episode, track, or
	clip is compared by itself. A show or season stands for every episode
	in it, and an artist or album for every track, each compared on its
	own, so two users at different points in a show are brought into
	line episode by episode. Anything else, such as a photo or a
	playlist, has no watched state and is an error.

*--unwatch*
	Invert the rules: an item unwatched by either user becomes unwatched for
	both, and where both have viewed it the earlier viewing wins.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the planned changes. When everything is already in
	step, a table prints a note on standard error instead, and a
	machine-readable format prints an empty list.

*-W*, *--wide*
	Never truncate the table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces the changes when more than 50 are planned, since each is a
	request of its own. *0* turns pacing off. Reading the two users' states
	is not paced.

*-v*, *--verbose*; *--debug*
	*--verbose* reports how many items were read for each user, and how
	many changes were made; *--debug* adds each change *-1* prevented.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	List the planned changes and stop without making any. A full-library
	comparison can plan a great many changes, so preview it first.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- The two _USER_ arguments must name different users, whether given as an
  ID or a title.
- *-t* takes precedence over *-l*: given *-t*, only that item is compared
  and *-l* is ignored.
- *-1* combines with *--unwatch*: the inverted rules then change the
  second user only.
- With *-1*, which user comes first decides who may be changed. Without
  it, the order only breaks ties: when both viewings carry the same date,
  the first user's wins.

# OUTPUT

One record per planned change:

*ratingKey*, *title*
	The item.

*action*
	What is done to the target, as steps joined by *+*: *markPlayed* or
	*markUnplayed* when the played flag changes, then *setProgress* when
	the winner has a resume point to copy, as in *markPlayed+setProgress*;
	or *clearProgress* alone, when only a resume point has to go.

*target*
	The user changed, as *user* followed by their numeric ID.

# EXIT STATUS

*0* on success, whether or not anything changed. *1* when a user, the
library, or the item is not found, when *-t* names something with no watched
state, when both _USER_ arguments name the same user, or when either user
has nothing shared and cannot be acted on. See
*plexdo-conventions*(7).

# EXAMPLES

Preview a full synchronisation between two users, then run it:

```
plexdo show-watched-cp Alice Bob --dry-run
plexdo show-watched-cp Alice Bob
```

Copy Alice's progress to Bob without ever changing Alice:

```
plexdo show-watched-cp Alice Bob -1
```

Synchronise one library only:

```
plexdo show-watched-cp 7 9 -l "TV Shows"
```

Synchronise a single film:

```
plexdo show-watched-cp 7 9 -t 881
```

Preview making Alice's TV watched state follow the Kids account's,
unwatching for Alice whatever Kids has not watched, without changing Kids:

```
plexdo show-watched-cp Kids Alice -1 --unwatch -l "TV Shows" --dry-run
```

Mirror the admin account's viewing to a managed account every night:

```
plexdo show-watched-cp 0 Kids -1 --throttle 0.1 > /dev/null
```

# SEE ALSO

*plexdo-playlist-clean*(1), *plexdo-users-list*(1), *plexdo-search*(1),
*plexdo-conventions*(7), *plexdo*(1)
