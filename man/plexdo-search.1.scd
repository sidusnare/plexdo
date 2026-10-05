plexdo-search(1) "plexdo" "User Commands"

# NAME

plexdo-search - search the libraries a user can see

# SYNOPSIS

*plexdo search* _USER_ _QUERY_ [*--media-type* _TYPE_]
\[*--library-id* _LIBRARY_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Searches for titles matching _QUERY_, as _USER_ sees the server: only the
libraries shared with _USER_ are searched, and only what they hold is found.
Each library is searched in turn using Plex's own library search, which
performs a prefix and substring match on titles.

A library in which the search fails is reported as a warning and skipped,
and the others are still searched.

# ARGUMENTS

_USER_
	Whose view of the server to search, by numeric user ID or title; *0*
	is the admin account, which sees every library. See
	*plexdo-conventions*(7).

_QUERY_
	The text to search for. Quote it when it contains spaces.

# OPTIONS

*--media-type* _TYPE_
	Return only results of this kind: *movie*, *show*, *episode*, *track*,
	*photo*, *album*, or *artist*.

*--library-id* _LIBRARY_
	Search only this library, by numeric ID or title. Unlike the *-l*
	option of some other commands, this one has no short form.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the output format. Every format carries the same four fields.

*-W*, *--wide*
	Never truncate the table; titles are what would shrink.

*--throttle* _SECONDS_
	No effect: libraries are searched one request each, without pacing.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the search being made and when nothing was found;
	*--debug* adds how the user's server connection was made.

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--media-type* is applied in every library searched, including those
  that cannot hold that kind of item. Plex may refuse such a search: each
  library that does is reported as a warning and skipped. Adding
  *--library-id* for a library of the right kind avoids those warnings.
- *--library-id* must name a library _USER_ can see; one that is not shared
  with _USER_ is reported as not found.

# OUTPUT

One record per result:

*ratingKey*
	The result's ratingKey, which commands taking a _ratingKey_ accept.

*libraryId*
	The ID of the library it was found in.

*type*
	What it is: *movie*, *show*, *episode*, *track*, and so on.

*title*
	Its title; an episode's is shown as *Show - Episode*.

No results gives an empty table, or an empty list in a machine-readable
format.

# EXIT STATUS

*0* on success, results found or not. *1* when _USER_ or the library is not
found, or when _USER_ has nothing shared and cannot be acted on. See
*plexdo-conventions*(7).

# EXAMPLES

Search everything the admin account can see:

```
plexdo search 0 "wire"
```

Search as another user, by title, for films only:

```
plexdo search Alice heat --media-type movie
```

Look for episodes in one library, so that libraries which cannot hold
episodes are not searched at all:

```
plexdo search 0 "pilot" --media-type episode --library-id "TV Shows"
```

Find a film's ratingKey for another command:

```
key=$(plexdo search 0 "Heat" --media-type movie --json | jq '.[0].ratingKey')
plexdo show-metadata "$key"
```

# SEE ALSO

*plexdo-list-titles*(1), *plexdo-show-metadata*(1), *plexdo-list-users*(1),
*plexdo-conventions*(7), *plexdo*(1)
