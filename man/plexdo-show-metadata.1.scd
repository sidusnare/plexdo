plexdo-show-metadata(1) "plexdo" "User Commands"

# NAME

plexdo-show-metadata - show the metadata and file paths of one item

# SYNOPSIS

*plexdo show-metadata* _ratingKey_ [_GLOBAL OPTIONS_]

# DESCRIPTION

Shows the details of any one item: a film, show, episode, track, or anything
else with a ratingKey, along with the server-side path of every file behind
it. The fields depend on what kind of item it is; see *OUTPUT*.

For a whole library's worth of fields at once, a machine-readable format of
*plexdo-list-titles*(1) carries more, but this command is the way to see one
item completely.

# ARGUMENTS

_ratingKey_
	The item, by ratingKey, as *plexdo-list-titles*(1),
	*plexdo-list-show*(1), or *plexdo-search*(1) report it.

# OPTIONS

None beyond the global options.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table shows the record as two columns, field and value, with one
	*file* row, or rows *file 1*, *file 2*, and so on when there are
	several. Every other format carries the same fields with the paths as
	a *files* list.

*-W*, *--wide*
	Never truncate the table; the summary and the file paths are what
	would shrink.

*--throttle* _SECONDS_
	No effect: the item is a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection to the server.

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None: the command takes no options of its own.

# OUTPUT

Every item has:

*ratingKey*, *type*, *title*
	Its key, its kind, and its title; an episode's title is shown as
	*Show - Episode*.

*year*, *contentRating*, *rating*
	Its year, its age rating, and its critic or audience rating, when
	known.

*duration*
	Its length, as _H_:_MM_:_SS_ or _M_:_SS_.

*addedAt*, *updatedAt*
	When it was added to Plex, and when its metadata last changed.

*summary*
	Its description.

An *episode* adds *show*, *season*, *episode*, *airDate*, and *studio*.

A *movie* adds *studio*, *airDate*, *tagline*, and its *genres* and
*directors* as comma-separated lists.

A *show* adds *studio*, *firstAired*, its counts of *seasons* and
*episodes*, its *genres*, and its *network*.

A *track* adds *album*, *artist*, and *trackNumber*.

Then the files: one path per media version and part, so a film held in two
qualities has two. A show, a season, or an album has no files of its own;
its files belong to its episodes or tracks.

# EXIT STATUS

*0* on success; *1* when the server has no item with that ratingKey. See
*plexdo-conventions*(7).

# EXAMPLES

Show a film's details:

```
$ plexdo show-metadata 881
+---------------+-----------------------------------------------+
| ratingKey     | 881                                           |
| type          | movie                                         |
| title         | Heat                                          |
| year          | 1995                                          |
| contentRating | R                                             |
| rating        | 8.3                                           |
| duration      | 2:50:12                                       |
| addedAt       | 2024-03-02 21:14:09                           |
| updatedAt     | 2025-01-11 08:02:44                           |
| summary       | A group of professional bank robbers...       |
| studio        | Warner Bros.                                  |
| airDate       | 1995-12-15 00:00:00                           |
| tagline       | A Los Angeles crime saga                      |
| genres        | Action, Crime, Drama                          |
| directors     | Michael Mann                                  |
| file          | /srv/media/movies/Heat (1995)/Heat (1995).mkv |
+---------------+-----------------------------------------------+
```

Print just the file paths, one per line:

```
plexdo show-metadata 881 --json | jq -r '.files[]'
```

Check that an episode's file is where it should be, from the server:

```
ls -l "$(plexdo show-metadata 4180 --json | jq -r '.files[0]')"
```

# SEE ALSO

*plexdo-list-titles*(1), *plexdo-search*(1), *plexdo-read*(1),
*plexdo-conventions*(7), *plexdo*(1)
