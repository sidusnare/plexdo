plexdo-playlist-build(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-playlist-build - build a playlist from shows, films, or a playlist,
or add items to one

# SYNOPSIS

*plexdo playlist-build* (*-I* | *-C*) _NAME_ _ratingKey_... [*-o*]
\[*--m3u* _PATH_ [*-p* _PREFIX_]] [*-u* _USER_ | *-a*] [_GLOBAL OPTIONS_]

*plexdo playlist-build* *-R* _USER_ _SOURCE_ _DEST_ [*-o*]
\[*--m3u* _PATH_ [*-p* _PREFIX_]] [*-u* _USER_ | *-a*] [_GLOBAL OPTIONS_]

*plexdo playlist-build* *-A* _USER_ _PLAYLIST_ _ratingKey_...
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Builds a new playlist, or adds to an existing one. Exactly one of *-I*,
*-C*, *-R*, and *-A* says which, and with it what the arguments are: see
*MODES*.

*-I*, *-C*, and *-R* build the whole list before anything is created, show
it as a numbered preview, and create the playlist in a single request.
Nothing is created when the list would be empty. By default the playlist
goes to the account its items came from: the admin account for *-I* and
*-C*, and _USER_'s own account for *-R*. *-u* creates it for another user
instead, and *-a* for every user. See *USERS* below.

*-A* changes a playlist where it is, so it creates nothing and takes none
of *-o*, *-u*, *-a*, *--m3u*, and *-p*.

# MODES

*-I*, *--interleaved*
	Take turns between several shows: the first episode of each show in
	the order given, then the second of each, and so on. A show that runs
	out of episodes drops out and the others carry on, so every episode
	of every show appears once. Specials, season 0, are left out.

*-C*, *--chronological*
	Every episode of the shows given, together with any films given, in
	the order they first aired or were released. It suits a franchise
	whose shows and films were made to be watched interleaved, in order
	of release. Specials, season 0, are left out. Items sharing a date
	keep the order they were given in. See *MISSING AIR DATES*.

*-R*, *--randomize*
	Shuffle one of _USER_'s playlists into a new playlist titled _DEST_,
	leaving _SOURCE_ as it was. The shuffle draws on the operating
	system's secure random source rather than a predictable generator,
	so every order is equally likely, and running the command again
	gives a different order.

*-A*, *--append*
	Add one or more items to the end of one of _USER_'s playlists, in the
	order given. Every _ratingKey_ is looked up first, as _USER_ sees the
	server, and the items are added only when all of them are found: one
	unknown key means nothing is added at all. The items are listed
	before they are added. An item already in the playlist is added
	again rather than skipped, since Plex allows a playlist to hold the
	same item more than once. A smart playlist's contents come from its
	filter, so Plex refuses to add items to one.

# ARGUMENTS

_NAME_ (*-I*, *-C*)
	The title of the new playlist. Quote it when it contains spaces.

_ratingKey_... (*-I*, *-C*, *-A*)
	One or more items, by ratingKey, as *plexdo-library-list*(1),
	*plexdo-show-list*(1), or *plexdo-search*(1) report them. With *-I*
	each must be a show, in the order their turns should come; with *-C*
	a show or a film; with *-A* anything _USER_ can see. Anything that is
	not a whole number is an error.

_USER_ (*-R*, *-A*)
	Whose playlist _SOURCE_ or _PLAYLIST_ is, by numeric user ID or
	title; *0* is the admin account. See *plexdo-conventions*(7).

_SOURCE_ (*-R*)
	The playlist to shuffle, by title or ratingKey. A value made only of
	digits is always taken as a ratingKey.

_DEST_ (*-R*)
	The title of the new playlist. It may not be _SOURCE_'s own title
	without *-o*, and with *-o* the source is replaced by its own shuffle.

_PLAYLIST_ (*-A*)
	The playlist to add to, by title or ratingKey. A value made only of
	digits is always taken as a ratingKey.

The arguments may come before or after the options, but not either side of
one: the arguments after _NAME_ or _USER_ must follow one another.

# OPTIONS

These apply to *-I*, *-C*, and *-R*, and are refused with *-A*.

*-o*, *--overwrite*
	Replace an existing playlist of the same title. Without it, a taken
	name is refused: see *OPTION INTERACTIONS*.

*-u*, *--user* _USER_
	Create the playlist for this user rather than the default account,
	by numeric user ID or title; *0* is the admin account itself.

*-a*, *--all-users*
	Create the playlist for every user on the server, the admin account
	included.

*--m3u* _PATH_
	Also write the items to an M3U file at _PATH_, replacing any file
	already there. A leading *~* is expanded. Each entry carries the
	item's length in seconds (*-1* when unknown), its title, and the path
	of its file.

*-p*, *--prefix* _PREFIX_
	Rewrite the paths written by *--m3u* so the server's library root is
	replaced by _PREFIX_. See *REWRITING EXPORTED PATHS* in
	*plexdo-conventions*(7).

# MISSING AIR DATES

Under *-C*, an episode with no air date in Plex is given an estimate, worked
out from its neighbours in the same season. Up to six known dates on either
side of it, by episode number, are gathered; at least three are needed,
giving at least two intervals between them. The median interval is added to
the latest date before the episode, subtracted from the earliest date after
it, and the two results averaged when both exist. *--verbose* reports each
estimate.

When an estimate is impossible, the command asks for the date on the
terminal, as *YYYY-MM-DD*, offering the last date it used as an example, and
asks again until a valid date is given. A film with no release date is asked
for in the same way, since a film has no neighbours to estimate from. An
episode is named in the question by show, season, and episode, as in
*The Wire S01E04 - Old Cases*, with *??* for a number Plex lacks; a film by
its title and year.

Run the command interactively when dates may be missing, or set them in Plex
first. Without a terminal to ask on, as from a script whose input has run
out, the command stops with an error naming the item that needs a date.

# USERS

With *-u* or *-a*, the item list is printed once, followed by one line per
user as each completes:

```
Mixed Run (42 items)
(the numbered item list)

  created  admin  (Mixed Run)
  created  Alice  (Mixed Run)
  skipped  Bob  ('Mixed Run' already exists (ratingKey 4120); --overwrite
           would replace it)
  skipped  Cara  (access denied (401) - no libraries are shared with 'Cara')
  failed   Dan  (500 Internal Server Error)
```

Each line is a single line; the third is wrapped above only to fit this page.
Nothing that goes wrong for one user stops the others: a title already taken
and a user the server will not act for are both *skipped*, and anything else
is *failed*. A user must be able to see the items' library for the playlist
to be created for them.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the preview, or under *-A* of the list of items
	to be added: *index*, *ratingKey*, and *title* for each. With *-u* or
	*-a*, a machine-readable format carries one record per user instead
	of the preview: *user*, *id*, *status*, *playlist*, and *detail*.

*-W*, *--wide*
	Never truncate the preview table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces *-a* when there are more than 50 users. *0* turns pacing off.
	Otherwise no effect.

*-v*, *--verbose*; *--debug*
	*--verbose* reports each show's episode count under *-I*, each
	estimated date under *-C*, the playlist's size, its creation or
	replacement, under *-a* how many users were served, and under *-A*
	how many items are being added and when they have been.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	Build and preview the list, check the title as usual, and stop
	without creating, replacing, or adding anything. Under *-u* or *-a*,
	each user's line says what would have happened. *--m3u* still writes
	its file.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-I*, *-C*, *-R*, and *-A* are mutually exclusive, and one is required.
- *-A* refuses *-o*, *-u*, *-a*, *--m3u*, and *-p*: it adds to a playlist
  where it is. *-A* is *--append*; *-a* is *--all-users*.
- *-u* and *-a* are mutually exclusive; giving both is an error.
- Without *-o*, a playlist already titled _NAME_ or _DEST_ is refused. For
  the account it would go to by default, that is an error, reported before
  the preview, and nothing is created or removed. Under *-u* or *-a* it
  makes that user *skipped*, and the others carry on.
- *-o* replaces the existing playlist; under *-u* or *-a*, on every user
  who has one, reported as *replaced*.
- *--prefix* only changes the paths written by *--m3u*; without *--m3u* it
  has no effect.
- *--m3u* is written once, whichever users the playlist is created for,
  and is written under *--dry-run* too.

# EXIT STATUS

*0* on success. Under *-u* or *-a*, *0* even when some users were skipped or
failed; their lines say so.

*1* when a ratingKey is not found, or is not a show (*-I*) or a show or film
(*-C*); when _USER_, _SOURCE_, or _PLAYLIST_ is not found, or _USER_ has
nothing shared and cannot be acted on; when the list would be empty; when a
date has to be asked for and there is no input to answer with; or when the
new title is taken without *-o* on the default account. Under *-A*, one
ratingKey not found means nothing is added.

*2* for a usage error: no mode or more than one, the wrong number of
arguments for the mode, a ratingKey that is not a whole number, *-u* with
*-a*, or *-A* with an option it refuses. See *plexdo-conventions*(7).

# EXAMPLES

Alternate two shows, an episode of each in turn:

```
plexdo playlist-build -I "Mixed Run" 4102 5310
```

Preview the result without creating anything:

```
plexdo playlist-build -I "Mixed Run" 4102 5310 --dry-run
```

Two shows and a film in the order they came out, replacing the old playlist:

```
plexdo playlist-build -C "In Release Order" 4102 5310 6021 -o
```

Build it for one user, named by title, and keep an M3U of it:

```
plexdo playlist-build -I "Mixed Run" 4102 5310 -u Alice --m3u mixed.m3u
```

Build it for everyone, replacing any older copy, and keep the per-user
results as JSON:

```
plexdo playlist-build -I "Mixed Run" 4102 5310 -a -o --json > results.json
```

Shuffle a playlist into a new one, then reshuffle it in place:

```
plexdo playlist-build -R 0 "Movie Night" "Movie Night (shuffled)"
plexdo playlist-build -R 0 Mix Mix -o
```

Shuffle the admin account's playlist and give the result to Alice:

```
plexdo playlist-build -R 0 "Movie Night" "Shuffled for you" -u Alice
```

Add three episodes to a playlist:

```
plexdo playlist-build -A 0 Mix 4180 4181 4182
```

Add every episode of a show, specials excepted, to another user's playlist:

```
plexdo playlist-build -A Alice "The Wire" \\
    $(plexdo show-list 4102 --json | jq -r '.[].ratingKey')
```

# SEE ALSO

*plexdo-merge-build*(1), *plexdo-playlist-copy*(1),
*plexdo-playlist-list*(1), *plexdo-playlist-clean*(1),
*plexdo-show-list*(1), *plexdo-conventions*(7), *plexdo*(1)
