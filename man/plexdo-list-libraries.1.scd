plexdo-list-libraries(1) "plexdo" "User Commands"

# NAME

plexdo-list-libraries - list the libraries on the Plex server

# SYNOPSIS

*plexdo list-libraries* [_GLOBAL OPTIONS_]

# DESCRIPTION

Lists every library section on the server: its numeric ID, its type, and
its title. Every command that takes a _LIBRARY_ argument accepts either the
ID or the title shown here.

The list is also written to the shell completion cache, so that completing
a _LIBRARY_ argument offers these libraries afterwards.

# ARGUMENTS

None.

# OPTIONS

None beyond the global options.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the output format. Every format carries the same three fields.

*-W*, *--wide*
	Never truncate the table; titles are the column that would shrink.

*--throttle* _SECONDS_
	No effect: listing the libraries is a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection to the server; *--debug* also
	reports the cache write.

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None: the command takes no options of its own.

# OUTPUT

One record per library:

*id*
	The library's numeric ID.

*type*
	*movie*, *show*, *artist* (music), or *photo*.

*title*
	The library's title.

# EXIT STATUS

*0* on success; *1* when the configuration or token is missing or the
server cannot be reached. See *plexdo-conventions*(7).

# EXAMPLES

List the libraries as a table:

```
$ plexdo list-libraries
+----+--------+----------+
| id | type   | title    |
+----+--------+----------+
| 1  | movie  | Movies   |
| 2  | show   | TV Shows |
| 3  | photo  | Photos   |
| 4  | artist | Music    |
+----+--------+----------+
```

The table is box-drawn on a console that can show the box characters; the
*+*, *-*, and *|* form above is what a console that cannot gets.

Print only the IDs of the show libraries, for a script:

```
plexdo list-libraries --json | jq '.[] | select(.type == "show") | .id'
```

Save the list as CSV:

```
plexdo list-libraries -f csv > libraries.csv
```

# SEE ALSO

*plexdo-list-titles*(1), *plexdo-export-titles*(1), *plexdo-rescan*(1),
*plexdo-conventions*(7), *plexdo*(1)
