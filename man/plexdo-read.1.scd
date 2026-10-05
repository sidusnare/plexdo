plexdo-read(1) "plexdo" "User Commands"

# NAME

plexdo-read - stream a media file to standard output

# SYNOPSIS

*plexdo read* _LIBRARY_ _ratingKey_ [_GLOBAL OPTIONS_]

# DESCRIPTION

Streams the file behind one item from the server to standard output,
unchanged, for piping into a player or redirecting to a file. Nothing is
transcoded: the bytes are the file the server holds.

Quitting the player before the end is not an error; *plexdo* stops quietly
when the pipe closes. Run in a terminal without a pipe or redirection, a
warning suggests piping into a player instead, since the media would
otherwise be written to the screen.

When an item has several versions or a version is split across several
files, only the first file of the first version is streamed, with a warning.
*plexdo-show-metadata*(1) lists them all.

# ARGUMENTS

_LIBRARY_
	The library the item belongs to, by numeric ID or title. It must be the
	item's own library: a mismatch is an error, which guards against
	streaming the wrong thing from a mistyped ratingKey.

_ratingKey_
	The item to stream, as *plexdo-list-titles*(1), *plexdo-list-show*(1),
	or *plexdo-search*(1) report it. It must be something with a file: an
	episode, film, track, or photo, not a show or season.

# OPTIONS

None beyond the global options.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	No effect: standard output carries the media itself. Giving a format
	other than *table* draws a warning saying so.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect: the file is one continuous request.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the item, its server-side path, and the URL it is
	streamed from. That URL carries the access token: do not share
	verbose output.

*--dry-run*
	Resolve the item and print its title, server-side path, and streaming
	URL on standard error instead of streaming it. The URL carries the
	access token, so treat it as a password: anyone holding it can use the
	server as the admin account.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

None: the command takes no options of its own.

# OUTPUT

The media file, byte for byte, on standard output.

# EXIT STATUS

*0* on success, including when the player closes the pipe early. *1* when
the library or item is not found, when the item belongs to another library,
when it has no file, or when the server refuses the download. See
*plexdo-conventions*(7).

# EXAMPLES

Play an episode in *mpv*(1), which reads standard input given *-*:

```
plexdo read "TV Shows" 4180 | mpv -
```

Save a film to a local file:

```
plexdo read Movies 881 > heat.mkv
```

On Linux with a display attached but no desktop environment, *mpv*(1) can
draw straight to the console through the kernel's modesetting driver, so
playback needs neither X nor Wayland. Run it from a virtual terminal rather
than a terminal emulator, as a user who can reach the DRM device, usually by
being in the *video* group:

```
plexdo read 2 4180 | mpv --vo=drm -
```

Listen to a track in a player that reads standard input:

```
plexdo read Music 5520 | ffplay -nodisp -autoexit -
```

Check what would be streamed, without streaming it:

```
plexdo read Movies 881 --dry-run
```

# SEE ALSO

*plexdo-show-metadata*(1), *plexdo-list-show*(1), *mpv*(1),
*plexdo-conventions*(7), *plexdo*(1)
