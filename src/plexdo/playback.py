# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Starting playback on a player: where it fetches the media from.

A player told to play something fetches it from the server itself, at an
address the command names, and that address has to work from the player's
network, not plexdo's. Every address the server has is a candidate:
plexdo's configured URL, and each direct connection plex.tv lists. The one
chosen is the one most like the player's own address - same family, same
scope, longest shared prefix - which picks the right interface on a routed
private network or across IPv6 sites. --server-url settles it outright
when the topology is one no heuristic could see.
"""

import argparse
import ipaddress
import sys
from typing import Any, NamedTuple
from urllib.parse import urlsplit

from plexapi.exceptions import PlexApiException
from plexapi.server import PlexServer
from requests import RequestException

from plexdo.constants import LOG
from plexdo.titles import display_title

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

_DEFAULT_PORT = 32400


class Candidate(NamedTuple):
    """One address the player could be told to fetch the media from."""

    protocol: str
    host: str  # what the player is given: a name or an IP
    port: int
    ip: IPAddress | None  # the address behind it, for ranking
    source: str  # where it came from, for messages


def parse_ip(text: str | None) -> IPAddress | None:
    """An IP address from text, or None for a name or nothing.

    An IPv4 address the server reports in IPv6-mapped form, ::ffff:10.0.0.5,
    is the IPv4 address it stands for: that is the network the player is on.
    """
    try:
        ip = ipaddress.ip_address((text or "").strip("[]"))
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _usable(ip: IPAddress | None, host: str) -> bool:
    """Whether an address could mean the server to a player elsewhere.

    Loopback means the player itself, a link-local address is meaningless
    off its own segment, and neither can be right for another device.
    """
    if ip is None:
        return host.lower() != "localhost"
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
    )


def _candidate_from_url(url: str, source: str) -> Candidate | None:
    """A candidate from a URL, or None when it cannot serve another device."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme not in ("http", "https") or not host:
        return None
    ip = parse_ip(host)
    if not _usable(ip, host):
        return None
    return Candidate(
        parts.scheme, host, parts.port or _DEFAULT_PORT, ip, source
    )


def _plex_tv_candidates(plex: PlexServer) -> list[Candidate]:
    """Every direct address plex.tv lists for the server.

    Relayed connections are left out: they are throttled far below what
    video needs. Each is named by the host in its URI rather than its bare
    address, since plex.tv's connections are normally https to a
    plex.direct name, whose certificate a bare IP would fail; the bare
    address is kept only to rank it.
    """
    try:
        resource = plex.myPlexAccount().resource(plex.friendlyName)
        connections = list(resource.connections)
    except (PlexApiException, RequestException) as exc:
        LOG.info(
            "Could not read the server's addresses from plex.tv (%s); "
            "only the configured URL is a candidate.",
            exc,
        )
        return []
    found = []
    for conn in connections:
        if conn.relay:
            continue
        where = "local" if conn.local else "remote"
        candidate = _candidate_from_url(
            conn.uri or conn.httpuri, f"plex.tv {where} address"
        )
        actual = parse_ip(conn.address)
        # The URI's host is usually a plex.direct name, which says nothing
        # about the address behind it; that has to pass the same test.
        if candidate is None or not _usable(actual, conn.address or ""):
            continue
        found.append(candidate._replace(ip=actual or candidate.ip))
    return found


def _shared_prefix(first: IPAddress, second: IPAddress) -> int:
    """How many leading bits two addresses of one family have in common."""
    return first.max_prefixlen - (int(first) ^ int(second)).bit_length()


def _rank(candidate: Candidate, player_ip: IPAddress) -> tuple[int, int, int]:
    """How well a candidate suits a player at player_ip; higher is better.

    First the family: an IPv4 player is given an IPv4 address, an IPv6 one
    an IPv6 address, and a name, whose family is unknown, ranks between a
    match and a mismatch. Then the scope: a player on a private or ULA
    network is given a private address, a player on a global one a global
    address. Then the longest shared prefix, which on a routed network
    picks the server's interface nearest the player, and between two IPv6
    sites picks the global address over a ULA one that ACLs would stop.
    """
    ip = candidate.ip
    if ip is None:
        return (1, 0, 0)
    if ip.version != player_ip.version:
        return (0, 0, 0)
    same_scope = int(ip.is_global == player_ip.is_global)
    return (2, same_scope, _shared_prefix(ip, player_ip))


def _choose_address(
    candidates: list[Candidate], player_ip: IPAddress
) -> Candidate | None:
    """The candidate to send a player at player_ip, or None if none at all.

    A tie keeps the earlier candidate, so plexdo's configured URL, listed
    first, wins over a plex.tv address that ranks the same.
    """
    if not candidates:
        return None
    return max(candidates, key=lambda c: _rank(c, player_ip))


def url_host(host: str) -> str:
    """A host as it goes into a URL: an IPv6 literal needs brackets."""
    if ":" in host:
        return f"[{host}]"
    return host


def url_of(candidate: Candidate) -> str:
    """A candidate as a URL."""
    return f"{candidate.protocol}://{url_host(candidate.host)}:{candidate.port}"


def fetch_address(
    plex: PlexServer,
    player_title: str,
    player_ip: IPAddress,
    server_url: str | None,
) -> Candidate:
    """Where to tell a player at player_ip to fetch the media from.

    --server-url is taken as given, loopback and all, since whoever passed
    it knows where the player is. Otherwise the candidates are ranked
    against the player's address.
    """
    if server_url is not None:
        parts = urlsplit(server_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            sys.exit(
                f"--server-url must be an http or https URL with a host, "
                f"such as http://10.1.2.3:32400; got {server_url!r}."
            )
        return Candidate(
            parts.scheme,
            parts.hostname,
            parts.port or _DEFAULT_PORT,
            parse_ip(parts.hostname),
            "--server-url",
        )

    base = plex._baseurl  # pylint: disable=protected-access
    configured = _candidate_from_url(base, "configured URL")
    candidates = ([configured] if configured else []) + _plex_tv_candidates(
        plex
    )
    chosen = _choose_address(candidates, player_ip)
    if chosen is None:
        sys.exit(
            f"No address for the server is usable from another device: the "
            f"configured URL, {base}, is a loopback address, and plex.tv "
            "lists no direct one. Pass --server-url with an address the "
            "player can reach, or set plex: url to one."
        )
    LOG.info(
        "Player %s is at %s; telling it to fetch from %s (%s).",
        player_title,
        player_ip,
        url_of(chosen),
        chosen.source,
    )
    return chosen


def play_fields(
    item: Any, fetch: Candidate, args: argparse.Namespace
) -> dict[str, Any]:
    """The fields closing every playback record.

    They say what was sent, where it is fetched from, and whether it was.
    """
    return {
        "ratingKey": int(item.ratingKey),
        "title": display_title(item),
        "fetchFrom": url_of(fetch),
        "status": "dry run" if args.dry_run else "sent",
    }


def add_play_arguments(parser: Any) -> None:
    """Add the ratingKey and --server-url every playback command takes."""
    parser.add_argument(
        "rating_key",
        type=int,
        metavar="ratingKey",
        help=(
            "The item to play (int): a film, episode, show, season, track, "
            "album, photo, or playlist. Obtain with list-titles or search."
        ),
    )
    parser.add_argument(
        "--server-url",
        dest="server_url",
        default=None,
        metavar="URL",
        help=(
            "The server address the player should fetch from, such as "
            "http://10.1.2.3:32400, used exactly as given. By default it is "
            "chosen from the server's addresses as the one most like the "
            "player's own."
        ),
    )
