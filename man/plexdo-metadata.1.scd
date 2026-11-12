plexdo-metadata(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-metadata - show or update the metadata of one item

# SYNOPSIS

*plexdo metadata* _ratingKey_ [*-u* _FILE_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Shows the details of any one item: a film, show, episode, track, or anything
else with a ratingKey, along with the server-side path of every file behind
it. The fields depend on what kind of item it is; see *OUTPUT*.

For a whole library's worth of fields at once, a machine-readable format of
*plexdo-library-list*(1) carries more, but this command is the way to see one
item completely.

With *--update*, it changes the item first: save the item's metadata with
*--json*, edit the copy, and give it back. Only what differs from the server
is changed; see *UPDATING*.

# ARGUMENTS

_ratingKey_
	The item, by ratingKey, as *plexdo-library-list*(1),
	*plexdo-show-list*(1), or *plexdo-search*(1) report it.

# OPTIONS

*-u*, *--update* _FILE_
	Change the item to match _FILE_, a JSON object shaped like the output of
	*--json*, or standard input when _FILE_ is *-*. The file is read before
	connecting to the server. After the change, the command shows the item
	as the server now has it.

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

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	No effect without *--update*. With it, check the file and list on
	standard error what would change, without changing it or printing the
	item.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

*--update* reads JSON whatever *--format* is; *--format* only sets how the
item is shown afterwards.

# UPDATING

Each key in the update file is a field from *OUTPUT*, and is handled one of
three ways:

- A key the file leaves out is not touched, so the file need hold only the
  fields being changed.
- A key whose value matches the server is skipped, whether or not the field
  could be changed. A file saved with *--json* can be given back with only
  some of its values edited.
- A key whose value differs is changed if the field can be edited on that
  kind of item. If it cannot, or the key is not a field *metadata* shows for
  that kind of item, or the value is not valid for the field, nothing at all
  is changed: the command exits naming every such key, with the server's
  value and the file's.

The fields that can be changed, where the kind of item allows them:

*title*
	Cannot be empty. An episode is shown as _Show_ *-* _Episode_; that form
	and the bare episode title are both accepted, and only the episode's
	own title is stored.

*summary*, *contentRating*, *studio*, *tagline*
	Text; empty or null clears it.

*rating*
	The critic rating, a number from 0 to 10; empty or null clears it.

*airDate*, *firstAired*
	The release date, as _YYYY-MM-DD_; a time after it, as *metadata*
	prints, is ignored. Empty or null clears it. *year* follows it, and
	cannot be changed on its own.

*addedAt*
	When the item was added, as _YYYY-MM-DD_ with an optional
	_HH:MM:SS_ in local time. It cannot be cleared.

*trackNumber*
	A whole number of 0 or more.

*genres*, *directors*
	Comma-separated text, as *metadata* prints them, or a JSON list of
	text, which is the way to give a tag holding a comma. The item ends up
	with exactly these tags; their order does not matter.

Which of these a kind of item allows:

- a movie: all but *firstAired* and *trackNumber*
- a show: *title*, *summary*, *contentRating*, *rating*, *addedAt*,
  *firstAired*, *studio*, and *genres*
- an episode: *title*, *summary*, *contentRating*, *rating*, *addedAt*,
  and *airDate*
- a track: *title*, *rating*, *addedAt*, and *trackNumber*
- a season, album, artist, collection, or photo: *title*, *addedAt*, and,
  as the kind allows, *summary*, *contentRating*, and *rating*

The rest cannot be changed: *ratingKey*, *type*, *year*, *duration*,
*updatedAt*, a show's counts of *seasons* and *episodes* and its *network*,
an episode's *show*, *season*, *episode*, and *studio*, a track's *album*
and *artist*, and *files*.

Every changed field is saved in a single request, and locked, so that a
metadata refresh by the agent does not put the old value back. Unlock a
field in Plex Web to let the agent manage it again.

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
its files belong to its episodes or tracks, so it has no *file* rows and no
*files* key.

# EXIT STATUS

*0* on success; *1* when the server has no item with that ratingKey, or
when the *--update* file cannot be read, is not one JSON object, or would
change a field that cannot be changed. See *plexdo-conventions*(7).

# EXAMPLES

Show a film's details:

```
$ plexdo metadata 881
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
plexdo metadata 881 --json | jq -r '.files[]'
```

Check that an episode's file is where it should be, from the server:

```
ls -l "$(plexdo metadata 4180 --json | jq -r '.files[0]')"
```

Edit a film's metadata in an editor, check the change, then make it:

```
plexdo metadata 881 --json > heat.json
$EDITOR heat.json
plexdo metadata 881 --update heat.json --dry-run
plexdo metadata 881 --update heat.json
```

Change only the tagline, with nothing else in the file:

```
echo '{"tagline": "A Los Angeles crime saga"}' |
	plexdo metadata 881 --update -
```

# SEE ALSO

*plexdo-library-list*(1), *plexdo-search*(1), *plexdo-read*(1),
*plexdo-conventions*(7), *plexdo*(1)
