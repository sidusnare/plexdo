plexdo-login(1) "plexdo" "User Commands"

# NAME

plexdo-login - sign in to plex.tv and save the token every other command uses

# SYNOPSIS

*plexdo login* [*-u* _USERNAME_] [*-p* _PASSWORD_] [*-c* _CODE_ | *-2*]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Signs in to plex.tv with a Plex account's username and password, and saves
the resulting token in the token store named by *[plex] token_path* in the
configuration. Every other command uses that token to reach the server; none
of them handles the password.

The store is a JSON file holding one token per username, written with mode
0600 on POSIX systems, so signing in as several accounts keeps each one's
token. After saving, the token is tried against the server at *[plex] url*;
a failure there is reported as a warning, and the token is kept.

The configuration file must exist first: *plexdo-write-config-example*(1)
creates one.

## Where the credentials come from

- *-u* given: that username is used, and any password in the configuration
  is ignored, since pairing it with a different username would be a silent
  mismatch. The password comes from *-p*, or a prompt.
- *-u* not given, but *[plex] username* set: that username is used, with
  the password from *-p*, or *[plex] password*, or a prompt, in that order.
- Neither: both are prompted for.

A prompted password is not echoed.

# OPTIONS

*-u*, *--username* _USERNAME_
	The Plex account's username or email address. This is a plex.tv
	login, not a _USER_ as other commands take: an ID or a display name
	does not work here.

*-p*, *--password* _PASSWORD_
	The account's password. Avoid it: a password on the command line is
	recorded in shell history and visible to other users in the process
	list while the command starts. *plexdo* overwrites it in its own
	process title as soon as it can, which is not possible on Windows, and
	warns each time it is used. Prefer the prompt, or *[plex] password* in
	a configuration file readable only by its owner.

*-c*, *--code* _CODE_
	The current two-factor authentication code, for an account that has
	two-factor authentication turned on.

*-2*, *--two-factor*
	Prompt for the two-factor code rather than giving it on the command
	line.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table prints where the token was saved and, when it worked, the
	server it was verified against. Any other format gives one record with
	*token_path* and *verified*.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the sign-in being made; *--debug* adds where the
	username came from and where the token was written.

*--dry-run*
	Sign in to plex.tv for real, to prove the credentials work, but write
	nothing: the path the token would go to is printed on standard error.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-u* makes the configuration's password unused, even when *-p* is not
  given; the password is then prompted for.
- *-p* overrides any password in the configuration.
- *-c* and *-2* both supply a two-factor code. Given *-c*, *-2* has no
  effect and nothing is prompted for.
- An account with two-factor authentication turned on needs one of them:
  without, plex.tv refuses the sign-in, and the error suggests *--code*.

# EXIT STATUS

*0* on success, even when the token could not be verified against the
server. *1* when the configuration file is missing, when no username or
password is given at a prompt, when plex.tv refuses the credentials or
needs a two-factor code, or when it rejects the sign-in for another reason.
See *plexdo-conventions*(7).

# EXAMPLES

Sign in, being prompted for the username and password:

```
plexdo login
```

Sign in as a named account, being prompted for the password only:

```
plexdo login -u fred@example.com
```

Sign in to an account with two-factor authentication, prompting for the
code:

```
plexdo login -u fred@example.com -2
```

Check that the configured credentials work, without saving anything:

```
plexdo login --dry-run
```

Sign in again after a reboot, when the default token store lives in a
directory cleared at logout; with the username and password in the
configuration, nothing is prompted for:

```
plexdo login
```

# FILES

The configuration and the token store are described under *FILES* in
*plexdo-conventions*(7).

# SEE ALSO

*plexdo-write-config-example*(1), *plexdo-conventions*(7), *plexdo*(1)
