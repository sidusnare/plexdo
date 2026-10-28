plexdo-set-pin(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-set-pin - save or remove a Plex Home member's PIN in the keyring

# SYNOPSIS

*plexdo set-pin* _USER_ID_ [*--remove*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Prompts for the PIN of a member of *plexdo*'s Plex Home, and saves it in
the system keyring: the Secret Service on Linux and BSD, the Keychain on
macOS, Credential Manager on Windows; or the private secrets file where
there is none. The PIN is not echoed.

*plexdo-player-remote-play*(1) needs it to send a command as a
PIN-protected member, such as a managed user signed in on a TV: it
switches into the member through plex.tv as a Plex app's user switcher
does, and plex.tv asks for the PIN then. A member without a PIN needs
nothing saved.

A Plex Home PIN is four digits. An empty answer at the prompt removes any
PIN saved for the member, as *--remove* does.

*set-pin* does not need the server, or the configuration file.

# ARGUMENTS

_USER_ID_
	The member's numeric plex.tv user ID, as *plexdo-list-users*(1) shows
	it. A title is not accepted: the ID is not looked up, so the server is
	not needed.

# OPTIONS

*--remove*
	Remove the PIN saved for the member, without prompting.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table prints one line saying what was done. Any other format gives
	one record: see *OUTPUT*.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect: the server is not contacted.

*-v*, *--verbose*; *--debug*
	*--debug* reports where secrets are kept.

*--dry-run*
	Prompt as the real run would, check the PIN, then save or remove
	nothing, saying on standard error what would be done.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--remove* skips the prompt, so it suits a script.
- An empty answer at the prompt and *--remove* do the same.

# OUTPUT

As a table, one line:

```
Saved the PIN for user 826699965 in the system keyring (SecretService Keyring).
```

In any other format, one record:

*userId*
	The user ID given.

*store*
	Where the PIN was saved, or removed from.

*status*
	*saved*, or *removed*.

# EXIT STATUS

*0* on success, including removing a PIN that was never saved. *1* when
the answer at the prompt is not four digits, or the keyring cannot be
used. *2* when _USER_ID_ is not a number. See *plexdo-conventions*(7).

# EXAMPLES

Save the PIN of a managed user, then send a film to the TV it is signed in
on:

```
plexdo set-pin 826699965
plexdo player-remote-play livingroom-tv.lan 881 --player-user 826699965
```

Remove it again:

```
plexdo set-pin 826699965 --remove
```

# FILES

Where secrets are kept is described under *FILES* in
*plexdo-conventions*(7).

# SEE ALSO

*plexdo-player-remote-play*(1), *plexdo-list-users*(1), *plexdo-login*(1),
*plexdo-logout*(1), *plexdo-conventions*(7), *plexdo*(1)
