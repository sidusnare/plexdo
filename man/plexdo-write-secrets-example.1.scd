plexdo-write-secrets-example(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-write-secrets-example - write, or print, an example secrets file

# SYNOPSIS

*plexdo write-secrets-example* [*-o*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Writes an example of the secrets file to the path *plex: secrets_file* names
in the configuration file, creating its directory as needed. On POSIX
systems the file is created with mode 0600, readable by your account alone.

When *plex: secrets_file* is not set, which includes there being no
configuration file at all, nothing is written. Standard error says so, and
the example is printed to standard output instead, so it can be read or
redirected to a file of your choosing.

An existing secrets file is never replaced unasked: without *-o* the command
refuses, and writes nothing, since that file may hold the only copy of a
saved password or PIN.

The example is the secrets file as it is with *plex: secret_store* set to
*file*: the store of saved passwords and Plex Home PINs. Session tokens are
not in it; with that setting they are kept in a session file of their own,
which *plexdo-login*(1) writes. See *SECRETS* in *plexdo*(1), and *FILES*
in *plexdo-conventions*(7). It is JSON, with one object for each kind:

*passwords*
	Passwords, by username, as *plexdo login --save-password* saves them.

*pins*
	Plex Home PINs, by numeric user ID, as *plexdo-set-pin*(1) saves them.

The example holds one placeholder entry of each kind, and a *\_comment*
entry saying so, which *plexdo* ignores and keeps. Every value in it is a
placeholder: replace each with a real one, or delete the entries and let
*plexdo login --save-password* and *plexdo-set-pin*(1) fill the file in. A
placeholder left in place does no harm until that account is signed in
without a prompt, when plex.tv refuses the password.

Where the secrets file is used only because there is no keyring, with
*secret_store* left at *auto*, it holds a *tokens* object as well, which
*plexdo-login*(1) adds.

*plexdo write-secrets-example --help* prints the exact example, without
writing anything.

# OPTIONS

*-o*, *--overwrite*
	Replace an existing secrets file with the example, instead of
	refusing to. Every secret the old file held is lost, so copy it aside
	first if any of them is worth keeping.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	No effect: the example is JSON whatever the format, and writing it
	prints one plain line naming the file.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect: the server is not contacted.

*-v*, *--verbose*; *--debug*
	No effect: there is nothing more to report.

*--debug-log* _PATH_
	Appends what *--debug* reports to _PATH_ instead, with the run's
	time, CPU and memory use, and function run times. There are no HTTP
	requests to record. See *DEBUG LOG* in *plexdo-conventions*(7).

*--dry-run*
	Write nothing, and say on standard error where the example would be
	written and whether that would create the file or replace one. An
	existing file without *-o* is still refused, just as the real run
	would refuse it. No effect when *plex: secrets_file* is not set, since
	nothing is written then anyway.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help with the full example, and
	exit without writing anything.

# OPTION INTERACTIONS

- Without *-o*, an existing secrets file is an error, and nothing is
  written; *--dry-run* refuses it the same way.
- With *-o*, an existing file is replaced; with *--dry-run* as well, it is
  only reported as what would be replaced.
- *-o* makes no difference when there is no secrets file yet, or when
  *plex: secrets_file* is not set.

# OUTPUT

When *plex: secrets_file* is set, one line on standard output once the file
is written:

```
Secrets example written to: /home/fred/.local/state/plexdo/secrets.json
```

When it is not set, a note on standard error, and the example on standard
output:

```
{
  "_comment": [
    "Example plexdo secrets file: every value is a placeholder.",
    "Replace each with a real one, or delete this file and let",
    "plexdo login --save-password and plexdo set-pin write it.",
    "Session tokens are not kept here. Keep this file readable",
    "by your account alone."
  ],
  "passwords": {
    "you@example.com": "your-plex.tv-password"
  },
  "pins": {
    "12345678": "0000"
  }
}
```

# EXIT STATUS

*0* on success, including a *--dry-run*, and when the example was printed
because *plex: secrets_file* is not set. *1* when a secrets file already
exists and *-o* is not given, when the configuration file cannot be read or
is not valid, or when the directory or file cannot be written. See
*plexdo-conventions*(7).

# EXAMPLES

See what a secrets file looks like:

```
plexdo write-secrets-example
```

Keep secrets in a file of your choosing, starting from the example. In the
configuration file:

```
plex:
  secret_store: file
  secrets_file: ~/.config/plexdo/secrets.json
```

then:

```
plexdo write-secrets-example
${EDITOR:-vi} ~/.config/plexdo/secrets.json
```

With no *plex: secrets_file* set, save the example somewhere by hand,
private from the start:

```
(umask 077; plexdo write-secrets-example > secrets.json)
```

Check where it would go, and whether anything would be replaced:

```
plexdo write-secrets-example --dry-run
```

# SEE ALSO

*plexdo-write-config-example*(1), *plexdo-login*(1), *plexdo-set-pin*(1),
*plexdo-conventions*(7), *plexdo*(1)
