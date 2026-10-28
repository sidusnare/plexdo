# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Telling a player to play something, by talking to the player directly.

The command goes to the player itself, at a host name or address, as a
Plex app on the same network does when it casts, so a player the server
has never heard of can still be reached. The player then fetches the item
from the server, at an address plexdo.playback chooses to suit the
player's network rather than plexdo's.

The player is addressed by IP alone. Some players refuse a request whose
Host header carries a name, as a defence against DNS rebinding, so a name
is resolved here and only the address it resolves to goes on the wire.

Each Plex app listens on its own port. Unless --port gives it, the player
is asked over GDM, Plex's discovery protocol, which every player answers
with its port; a player that does not answer is tried on the ports the
common apps use.

A player accepts commands only from an account it trusts, normally the one
signed in to it. --player-user names that account, which may be a member of
plexdo's Plex Home, a managed user included, switched into without a
password. Otherwise, when
plexdo's own account is not the server's admin and is not signed in to the
player, an account from the config that is signed in to it is used
instead; with none, the command is tried anyway with a warning, since some
players accept it regardless.
"""

import argparse
import socket
import sys
from typing import Any, NamedTuple
from xml.etree.ElementTree import ParseError

from plexapi.client import PlexClient
from plexapi.exceptions import PlexApiException, Unauthorized
from plexapi.myplex import MyPlexAccount, MyPlexUser
from plexapi.server import PlexServer
from requests import RequestException

from plexdo.accounts import (
    configured_account,
    configured_accounts,
    configured_entries,
    connect_as_shared_user,
    connect_with_token,
)
from plexdo.console import clean_text, output, output_format
from plexdo.constants import CONFIG_PATH, LOG
from plexdo.playback import (
    IPAddress,
    add_play_arguments,
    fetch_address,
    parse_ip,
    play_fields,
    url_host,
)
from plexdo.titles import fetch_item
from plexdo.tokens import saved_pin

# The UDP port players answer GDM discovery on, the message asking them,
# and the seconds to wait for the answer.
_GDM_PORT = 32412
_GDM_SEARCH = b"M-SEARCH * HTTP/1.0"
_GDM_TIMEOUT = 2

# The ports the common Plex apps listen on for remote control, tried in this
# order when a player does not say over GDM: Plex for Android, Android TV
# and Fire TV; Roku; Plex HTPC and Plex Media Player; Plex Home Theater.
_KNOWN_PORTS = (32500, 8324, 32433, 3005)

# Seconds to wait for a TCP connection to a guessed port before passing
# over it, so a firewall dropping the guesses costs little.
_CONNECT_TIMEOUT = 2

# Seconds to wait for a player to answer at one address before trying the
# next: a name may resolve to addresses the player does not listen on.
_PROBE_TIMEOUT = 10


class Controller(NamedTuple):
    """The account a command is sent as, and the server it fetches through."""

    name: str
    token: str
    server: PlexServer  # the item is fetched as this account, so the play is
    # recorded against it


def _player_addresses(host: str) -> list[IPAddress]:
    """The IP addresses to try for host, in the resolver's order.

    An address is itself. A name is resolved here, and each address it has
    is tried in turn, so a dual-stack name whose first address the player
    does not answer on still reaches it on the next.
    """
    ip = parse_ip(host)
    if ip is not None:
        return [ip]
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        sys.exit(f"Could not resolve the player's host name {host!r}: {exc}")
    found: list[IPAddress] = []
    for info in infos:
        address = parse_ip(str(info[4][0]))
        if address is not None and address not in found:
            found.append(address)
    LOG.info("%s resolves to %s.", host, ", ".join(map(str, found)))
    return found


def _player_url(address: IPAddress, port: int) -> str:
    """The URL of a player at an IP address.

    The address is then all the Host header carries.
    """
    return f"http://{url_host(str(address))}:{port}"


def _gdm_port(reply: bytes) -> int | None:
    """The port a GDM reply advertises, or None when it is not a player's.

    The reply is HTTP-like: a status line, then "Name: value" headers.
    """
    lines = reply.decode("utf-8", "replace").splitlines()
    if not lines or "200 OK" not in lines[0]:
        return None
    headers = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    if "player" not in headers.get("content-type", "player"):
        return None  # a server, sharing the address with a player
    try:
        return int(headers.get("port", ""))
    except ValueError:
        return None


def _advertised_port(address: IPAddress) -> int | None:
    """Ask the player at address over GDM which port it listens on.

    GDM is IPv4 only, and a player that does not answer, or a network
    dropping UDP, gives None.
    """
    if address.version != 4:
        return None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(_GDM_TIMEOUT)
        try:
            sock.sendto(_GDM_SEARCH, (str(address), _GDM_PORT))
            while True:
                reply, sender = sock.recvfrom(4096)
                port = _gdm_port(reply) if sender[0] == str(address) else None
                if port is not None:
                    LOG.info(
                        "%s says over GDM that it listens on port %d.",
                        address,
                        port,
                    )
                    return port
        except OSError as exc:  # socket.timeout included
            LOG.info("%s did not answer over GDM: %s", address, exc)
            return None


def _listening(address: IPAddress, port: int) -> bool:
    """Whether a guessed port takes a TCP connection at all."""
    try:
        with socket.create_connection(
            (str(address), port), timeout=_CONNECT_TIMEOUT
        ):
            return True
    except OSError as exc:
        LOG.info("Nothing listening at %s: %s", _player_url(address, port), exc)
        return False


def _endpoints(address: IPAddress, port: int | None) -> list[tuple[int, bool]]:
    """The ports to try at address, each with whether it is a guess."""
    if port is not None:
        return [(port, False)]
    advertised = _advertised_port(address)
    if advertised is not None:
        return [(advertised, False)]
    return [(known, True) for known in _KNOWN_PORTS]


def _probe(url: str, fallback_token: str) -> PlexClient:
    """Ask the player at url who it is.

    Asked without a token first: players answer this unauthenticated, and
    sending a token to an address that may not be the player at all would
    be giving it away. A player that insists is asked again with
    fallback_token.
    """
    try:
        return PlexClient(baseurl=url, timeout=_PROBE_TIMEOUT)
    except Unauthorized:
        LOG.debug("%s wants a token to say who it is; asking with one.", url)
        return PlexClient(
            baseurl=url, token=fallback_token, timeout=_PROBE_TIMEOUT
        )


def _find_player(
    addresses: list[IPAddress], port: int | None, fallback_token: str
) -> tuple[PlexClient, IPAddress, str]:
    """The player, and the address and URL it answered at.

    Each address is tried in turn, and each port when port is None.
    """
    failures = []
    for address in addresses:
        for each, guessed in _endpoints(address, port):
            url = _player_url(address, each)
            if guessed and not _listening(address, each):
                failures.append(f"{url}: nothing listening")
                continue
            try:
                probe = _probe(url, fallback_token)
            # A ParseError or IndexError is something answering that is not
            # a player: plexapi parses the reply and takes its first element.
            except (
                PlexApiException,
                RequestException,
                ParseError,
                IndexError,
            ) as exc:
                LOG.info("No player answered at %s: %s", url, exc)
                failures.append(f"{url}: {exc}")
                continue
            if probe.machineIdentifier:
                return probe, address, url
            # Something answered, but not with a player's description.
            failures.append(f"{url}: not a Plex player")
    hint = (
        "the --port given"
        if port is not None
        else "the port, which the player did not say over GDM: give it with "
        "--port"
    )
    sys.exit(
        "No Plex player answered at " + "; ".join(failures) + ". Check the "
        f"address and {hint}, and that the player allows remote control: "
        "in most Plex apps that is the Advertise as player setting."
    )


def _signed_in_to(account: MyPlexAccount, machine_id: str) -> bool:
    """Whether the player is one of the account's devices on plex.tv."""
    try:
        devices = account.devices()
    except (PlexApiException, RequestException) as exc:
        LOG.info(
            "Could not list %s's devices on plex.tv: %s", account.username, exc
        )
        return False
    return any(device.clientIdentifier == machine_id for device in devices)


def _is_admin(plex: PlexServer, account: MyPlexAccount) -> bool:
    """Whether account owns the server.

    The server names its owner by email; compared ignoring case, as plex.tv
    does, and against the username too in case a server reports that.
    """
    owner = (plex.myPlexUsername or "").lower()
    return bool(owner) and owner in (
        (account.email or "").lower(),
        (account.username or "").lower(),
    )


def _server_as(
    plex: PlexServer, current: MyPlexAccount, account: MyPlexAccount
) -> PlexServer | None:
    """The server as account, or None when it will not have it.

    The account's own plex.tv token first. A server may refuse that, as it
    does a managed user's, so then the server-scoped token plexdo's account
    can mint for any user the server is shared with, as every per-user
    command does.
    """
    server = connect_with_token(plex, account.authenticationToken)
    if server is not None:
        return server
    for user in current.users():
        if user.id == account.id:
            LOG.info(
                "The server refused %s's own token; using the token "
                "it issues for that user.",
                user.title,
            )
            return connect_as_shared_user(plex, user)
    return None


def _as_account(
    plex: PlexServer,
    current: MyPlexAccount,
    account: MyPlexAccount,
    strict: bool,
) -> Controller:
    """Send as account, and fetch the item as it too.

    The player plays with the play queue and token of whichever account
    fetched the item, and switches its own user to match, so fetching as
    anyone else would switch the player away from the person whose player
    it is. That is an error when strict, for an account --player-user
    named; otherwise plexdo's own account fetches it, with a warning.
    """
    token = account.authenticationToken
    # A managed user has no username, only the name it is shown by.
    name = account.username or account.title
    server = _server_as(plex, current, account)
    if server is not None:
        return Controller(name, token, server)
    if strict:
        sys.exit(
            f"The server will not let {name} fetch the item, so the player "
            f"would play it as {current.username} and switch to that user. "
            f"Share the library with {name}, or leave out --player-user to "
            "send as plexdo's own account."
        )
    LOG.warning(
        "The server will not let %s fetch the item; fetching it as "
        "%s, which the player will switch to.",
        name,
        current.username,
    )
    return Controller(name, token, plex)


def _is_account(account: MyPlexAccount, value: str) -> bool:
    """Whether value names account by plex.tv id, username, or email."""
    return value.lower() in (
        str(account.id),
        (account.username or "").lower(),
        (account.email or "").lower(),
    )


def _home_member_named(current: MyPlexAccount, value: str) -> MyPlexUser | None:
    """The member of plexdo's Plex Home that value names, or None.

    Named by plex.tv id, username, or email, or, for a managed user, which
    has neither a username nor an email, by the name it is shown by.
    """
    wanted = value.lower()
    for user in current.users():
        if not user.home:
            continue
        names = {
            str(user.id),
            (user.username or "").lower(),
            (user.email or "").lower(),
        }
        if not user.username:
            names.add((user.title or "").lower())
        if wanted in names - {""}:
            return user
    return None


def _switch_to(
    current: MyPlexAccount, user: MyPlexUser
) -> tuple[MyPlexAccount | None, str]:
    """Switch into a Plex Home member: its account, or None and why not.

    No password is needed, only the member's PIN when it has one, which
    plexdo set-pin saves.
    """
    pin = saved_pin(user.id)
    try:
        account = current.switchHomeUser(user, pin=pin)
    except PlexApiException as exc:
        LOG.info("plex.tv refused the switch to %s: %s", user.title, exc)
        return None, str(exc)
    LOG.info("--player-user is %s, a member of plexdo's Plex Home.", user.title)
    return account, ""


def _configured_account_named(value: str) -> MyPlexAccount | None:
    """The account from the config that value names, signed in, or None.

    An entry whose id or username is value is taken at its word, before
    any sign-in. Failing that, the others are signed in one at a time and
    compared by id, username, and email, since an entry may file an
    account under its email when value is its username, or the reverse.
    """
    entries = configured_entries()
    named = [e for e in entries if value.lower() in (str(e[0]), e[1].lower())]
    for user_id, username in named + [e for e in entries if e not in named]:
        account = configured_account(user_id, username)
        if account is None:
            continue
        if (user_id, username) in named or _is_account(account, value):
            LOG.info(
                "--player-user %s is %s, from users entry %s.",
                value,
                account.username,
                user_id,
            )
            return account
    return None


def _named_controller(plex: PlexServer, value: str) -> Controller:
    """The account --player-user names, which the command is sent as.

    plexdo's own account when value names it, or is 0, plexdo's name for
    the admin, and plexdo is the admin; otherwise a member of plexdo's
    Plex Home, switched into; otherwise an account from the config. One it
    cannot act as is an error rather than a silent fallback to some other
    account.
    """
    refused = ""
    try:
        current = plex.myPlexAccount()
        if _is_account(current, value) or (
            value == "0" and _is_admin(plex, current)
        ):
            LOG.info("--player-user %s is plexdo's own account.", value)
            # pylint: disable-next=protected-access
            return Controller(current.username, plex._token, plex)
        member = _home_member_named(current, value)
        account, refused = _switch_to(current, member) if member else (None, "")
        if account is None:
            account = _configured_account_named(value)
        if account is not None:
            return _as_account(plex, current, account, strict=True)
    except (PlexApiException, RequestException) as exc:
        sys.exit(
            f"Could not ask plex.tv about the account to send as "
            f"({exc}); --player-user {value} needs it."
        )
    if member is not None:
        sys.exit(
            f"Could not switch to {member.title!r}, a member of plexdo's "
            f"Plex Home: plex.tv refused ({refused}). A member with a PIN "
            f"needs it saved with plexdo set-pin {member.id}; or add a users "
            f"entry for it to {CONFIG_PATH} and sign it in once with plexdo "
            "login --username."
        )
    sys.exit(
        f"No credentials for the player user {value!r}: it is not plexdo's "
        f"own account, {current.username}, nor a member of its Plex Home, "
        f"and no users entry in {CONFIG_PATH} is for it, by id, username, "
        "or email. Add one with that account's username, and sign it in once "
        "with plexdo login --username."
    )


def _configured_controller(
    plex: PlexServer, current: MyPlexAccount, machine_id: str
) -> Controller | None:
    """An account from the config signed in to the player, if there is one."""
    try:
        for user_id, account in configured_accounts():
            if not _signed_in_to(account, machine_id):
                continue
            LOG.info(
                "The player is signed in as %s, from users entry %s.",
                account.username,
                user_id,
            )
            return _as_account(plex, current, account, strict=False)
    except (PlexApiException, RequestException) as exc:
        LOG.warning(
            "Could not sign in the accounts in %s (%s); trying the "
            "player as plexdo's own account.",
            CONFIG_PATH,
            exc,
        )
    return None


def _controller(plex: PlexServer, machine_id: str, title: str) -> Controller:
    """The account to send the command as.

    plexdo's own account when it is the server's admin or is signed in to
    the player; otherwise an account from the config signed in to the
    player; otherwise plexdo's own account anyway, with a warning, since
    the player may accept it regardless.
    """
    own_token = plex._token  # pylint: disable=protected-access
    try:
        current = plex.myPlexAccount()
    except (PlexApiException, RequestException) as exc:
        LOG.warning(
            "Could not ask plex.tv which account plexdo is signed in "
            "as (%s); trying the player with plexdo's own token.",
            exc,
        )
        return Controller("plexdo's account", own_token, plex)

    own = Controller(current.username, own_token, plex)
    if _is_admin(plex, current):
        LOG.info(
            "%s is the server's admin; sending as that account.",
            current.username,
        )
        return own
    if _signed_in_to(current, machine_id):
        LOG.info(
            "%s is signed in to the player; sending as that account.",
            current.username,
        )
        return own
    configured = _configured_controller(plex, current, machine_id)
    if configured is not None:
        return configured
    LOG.warning(
        "%s is neither the server's admin nor signed in to %s, and no account "
        "in %s is signed in to it either; trying anyway, but the player may "
        "refuse. Add the account signed in to the player as a users entry, "
        "and sign it in once with plexdo login --username, to fix that.",
        current.username,
        title,
        CONFIG_PATH,
    )
    return own


def _report_remote(record: dict[str, Any], args: argparse.Namespace) -> None:
    """One line for a table, or the record in any other format."""
    if output_format(args) != "table":
        output(record, args)
        return
    verb = "Would send" if record["status"] == "dry run" else "Sent"
    print(
        f'{verb} "{record["title"]}" to {record["player"]} at '
        f"{record['playerAddress']} as {record['account']}, fetching from "
        f"{record['fetchFrom']}."
    )


def cmd_player_remote_play(plex: PlexServer, args: argparse.Namespace) -> None:
    """Connect to a player directly and tell it to play one item."""
    item = fetch_item(plex, args.rating_key)  # a bad key fails before probing
    own_token = plex._token  # pylint: disable=protected-access
    probe, address, url = _find_player(
        _player_addresses(args.host), args.port, own_token
    )
    title = clean_text(probe.title or "") or str(address)
    controller = (
        _named_controller(plex, args.player_user)
        if args.player_user is not None
        else _controller(plex, probe.machineIdentifier, title)
    )
    if controller.server is not plex:
        # Fetched as the account sending it, so the play is recorded there.
        item = fetch_item(controller.server, args.rating_key)
    fetch = fetch_address(plex, title, address, args.server_url)

    record = {
        "player": title,
        "machineIdentifier": probe.machineIdentifier,
        "product": probe.product,
        "host": args.host,
        "playerAddress": url,
        "account": controller.name,
        **play_fields(item, fetch, args),
    }
    if args.dry_run:
        LOG.info("--dry-run: not sending anything to %s.", url)
        _report_remote(record, args)
        return

    try:
        client = PlexClient(
            server=controller.server, baseurl=url, token=controller.token
        )
        client.playMedia(
            item,
            protocol=fetch.protocol,
            address=url_host(fetch.host),
            port=str(fetch.port),
        )
    except Unauthorized as exc:
        sys.exit(
            f"{title} at {url} refused the command from {controller.name}: "
            f"{exc}\nA player takes commands only from an account it trusts, "
            f"normally the one signed in to it. Add that account to "
            f"{CONFIG_PATH} as a users entry, sign it in once with plexdo "
            "login --username, and plexdo will send as that account."
        )
    except ParseError:
        # The status was a success, or plexapi would have raised before
        # parsing; some players just answer one with a bare "OK".
        LOG.debug("%s accepted the command with a reply that is not XML.", url)
    except (PlexApiException, RequestException) as exc:
        sys.exit(
            f"Could not start {record['title']!r} on {title} at {url}: {exc}"
        )
    _report_remote(record, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "list[argparse.ArgumentParser]",
) -> None:
    """Register the player-remote-play subparser."""
    parser = sub.add_parser(
        "player-remote-play",
        parents=parents,
        help="Connect to a player directly and tell it to play an item.",
    )
    parser.add_argument(
        "host",
        metavar="HOST",
        help=(
            "The player's host name or IP address. A name is resolved here "
            "and only the address is sent to the player."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="PORT",
        help=(
            "The port the player listens on for remote control (int). By "
            "default the player is asked over GDM, and failing that the "
            "ports the common Plex apps use are tried."
        ),
    )
    parser.add_argument(
        "--player-user",
        dest="player_user",
        default=None,
        metavar="USER",
        help=(
            "The account signed in to the player, to send the command as: "
            "a plex.tv user id, username, or email. plexdo's own account, a "
            "Plex Home member, or one with a users entry in the config. By "
            "default it is worked out from the player's plex.tv devices."
        ),
    )
    add_play_arguments(parser)


COMMANDS = {"player-remote-play": cmd_player_remote_play}

REQUIRES_PLEX = frozenset(COMMANDS)
