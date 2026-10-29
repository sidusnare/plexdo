plexdo-build-merge(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-build-merge - mix two playlists into a new one at a ratio

# SYNOPSIS

*plexdo build-merge* _USER_ _NAME_ _FIRST_ _SECOND_ [*--ratio* _A_:_B_] [*-s*]
\[*-U*] [*-o*] [*--m3u* _PATH_ [*-p* _PREFIX_]] [*-u* _TARGET_ | *-a*]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Mixes two of _USER_'s playlists into a new playlist titled _NAME_, taking
items from each in turn at a ratio: by default one from _FIRST_, then one
from _SECOND_, and so on. With *--ratio 2:1* it takes two from _FIRST_,
then one from _SECOND_. Each playlist keeps its own order, and both are
left as they were.

A playlist has run out on the first turn it has nothing to give. By default
the rest of the other then follows on its own, so nothing is left out;
*--verbose* says how many items that is. With *-s* the result stops there
instead, ending with the last turn both playlists took part in, so all of it
keeps the ratio. Playlists whose sizes match the ratio, such as 20 and 10
items at 2:1, run out together, and *-s* changes nothing.

Both playlists are read before anything is written, so either may also be
_NAME_: with *-o*, *build-merge 0 Mix Mix Extras -o* mixes Extras into Mix.

By default an item in both playlists appears twice, as Plex permits; *-U*
keeps only its first appearance. An empty playlist is reported with a
warning, since a mistyped name that matched the wrong playlist looks exactly
like one that happens to be empty; the result is then the other playlist
unchanged, or, with *-s*, nothing.

The whole list is built before anything is created, then shown as a
numbered preview, and the playlist is created in a single request. Nothing is
created when the result is empty.

By default _NAME_ is created on _USER_'s own account. *-u* creates it for
another user instead, and *-a* for every user. See *USERS* below.

# ARGUMENTS

_USER_
	Whose playlists are mixed, by numeric user ID or title; *0* is the
	admin account. See *plexdo-conventions*(7).

_NAME_
	The title of the new playlist.

_FIRST_, _SECOND_
	The two playlists, by title or ratingKey. A value made only of digits
	is always taken as a ratingKey. _FIRST_ starts the result. They may be
	the same playlist.

# OPTIONS

*--ratio* _A_:_B_
	Take _A_ items from _FIRST_, then _B_ from _SECOND_, in turn. Both are
	whole numbers above 0. The default is *1:1*.

*-s*, *--stop-short*
	Stop when either playlist runs out, leaving out the rest of the other.
	A turn cut short because a playlist had fewer items left than the
	ratio asks for still counts: the result stops at the first turn a
	playlist has nothing at all to give.

*-U*, *--unique*
	Skip an item already taken, so an item in both playlists, or twice in
	one, is listed once, where it first appears. The next item of the same
	playlist takes the place of one skipped, so the ratio still holds.
	Items are matched by ratingKey rather than title, so two episodes
	sharing a title are both kept.

*-o*, *--overwrite*
	Replace an existing playlist titled _NAME_. Without it, a taken name is
	refused: see *OPTION INTERACTIONS*.

*--m3u* _PATH_
	Also write the mixed items to an M3U file at _PATH_, replacing any file
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

With *-u* or *-a*, the mixed list is printed once, followed by one line per
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
	Paces *-a* when there are more than 50 users. *0* turns pacing off.

*-v*, *--verbose*; *--debug*
	*--verbose* reports each playlist's size as it is read, how many items
	follow unmixed once the other playlist runs out, or with *-s* how many
	were left out, how many repeats *-U* skipped, the size of the result,
	its creation or replacement, and under *-a* how many users were
	served.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	Read, mix, and preview, check _NAME_ as usual, and stop without
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
- *-o* replaces the existing playlist, which may be _FIRST_ or _SECOND_:
  both are read first, so their items are not lost.
- *--ratio 1:1* and *--ratio 3:3* differ: the second takes runs of three.
- *-s* with an empty playlist gives an empty result, so nothing is created.
- Under *-U* and *-s* together, a playlist with only repeats left has run
  out: it has nothing new to give.
- *-u* is *--user*, the account _NAME_ is created for; *-U* is *--unique*.
- *--prefix* only changes the paths written by *--m3u*; without *--m3u* it
  has no effect.
- *--m3u* is written once, whichever users the playlist is created for,
  and is written under *--dry-run* too.

# EXIT STATUS

*0* on success. Under *-u* or *-a*, *0* even when some users were skipped or
failed; their lines say so. *1* when _USER_, _FIRST_, or _SECOND_ is not
found, when the result is empty, when _USER_ has nothing shared and
cannot be acted on, or when _NAME_ is taken without *-o* on _USER_'s
account. *2* when *--ratio* is not two whole numbers above 0, or *-u* and
*-a* are both given. See *plexdo-conventions*(7).

# EXAMPLES

Alternate two playlists, one item from each:

```
plexdo build-merge 0 "Date Night" "Her Picks" "His Picks"
```

Two cartoons for every film, checking the result first:

```
plexdo build-merge 0 "Saturday" Cartoons Films --ratio 2:1 --dry-run
```

Two shows for every film, ending with the last film, and without an
episode the two playlists share appearing twice:

```
plexdo build-merge 0 "Weekend" Shows Films --ratio 2:1 -s -U
```

Mix new finds into an existing playlist, one for every three, in place:

```
plexdo build-merge 0 Mix Mix "New Finds" --ratio 3:1 -o
```

Mix playlists by ratingKey, and give the result to every user:

```
plexdo build-merge 0 "Holiday Mix" 9001 9017 -a
```

# SEE ALSO

*plexdo-build-concatenated*(1), *plexdo-build-interleaved*(1),
*plexdo-list-playlists*(1), *plexdo-conventions*(7), *plexdo*(1)
