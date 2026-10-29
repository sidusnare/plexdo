plexdo-write-config-example(1) "plexdo" "User Commands"
; SPDX-FileCopyrightText: 2026 SidusNare
; SPDX-License-Identifier: GPL-3.0-or-later
; SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

# NAME

plexdo-write-config-example - write a commented configuration template

# SYNOPSIS

*plexdo write-config-example* [*-o*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Writes a commented template of the configuration file to the platform's
configuration path, creating its directory as needed:
_$XDG_CONFIG_HOME/plexdo/config.yaml_, by default
_~/.config/plexdo/config.yaml_, on Linux, BSD, and macOS, and
_%LOCALAPPDATA%\\PlexDo\\config.yaml_ on Windows. The file is YAML, and
holds no secret; on POSIX systems it is given mode 0600 all the same.

An existing configuration file is never replaced unasked: without *-o* the
command refuses, and writes nothing.

Every option is explained in the file itself: its meaning, the values it
takes, and its default. The template sets:

*plex: url*
	The server's address, *http://localhost:32400* to begin with.

and shows commented out, each with its default, ready to enable:

*plex: username*
	The account *plexdo-login*(1) signs in as, and whose token every
	command uses.

*plex: cache_dir*
	Where the shell completion cache lives, with this platform's default
	filled in.

*plex: secret_store*, *plex: secrets_file*
	Where tokens, saved passwords, and PINs are kept: the system keyring,
	or a private file where there is none.

*users*
	An example entry for another account, keyed by its numeric user ID,
	used when the server refuses the admin account's token for that user,
	and by *plexdo-player-remote-play*(1).

Passwords, tokens, and PINs never go in the file: see *plexdo-login*(1)
and *plexdo-set-pin*(1).

*plexdo write-config-example --help* prints the exact template that would be
written, without writing anything. The settings themselves are described
under *FILES* in *plexdo-conventions*(7).

# OPTIONS

*-o*, *--overwrite*
	Replace an existing configuration file with the template, instead of
	refusing to. Whatever the old file held is lost, so copy it aside first
	if any of it is worth keeping.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	No effect: the command prints one plain line naming the file, in any
	format.

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
	Write nothing, and say on standard error where the template would be
	written and whether that would create the file or replace one. An
	existing file without *-o* is still refused, just as the real run would
	refuse it.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help with the full template, and
	exit without writing anything.

# OPTION INTERACTIONS

- Without *-o*, an existing configuration file is an error, and nothing is
  written; *--dry-run* refuses it the same way.
- With *-o*, an existing file is replaced; with *--dry-run* as well, it is
  only reported as what would be replaced.
- *-o* makes no difference when there is no configuration file yet.

# OUTPUT

One line on standard output when the file is written:

```
Config example written to: /home/fred/.config/plexdo/config.yaml
```

# EXIT STATUS

*0* on success, including a *--dry-run*. *1* when a configuration file already
exists and *-o* is not given, or when the directory or file cannot be
written. See *plexdo-conventions*(7).

# EXAMPLES

Set up *plexdo* for the first time:

```
plexdo write-config-example
${EDITOR:-vi} ~/.config/plexdo/config.yaml
plexdo login
plexdo list-libraries
```

Read the template without writing it:

```
plexdo write-config-example --help
```

Check where it would go, and whether anything would be replaced:

```
plexdo write-config-example --dry-run
```

Start again from the template, keeping the old configuration aside:

```
cp ~/.config/plexdo/config.yaml ~/.config/plexdo/config.yaml.bak
plexdo write-config-example --overwrite
```

# SEE ALSO

*plexdo-login*(1), *plexdo-conventions*(7), *plexdo*(1)
