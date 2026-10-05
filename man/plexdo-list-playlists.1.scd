plexdo-list-playlists(1) "plexdo" "User Commands"

# NAME

plexdo-list-playlists - list a user's playlists

# SYNOPSIS

*plexdo list-playlists* _USER_ [_GLOBAL OPTIONS_]

# DESCRIPTION

Lists the playlists belonging to _USER_, with how many items each holds.
Smart playlists are listed alongside ordinary ones. Every command that names
an existing playlist accepts either its title or the ratingKey shown here.

The list is also written to the shell completion cache, so that completing a
playlist argument for _USER_ offers these playlists afterwards.

# ARGUMENTS

_USER_
	Whose playlists to list, by numeric user ID or title; *0* is the admin
	account. See *plexdo-conventions*(7).

# OPTIONS

None beyond the global options.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the output format. Every format carries the same three fields.

*-W*, *--wide*
	Never truncate the table; playlist titles are what would shrink.

*--throttle* _SECONDS_
	No effect: the playlists come back in a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection; *--debug* adds how the user's
	connection was made and the cache write.

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None: the command takes no options of its own.

# OUTPUT

One record per playlist:

*ratingKey*
	The playlist's ratingKey, which playlist arguments accept.

*title*
	Its title, which playlist arguments also accept.

*items*
	How many items it holds.

# EXIT STATUS

*0* on success. *1* when _USER_ is not found or has nothing shared and
cannot be acted on. See *plexdo-conventions*(7).

# EXAMPLES

List the admin account's playlists:

```
$ plexdo list-playlists 0
+-----------+-------------+-------+
| ratingKey | title       | items |
+-----------+-------------+-------+
| 9001      | Movie Night | 12    |
| 9002      | Mix         | 40    |
+-----------+-------------+-------+
```

List another user's, by title:

```
plexdo list-playlists Alice
```

Find the ratingKey of a playlist by title, for a script:

```
plexdo list-playlists 0 --json |
    jq '.[] | select(.title == "Movie Night") | .ratingKey'
```

# SEE ALSO

*plexdo-list-playlist*(1), *plexdo-export-playlist*(1),
*plexdo-copy-playlist-to-user*(1), *plexdo-conventions*(7), *plexdo*(1)
