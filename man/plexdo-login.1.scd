plexdo-login(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-login - sign in to plex.tv and save the token every other command uses

# SYNOPSIS

*plexdo login* [*-u* _USERNAME_] [*-p* _PASSWORD_] [*--save-password*]
\[*-c* _CODE_ | *-2*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Signs in to plex.tv with a Plex account's username and password, and saves
the resulting token in the system keyring: the Secret Service on Linux and
BSD, the Keychain on macOS, Credential Manager on Windows. Every other
command uses that token to reach the server; none of them handles the
password. Where there is no keyring, the token goes in a private file
instead, with a warning; see *FILES* in *plexdo-conventions*(7).

Tokens are filed by username, so signing in as several accounts keeps each
one's token; that is how an account in the configuration's *users* entries
is signed in. A token survives a reboot. After saving, the token is tried
against the server at *plex: url*; a failure there is reported as a
warning, and the token is kept.

The configuration file must exist first: *plexdo-write-config-example*(1)
creates one.

## Where the credentials come from

The username is *-u*, else *plex: username* in the configuration, else
prompted for. The password is *-p*, else the one saved for that username
by an earlier *--save-password*, else prompted for. A saved password is
filed by username, so it is never paired with another account.

A prompted password is not echoed. A password is never read from the
configuration file: one left there by plexdo 1.x is ignored with a
warning, and the first run moves it to the keyring by itself.

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
	warns each time it is used. Prefer the prompt.

*--save-password*
	Save the password in the keyring alongside the token, so that plexdo
	can sign the account in again by itself once the token stops working,
	as a per-user command does for an account in *users*. Without it the
	password is used once and forgotten. *plexdo-logout*(1) removes it
	again.

*-c*, *--code* _CODE_
	The current two-factor authentication code, for an account that has
	two-factor authentication turned on.

*-2*, *--two-factor*
	Prompt for the two-factor code rather than giving it on the command
	line.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table prints where the token was saved, whether the password was
	too, and, when it worked, the server it was verified against. Any other
	format gives one record with *user*, *store*, *verified*, and
	*passwordSaved*.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the sign-in being made; *--debug* adds whether a
	saved password was used, and where secrets are kept.

*--dry-run*
	Sign in to plex.tv for real, to prove the credentials work, but save
	nothing: where the token, and with *--save-password* the password,
	would go is printed on standard error.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-p* overrides a saved password.
- *--save-password* saves whichever password signed in, given, saved, or
  prompted for.
- *-c* and *-2* both supply a two-factor code. Given *-c*, *-2* has no
  effect and nothing is prompted for.
- An account with two-factor authentication turned on needs one of them:
  without, plex.tv refuses the sign-in, and the error suggests *--code*.

# EXIT STATUS

*0* on success, even when the token could not be verified against the
server. *1* when the configuration file is missing or has no *plex: url*,
when no username or password is given at a prompt, when plex.tv refuses
the credentials or needs a two-factor code, or rejects the sign-in for
another reason, or when the keyring cannot be used. See
*plexdo-conventions*(7).

# EXAMPLES

Sign in, being prompted for the username and password:

```
plexdo login
```

Sign in as a named account, being prompted for the password only:

```
plexdo login -u fred@example.com
```

Sign in another account, listed under *users* in the configuration, and
let plexdo sign it in again by itself when its token stops working:

```
plexdo login -u bob@example.com --save-password
```

Sign in to an account with two-factor authentication, prompting for the
code:

```
plexdo login -u fred@example.com -2
```

Check that the credentials work, without saving anything:

```
plexdo login --dry-run
```

# FILES

The configuration and where secrets are kept are described under *FILES*
in *plexdo-conventions*(7).

# SEE ALSO

*plexdo-logout*(1), *plexdo-set-pin*(1), *plexdo-write-config-example*(1),
*plexdo-conventions*(7), *plexdo*(1)
