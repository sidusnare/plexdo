plexdo-logout(1) "plexdo" "User Commands"

# NAME

plexdo-logout - sign out of plex.tv and remove the saved tokens

# SYNOPSIS

*plexdo logout* [*-u* _USERNAME_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Signs out every session in the token store, the file named by
*[plex] token_path* in the configuration, and removes each one from the
file. Signing out asks plex.tv to invalidate the token, so a copy of the
file left behind somewhere, in a backup for instance, no longer grants
anything.

The store holds one token per username: the one *plexdo-login*(1) saved,
and any saved for the accounts in the configuration's per-user sections
when *plexdo* signed in as them. *-u* signs out just one of them.

Each token is removed from the file only once it is known to be dead:
when plex.tv has signed it out, or when plex.tv already refuses it, as it
does a token signed out elsewhere or a password since changed. A token
that could not be signed out, because plex.tv could not be reached, stays
in the file, still valid, so running *logout* again can finish the job.

A token filed under two names is signed out once and removed under both.
When nothing is left, the file itself is deleted, and the next command
needing a server says to run *plexdo login*.

*logout* does not need the server, and works when the server is down.

# OPTIONS

*-u*, *--username* _USERNAME_
	Sign out only the session saved under this name, as the token file
	holds it: the username or email address it was saved under, or
	*@admin* for a token saved by a version of *plexdo* before 1.0.4. It
	matches exactly first, then ignoring case. A name the file does not
	hold is an error that lists the names it does.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table prints one line per session as it is signed out. Any other
	format gives one record per session: see *OUTPUT*.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect.

*-v*, *--verbose*; *--debug*
	*--verbose* reports how many sessions were removed and how many are
	left; *--debug* adds the token file being rewritten or deleted.

*--dry-run*
	List the sessions that would be signed out, without contacting plex.tv
	or changing the file.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- Without *-u*, every session in the file is signed out, the one every
  other command uses included.
- With *-u*, the other sessions are left exactly as they were.
- A store with nothing in it, or no file at all, is not an error without
  *-u*: there is nothing to sign out. With *-u* it is, since the name is
  not there.

# OUTPUT

As a table, one line per session:

```
@admin: signed out and removed.
bob: already signed out (plex.tv no longer accepted the token); removed.
carol: could not sign out (...); kept.
```

followed, when the file is left empty, by a line saying it was removed.

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
and when there was nothing to sign out. *1* when the configuration file is
missing; when *-u* names a session the file does not hold; or when any
session could not be signed out, after the others have been removed. See
*plexdo-conventions*(7).

# EXAMPLES

Sign out of everything:

```
plexdo logout
```

Sign out one account, keeping the rest:

```
plexdo logout -u bob@example.com
```

See which sessions the file holds, without signing anything out:

```
plexdo logout --dry-run
```

Sign out as part of a script, failing if anything is left valid:

```
plexdo logout --json | jq -r '.[] | "\\(.user) \\(.status)"'
```

# FILES

The configuration and the token store are described under *FILES* in
*plexdo-conventions*(7).

# SEE ALSO

*plexdo-login*(1), *plexdo-player-remote-play*(1), *plexdo-conventions*(7),
*plexdo*(1)
