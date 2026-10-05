plexdo-build-interleaved(1) "plexdo" "User Commands"

# NAME

plexdo-build-interleaved - build a playlist taking turns between shows

# SYNOPSIS

*plexdo build-interleaved* _NAME_ _ratingKey_... [*-o*] [*--m3u* _PATH_
\[*-p* _PREFIX_]] [*-u* _USER_ | *-a*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Builds a playlist that takes turns between several shows: the first episode
of each show in the order given, then the second of each, and so on. A show
that runs out of episodes drops out and the others carry on, so every
episode of every show appears once. Specials, season 0, are left out.

The whole list is built before anything is created, then shown as a
numbered preview, and the playlist is created in a single request. Nothing is
created when the list would be empty.

By default the playlist is created on the admin account. *-u* creates it for
another user instead, and *-a* for every user. See *USERS* below.

# ARGUMENTS

_NAME_
	The title of the new playlist. Quote it when it contains spaces.

_ratingKey_...
	One or more shows, by ratingKey, as *plexdo-list-titles*(1) or
	*plexdo-search*(1) report them, in the order their turns should come.
	Each must be a show: an episode, season, or film is an error.

# OPTIONS

*-o*, *--overwrite*
	Replace an existing playlist titled _NAME_. Without it, a taken name is
	refused: see *OPTION INTERACTIONS*.

*--m3u* _PATH_
	Also write the episodes to an M3U file at _PATH_, replacing any file
	already there. A leading *~* is expanded. Each entry carries the
	episode's length in seconds (*-1* when unknown), its title, and the path
	of its file.

*-p*, *--prefix* _PREFIX_
	Rewrite the paths written by *--m3u* so the server's library root is
	replaced by _PREFIX_. See *REWRITING EXPORTED PATHS* in
	*plexdo-conventions*(7).

*-u*, *--user* _USER_
	Create the playlist for this user rather than the admin account, by
	numeric user ID or title; *0* is the admin account itself.

*-a*, *--all-users*
	Create the playlist for every user on the server, the admin account
	included.

# USERS

With *-u* or *-a*, the episode list is printed once, followed by one line
per user as each completes:

```
Mixed Run (42 items)
(the numbered episode list)

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
is *failed*. A user must be able to see the shows' library for the playlist
to be created for them.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the episode preview. With *-u* or *-a*, a
	machine-readable format carries one record per user instead of the
	preview: *user*, *id*, *status*, *playlist*, and *detail*.

*-W*, *--wide*
	Never truncate the preview table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces *-a* when there are more than 50 users. *0* turns pacing off.
	Otherwise no effect.

*-v*, *--verbose*; *--debug*
	*--verbose* reports each show's episode count, the playlist's size, its
	creation or replacement, and under *-a* how many users were served.

*--dry-run*
	Build and preview the list, check the title as usual, and stop
	without creating or replacing anything. Under *-u* or *-a*, each user's
	line says what would have happened. *--m3u* still writes its file.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-u* and *-a* are mutually exclusive; giving both is an error.
- Without *-o*, a playlist already titled _NAME_ is refused. For the
  account it would go to by default, that is an error, reported before the
  preview, and nothing is created or removed. Under *-u* or *-a* it makes
  that user *skipped*, and the others carry on.
- *-o* replaces the existing playlist; under *-u* or *-a*, on every user
  who has one, reported as *replaced*.
- *--prefix* only changes the paths written by *--m3u*; without *--m3u* it
  has no effect.
- *--m3u* is written once, whichever users the playlist is created for,
  and is written under *--dry-run* too.

# EXIT STATUS

*0* on success. Under *-u* or *-a*, *0* even when some users were skipped or
failed; their lines say so. *1* when a ratingKey is not found or is not a
show, when the list would be empty, or when _NAME_ is taken without *-o* on
the default account. *2* when *-u* and *-a* are both given. See
*plexdo-conventions*(7).

# EXAMPLES

Alternate two shows, an episode of each in turn:

```
plexdo build-interleaved "Mixed Run" 4102 5310
```

Preview the result without creating anything:

```
plexdo build-interleaved "Mixed Run" 4102 5310 --dry-run
```

Rebuild it after adding episodes, replacing the old playlist:

```
plexdo build-interleaved "Mixed Run" 4102 5310 -o
```

Build it for one user, named by title, and keep an M3U of it:

```
plexdo build-interleaved "Mixed Run" 4102 5310 -u Alice --m3u mixed.m3u
```

Build it for everyone, replacing any older copy, and keep the per-user
results as JSON:

```
plexdo build-interleaved "Mixed Run" 4102 5310 -a -o --json > results.json
```

# SEE ALSO

*plexdo-build-chronological*(1), *plexdo-build-randomize*(1),
*plexdo-build-concatenated*(1), *plexdo-list-show*(1),
*plexdo-conventions*(7), *plexdo*(1)
