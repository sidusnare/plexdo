plexdo-rescan(1) "plexdo" "User Commands"

# NAME

plexdo-rescan - scan a library for new files, or list the server's activity

# SYNOPSIS

*plexdo rescan* _LIBRARY_ [*-n*] [_GLOBAL OPTIONS_]

*plexdo rescan* *-s* [_GLOBAL OPTIONS_]

# DESCRIPTION

Asks the server to scan a library's folders for files that have been added,
changed, or removed, the same as *Scan Library Files* in Plex. Only files are
scanned; existing items' metadata is not refreshed. The scan runs on the
server after the command has returned.

With *-s*, nothing is scanned; instead the server's background activity is
listed, scans among it, so a scan started earlier can be followed.

# ARGUMENTS

_LIBRARY_
	The library to scan, by numeric ID or title. Required unless *-s* is
	given. With *-s* it is not used, though a title matching no library
	is still an error, since titles are resolved before anything else.

# OPTIONS

*-s*, *--status*
	List the server's current activity instead of scanning: library scans,
	and whatever else the server is busy with.

*-n*, *--now*
	Before starting the scan, cancel every scan pending or running on
	every library, not only on _LIBRARY_, so this one starts at once rather
	than waiting in the queue.

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

*--dry-run*
	Resolve _LIBRARY_ and stop: nothing is cancelled and no scan starts.
	*-s* is unaffected, since listing changes nothing.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-s* takes precedence over everything else: given *-s*, nothing is
  scanned or cancelled, and *-n* is ignored. So is _LIBRARY_, except that
  a title matching no library is still reported as an error.
- Without *-s*, _LIBRARY_ is required.
- *-n* cancels scans on every library, including ones unrelated to
  _LIBRARY_; any of those still wanted must be started again.
- *--dry-run* suppresses *-n*'s cancellation as well as the scan.

# OUTPUT

A scan prints one line on standard output:

```
Rescan triggered for library: 'TV Shows'
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

With no activity, *-s* prints *No active scan jobs.* on standard error.

# EXIT STATUS

*0* on success. *1* when _LIBRARY_ is missing without *-s*, or not found, or
ambiguous. See *plexdo-conventions*(7).

# EXAMPLES

Scan a library after copying new files into it:

```
plexdo rescan "TV Shows"
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

*plexdo-status*(1), *plexdo-find-missing*(1), *plexdo-list-libraries*(1),
*plexdo-conventions*(7), *plexdo*(1)
