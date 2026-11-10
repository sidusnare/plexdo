plexdo-rescan(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-rescan - scan a library for new files, or list the server's activity

# SYNOPSIS

*plexdo rescan* _LIBRARY_ [*-n*] [_GLOBAL OPTIONS_]

*plexdo rescan* *-a* [*-n*] [_GLOBAL OPTIONS_]

*plexdo rescan* *-s* [_GLOBAL OPTIONS_]

# DESCRIPTION

Asks the server to scan a library's folders for files that have been added,
changed, or removed, the same as *Scan Library Files* in Plex. Only files are
scanned; existing items' metadata is not refreshed. The scan runs on the
server after the command has returned.

*-a* scans every library in place of one. Naming neither a library nor *-a*
is an error that says to use *--all* to rescan them all, so a library left
off the command line by mistake does not set the whole server scanning.

With *-s*, nothing is scanned; instead the server's background activity is
listed, scans among it, so a scan started earlier can be followed.

# ARGUMENTS

_LIBRARY_
	The library to scan, by numeric ID or title. Required unless *-a* or
	*-s* is given, and not allowed with *-a*. With *-s* it is not used,
	though a title matching no library is still an error, since titles
	are resolved before anything else.

# OPTIONS

*-a*, *--all*
	Scan every library, in a single request to the server, which queues
	the scans itself.

*-s*, *--status*
	List the server's current activity instead of scanning: library scans,
	and whatever else the server is busy with.

*-n*, *--now*
	Before starting the scan, cancel every scan pending or running on
	every library, not only on _LIBRARY_, so this one starts at once rather
	than waiting in the queue. With *-a*, the scans are started afresh.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	Choose the format of the *-s* listing. A scan prints one plain line in
	any format.

*-W*, *--wide*
	Never truncate the *-s* table; titles and subtitles are what would
	shrink.

*--throttle* _SECONDS_
	No effect: neither form loops over requests in a way that is paced.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the scan being triggered and, with *-n*, the
	cancellation; *--debug* adds each library's cancellation.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	Resolve _LIBRARY_ and say on standard error what would be scanned,
	and whether pending scans would be cancelled first: nothing is
	cancelled and no scan starts. *-s* is unaffected, since listing
	changes nothing.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-s* takes precedence over everything else: given *-s*, nothing is
  scanned or cancelled, and *-n* is ignored. So is _LIBRARY_, except that
  a title matching no library is still reported as an error.
- Without *-s*, exactly one of _LIBRARY_ and *-a* is required: neither is
  an error saying to use *--all*, and both is an error too.
- *-n* cancels scans on every library, including ones unrelated to
  _LIBRARY_; any of those still wanted must be started again.
- *--dry-run* suppresses *-n*'s cancellation as well as the scan.

# OUTPUT

A scan prints one line on standard output:

```
Rescan triggered for library: 'TV Shows'
```

or, with *-a*:

```
Rescan triggered for all 4 libraries.
```

*-s* lists one record per activity:

*type*
	What kind of work it is.

*title*, *subtitle*
	What the server says it is doing.

*progress*
	How far along it is, as a percentage.

*uuid*
	The activity's identifier.

With no activity, *-s* as a table prints *No active scan jobs.* on standard
error, and in any other format an empty list, so that what reads it has a
document to read.

# EXIT STATUS

*0* on success. *1* when _LIBRARY_ is not found, or ambiguous. *2* when
neither _LIBRARY_ nor *-a* is given without *-s*, or both are. See
*plexdo-conventions*(7).

# EXAMPLES

Scan a library after copying new files into it:

```
plexdo rescan "TV Shows"
```

Scan every library:

```
plexdo rescan --all
```

Scan one library at once, cancelling the scans queued ahead of it:

```
plexdo rescan Movies -n
```

Follow the scan while it runs:

```
watch -n 5 plexdo rescan -s
```

Scan a library from a script once a download finishes, quietly:

```
plexdo rescan 2 > /dev/null
```

# SEE ALSO

*plexdo-status*(1), *plexdo-missing-find*(1), *plexdo-libraries-list*(1),
*plexdo-conventions*(7), *plexdo*(1)
