plexdo-wait(1) "plexdo" "User Commands"

# NAME

plexdo-wait - sleep until a session's current play, or every play, is over

# SYNOPSIS

*plexdo wait* [*-s* _KEY_] [*-r* _KEY_ [*--now*]] [*-i* _SECONDS_]
\[*--fast-interval* _SECONDS_] [*--no-credits*] [*--offset* _SECONDS_]
\[*--paused* _SECONDS_] [_GLOBAL OPTIONS_]

*plexdo wait* *-a* [*-i* _SECONDS_] [*--fast-interval* _SECONDS_]
\[*--no-credits*] [*--offset* _SECONDS_] [*--paused* _SECONDS_]
\[_GLOBAL OPTIONS_]

# DESCRIPTION

Sleeps until a play on the server is over, then exits 0, so that whatever
follows *&&* runs once the viewer is done:

```
plexdo wait && sudo systemctl restart plexmediaserver
```

By default the first session listed is followed, and the wait is for
whatever it is playing when the command starts.

## When a play is over

A play is over at the first of these:

- *Its end point.* Playback reaches the start of the end credits, when Plex
  has a credits marker for the video, or the end of the video otherwise.
  Where a film carries two credits markers around a mid-credits scene, the
  final one is used, so the scene is not cut off. *--no-credits* ignores
  the marker and uses the end of the video; *--offset* can move the point.
- *It stops.* The viewer quits, or autoplay moves on to the next video:
  either way, the video waited for is no longer playing, wherever playback
  had got to.
- *It sits paused*, with *--paused*, for that many seconds.

## Polling

The server is asked every 10 seconds (*-i*) until playback is within 30
seconds of the end point, or past it, and every second (*--fast-interval*)
from then on, so the end is noticed within about a second. Each delay
varies by up to 20% either way. A long *-i* never sleeps past the start of
those last 30 seconds, nor past the moment an allowed pause runs out.

A poll that fails is reported and retried; five failures in a row end the
wait with an error.

## Progress

Every poll prints a line naming the session's user, what it is playing, the
video waited for, the playback position, the time waited so far, and the
estimated time left:

```
Waiting for "The Wire - The Target" (Alice) to reach the credits at 55:40.
Alice | playing: The Wire - The Target | waiting for: The Wire - The Target
    | 55:00 / 58:12 | waited 0:00 | ~0:40 left
Alice | playing: The Wire - The Target | waiting for: The Wire - The Target
    | 55:41 / 58:12 reached | waited 0:12 | done
"The Wire - The Target" reached its end point.
```

Each update is a single line; they are wrapped above only to fit this page.

## Waiting for everything

With *-a*, every session on the server is followed at once, each judged on
its own video by the same rules, with a line per session each poll. A
session that disappears is reported once as *stopped*. The wait ends only
when two polls a normal interval apart both find nothing left to wait for:
the second is what catches a play started in the meantime, an autoplayed
next episode or a new viewer, which is then waited for too. That second look
is taken even when nothing was playing to begin with.

# OPTIONS

*-s*, *--session* _KEY_
	Follow the session with this sessionKey, as *plexdo status --section
	sessions* lists them, instead of the first one listed. Its user is
	followed from then on: a stop ends the wait, but a stop and restart
	falling between two polls is recognised as the same play, even though
	the restart has a new sessionKey.

*-r*, *--rating-key* _KEY_
	Wait for this video, by ratingKey, rather than whatever is playing.
	Without *-s*, whichever session is playing it is followed. If nobody
	is, every poll says so, naming what the user is watching instead, and
	the wait lasts until the video starts and is then over.

*-a*, *--all*
	Wait for every play by every user to be over. See *Waiting for
	everything* above.

*-i*, *--interval* _SECONDS_
	Seconds between polls before the last 30 seconds, varied by up to 20%
	either way. Default 10. It must be above zero; fractions are allowed.
	Under *-a* it is also the delay before the confirming second look.

*--fast-interval* _SECONDS_
	Seconds between polls from 30 seconds before the end point on,
	likewise varied by up to 20%. Default 1. It must be above zero.

*--no-credits*
	Ignore the end credits marker and wait for the video itself to end.

*--offset* _SECONDS_
	A whole number of seconds, which may be negative. Negative ends the
	wait that many seconds before the end point: before the start of the
	credits, or before the end with *--no-credits* or no marker. Positive
	leaves the end point alone and sleeps that many seconds once the wait
	is over, whichever way it ended. Default 0.

*--paused* _SECONDS_
	Count a play as over once its player has sat paused this many seconds:
	someone fell asleep, or walked away. Plex does not report when a pause
	began, so the count starts at the first poll that sees it, and may
	begin up to one interval after the pause did. Any other state resets
	the count. *0* ends the play at the first sight of a pause.

*--now*
	With *-r*: if the video is not playing on the first poll, exit 0 at
	once instead of waiting for it to start.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	*table* prints the progress lines shown above. In a machine-readable
	format every poll is one record, flushed as it is written so a pipe
	sees each at once: *json* as one line per record, *yaml* as one
	document per record, and *csv* as one row per record under a single
	header. The opening and closing lines then go to the log instead.
	*clixml* cannot be streamed, since *Import-Clixml* reads one whole
	document, and is refused.

*-W*, *--wide*
	No effect: progress lines are not truncated.

*--throttle* _SECONDS_
	No effect: polling is timed by *-i* and *--fast-interval*, not paced.

*-v*, *--verbose*; *--debug*
	*--verbose* shows the opening and closing lines in a machine-readable
	format, where they would otherwise be hidden. A failed poll is warned
	about whatever the setting.

*--dry-run*
	No effect: waiting changes nothing on the server.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *-a* waits for every session, so it takes neither *-s* nor *-r*; giving
  either with it is an error.
- *--now* only applies with *-r*. Without *-r* the video waited for is the
  one already playing, so *--now* alone is an error.
- *-s* and *-r* together follow the user of session _KEY_ and wait for
  them to play video _KEY_, which they may not be playing yet.
- *--offset* below zero is measured from whichever end point applies: the
  credits by default, the end of the video with *--no-credits* or when
  there is no marker. An offset larger than the end point ends the wait
  at once.
- *--offset* above zero is added after any ending: the end point, a stop,
  or a pause under *--paused*. Without *-a* it is not added when *--now*
  gives up, nor when nothing was playing at all; with *-a* it always is.
- *--paused* and *--offset* apply to every play under *-a*.
- *--fast-interval* is used near the end point whatever *-i* is, even when
  it is the longer of the two.

# OUTPUT

In a machine-readable format, each record carries every one of these keys,
so CSV columns stay fixed:

*user*, *sessionKey*
	The session's user and key, empty when nothing is playing.

*playing*
	What the session is playing now.

*waitingFor*, *ratingKey*
	The video waited for, and its ratingKey.

*state*
	*playing*, *paused*, or *buffering* while the video plays; *not
	started* when it has not begun yet; *nothing playing* under *-a*
	with no sessions at all; and, once the play is over, *reached*,
	*stopped*, or *left paused*.

*position*, *duration*, *target*
	The playback position, the video's length, and the end point, in
	seconds.

*pausedFor*
	Seconds seen paused, while paused.

*elapsed*
	Seconds waited so far.

*remaining*
	Estimated seconds until the wait is over, including any positive
	*--offset*. While paused under *--paused*, it is the time the pause has
	left, since the position is not moving.

# EXIT STATUS

*0*
	The wait is over; or nothing was playing, so there was nothing to wait
	for; or *--now* found the video not playing.

*1*
	*-s* names no active session (the active sessionKeys are listed, so a
	typo cannot let *&&* run); *-r* names no item; *-a* is combined with
	*-s* or *-r*; *--now* is given without *-r*; *--format clixml* is
	given; or five polls in a row failed.

*2*
	An option value is invalid: an interval of zero or below, a fractional
	*--offset*, or a negative *--paused*.

*130*
	The wait was interrupted, with Ctrl-C, before the play was over, so a
	command chained with *&&* does not run.

# EXAMPLES

Restart the server once the current episode reaches its credits:

```
plexdo wait && sudo systemctl restart plexmediaserver
```

Wait through the credits to the very end of the video:

```
plexdo wait --no-credits
```

Start a backup two minutes before the credits, to give it a head start:

```
plexdo wait --offset -120 && start-backup
```

Give the viewer a minute after the play ends before acting:

```
plexdo wait --offset 60 && sudo poweroff
```

Follow a particular session, found with *status*:

```
plexdo status --section sessions
plexdo wait -s 42
```

Wait for a film that has not been started yet to be watched, or, from a
scheduled job, act straight away if it is not playing right now:

```
plexdo wait -r 881
plexdo wait -r 881 --now && echo "Heat is not on (or has finished)"
```

Treat a ten-minute pause as the viewer having gone to bed:

```
plexdo wait --paused 600 && sudo poweroff
```

Reboot once nobody at all is watching anything, giving a binge's next
episode 30 seconds to start before deciding everyone is done:

```
plexdo wait --all -i 30 && sudo reboot
```

Record every poll as JSON Lines while waiting, for a dashboard:

```
plexdo wait --all --json | tee wait.log | jq -c '{user, state, remaining}'
```

From PowerShell, which cannot read a CLIXML stream, read the JSON a line at a
time:

```
plexdo wait --json | ForEach-Object { $_ | ConvertFrom-Json }
```

# SEE ALSO

*plexdo-status*(1), *plexdo-show-metadata*(1), *plexdo-conventions*(7),
*plexdo*(1)
