# SPDX-License-Identifier: GPL-3.0-or-later

"""player-remote-play: reaching a player by address, and whom to send as."""

import ipaddress
import json
import socket
import threading
import types
import xml.etree.ElementTree as ET

import pytest
from plexapi.exceptions import BadRequest, Unauthorized
from plexapi.video import Movie
from requests import ConnectionError as RequestsConnectionError

from plexdo.cli import build_parser
from plexdo.commands import remote


class Account:
    """A plex.tv account, the devices signed in to it, and the users it
    shares with, the members of its Plex Home among them."""

    def __init__(self, username, devices=(), email=None, token=None, uid=7,
                 users=()):
        self.username, self.email = username, email or f"{username}@x.example"
        self.title = username
        self.id = uid
        self.authenticationToken = token or f"t-{username}"
        self._devices = [types.SimpleNamespace(clientIdentifier=d)
                         for d in devices]
        self._users = list(users)
        self.switched = []

    def devices(self):
        return self._devices

    def users(self):
        return self._users

    def switchHomeUser(self, user, pin=None):
        self.switched.append((user.id, pin))
        if user.pin is not None and pin != user.pin:
            raise BadRequest("(400) bad_request; PIN is required")
        switched = Account(user.username, uid=user.id, token=f"t-{user.id}")
        switched.username, switched.title = user.username, user.title
        return switched

    def resource(self, _name):
        return types.SimpleNamespace(connections=[])


def accepting(_plex, token):
    """The server as whoever token belongs to: it accepts every account."""
    return Server(Account("someone"), token=token)


def member(uid, title, username="", email="", home=True, pin=None):
    """A user from plex.tv's list: a Plex Home member unless home is False,
    and a managed one when it has no username."""
    return types.SimpleNamespace(id=uid, title=title, username=username,
                                 email=email, home=home, pin=pin)


class Server:
    """The Plex server plexdo is connected to, as some account."""

    friendlyName = "nas"

    def __init__(self, account, owner="admin@x.example", token="t-plexdo",
                 plex_tv_down=False):
        self._baseurl, self._token = "http://10.10.0.5:32400", token
        self.myPlexUsername = owner
        self._account, self._down = account, plex_tv_down

    def myPlexAccount(self):
        if self._down:
            raise RequestsConnectionError("plex.tv unreachable")
        return self._account

    def fetchItem(self, _key):
        return Movie(self, ET.Element(
            "Video", {"type": "movie", "ratingKey": "881", "title": "Heat"}))


class PlayerAt:
    """Stands in for PlexClient: a player answering at some addresses.

    Every client built is recorded, with the media it is told to play.
    """

    def __init__(self, answers=("10.20.0.40",), fails=None, product="Plex HTPC",
                 ports=(32500,)):
        self.answers, self.fails, self.product = answers, fails, product
        self.ports = ports
        self.built = []

    def __call__(self, baseurl=None, token=None, server=None, timeout=None):
        host, port = baseurl.split("//")[1].rsplit(":", 1)
        host = host.strip("[]")
        if host not in self.answers or int(port) not in self.ports:
            raise RequestsConnectionError(f"no route to {host}:{port}")
        recorder = self
        client = types.SimpleNamespace(
            baseurl=baseurl, token=token, server=server, played=[],
            title="Living Room", machineIdentifier="tv-1",
            product=self.product)

        def play_media(media, **params):
            if recorder.fails:
                raise recorder.fails
            client.played.append((media, params))

        client.playMedia = play_media
        self.built.append(client)
        return client


@pytest.fixture(autouse=True)
def no_discovery(monkeypatch):
    """No player answers over GDM, and every guessed port takes a
    connection, unless a test says otherwise: nothing goes on the wire."""
    monkeypatch.setattr(remote, "_advertised_port", lambda address: None)
    monkeypatch.setattr(remote, "_listening", lambda address, port: True)


@pytest.fixture
def player(monkeypatch):
    found = PlayerAt()
    monkeypatch.setattr(remote, "PlexClient", found)
    return found


def configured(monkeypatch, *accounts, filed=None):
    """Config sections [100], [101], ... for these accounts, each filed
    under its username unless `filed` gives another name; an account of
    None is a section whose sign-in fails. Returns the sign-ins made."""
    names = filed or [a.username if a else "nobody" for a in accounts]
    sections = list(enumerate(names, start=100))
    signed_in = []

    def account_of(user_id, username):
        assert (user_id, username) in sections
        signed_in.append(user_id)
        return accounts[user_id - 100]

    monkeypatch.setattr(remote, "configured_sections", lambda: sections)
    monkeypatch.setattr(remote, "configured_account", account_of)
    monkeypatch.setattr(remote, "configured_accounts", lambda: (
        (uid, a) for uid, a in enumerate(accounts, start=100) if a))
    return signed_in


def play(server, host="10.20.0.40", fmt="json", dry_run=False, port=None,
         player_user=None):
    # Parsed as a real command line, so every option the command reads is
    # one the parser actually defines.
    argv = ["player-remote-play", host, "881", "--format", fmt]
    argv += ["--port", str(port)] if port is not None else []
    argv += ["--dry-run"] if dry_run else []
    argv += ["--player-user", player_user] if player_user else []
    remote.cmd_player_remote_play(server, build_parser().parse_args(argv))


def ips(*texts):
    return [ipaddress.ip_address(text) for text in texts]


def addresses(host):
    return [str(ip) for ip in remote._player_addresses(host)]


# --- reaching the player by address -----------------------------------------

def test_an_address_is_used_as_it_is():
    assert addresses("10.20.0.40") == ["10.20.0.40"]
    assert addresses("[2a01:4f8:10::40]") == ["2a01:4f8:10::40"]


def test_a_name_is_resolved_here_in_the_resolvers_order(monkeypatch):
    def getaddrinfo(host, port, type=0):  # pylint: disable=redefined-builtin
        assert (host, port, type) == ("tv.lan", None, socket.SOCK_STREAM)
        return [(socket.AF_INET6, type, 6, "", ("2a01:4f8:10::40", 0, 0, 0)),
                (socket.AF_INET, type, 6, "", ("10.20.0.40", 0)),
                (socket.AF_INET, type, 6, "", ("10.20.0.40", 0))]
    monkeypatch.setattr(remote.socket, "getaddrinfo", getaddrinfo)
    assert addresses("tv.lan") == ["2a01:4f8:10::40", "10.20.0.40"]


def test_a_name_that_does_not_resolve_is_an_error(monkeypatch):
    def getaddrinfo(*_args, **_kwargs):
        raise socket.gaierror("Name or service not known")
    monkeypatch.setattr(remote.socket, "getaddrinfo", getaddrinfo)
    with pytest.raises(SystemExit) as exc:
        remote._player_addresses("tv.nowhere")
    assert "tv.nowhere" in str(exc.value)


def test_the_player_is_asked_by_ip_so_the_host_header_carries_no_name(
        monkeypatch, player):
    monkeypatch.setattr(remote.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.20.0.40", 32500))])
    play(Server(Account("admin", email="admin@x.example")), host="tv.lan")
    assert {c.baseurl for c in player.built} == {"http://10.20.0.40:32500"}


def test_port_sets_the_port_the_player_is_reached_on(player):
    player.ports = (32433,)
    play(Server(Account("admin", email="admin@x.example")), port=32433)
    assert {c.baseurl for c in player.built} == {"http://10.20.0.40:32433"}


def test_each_address_is_tried_until_the_player_answers(player):
    client, address, url = remote._find_player(
        ips("2a01:4f8:10::40", "10.20.0.40"), 32500, "t-plexdo")
    assert str(address) == "10.20.0.40"
    assert client.baseurl == url == "http://10.20.0.40:32500"
    # Asked who it is without a token: it may not be the player at all.
    assert client.token is None


def test_an_ipv6_player_is_reached_bracketed(player):
    player.answers = ("2a01:4f8:10::40",)
    client, _, _ = remote._find_player(ips("2a01:4f8:10::40"), 32500, "t")
    assert client.baseurl == "http://[2a01:4f8:10::40]:32500"


def test_no_player_answering_is_an_error_naming_the_port(player):
    with pytest.raises(SystemExit) as exc:
        remote._find_player(ips("10.99.0.1"), 32500, "t")
    assert "10.99.0.1" in str(exc.value) and "32500" in str(exc.value)


# --- finding the player's port ------------------------------------------------

def test_the_port_the_player_advertises_over_gdm_is_used(monkeypatch, player):
    player.ports = (36000,)
    monkeypatch.setattr(remote, "_advertised_port", lambda address: 36000)
    _, _, url = remote._find_player(ips("10.20.0.40"), None, "t")
    assert url == "http://10.20.0.40:36000"
    assert [c.baseurl for c in player.built] == [url]


def test_a_player_silent_over_gdm_is_tried_on_the_known_ports(player):
    player.ports = (8324,)   # a Roku
    _, _, url = remote._find_player(ips("10.20.0.40"), None, "t")
    assert url == "http://10.20.0.40:8324"


def test_a_guessed_port_taking_no_connection_is_not_probed(monkeypatch,
                                                           player):
    player.ports = (32433,)
    monkeypatch.setattr(remote, "_listening",
                        lambda address, port: port == 32433)
    _, _, url = remote._find_player(ips("10.20.0.40"), None, "t")
    assert url == "http://10.20.0.40:32433"
    # Only the port taking a connection was asked who it is.
    assert [c.baseurl for c in player.built] == [url]


def test_port_given_skips_discovery(monkeypatch, player):
    def advertised(address):
        raise AssertionError("asked over GDM despite --port")
    monkeypatch.setattr(remote, "_advertised_port", advertised)
    player.ports = (8324,)
    remote._find_player(ips("10.20.0.40"), 8324, "t")


def test_no_port_found_says_to_give_port(player):
    player.ports = ()
    with pytest.raises(SystemExit) as exc:
        remote._find_player(ips("10.20.0.40"), None, "t")
    message = str(exc.value)
    assert "--port" in message
    assert all(f"10.20.0.40:{port}" in message for port in remote._KNOWN_PORTS)


@pytest.mark.parametrize("reply, port", [
    (b"HTTP/1.0 200 OK\r\nContent-Type: plex/media-player\r\n"
     b"Name: Living Room\r\nPort: 8324\r\nResource-Identifier: tv-1\r\n",
     8324),
    (b"HTTP/1.0 200 OK\r\nPort: 32500\r\n", 32500),
    (b"HTTP/1.0 200 OK\r\nContent-Type: plex/media-server\r\n"
     b"Port: 32400\r\n", None),
    (b"HTTP/1.0 404 Not Found\r\nPort: 8324\r\n", None),
    (b"HTTP/1.0 200 OK\r\nPort: soon\r\n", None),
    (b"", None),
])
def test_a_gdm_reply_gives_a_players_port(reply, port):
    assert remote._gdm_port(reply) == port


def test_gdm_is_asked_by_unicast_udp(monkeypatch):
    monkeypatch.undo()   # the real _advertised_port
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as fake_player:
        fake_player.bind(("127.0.0.1", 0))
        fake_player.settimeout(5)
        monkeypatch.setattr(remote, "_GDM_PORT", fake_player.getsockname()[1])

        def answer():
            message, sender = fake_player.recvfrom(1024)
            assert message.startswith(b"M-SEARCH * HTTP/1.0")
            fake_player.sendto(b"HTTP/1.0 200 OK\r\nContent-Type: "
                               b"plex/media-player\r\nPort: 8324\r\n",
                               sender)
        responder = threading.Thread(target=answer)
        responder.start()
        assert remote._advertised_port(ipaddress.ip_address("127.0.0.1")) \
            == 8324
        responder.join()


def test_gdm_silence_gives_no_port(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(remote, "_GDM_TIMEOUT", 0.2)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as silent:
        silent.bind(("127.0.0.1", 0))
        monkeypatch.setattr(remote, "_GDM_PORT", silent.getsockname()[1])
        assert remote._advertised_port(ipaddress.ip_address("127.0.0.1")) \
            is None


def test_gdm_is_not_asked_over_ipv6(monkeypatch):
    monkeypatch.undo()
    assert remote._advertised_port(ipaddress.ip_address("2a01:4f8:10::40")) \
        is None


def test_a_closed_port_is_not_listening(monkeypatch):
    monkeypatch.undo()
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]   # bound, never listening
        assert remote._listening(ipaddress.ip_address("127.0.0.1"), port) \
            is False
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        assert remote._listening(ipaddress.ip_address("127.0.0.1"),
                                 server.getsockname()[1]) is True


def test_something_answering_that_is_no_player_is_passed_over(monkeypatch):
    monkeypatch.setattr(remote, "PlexClient", lambda **_: types.SimpleNamespace(
        machineIdentifier=None))
    with pytest.raises(SystemExit) as exc:
        remote._find_player(ips("10.20.0.40"), 32500, "t")
    assert "not a Plex player" in str(exc.value)


def test_a_player_wanting_a_token_to_say_who_it_is_gets_plexdos(monkeypatch):
    def client(baseurl=None, token=None, timeout=None):
        if token is None:
            raise Unauthorized("(401) unauthorized")
        return types.SimpleNamespace(machineIdentifier="tv-1", token=token)
    monkeypatch.setattr(remote, "PlexClient", client)
    found, _, _ = remote._find_player(ips("10.20.0.40"), 32500, "t-plexdo")
    assert found.token == "t-plexdo"


# --- which account to send as -------------------------------------------------

def test_the_servers_admin_sends_as_itself(monkeypatch):
    configured(monkeypatch, Account("bob", devices=["tv-1"]))
    server = Server(Account("admin", email="Admin@X.example"))
    assert remote._controller(server, "tv-1", "TV").token == "t-plexdo"


def test_an_account_signed_in_to_the_player_sends_as_itself(monkeypatch):
    configured(monkeypatch)
    server = Server(Account("carol", devices=["tv-1"]))
    picked = remote._controller(server, "tv-1", "TV")
    assert (picked.name, picked.token) == ("carol", "t-plexdo")


def test_otherwise_a_configured_account_signed_in_to_the_player_is_used(
        monkeypatch):
    other = Server(Account("x"))
    monkeypatch.setattr(remote, "connect_with_token",
                        lambda plex, token: other)
    configured(monkeypatch, Account("dave", devices=["tv-9"]),
               Account("bob", devices=["tv-1"]))
    server = Server(Account("carol", devices=["phone-3"]))
    picked = remote._controller(server, "tv-1", "TV")
    assert (picked.name, picked.token, picked.server) == \
        ("bob", "t-bob", other)


def test_a_configured_account_the_server_refuses_fetches_as_plexdo(
        monkeypatch):
    monkeypatch.setattr(remote, "connect_with_token", lambda plex, token: None)
    configured(monkeypatch, Account("bob", devices=["tv-1"]))
    server = Server(Account("carol"))
    picked = remote._controller(server, "tv-1", "TV")
    assert (picked.token, picked.server) == ("t-bob", server)


def test_with_no_matching_account_it_is_tried_anyway_with_a_warning(
        monkeypatch, caplog):
    configured(monkeypatch, Account("dave", devices=["tv-9"]))
    server = Server(Account("carol"))
    picked = remote._controller(server, "tv-1", "TV")
    assert picked.token == "t-plexdo"
    assert "trying anyway" in caplog.text


def test_plex_tv_being_down_tries_plexdos_own_token(monkeypatch, caplog):
    configured(monkeypatch)
    picked = remote._controller(Server(None, plex_tv_down=True), "tv-1", "TV")
    assert picked.token == "t-plexdo"
    assert "plex.tv" in caplog.text


# --- naming the player's account ---------------------------------------------

@pytest.mark.parametrize("value", ["carol", "CAROL@x.example", "7"])
def test_player_user_naming_plexdos_own_account_sends_as_it(monkeypatch,
                                                             value):
    signed_in = configured(monkeypatch, Account("bob"))
    picked = remote._named_controller(Server(Account("carol")), value)
    assert (picked.name, picked.token) == ("carol", "t-plexdo")
    assert signed_in == []


def test_player_user_0_is_plexdo_only_when_plexdo_is_the_admin(monkeypatch):
    configured(monkeypatch)
    admin = Server(Account("admin", email="admin@x.example"))
    assert remote._named_controller(admin, "0").token == "t-plexdo"
    with pytest.raises(SystemExit):
        remote._named_controller(Server(Account("carol")), "0")


def test_player_user_overrides_plexdo_being_the_admin(monkeypatch):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    configured(monkeypatch, Account("bob"))
    admin = Server(Account("admin", email="admin@x.example"))
    assert remote._named_controller(admin, "bob").token == "t-bob"


def test_a_section_named_by_id_or_username_is_signed_in_alone(monkeypatch):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    signed_in = configured(monkeypatch, Account("dave"), Account("bob"))
    assert remote._named_controller(Server(Account("carol")),
                                     "101").token == "t-bob"
    assert remote._named_controller(Server(Account("carol")),
                                     "Bob").token == "t-bob"
    assert signed_in == [101, 101]


def test_an_account_filed_under_its_email_is_found_by_username(monkeypatch):
    """Nothing in the config says bob is bob@x.example until he signs in."""
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    signed_in = configured(monkeypatch, None, Account("dave"),
                           Account("bob", uid=55),
                           filed=["eve@x.example", "dave@x.example",
                                  "bob@x.example"])
    for value in ("bob", "55"):
        assert remote._named_controller(Server(Account("carol")),
                                         value).token == "t-bob"
    # Sections are signed in only until the account turns up.
    assert signed_in == [100, 101, 102, 100, 101, 102]


def test_a_player_user_without_credentials_is_an_error_not_a_fallback(
        monkeypatch):
    configured(monkeypatch, Account("dave"))
    with pytest.raises(SystemExit) as exc:
        remote._named_controller(Server(Account("carol")), "bob")
    assert "[<user id>]" in str(exc.value) and "carol" in str(exc.value)


def test_a_player_user_needs_plex_tv(monkeypatch):
    configured(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        remote._named_controller(Server(None, plex_tv_down=True), "bob")
    assert "plex.tv" in str(exc.value)


CLARE = member(826699965, "Clare")                      # managed
ALEX = member(9006167, "alexfreas", username="alexfreas",
              email="alex@x.example")                    # home, own account
BUGS = member(8401793, "Bugs Bunny", username="bugs", home=False)  # shared


def home_admin(*users):
    return Server(Account("admin", email="admin@x.example",
                          users=users or (CLARE, ALEX, BUGS)))


@pytest.mark.parametrize("value", ["826699965", "Clare", "clare"])
def test_a_managed_user_is_switched_into_by_id_or_name(monkeypatch, value):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    signed_in = configured(monkeypatch, Account("bob"))
    server = home_admin()
    picked = remote._named_controller(server, value)
    assert (picked.name, picked.token) == ("Clare", "t-826699965")
    assert server._account.switched == [(826699965, None)]
    assert signed_in == []   # no password needed


@pytest.mark.parametrize("value", ["9006167", "ALEXFREAS", "alex@x.example"])
def test_a_home_member_is_switched_into_by_id_username_or_email(monkeypatch,
                                                                value):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    configured(monkeypatch)
    assert remote._named_controller(home_admin(), value).token == "t-9006167"


def test_a_shared_user_outside_the_home_is_not_switched_into(monkeypatch):
    configured(monkeypatch)
    server = home_admin()
    with pytest.raises(SystemExit) as exc:
        remote._named_controller(server, "bugs")
    assert server._account.switched == []
    assert "Plex Home" in str(exc.value)


def test_a_home_member_with_a_pin_takes_it_from_its_section(monkeypatch):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    configured(monkeypatch)
    monkeypatch.setattr(remote, "section_optional",
                        lambda cfg, section, key: "4321"
                        if (section, key) == ("826699965", "pin") else None)
    kid = member(826699965, "Clare", pin="4321")
    server = home_admin(kid)
    assert remote._named_controller(server, "Clare").token == "t-826699965"
    assert server._account.switched == [(826699965, "4321")]


def test_a_refused_switch_without_a_section_says_what_to_add(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(remote, "section_optional", lambda *a: None)
    with pytest.raises(SystemExit) as exc:
        remote._named_controller(
            home_admin(member(826699965, "Clare", pin="4321")), "Clare")
    message = str(exc.value)
    assert "PIN" in message and "[826699965]" in message


def test_a_refused_switch_falls_back_to_the_section_password(monkeypatch):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    monkeypatch.setattr(remote, "section_optional", lambda *a: None)
    configured(monkeypatch, Account("alexfreas", uid=9006167))
    alex = member(9006167, "alexfreas", username="alexfreas", pin="1")
    assert remote._named_controller(home_admin(alex),
                                     "alexfreas").token == "t-alexfreas"


def test_the_command_sends_as_a_managed_user(monkeypatch, player, capsys):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    configured(monkeypatch)
    play(home_admin(), player_user="826699965")
    assert player.built[-1].token == "t-826699965"
    assert json.loads(capsys.readouterr().out)["account"] == "Clare"


def test_a_managed_user_the_server_refuses_fetches_with_its_issued_token(
        monkeypatch, player):
    """A managed user's own plex.tv token is refused by the server, so the
    item is fetched with the token the server issues for it: fetched as
    plexdo, the player would switch to plexdo's user."""
    monkeypatch.setattr(remote, "connect_with_token", lambda plex, token: None)
    shared = Server(Account("Clare"), token="t-issued")
    monkeypatch.setattr(remote, "connect_as_shared_user",
                        lambda plex, user: shared if user is CLARE else None)
    configured(monkeypatch)
    picked = remote._named_controller(home_admin(), "Clare")
    assert (picked.name, picked.token, picked.server) == (
        "Clare", "t-826699965", shared)


def test_a_player_user_the_server_will_not_have_is_an_error(monkeypatch):
    monkeypatch.setattr(remote, "connect_with_token", lambda plex, token: None)
    monkeypatch.setattr(remote, "connect_as_shared_user",
                        lambda plex, user: None)
    configured(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        remote._named_controller(home_admin(), "Clare")
    assert "switch to that user" in str(exc.value)


def test_the_command_fetches_the_item_as_the_player_user(monkeypatch, player):
    """plexapi makes the play queue and the player's token on the server
    the item came from, so that decides whom the player plays as."""
    fetched_by = []

    class Recording(Server):
        def fetchItem(self, key):
            fetched_by.append(self._token)
            return super().fetchItem(key)
    monkeypatch.setattr(remote, "connect_with_token", lambda plex, token:
                        Recording(Account("someone"), token=token))
    configured(monkeypatch)
    play(home_admin(), player_user="Clare")
    assert fetched_by == ["t-826699965"]


def test_the_command_sends_as_the_player_user(monkeypatch, player):
    monkeypatch.setattr(remote, "connect_with_token", accepting)
    configured(monkeypatch, Account("bob", devices=["phone-1"]))
    play(Server(Account("admin", email="admin@x.example")), player_user="bob")
    assert player.built[-1].token == "t-bob"


# --- the command -------------------------------------------------------------

def test_the_command_goes_straight_to_the_player_as_the_chosen_account(
        monkeypatch, player, capsys):
    other = Server(Account("x"))
    monkeypatch.setattr(remote, "connect_with_token",
                        lambda plex, token: other)
    configured(monkeypatch, Account("bob", devices=["tv-1"]))
    play(Server(Account("carol")))
    sender = player.built[-1]
    assert (sender.baseurl, sender.token, sender.server) == \
        ("http://10.20.0.40:32500", "t-bob", other)
    [(media, params)] = sender.played
    # Fetched through bob's own connection, so the play counts as his.
    assert media._server is other
    assert params == {"protocol": "http", "address": "10.10.0.5",
                      "port": "32400"}
    record = json.loads(capsys.readouterr().out)
    assert (record["account"], record["playerAddress"], record["fetchFrom"]) \
        == ("bob", "http://10.20.0.40:32500", "http://10.10.0.5:32400")


def test_dry_run_finds_everything_and_sends_nothing(player, capsys):
    play(Server(Account("admin", email="admin@x.example")), fmt="table",
         dry_run=True)
    assert all(not c.played for c in player.built)
    assert capsys.readouterr().out.strip() == (
        'Would send "Heat" to Living Room at http://10.20.0.40:32500 as '
        "admin, fetching from http://10.10.0.5:32400.")


def test_a_refused_command_says_how_to_send_as_the_players_account(player):
    player.fails = Unauthorized("(401) unauthorized")
    with pytest.raises(SystemExit) as exc:
        play(Server(Account("admin", email="admin@x.example")))
    assert "[<user id>]" in str(exc.value)


def test_a_reply_that_is_not_xml_still_counts_as_sent(player, capsys):
    player.fails = ET.ParseError("syntax error")
    play(Server(Account("admin", email="admin@x.example")), fmt="table")
    assert capsys.readouterr().out.startswith('Sent "Heat"')
