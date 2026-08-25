# SPDX-License-Identifier: GPL-3.0-or-later

"""Consolidated server status: sessions, users, activity, and identity."""

from typing import Any, Dict, List, Optional
import argparse
import sys

from plexapi.server import PlexServer

from plexdo.accounts import account_type
from plexdo.console import clean_text, output, output_format, print_metadata, print_table, table_limit
from plexdo.constants import LOG
from plexdo.convert import format_duration, parse_date
from plexdo.formats import render
from plexdo.titles import display_title


# Activity types Plex uses for library scanning, as opposed to the other
# background work (metadata refresh, subscriptions, media analysis).
_SCAN_MARKERS = ("scan", "refresh", "library")


def _server_record(plex: PlexServer) -> Dict[str, Any]:
    """Identity and version details for the server itself."""
    updated = parse_date(getattr(plex, "updatedAt", None))
    return {
        "name": clean_text(getattr(plex, "friendlyName", "") or ""),
        "version": clean_text(getattr(plex, "version", "") or ""),
        "machineIdentifier": clean_text(getattr(plex, "machineIdentifier", "") or ""),
        "platform": clean_text(getattr(plex, "platform", "") or ""),
        "platformVersion": clean_text(getattr(plex, "platformVersion", "") or ""),
        "updatedAt": updated.isoformat(sep=" ") if updated else "",
        "myPlexUsername": clean_text(getattr(plex, "myPlexUsername", "") or ""),
        "myPlexSubscription": bool(getattr(plex, "myPlexSubscription", False)),
    }


def _format_offset(milliseconds: Any, duration: Any) -> str:
    """Render a playback position as elapsed / total."""
    elapsed = format_duration(milliseconds) or "-"
    total = format_duration(duration) or "-"
    return f"{elapsed} / {total}"


def _session_rows(plex: PlexServer) -> List[Dict[str, Any]]:
    """One row per item currently being played."""
    rows: List[Dict[str, Any]] = []
    for item in plex.sessions():
        players = getattr(item, "players", []) or []
        player = players[0] if players else None
        usernames = getattr(item, "usernames", []) or []
        rows.append({
            "user": clean_text(usernames[0] if usernames else ""),
            "title": display_title(item),
            "state": clean_text(getattr(player, "state", "") or ""),
            "player": clean_text(getattr(player, "title", "") or ""),
            "platform": clean_text(getattr(player, "platform", "") or ""),
            "address": clean_text(getattr(player, "address", "") or ""),
            "progress": _format_offset(
                getattr(item, "viewOffset", 0), getattr(item, "duration", 0)
            ),
        })
    return rows


def _user_rows(plex: PlexServer) -> List[Dict[str, Any]]:
    """Shared and managed users visible to the admin token."""
    return [
        {
            "id": int(user.id),
            "type": account_type(user),
            "title": clean_text(user.title or ""),
            "username": clean_text(getattr(user, "username", "") or ""),
            "email": clean_text(getattr(user, "email", "") or ""),
        }
        for user in plex.myPlexAccount().users()
    ]


def _system_account_rows(plex: PlexServer) -> List[Dict[str, Any]]:
    """Accounts the server itself knows about, which is not the same list."""
    return [
        {
            "id": int(account.id),
            "name": clean_text(account.name or ""),
            "audioLanguage": clean_text(getattr(account, "defaultAudioLanguage", "") or ""),
            "subtitleLanguage": clean_text(
                getattr(account, "defaultSubtitleLanguage", "") or ""
            ),
        }
        for account in plex.systemAccounts()
    ]


def _connection_rows(plex: PlexServer) -> List[Dict[str, Any]]:
    """Addresses plex.tv advertises for this server."""
    try:
        resource = plex.myPlexAccount().resource(plex.friendlyName)
        connections = list(resource.connections)
    except Exception as exc:  # pylint: disable=broad-except
        # Needs a plex.tv round trip, which a local-only or offline server
        # cannot satisfy; the rest of the report is still worth printing.
        LOG.debug("Could not list connections: %s", exc)
        return []
    return [
        {
            "uri": clean_text(conn.uri or ""),
            "address": clean_text(conn.address or ""),
            "port": conn.port,
            "protocol": clean_text(conn.protocol or ""),
            "local": bool(conn.local),
            "relay": bool(conn.relay),
            "ipv6": bool(getattr(conn, "ipv6", False)),
        }
        for conn in connections
    ]


def _is_scan(activity: Any) -> bool:
    """True when an activity is library scanning rather than other work."""
    kind = str(getattr(activity, "type", "")).lower()
    return any(marker in kind for marker in _SCAN_MARKERS)


def _split_activity_rows(plex: PlexServer, scans: bool) -> List[Dict[str, Any]]:
    """In-progress activities, split into scans and everything else."""
    return [
        {
            "type": clean_text(getattr(act, "type", "") or ""),
            "title": clean_text(getattr(act, "title", "") or ""),
            "subtitle": clean_text(getattr(act, "subtitle", "") or ""),
            "progress": getattr(act, "progress", ""),
            "cancellable": bool(getattr(act, "cancellable", False)),
        }
        for act in plex.activities
        if _is_scan(act) is scans
    ]


def _butler_rows(plex: PlexServer) -> List[Dict[str, Any]]:
    """Scheduled maintenance tasks and whether each is enabled."""
    try:
        tasks = plex.butlerTasks()
    except Exception as exc:  # pylint: disable=broad-except
        LOG.debug("Could not list butler tasks: %s", exc)
        return []
    return [
        {
            "name": clean_text(task.name or ""),
            "title": clean_text(getattr(task, "title", "") or ""),
            "enabled": bool(getattr(task, "enabled", False)),
            "interval": getattr(task, "interval", ""),
        }
        for task in tasks
    ]


# Section name -> (heading, collector). Order sets the order of the report.
_SECTIONS: Dict[str, Any] = {
    "server": ("Server", _server_record),
    "sessions": ("Active sessions", _session_rows),
    "users": ("Shared users", _user_rows),
    "accounts": ("System accounts", _system_account_rows),
    "connections": ("Reachable addresses", _connection_rows),
    "scans": ("Library scans in progress", lambda p: _split_activity_rows(p, True)),
    "activities": ("Other background activity", lambda p: _split_activity_rows(p, False)),
    "tasks": ("Scheduled background tasks", _butler_rows),
}

SECTION_NAMES = tuple(_SECTIONS)


def _collect(plex: PlexServer, names: List[str]) -> Dict[str, Any]:
    """Gather the requested sections, tolerating a failure in any one."""
    gathered: Dict[str, Any] = {}
    for name in names:
        _, collector = _SECTIONS[name]
        try:
            gathered[name] = collector(plex)
        except Exception as exc:  # pylint: disable=broad-except
            # One unavailable section must not cost the whole report.
            LOG.warning("Could not read %s: %s", name, exc)
            gathered[name] = [] if name != "server" else {}
    return gathered


def _print_report(gathered: Dict[str, Any], limit: Optional[int]) -> None:
    """Print the full multi-section report for the table renderer."""
    for name, payload in gathered.items():
        heading, _ = _SECTIONS[name]
        print(f"\n{heading}")
        if isinstance(payload, dict):
            print_metadata(payload, limit)
        elif payload:
            print_table(payload, limit)
        else:
            print("  (none)")


def cmd_status(plex: PlexServer, args: argparse.Namespace) -> None:
    """Show a consolidated view of what the server is doing."""
    names = [args.section] if args.section else list(SECTION_NAMES)
    chosen = output_format(args)

    # csv and clixml are flat by nature and cannot carry eight differently
    # shaped sections, so one must be named.
    if chosen in ("csv", "clixml") and not args.section:
        sys.exit(
            f"--format {chosen} needs a single section: pass --section with "
            f"one of {', '.join(SECTION_NAMES)}."
        )

    gathered = _collect(plex, names)

    if args.section:
        output(gathered[args.section], args)
        return
    if chosen == "table":
        _print_report(gathered, table_limit(args))
        return
    print(render(gathered, chosen))


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the status subparser."""
    parser = sub.add_parser(
        "status", parents=parents,
        help="Show server identity, sessions, users, scans, and background tasks.",
    )
    parser.add_argument(
        "--section", choices=list(SECTION_NAMES), default=None, metavar="SECTION",
        help=(
            "Show only one section: " + ", ".join(SECTION_NAMES) + ". "
            "Required for --format csv and --format clixml."
        ),
    )


COMMANDS = {"status": cmd_status}

REQUIRES_PLEX = frozenset(COMMANDS)
