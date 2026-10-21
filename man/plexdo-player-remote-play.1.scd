plexdo-player-remote-play(1) "plexdo" "User Commands"

# NAME

plexdo-player-remote-play - connect to a player directly and tell it to play
an item

# SYNOPSIS

*plexdo player-remote-play* _HOST_ _ratingKey_ [*--port* _PORT_]
\[*--player-user* _USER_] [*--server-url* _URL_] [_GLOBAL OPTIONS_]

# DESCRIPTION

Connects to a Plex player, such as a TV app or Plex HTPC, at its host name
or address, and tells it to start playing one item at once, the same as
casting to it from a Plex app on the same network. Whatever the player was
playing is replaced.

The command goes straight to the player, so *plexdo* must be able to reach
it, and the player must allow remote control; in most Plex apps that is the
*Advertise as player* setting. In exchange, the server need not know of the
player at all.

## Reaching the player

The player is addressed by IP address alone. Some players refuse a request
whose Host header carries a name, as a defence against DNS rebinding, so a
_HOST_ that is a name is resolved by *plexdo* itself, and only the address
goes on the wire, in the URL and in the Host header alike. A name with
several addresses, IPv6 and IPv4 for instance, has each tried in the order
the system's resolver gives them, until a player answers.

Each Plex app listens for remote control on its own port, so unless
*--port* gives it, the player is asked: *plexdo* sends a GDM search, Plex's
discovery protocol, to UDP port 32412 at the player's address, and a player
answers with its port. GDM is IPv4 only, and a firewall may drop it, so a
player that does not answer within two seconds is tried on the ports the
common Plex apps use, in this order:

- *32500*: Plex for Android, Android TV, and Fire TV;
- *8324*: Roku;
- *32433*: Plex HTPC and Plex Media Player;
- *3005*: Plex Home Theater.

A guessed port that does not take a TCP connection within two seconds is
passed over without asking it anything, so a firewall dropping the guesses
costs little.

The player is first asked who it is without any token, since what answers
at an address may not be a player at all; a player that insists is asked
again with *plexdo*'s own token.

## Which account sends it

A player takes commands only from an account it trusts, normally the one
signed in to it. *--player-user* names that account, and the command is
sent as it. Without it, the command is sent as:

- *plexdo*'s own account, the one *plexdo-login*(1) signed in, when it is
  the server's admin;
- otherwise *plexdo*'s own account when the player is one of that
  account's devices on plex.tv;
- otherwise the first account in the configuration's per-user sections,
  *[<user id>]* with *username* and *password*, that the player is one of
  the devices of;
- otherwise *plexdo*'s own account anyway, with a warning: some players
  accept it regardless, and if this one does not, the error says what to
  add to the configuration.

*--player-user* takes a plex.tv user id, a username, or an email address,
the last two ignoring case. It names, in this order:

- *plexdo*'s own account, when it matches that account's id, username, or
  email, or is *0* and *plexdo*'s account is the server's admin, as *0*
  means the admin to every other command;
- a member of *plexdo*'s Plex Home, as *plexdo-list-users*(1) shows with
  the type *home* or *managed*. A managed user has no username or email,
  so it is named by its id or the name it is shown by. *plexdo* switches
  into the member through plex.tv, as the user switcher in a Plex app
  does, which needs no password, only the member's PIN when it has one,
  given as *pin* in a section named for its user id;
- an account from a per-user section: one whose section id or *username*
  is the value is taken at its word; failing that, the sections are
  signed in one at a time and compared by id, username, and email, since
  a section may file an account under its email when the value is its
  username. A Home member plex.tv refuses to switch into, for want of its
  PIN for instance, is looked for here too.

An account *plexdo* cannot act as is an error: the command is never sent as
some other account in its place.

An account from the configuration signs in with a token saved for it
earlier when plex.tv still accepts that, and otherwise with its password,
saving the new token so that happens once; *plexdo-logout*(1) signs such
tokens out again.

The item is then fetched through the server as the account sending the
command, a Home member's included. This matters: the player plays with the
play queue and the token of whichever account fetched the item, and
switches its own user to match, so the item fetched as anyone else would
switch the player away from the person whose player it is. A server may
refuse an account's own plex.tv token, as it does a managed user's, and
then the token the server issues for that user is used instead, as every
per-user command uses it. When the server will have neither, the item would
have to be fetched as *plexdo*'s own account: with *--player-user* that is
an error, and otherwise a warning that the player will switch to that
account.

## Where the player fetches from

The player fetches the item from the server itself, at an address the
command gives it, and that address has to work from the player's network,
which need not be *plexdo*'s. A server on several routed private networks,
or across IPv6 sites joined by router ACLs, has several addresses, and the
one *plexdo* itself uses may be the wrong one for the player.

So every address the server has is a candidate: *plexdo*'s configured
*[plex] url*, and each direct address plex.tv lists for the server, on the
local network or the public one. They are ranked against the address the
player answered at:

- *Same family first*: an IPv4 player gets an IPv4 address, an IPv6 player
  an IPv6 one. An IPv4 address in IPv6-mapped form, *::ffff:10.1.2.3*,
  counts as IPv4. A host name, whose family is unknown, ranks below a match
  and above a mismatch.
- *Then the same scope*: a player on a private network, an IPv6 ULA, or
  carrier-grade NAT space such as a VPN overlay gets a private address; a
  player on a global address gets a global one. A global IPv6 address is
  what crosses sites whose routers permit direct connections, where a ULA
  usually would not be routed.
- *Then the longest shared prefix*: among what is left, the address
  sharing the most leading bits with the player's, which on a routed
  network picks the server's interface nearest the player.

A tie goes to the configured URL. Some addresses never qualify: loopback
ones, such as the template's *http://localhost:32400*, which would send a
player looking on itself; IPv6 link-local ones, which mean nothing off
their own segment; and plex.tv relays, which are throttled far below what
video needs. An address from plex.tv is given to the player by its
*plex.direct* name rather than the bare address, since its connections are
normally https, and a bare address would fail the certificate.

*plexdo* does not test the address it chooses, because a test could only be
made from *plexdo*'s network, which may not be the player's. The chosen
address is shown in the output, and *--server-url* overrides the choice
when the topology is one no ranking could see, such as NAT between the
networks or a name that resolves differently on each.

# ARGUMENTS

_HOST_
	The player's host name, or its IPv4 or IPv6 address. An IPv6 address
	may be given with or without brackets.

_ratingKey_
	What to play: a film, episode, show, season, track, album, photo, or
	playlist, as *plexdo-list-titles*(1), *plexdo-search*(1), or
	*plexdo-list-playlists*(1) report it. A show, season, album, or
	playlist plays from its start.

# OPTIONS

*--port* _PORT_
	The port the player listens on for remote control, used without asking
	the player or guessing. By default the player is asked over GDM, and
	failing that the common apps' ports are tried: see *Reaching the
	player*.

*--player-user* _USER_
	The account signed in to the player, to send the command as: a plex.tv
	user id, as *plexdo-list-users*(1) shows it, a username, or an email
	address, or a managed user's name. It must be *plexdo*'s own account, a
	member of its Plex Home, or have a per-user section in the
	configuration. See *Which account sends it*.

*--server-url* _URL_
	The server address the player should fetch from, such as
	*http://10.1.2.3:32400* or *http://[2a01:4f8:10::5]:32400*, used exactly
	as given, with no ranking and no plex.tv lookup. It must be an http or
	https URL with a host; the port defaults to 32400. A loopback address is
	accepted here, for a player on the server's own machine.

# GLOBAL OPTIONS

*-f*, *--format* _FORMAT_; *--json*
	A table prints one line saying what was sent where. Any other format
	gives one record: see *OUTPUT*.

*-W*, *--wide*
	No effect: there is no table.

*--throttle* _SECONDS_
	No effect: one command is sent.

*-v*, *--verbose*; *--debug*
	*--verbose* reports the addresses a name resolved to, the port a player
	gave over GDM or its silence, each address and port no player answered
	at, the account chosen and why, and the address the player is told to
	fetch from.

*--dry-run*
	Find the item and the player, choose the account and the address,
	failing exactly where the real run would, then stop without sending
	anything. Choosing the account, with or without *--player-user*, may
	still sign in an account from the configuration, and save its token.
	The line or record then says *Would send*, or has the status
	*dry run*.

*-V*, *--version*; *-h*, *--help*
	Print the version, or this command's help, and exit.

# OPTION INTERACTIONS

- *--port* applies to every address a name resolves to. Without it,
  each IPv4 address is asked over GDM separately, and every address,
  IPv6 included, falls back to the common apps' ports.
- *--player-user* replaces the automatic choice of account, including
  sending as *plexdo*'s own account because it is the server's admin. It
  has no bearing on the server address the player fetches from.
- *--server-url* replaces the whole choice of server address: nothing is
  ranked, and plex.tv is not asked for the server's addresses. It has no
  bearing on which account sends the command.
- Without it, the choice depends on the address the player answered at,
  *[plex] url*, and what plex.tv lists. When plex.tv cannot be reached, the
  configured URL is the only candidate; when that is a loopback address
  too, the command stops and asks for *--server-url*, or a *[plex] url* a
  player can reach.

# OUTPUT

As a table, one line:

```
Sent "Heat" to Living Room at http://10.20.0.40:8324 as fred, fetching
from https://192-168-50-5.abc123.plex.direct:32400.
```

The line is a single line; it is wrapped here only to fit the page.

In any other format, one record:

*player*, *machineIdentifier*, *product*
	The player's name, its machine identifier, and the Plex app it is.

*host*
	_HOST_ as given.

*playerAddress*
	The URL the player was reached at, by IP address and the port it
	answered on.

*account*
	The account the command was sent as.

*ratingKey*, *title*
	The item sent.

*fetchFrom*
	The server address the player was told to fetch from.

*status*
	*sent*, or *dry run*.

# EXIT STATUS

*0* when the player accepted the command. *1* when the item is not found,
by *plexdo*'s account or by the account sending the command; when _HOST_
does not resolve; when *--player-user* names an account *plexdo* has no
credentials for and is not a member of its Plex Home, names a member
plex.tv refuses to switch into, or one the server will not let fetch the
item, or plex.tv cannot be asked about it; when
no player answers at any of its addresses, on *--port* or on any port it
gave or was guessed; when *--server-url* is not an http or
https URL; when no address could serve the player, because the configured
URL is a loopback address and plex.tv lists no direct one; or when the
player refuses the command, as it does from an account it does not trust.
See *plexdo-conventions*(7).

# EXAMPLES

Play a film on the living room TV:

```
plexdo player-remote-play 10.20.0.40 881
```

The same by name; the name is resolved here, and the TV sees only its
address:

```
plexdo player-remote-play livingroom-tv.lan 881
```

A player that does not answer GDM, on a port none of the common apps
use:

```
plexdo player-remote-play 10.20.0.41 881 --port 36000
```

Check that the player answers, and see which account would send the
command and where the player would fetch from, without playing anything:

```
plexdo player-remote-play livingroom-tv.lan 881 --dry-run --json |
    jq '{account, fetchFrom}'
```

Send as the account signed in to the TV, which has a per-user section in
the configuration, rather than working it out:

```
plexdo player-remote-play livingroom-tv.lan 881 --player-user bob@example.com
```

A player on a network the ranking cannot see into, behind NAT for
instance, told exactly where to fetch from:

```
plexdo player-remote-play 10.40.0.9 881 --server-url http://203.0.113.20:32400
```

Find a film by title and play it:

```
key=$(plexdo search 0 "Heat" --media-type movie --json | jq '.[0].ratingKey')
plexdo player-remote-play livingroom-tv.lan "$key"
```

Send as a managed user of the Plex Home, signed in on the TV, by the
name *plexdo-list-users*(1) shows:

```
plexdo player-remote-play livingroom-tv.lan 881 --player-user Clare
```

# FILES

The per-user sections of the configuration, and the token store, are
described under *FILES* in *plexdo-conventions*(7). A section for a
PIN-protected Home member holds just the PIN:

```
[826699965]
pin = 1234
```

# SEE ALSO

*plexdo-status*(1), *plexdo-wait*(1), *plexdo-search*(1),
*plexdo-logout*(1), *plexdo-conventions*(7), *plexdo*(1)
