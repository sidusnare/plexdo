plexdo-write-config-example(1) "plexdo" "User Commands"

# NAME

plexdo-write-config-example - write a commented configuration template

# SYNOPSIS

*plexdo write-config-example* [*-o*] [_GLOBAL OPTIONS_]

# DESCRIPTION

Writes a commented template of the configuration file to the platform's
configuration path, creating its directory as needed:
_~/.local/etc/plexdo.ini_ on Linux and macOS, and
_%LOCALAPPDATA%\\PlexDo\\plexdo.ini_ on Windows. On POSIX systems the file is
given mode 0600, since it may come to hold a password.

An existing configuration file is never replaced unasked: without *-o* the
command refuses, and writes nothing.

The template sets:

*[plex] url*
	The server's address, *http://localhost:32400* to begin with.

*[plex] token_path*
	Where *plexdo-login*(1) saves tokens: *$XDG_RUNTIME_DIR/.plex.token* on
	POSIX systems, *%TEMP%\\plexdo.token* on Windows, with a note on the
	trade-offs of each.

and shows commented out, ready to enable:

*cache_dir*
	Where the shell completion cache lives, with this platform's default
	filled in.

*username*, *password*
	The account *plexdo login* signs in as, so it needs no prompting.

*[99]*
	An example section for a user's own credentials, used when the server
	refuses the admin account's token for that user. The section is named
	for the user's numeric ID.

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
Config example written to: /home/fred/.local/etc/plexdo.ini
```

# EXIT STATUS

*0* on success, including a *--dry-run*. *1* when a configuration file already
exists and *-o* is not given, or when the directory or file cannot be
written. See *plexdo-conventions*(7).

# EXAMPLES

Set up *plexdo* for the first time:

```
plexdo write-config-example
${EDITOR:-vi} ~/.local/etc/plexdo.ini
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
cp ~/.local/etc/plexdo.ini ~/.local/etc/plexdo.ini.bak
plexdo write-config-example --overwrite
```

# SEE ALSO

*plexdo-login*(1), *plexdo-conventions*(7), *plexdo*(1)
