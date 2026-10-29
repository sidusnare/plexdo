plexdo-logout(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-logout - sign out of plex.tv and remove the saved tokens and passwords

# SYNOPSIS

*plexdo logout* [*-u* _USERNAME_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Signs out every session saved in the system keyring, or the secrets file
where there is none, and removes each one. Signing out asks plex.tv to
invalidate the token, so a copy of it left behind somewhere, in a backup
for instance, no longer grants anything.

There is one session per username: the one *plexdo-login*(1) saved, and
any saved for the accounts in the configuration's *users* entries when
*plexdo* signed in as them. *-u* signs out just one of them.

Each token is removed only once it is known to be dead: when plex.tv has
signed it out, or when plex.tv already refuses it, as it does a token
signed out elsewhere or a password since changed. A token that could not
be signed out, because plex.tv could not be reached, stays saved, still
valid, so running *logout* again can finish the job.

The password *plexdo login --save-password* saved for an account goes
with its session, since plexdo would otherwise sign the account straight
back in the next time it needed it. A Plex Home PIN saved by
*plexdo-set-pin*(1) is kept.

A token filed under two names is signed out once and removed under both.
When nothing is left, the next command needing a server says to run
*plexdo login*.

*logout* does not need the server, and works when the server is down.

# OPTIONS

*-u*, *--username* _USERNAME_
	Sign out only the session saved under this name: the username or
	email address it was saved under, or *@admin* for a token saved with
	no username known. It matches exactly first, then ignoring case. A
	name with no session is an error that lists the names there are.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table prints one line per session as it is signed out. Any other
	format gives one record per session: see *OUTPUT*.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect.

*-v*, *--verbose*; *--debug*
	*--verbose* reports how many sessions and saved passwords were
	removed, and how many sessions are left; *--debug* adds where secrets
	are kept.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run
	profiled: each phase's time, every HTTP request and its wait, CPU and
	memory use, and function run times. See *DEBUG LOG* in
	*plexdo-conventions*(7).

*--dry-run*
	List the sessions that would be signed out, without contacting plex.tv
	or removing anything.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- Without *-u*, every saved session is signed out, the one every other
  command uses included.
- With *-u*, the other sessions are left exactly as they were.
- No saved session at all is not an error without *-u*: there is nothing
  to sign out. With *-u* it is, since the name is not there.

# OUTPUT

As a table, one line per session:

```
@admin: signed out and removed.
bob: already signed out (plex.tv no longer accepted the token); removed.
carol: could not sign out (...); kept.
```

followed, when no session is left, by a line saying to sign in again.

In any other format, a list of records:

*user*
	The name the session was saved under.

*status*
	*signed out*; *already signed out*, when plex.tv refused the token as
	no longer valid; *failed*, when the token could not be signed out and
	was kept; or *dry run*.

*detail*
	Why a session was already signed out, or why signing it out failed;
	empty otherwise.

# EXIT STATUS

*0* when every session asked for was signed out or was already invalid,
and when there was nothing to sign out. *1* when *-u* names a session there
is not; when the keyring cannot be used; or when any session could not be
signed out, after the others have been removed. *logout* needs neither the
server nor the configuration file. See *plexdo-conventions*(7).

# EXAMPLES

Sign out of everything:

```
plexdo logout
```

Sign out one account, keeping the rest:

```
plexdo logout -u bob@example.com
```

See which sessions are saved, without signing anything out:

```
plexdo logout --dry-run
```

Sign out as part of a script, failing if anything is left valid:

```
plexdo logout --json | jq -r '.[] | "\\(.user) \\(.status)"'
```

# FILES

Where secrets are kept is described under *FILES* in
*plexdo-conventions*(7).

# SEE ALSO

*plexdo-login*(1), *plexdo-set-pin*(1), *plexdo-player-remote-play*(1),
*plexdo-conventions*(7), *plexdo*(1)
