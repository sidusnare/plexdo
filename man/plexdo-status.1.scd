plexdo-status(1) "plexdo" "User Commands"

# NAME

plexdo-status - report what the server is and what it is doing

# SYNOPSIS

*plexdo status* [*--section* _SECTION_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Gathers a consolidated report in eight sections: the server's identity, who
is playing what, the users and accounts it knows, the addresses it can be
reached at, the scans and other work under way, and its scheduled tasks.

Each section is read separately, and one that cannot be read is reported as
a warning and left empty rather than losing the whole report. The reachable
addresses, for instance, need plex.tv, which a server without internet
access cannot reach.

# OPTIONS

*--section* _SECTION_
	Report only one section, named as below. Required for *--format csv*
	and *--format clixml*.

# SECTIONS

*server*
	Its *name*, *version*, *machineIdentifier*, *platform* and
	*platformVersion*, when it was last *updatedAt*, the plex.tv account
	it belongs to (*myPlexUsername*), and whether that account has a Plex
	Pass (*myPlexSubscription*).

*sessions*
	One row per active playback: the *sessionKey*, which *plexdo-wait*(1)
	takes; the *user*; the *library* ID and *ratingKey* of what is
	playing, and its *title*; the player's *state* (playing, paused, or
	buffering); the *player*'s name, *platform*, and *address*; the
	*progress* as position over length; and the *file* the player has
	open. For an item with several versions or parts, *file* is the one
	the session is actually playing.

*users*
	The users the server is shared with: *id*, *type*, *title*,
	*username*, and *email*. *plexdo-list-users*(1) gives the first three.

*accounts*
	The accounts the server itself knows, which is not the same list: *id*,
	*name*, and their default *audioLanguage* and *subtitleLanguage*.

*connections*
	The addresses plex.tv advertises for the server: *uri*, *address*,
	*port*, *protocol*, and whether each is *local*, a *relay*, or *ipv6*.

*scans*
	Library scans and refreshes in progress: *type*, *title*, *subtitle*,
	*progress*, and whether each is *cancellable*.

*activities*
	The server's other background work, such as media analysis, with the
	same fields as *scans*.

*tasks*
	The scheduled maintenance tasks: *name*, *title*, whether each is
	*enabled*, and its *interval*.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	*table* prints every section, or the one chosen, as a titled table,
	with *(none)* for an empty one. *json* and *yaml* give one object keyed
	by section name, or just the chosen section. *csv* and *clixml* are
	flat, so they need *--section*.

*-W*, *--wide*
	Never truncate the tables; file paths and titles are what would
	shrink.

*--throttle* _SECONDS_
	No effect: each section is a request or two, without pacing.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the connection; *--debug* adds the reason a
	section such as *connections* or *tasks* came back empty.

*--dry-run*
	No effect: nothing on the server changes.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--format csv* and *--format clixml* require *--section*: their flat rows
  cannot carry eight sections of different shapes. Without it, they are an
  error before anything is read.
- With *--section*, only that section is read from the server, which is
  quicker, and a failure elsewhere cannot warn.

# EXIT STATUS

*0* on success, even when a section could not be read. *1* when *--format
csv* or *--format clixml* is given without *--section*, or when the server
cannot be reached at all. See *plexdo-conventions*(7).

# EXAMPLES

The whole report, as tables:

```
plexdo status
```

Who is watching what, and the sessionKey of each playback:

```
plexdo status --section sessions
```

Every section as one JSON object, and the server's version from it:

```
plexdo status --json | jq -r '.server.version'
```

The scheduled tasks as CSV, which needs a section:

```
plexdo status --section tasks -f csv
```

Read the sessions from PowerShell:

```
plexdo status --section sessions -f clixml > sessions.xml
Import-Clixml sessions.xml | Format-Table user, title, state
```

Warn when anyone is still watching, from a nightly maintenance script:

```
if [ "$(plexdo status --section sessions --json | jq length)" -gt 0 ]; then
    echo "Someone is still watching; try plexdo wait --all" >&2
fi
```

# SEE ALSO

*plexdo-wait*(1), *plexdo-rescan*(1), *plexdo-list-users*(1),
*plexdo-conventions*(7), *plexdo*(1)
