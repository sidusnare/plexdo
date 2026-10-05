plexdo-find-missing(1) "plexdo" "User Commands"

# NAME

plexdo-find-missing - report gaps in the episode numbering of a show's seasons

# SYNOPSIS

*plexdo find-missing* _SHOW_ [*-l* _LIBRARY_] [*-s* _SEASONS_]
\[*--include-specials*] [_GLOBAL OPTIONS_]

*plexdo find-missing* *-A* [*-l* _LIBRARY_] [*--include-specials*]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Reports the episode numbers missing from each season: those between the
start of the season and the highest episode number present. A season runs
from episode 0 when it has an episode 0, and from episode 1 otherwise.

A season that simply stops early is not reported as a gap, since an episode
not yet aired cannot be told apart from a missing one: a season holding
episodes 1 to 6 of an eventual 10 is complete as far as this command can
know. Only holes below the highest episode present count.

Season 0, the specials, is skipped unless asked for, because specials are
numbered irregularly and would almost always appear to have gaps.

By default one show is checked. *-A* checks every show in every show
library, or in the one library *-l* names.

# ARGUMENTS

_SHOW_
	The show to check, by ratingKey or by title. A title is matched
	exactly first and then ignoring case, among the shows of every show
	library, or of the library *-l* names; a title shared by two shows is
	an error that lists their ratingKeys. Required unless *-A* is given,
	and refused with it.

# OPTIONS

*-l*, *--library* _LIBRARY_
	Look only in this library, by numeric ID or title. Narrows the search
	for _SHOW_, which helps when two libraries hold shows of the same
	title, or narrows the sweep of *-A*. It must be a show library.

*-A*, *--all*
	Check every show, instead of one named show.

*-s*, *--season* _SEASONS_
	Check only these seasons: one number, or several separated by commas,
	as in *1,3,5*. Naming season *0* checks the specials, whatever
	*--include-specials* says. Applies to a single named show only.

*--include-specials*
	Also check season 0 when no season is named.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	In a table the missing numbers are joined into one comma-separated
	column; every other format carries them as a list of numbers.

*-W*, *--wide*
	Never truncate the table; show titles and long lists of missing
	numbers are what would shrink.

*--throttle* _SECONDS_
	Paces *-A* when a library has more than 50 shows, since each show's
	seasons are a request of their own. *0* turns pacing off. A single show
	is never paced.

*-v*, *--verbose*; *--debug*
	*--verbose* reports each library checked and how many seasons have
	gaps.

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- Exactly one of _SHOW_ and *-A* must be given: naming neither, or both, is
  an error.
- *-s* applies only to a single named show; *-A* with *-s* is an error.
- *-s* overrides *--include-specials*: once seasons are named, exactly those
  are checked, season 0 among them only when named. *--include-specials*
  then has no effect.
- *-l* works with either form. With _SHOW_ it limits where the title is
  looked up; with *-A* it limits the sweep. A library that is not a show
  library is an error.

# OUTPUT

One record per season with gaps:

*show*, *ratingKey*
	The show's title and ratingKey.

*season*
	The season number.

*missing*
	The missing episode numbers.

*missingCount*
	How many are missing.

*have*
	How many episodes the season has.

*highest*
	The highest episode number present.

When nothing is missing, a table prints the single line *No gaps found.*
instead, and a machine-readable format an empty list.

# EXIT STATUS

*0* on success, gaps found or not. *1* when the show or library is not
found, a title is ambiguous, the library holds no shows, _SHOW_ and *-A* are
both or neither given, *-s* is used with *-A*, or a season number cannot be
read. See *plexdo-conventions*(7).

# EXAMPLES

Check one show by title:

```
$ plexdo find-missing "The Wire"
+----------+-----------+--------+---------+--------------+------+---------+
| show     | ratingKey | season | missing | missingCount | have | highest |
+----------+-----------+--------+---------+--------------+------+---------+
| The Wire | 4102      | 2      | 4, 7    | 2            | 10   | 12      |
+----------+-----------+--------+---------+--------------+------+---------+
```

Check only seasons 1 and 3 of a show named by ratingKey:

```
plexdo find-missing 4102 -s 1,3
```

Check the specials alone; naming season 0 includes them:

```
plexdo find-missing 4102 -s 0
```

A title found in two libraries is ambiguous; narrow it to one:

```
plexdo find-missing "Doctor Who" -l "TV Shows"
```

Sweep every show in every show library, including their specials, and save
the result for a script:

```
plexdo find-missing -A --include-specials --json > gaps.json
```

Sweep one library without pacing on a fast local network:

```
plexdo find-missing -A -l 2 --throttle 0
```

# SEE ALSO

*plexdo-list-show*(1), *plexdo-list-titles*(1), *plexdo-rescan*(1),
*plexdo-conventions*(7), *plexdo*(1)
