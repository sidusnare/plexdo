plexdo-list-users(1) "plexdo" "User Commands"

# NAME

plexdo-list-users - list the users the server is shared with

# SYNOPSIS

*plexdo list-users* [_GLOBAL OPTIONS_]

# DESCRIPTION

Lists the accounts associated with the admin account: Plex Home members,
managed accounts, and friends the server is shared with. Every command that
takes a _USER_ argument accepts either the ID or the title shown here.

The admin account itself is not listed. Commands refer to it as user *0*.

The list is also written to the shell completion cache, so that completing a
_USER_ argument offers these users afterwards.

# ARGUMENTS

None.

# OPTIONS

None beyond the global options.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the output format. Every format carries the same three fields.

*-W*, *--wide*
	Never truncate the table; titles are what would shrink.

*--throttle* _SECONDS_
	No effect: the users come back in a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection to the server; *--debug* also
	reports the cache write.

*--dry-run*
	No effect: nothing on the server or the account changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None: the command takes no options of its own.

# OUTPUT

One record per user:

*id*
	The user's numeric ID, which _USER_ arguments accept.

*type*
	*managed* for a restricted account of the Plex Home, *home* for any
	other Plex Home member, *friend* for a friend, and *shared* for
	anyone else the server is shared with.

*title*
	The user's display name, which _USER_ arguments also accept.

For their usernames and email addresses as well, see
*plexdo status --section users*.

# EXIT STATUS

*0* on success; *1* when the configuration or token is missing or plex.tv
cannot be reached. See *plexdo-conventions*(7).

# EXAMPLES

List the users:

```
$ plexdo list-users
+----+---------+-------+
| id | type    | title |
+----+---------+-------+
| 7  | home    | Alice |
| 9  | friend  | Bob   |
| 12 | managed | Kids  |
+----+---------+-------+
```

The IDs and titles work interchangeably wherever a user is named:

```
plexdo list-playlists 7
plexdo list-playlists Alice
```

List only the managed accounts:

```
plexdo list-users --json | jq -r '.[] | select(.type == "managed") | .title'
```

# SEE ALSO

*plexdo-status*(1), *plexdo-list-playlists*(1), *plexdo-copy-watched*(1),
*plexdo-conventions*(7), *plexdo*(1)
