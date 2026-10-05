plexdo-list-show(1) "plexdo" "User Commands"

# NAME

plexdo-list-show - list the episodes of a show, optionally writing an M3U

# SYNOPSIS

*plexdo list-show* _ratingKey_ [*--m3u* _PATH_ [*-p* _PREFIX_]]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Lists every episode of one show, numbered in the order Plex returns them,
which is season by season. Specials, season 0, are left out.

With *--m3u*, the same episodes are also written to an M3U playlist that
holds the server's own file paths, for a player that can read those files
directly.

# ARGUMENTS

_ratingKey_
	The show's ratingKey, as *plexdo-list-titles*(1) or *plexdo-search*(1)
	report it. It must be a show: an episode, season, or film is an error.

# OPTIONS

*--m3u* _PATH_
	Also write the episodes to an M3U file at _PATH_, replacing any file
	already there. A leading *~* is expanded. Each entry carries the
	episode's length in seconds (*-1* when unknown), its title, and the
	path of its file; an episode with several files has an entry per file,
	and one with none is left out.

*-p*, *--prefix* _PREFIX_
	Rewrite the paths written by *--m3u* so the server's library root is
	replaced by _PREFIX_, for reading the playlist where the media is
	mounted somewhere else. See *REWRITING EXPORTED PATHS* in
	*plexdo-conventions*(7).

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the episode list. The M3U file is unaffected.

*-W*, *--wide*
	Never truncate the table; episode titles are what would shrink.

*--throttle* _SECONDS_
	No effect: the episodes come back in a single request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection and the M3U written; *--debug* adds
	the library roots used by *--prefix*.

*--dry-run*
	No effect: nothing on the server changes, and *--m3u* still writes its
	file.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--prefix* only changes the paths written by *--m3u*. Without *--m3u* it
  is accepted and has no effect, and costs no request.
- *--m3u* replaces an existing file at _PATH_ without asking.

# OUTPUT

One record per episode:

*index*
	The episode's position in the list, from 1.

*ratingKey*
	The episode's ratingKey.

*season*, *episode*
	Its season and episode numbers.

*title*
	The show's title and the episode's, as *Show - Episode*.

# EXIT STATUS

*0* on success. *1* when _ratingKey_ is not a show or the server has no such
item. See *plexdo-conventions*(7).

# EXAMPLES

List the episodes of a show:

```
plexdo list-show 4102
```

List them and write an M3U of the server's own paths at the same time:

```
plexdo list-show 4102 --m3u ~/the-wire.m3u
```

Write an M3U for a Windows machine that reaches the media through a share.
The server keeps the show under _/srv/media/tv_, a library root, so an
episode at _/srv/media/tv/The Wire/S01E01.mkv_ is written as
_\\\\NAS\\tv\\The Wire\\S01E01.mkv_:

```
plexdo list-show 4102 --m3u the-wire.m3u -p '\\\\NAS\\tv'
```

Count a show's episodes, specials excepted:

```
plexdo list-show 4102 --json | jq length
```

# SEE ALSO

*plexdo-list-titles*(1), *plexdo-export-titles*(1), *plexdo-find-missing*(1),
*plexdo-build-interleaved*(1), *plexdo-conventions*(7), *plexdo*(1)
