plexdo-copy-playlist-all-users(1) "plexdo" "User Commands"

# NAME

plexdo-copy-playlist-all-users - copy a playlist to every user it is shared with

# SYNOPSIS

*plexdo copy-playlist-all-users* _SOURCE_USER_ _PLAYLIST_ [*-o*]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Copies one of _SOURCE_USER_'s playlists to every user the server is shared
with, as *plexdo-list-users*(1) lists them, each copy under the playlist's
own title. The admin account is not among them, and _SOURCE_USER_ is skipped,
since the playlist is already theirs.

On each account where the title is already taken, the copy falls back to the
title followed by *admin copy*, and when that is taken too, that user is
skipped. *-o* instead replaces the playlist of that title.

The item list is printed once, since it is the same for everyone, and then
one line per user as each completes, so a long run shows progress:

```
Movie Night (3 items)
(the numbered item list)

  skipped  Fred  (source user)
  created  Alice  (Movie Night)
  created  Bob  (Movie Night admin copy)
  skipped  Cara  (both 'Movie Night' and 'Movie Night admin copy' already
           exist; use --overwrite to replace)
  skipped  Dan  (access denied (401) - no libraries are shared with 'Dan')
```

Each line is a single line; one is wrapped above only to fit this page.
Nothing that goes wrong for one user stops the others: a user the server will
not act for is *skipped*, and any other error is *failed*.

To give a playlist to the admin account, or to one user, see
*plexdo-copy-playlist-to-user*(1).

# ARGUMENTS

_SOURCE_USER_
	Whose playlist to copy, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

_PLAYLIST_
	The playlist to copy, by title or ratingKey. A value made only of
	digits is always taken as a ratingKey.

# OPTIONS

*-o*, *--overwrite*
	On each account, replace a playlist already titled like the source,
	instead of falling back to the title followed by *admin copy*.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table prints the item list and the per-user lines shown above. A
	machine-readable format carries one record per user instead: *user*,
	*id*, *status*, *playlist*, and *detail*.

*-W*, *--wide*
	Never truncate the item table; titles are what would shrink.

*--throttle* _SECONDS_
	Paces the copies when there are more than 50 users. *0* turns pacing
	off.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the title each copy is made under and whether it
	replaces anything; *--debug* adds the full error behind each *failed*.

*--dry-run*
	Decide each user's title and outcome, print the lines, and stop
	without creating or replacing anything.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- Without *-o*, a taken title falls back to the title followed by *admin
  copy*; if that is taken too, that user is skipped and nothing of theirs
  is created or removed.
- With *-o*, the source's own title is always used, replacing any playlist
  of that title, and the *admin copy* fallback never applies.

# OUTPUT

Per user:

*user*, *id*
	The user's title and numeric ID.

*status*
	*created*, *replaced*, *skipped*, or *failed*.

*playlist*
	The title the copy was created under.

*detail*
	Why the user was skipped or failed: the source user, both titles
	taken, no access, or the server's error.

# EXIT STATUS

*0* once every user has been tried, even when some were skipped or failed;
their lines say so. *1* when _SOURCE_USER_ or the playlist is not found, when
the playlist is empty, or when _SOURCE_USER_ has nothing shared and cannot be
acted on. See *plexdo-conventions*(7).

# EXAMPLES

Give every user a copy of the admin account's playlist:

```
plexdo copy-playlist-all-users 0 "Movie Night"
```

Push an updated version, replacing everyone's earlier copy:

```
plexdo copy-playlist-all-users 0 "Movie Night" -o
```

See who would get what, without copying:

```
plexdo copy-playlist-all-users 0 "Movie Night" --dry-run
```

Share one user's playlist with everyone else, and list who failed:

```
plexdo copy-playlist-all-users Alice "Road Trip" --json |
    jq -r '.[] | select(.status == "failed") | "\\(.user): \\(.detail)"'
```

# SEE ALSO

*plexdo-copy-playlist-to-user*(1), *plexdo-build-randomize*(1),
*plexdo-list-users*(1), *plexdo-conventions*(7), *plexdo*(1)
