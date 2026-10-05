plexdo-build-chronological(1) "plexdo" "User Commands"

# NAME

plexdo-build-chronological - build a playlist in air-date order

# SYNOPSIS

*plexdo build-chronological* _NAME_ _ratingKey_... [*-o*] [*--m3u* _PATH_
\[*-p* _PREFIX_]] [*-u* _USER_ | *-a*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Builds a playlist of every episode of the shows given, together with any
films given, in the order they first aired or were released. It suits a
franchise whose shows and films were made to be watched interleaved, in
order of release. Specials, season 0, are left out.

Items sharing a date keep the order they were given in, so naming the shows
in the order their episodes should come settles a tie.

The whole list is built before anything is created, then shown as a
numbered preview, and the playlist is created in a single request.

By default the playlist is created on the admin account. *-u* creates it for
another user instead, and *-a* for every user. See *USERS* below.

## Missing air dates

An episode with no air date in Plex is given an estimate, worked out from
its neighbours in the same season. Up to six known dates on either side of
it, by episode number, are gathered; at least three are needed, giving at
least two intervals between them. The median interval is added to the latest
date before the episode, subtracted from the earliest date after it, and the
two results averaged when both exist. *--verbose* reports each estimate.

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

# ARGUMENTS

_NAME_
	The title of the new playlist. Quote it when it contains spaces.

_ratingKey_...
	One or more shows or films, by ratingKey, as *plexdo-list-titles*(1)
	or *plexdo-search*(1) report them. A show contributes all of its
	episodes outside season 0; a film contributes itself. Anything else,
	such as an episode or a season, is an error.

# OPTIONS

*-o*, *--overwrite*
	Replace an existing playlist titled _NAME_. Without it, a taken name is
	refused: see *OPTION INTERACTIONS*.

*--m3u* _PATH_
	Also write the items to an M3U file at _PATH_, replacing any file
	already there. A leading *~* is expanded. Each entry carries the item's
	length in seconds (*-1* when unknown), its title, and the path of its
	file.

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

With *-u* or *-a*, the item list is printed once, followed by one line per
user as each completes: *created*, *replaced*, *skipped* (the title is
taken, or the server will not act for that user), or *failed*. Nothing that
goes wrong for one user stops the others. A user must be able to see the
libraries the items come from for the playlist to be created for them.

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
	*--verbose* reports every estimated air date, the playlist's size, its
	creation or replacement, and under *-a* how many users were served.
	*--debug* adds each ratingKey as it is processed.

*--dry-run*
	Build, date, and preview the list, check the title as usual, and stop
	without creating or replacing anything. Missing dates are still
	estimated or asked for. Under *-u* or *-a*, each user's line says what
	would have happened. *--m3u* still writes its file.

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
failed; their lines say so. *1* when a ratingKey is not found or is neither a
show nor a film, when a date has to be asked for and there is no input to
answer with, or when _NAME_ is taken without *-o* on the default account.
*2* when *-u* and *-a* are both given. See *plexdo-conventions*(7).

# EXAMPLES

Two shows and a film, in the order they aired:

```
plexdo build-chronological "Watch Order" 6001 6002 881
```

Check the order, and see any estimated dates, before creating anything:

```
plexdo build-chronological "Watch Order" 6001 6002 881 --dry-run -v
```

Rebuild it after new episodes arrive:

```
plexdo build-chronological "Watch Order" 6001 6002 881 -o
```

Create it for everyone on the server, and keep an M3U of the server's paths.
Leave *--prefix* off here: the shows and the film come from different
libraries, and one prefix would map both library roots to the same place:

```
plexdo build-chronological "Watch Order" 6001 6002 881 -a --m3u order.m3u
```

# SEE ALSO

*plexdo-build-interleaved*(1), *plexdo-build-concatenated*(1),
*plexdo-show-metadata*(1), *plexdo-conventions*(7), *plexdo*(1)
