# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""The server address a player is told to fetch from, whatever its network."""

import types

import pytest
from plexapi.exceptions import BadRequest

from plexdo.playback import (
    Candidate,
    _choose_address,
    _plex_tv_candidates,
    fetch_address,
    parse_ip,
    url_of,
)


def connection(address, local=True, relay=False, secure=True, port=32400):
    """A plex.tv connection, https to a plex.direct name as plex.tv lists."""
    dashed = address.replace(".", "-").replace(":", "-")
    uri = (
        f"https://{dashed}.abc123.plex.direct:{port}"
        if secure
        else f"http://{address}:{port}"
    )
    return types.SimpleNamespace(
        address=address,
        port=port,
        local=local,
        relay=relay,
        uri=uri,
        protocol="https" if secure else "http",
        httpuri=f"http://{address}:{port}",
    )


class FakeServer:
    """A Plex server and the addresses plex.tv lists for it."""

    friendlyName = "nas"

    def __init__(
        self,
        baseurl="http://10.10.0.5:32400",
        connections=(),
        plex_tv_down=False,
    ):
        self._baseurl = baseurl
        self._connections, self._down = list(connections), plex_tv_down

    def myPlexAccount(self):
        if self._down:
            raise BadRequest("plex.tv unreachable")
        return self

    def resource(self, _name):
        return types.SimpleNamespace(connections=self._connections)


def candidate(host, source="plex.tv local address", protocol="https"):
    """A candidate whose ranking address is host itself."""
    return Candidate(protocol, host, 32400, parse_ip(host), source)


def chosen_host(candidates, player_address):
    return _choose_address(candidates, parse_ip(player_address)).host


# --- choosing the address the player can reach -----------------------------

# Global addresses here are real-world ranges, not the documentation ones
# (2001:db8::/32, 192.0.2.0/24 and friends): Python rightly counts those as
# not global, so they would never exercise the scope rule.
SERVER = [
    candidate("10.10.0.5", source="configured URL", protocol="http"),
    candidate("192.168.50.5"),
    candidate("fd12::5"),
    candidate("2a01:4f8:10::5"),
    candidate("81.2.69.160", source="plex.tv remote address"),
]


def test_routed_private_ipv4_picks_the_nearest_private_address():
    """Player and server on different routed private networks."""
    assert chosen_host(SERVER, "10.20.0.40") == "10.10.0.5"


def test_a_multi_homed_server_offers_the_interface_on_the_players_network():
    assert chosen_host(SERVER, "192.168.50.77") == "192.168.50.5"


def test_an_ipv6_player_on_another_site_gets_the_global_address():
    """Router ACLs pass global addresses between sites; a ULA would not do."""
    assert chosen_host(SERVER, "2a01:4f8:20::77") == "2a01:4f8:10::5"


def test_scope_outranks_a_longer_shared_prefix():
    """Leading bits shared across the private/global line mean nothing.

    11.0.0.9 is global and shares 7 bits with the private 10.255.255.5 but
    only 1 with the global 81.2.69.160; the global one must still win. The
    mirror case holds for a private player.
    """
    assert (
        chosen_host(
            [candidate("10.255.255.5"), candidate("81.2.69.160")], "11.0.0.9"
        )
        == "81.2.69.160"
    )
    assert (
        chosen_host(
            [candidate("11.0.0.5"), candidate("172.16.0.5")], "10.200.0.9"
        )
        == "172.16.0.5"
    )


def test_an_ipv6_player_on_a_ula_network_gets_the_ula_address():
    assert chosen_host(SERVER, "fd34::77") == "fd12::5"


def test_an_ipv4_mapped_player_address_counts_as_ipv4():
    """The server may report an IPv4 player in IPv6-mapped form."""
    assert chosen_host(SERVER, "::ffff:192.168.50.77") == "192.168.50.5"


def test_a_remote_player_gets_the_servers_public_address():
    assert chosen_host(SERVER, "90.200.1.9") == "81.2.69.160"


def test_a_name_beats_an_address_of_the_wrong_family():
    """A hostname might resolve to either family; a wrong family cannot work."""
    named = [
        candidate("2a01:4f8:10::5"),
        candidate("plex.example.lan", source="configured URL"),
    ]
    assert chosen_host(named, "10.20.0.40") == "plex.example.lan"


def test_a_tie_keeps_the_configured_url():
    """The same address listed twice ranks the same.

    plexdo's own URL, which fetch_address lists first, wins.
    """
    same = [
        candidate("10.10.0.5"),
        candidate("10.10.0.5", source="configured URL", protocol="http"),
    ]
    picked = _choose_address(same[::-1], parse_ip("10.20.0.40"))
    assert picked.source == "configured URL"


# --- plex.tv's addresses ---------------------------------------------------


def test_plex_tv_addresses_are_named_by_their_plex_direct_host():
    """Https to a bare IP would fail the plex.direct certificate."""
    [found] = _plex_tv_candidates(
        FakeServer(connections=[connection("192.168.50.5")])
    )
    assert found.host == "192-168-50-5.abc123.plex.direct"
    assert str(found.ip) == "192.168.50.5"


def test_relayed_link_local_and_loopback_addresses_are_left_out():
    found = _plex_tv_candidates(
        FakeServer(
            connections=[
                connection("10.10.0.5", relay=True),
                connection("fe80::1"),
                connection("127.0.0.1"),
                connection("192.168.50.5"),
            ]
        )
    )
    assert [str(c.ip) for c in found] == ["192.168.50.5"]


def test_plex_tv_being_unreachable_leaves_the_configured_url():
    assert _plex_tv_candidates(FakeServer(plex_tv_down=True)) == []


# --- the address for a particular player -------------------------------------


def test_a_loopback_url_is_never_offered():
    """The template's localhost URL would send a TV looking on itself."""
    server = FakeServer(
        baseurl="http://localhost:32400", connections=[connection("10.10.0.5")]
    )
    assert (
        fetch_address(server, "TV", parse_ip("10.20.0.40"), None).host
        == "10-10-0-5.abc123.plex.direct"
    )


def test_no_usable_address_is_an_error_suggesting_server_url():
    server = FakeServer(baseurl="http://127.0.0.1:32400", plex_tv_down=True)
    with pytest.raises(SystemExit) as exc:
        fetch_address(server, "TV", parse_ip("10.20.0.40"), None)
    assert "--server-url" in str(exc.value)


def test_server_url_is_taken_exactly_as_given():
    picked = fetch_address(
        FakeServer(),
        "TV",
        parse_ip("10.20.0.40"),
        "http://plex.site-b.example:32401",
    )
    assert (picked.protocol, picked.host, picked.port) == (
        "http",
        "plex.site-b.example",
        32401,
    )


def test_a_server_url_that_is_not_a_url_is_refused():
    with pytest.raises(SystemExit):
        fetch_address(FakeServer(), "TV", parse_ip("10.20.0.40"), "10.1.2.3")


def test_an_ipv6_literal_goes_into_a_url_bracketed():
    """The player joins address and port into a URL."""
    picked = fetch_address(
        FakeServer(),
        "TV",
        parse_ip("2a01:4f8:20::77"),
        "http://[2a01:4f8:10::5]:32400",
    )
    assert url_of(picked) == "http://[2a01:4f8:10::5]:32400"
