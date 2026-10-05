plexdo-conventions(7) "plexdo" "Miscellaneous Information Manual"

# NAME

plexdo-conventions - options, names, and output shared by every plexdo command

# DESCRIPTION

Each *plexdo* command has a page of its own, *plexdo-*_COMMAND_(1). This page
covers what they all share: the global options, how users, libraries,
playlists, and items are named on the command line, the output formats, the
rewriting of exported paths, request pacing, exit status, and the files
*plexdo* reads and writes.

# GLOBAL OPTIONS

Every command accepts these, and they may be given either before or after
the command name: *plexdo --json list-users* and *plexdo list-users --json*
are the same command. Each command page says what each option means for that
command in particular.

*-f*, *--format* _FORMAT_
	Output format: *table* (the default), *json*, *yaml*, *csv*, or
	*clixml*. See *OUTPUT FORMATS* below.

*--json*
	Shorthand for *--format json*. Both write the same setting, so when
	both are given the one parsed last wins; options after the command
	name are parsed after those before it.

*-W*, *--wide*
	Never shrink table columns to fit the terminal. Without it the widest
	column is truncated, repeatedly, until a row fits on one line.
	Output that is not going to a terminal is never truncated either way,
	so a file or a pipe always receives every character.

*--throttle* _SECONDS_
	The pause between requests in loops that make one request per
	element, once there are more than 50 elements. Default 0.25; *0*
	turns pacing off. See *PACING* below.

*-v*, *--verbose*
	Report high-level progress on standard error.

*--debug*
	Report detailed internal logging on standard error. Implies
	everything *--verbose* shows.

*--dry-run*
	For a command that changes Plex: do everything up to the change,
	show what would be done, and stop. It concerns Plex only: a file a
	command writes, such as an M3U export, is written either way. Each
	command page says exactly what *--dry-run* does there.

*-V*, *--version*
	Print the installed version and exit.

*-h*, *--help*
	Print help, for *plexdo* or for the command it follows, and exit.

# NAMING THINGS ON THE COMMAND LINE

## Users

An argument shown as _USER_ takes either a numeric user ID or a user's
title, as *plexdo-list-users*(1) lists them. *0* is the admin account
itself, whose own title works too. The rules, in order:

- A title matches exactly first, and only then ignoring case.
- A title matching more than one user is an error that lists the
  matching IDs; pass the ID instead.
- A number that is a real user ID selects that user. If it is also
  another user's title, a warning names the user not selected.
- A number that is not a user ID but is a title selects by title.
- A number matching nothing is passed on, and the command then reports
  *User ID not found*.
- Anything else matching nothing is an error pointing at
  *plexdo list-users*.

Plex scopes every token to what its user can see, and being the server
admin does not override that. A user with no libraries shared to them
cannot be acted on at all. A command acting for one user stops with an
explanation; a command looping over users reports the user as skipped and
carries on. If such a user does have access under their own login, a
config section named for their user ID holding their *username* and
*password* is used automatically, and the token it yields is saved so the
login happens once. See *FILES*.

## Libraries

An argument shown as _LIBRARY_ takes a numeric library ID or a library
title, as *plexdo-list-libraries*(1) lists them, under exactly the rules
for users above; the error for an unknown title points at
*plexdo list-libraries*.

## Playlists

An argument shown as _PLAYLIST_ that names an existing playlist takes its
title or its ratingKey, as *plexdo-list-playlists*(1) lists them. A value
made only of digits is always taken as a ratingKey, so a playlist whose
title is a number can only be named by its ratingKey. A title must match
exactly. A ratingKey belonging to something other than a playlist is an
error.

## Items

An argument shown as _ratingKey_ is the numeric key Plex gives every show,
season, episode, film, track, and photo. *plexdo-list-titles*(1),
*plexdo-list-show*(1), *plexdo-search*(1), and *plexdo-show-metadata*(1)
all report them. Items are named by ratingKey only; titles are not
accepted, since many items share one.

## Sessions

A _sessionKey_ identifies one active playback. *plexdo status --section
sessions* lists them; *plexdo-wait*(1) takes one.

# OUTPUT FORMATS

Results go to standard output; logging, warnings, and errors go to
standard error, so machine-readable output is always safe to pipe.

*table*
	Box-drawn and width-aligned, allowing for characters that occupy two
	columns. A console whose encoding cannot draw the box characters gets
	the same table drawn with *+*, *-*, and *|*. Fitted to the terminal
	width unless *--wide* is given or the output is not a terminal.

*json*
	One JSON document. Characters outside ASCII are escaped, so it prints
	on any console.

*yaml*
	One YAML document. Strings are always double-quoted, so that a title
	such as *NO* or *1.10* reads back as a string rather than a boolean or
	a number.

*csv*
	A header row, then one row per record, with *\\n* line endings.
	Nested values are flattened to text.

*clixml*
	PowerShell CLIXML, readable by *Import-Clixml*, with typed properties.

A command emitting one record and a command emitting many share the same
formats. *plexdo-wait*(1) reports as it goes rather than once at the end:
there, *json* is one line per record, *yaml* one document per record, *csv*
a single header, and *clixml*, which cannot be streamed, is refused.

# REWRITING EXPORTED PATHS

M3U files and photo galleries carry the paths the Plex server itself uses
for its media files, not HTTP URLs. Where the files are reached some other
way (an SMB share, another mount point, a Windows drive letter) the commands
that export take *-p*, *--prefix* _PREFIX_:

- The library root at the start of each path is replaced by _PREFIX_.
- When one library lies inside another's directory, the longest matching
  root is the one replaced.
- The rest of the path is joined using _PREFIX_'s own separator, so a
  Windows prefix produces backslashes throughout.
- A path under no library root is appended whole to _PREFIX_, with a
  warning the first time only.

Because the library root is what is replaced, one prefix maps every library
to the same place; export libraries separately if they are mounted apart.
Without *--prefix* the server's paths are written unchanged, and no extra
request is made.

# PACING

Walking a large library one item at a time, or changing many items one at a
time, is one request per element. Once a loop has more than 50 elements,
*plexdo* waits *--throttle* seconds between requests, 0.25 by default. The
pause goes between elements, so _n_ elements wait _n_-1 times, and a run of
50 or fewer is never paced. A paced run is announced once, at *--verbose*
level, with its expected duration. *--throttle 0* turns pacing off. Each
command page says which of its loops are paced.

# EXIT STATUS

*0*
	Success.

*1*
	An error, reported on standard error: missing configuration or token,
	a user, library, item, or playlist not found, an ambiguous title, a
	refused name collision, an unsupported combination of options, or a
	request the server refused.

*2*
	The command line itself could not be understood: an unknown command or
	option, a missing argument, or a value of the wrong kind.

*130*
	*plexdo-wait*(1) was interrupted before the play it was waiting for was
	over.

# FILES

_~/.local/etc/plexdo.ini_, or _%LOCALAPPDATA%\\PlexDo\\plexdo.ini_ on Windows
	The configuration: the server URL in *[plex] url*, where the token
	store lives in *[plex] token_path*, and optionally *cache_dir*,
	*username*, and *password*. A section named for a numeric user ID
	holds that user's own *username* and *password*. Environment
	variables are expanded in every *[plex]* value. A warning is printed
	when the file is readable by group or other. *plexdo
	write-config-example* writes a commented template.

_$XDG_RUNTIME_DIR/.plex.token_, or _%TEMP%\\plexdo.token_ on Windows
	The default token store: a JSON object mapping each username to its
	token, written by *plexdo login* with mode 0600.

_~/.cache/plexdo/_, or _%LOCALAPPDATA%\\PlexDo\\Cache\\_ on Windows
	The shell completion cache, written as a side effect of listing:
	_libraries.json_, _users.json_, _titles.LIBRARY.json_, and
	_playlists.USER.json_, keyed by numeric ID. *[plex] cache_dir* moves
	it.

# ENVIRONMENT

*XDG_RUNTIME_DIR*
	Referenced by the default POSIX token path: a private tmpfs on most
	Linux systems, cleared at logout, so *plexdo login* is needed again
	after a reboot.

*LOCALAPPDATA*, *APPDATA*
	On Windows, where the configuration and cache live; *APPDATA* is used
	when *LOCALAPPDATA* is unset.

*TEMP*
	On Windows, referenced by the default token path.

# SEE ALSO

*plexdo*(1), and a page per command:
*plexdo-list-libraries*(1), *plexdo-list-titles*(1), *plexdo-list-show*(1),
*plexdo-export-titles*(1), *plexdo-find-missing*(1), *plexdo-search*(1),
*plexdo-list-users*(1), *plexdo-list-playlists*(1),
*plexdo-list-playlist*(1), *plexdo-export-playlist*(1),
*plexdo-remove-playlist*(1), *plexdo-append-playlist*(1),
*plexdo-clean-playlist*(1), *plexdo-show-metadata*(1), *plexdo-read*(1),
*plexdo-rescan*(1), *plexdo-status*(1), *plexdo-wait*(1),
*plexdo-build-interleaved*(1), *plexdo-build-chronological*(1),
*plexdo-build-randomize*(1), *plexdo-build-concatenated*(1),
*plexdo-copy-playlist-all-users*(1), *plexdo-copy-playlist-to-user*(1),
*plexdo-copy-watched*(1), *plexdo-login*(1), and
*plexdo-write-config-example*(1).
