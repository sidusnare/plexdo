# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Where secrets are kept: the system keyring, or a private file.

Three kinds are kept, each one JSON object filed as a single entry under
the service name "plexdo": "tokens" (username -> plex.tv token),
"passwords" (username -> password, saved only on request), and "pins"
(user id -> Plex Home PIN). A whole kind is one entry because a keyring
cannot list what it holds, and logout must find every token to sign out.

The keyring is the Secret Service on Linux and BSD, the Keychain on macOS,
and Credential Manager on Windows, all through the keyring package. Where
there is none, as on a headless machine with no session bus, the secrets
go in a JSON file readable by the user alone, with a warning, since that
file is not encrypted.
"""

import json
import os
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Protocol, TypeVar

import keyring
import keyring.errors
from keyring.backends import chainer, fail

from plexdo.config import cached_config, check_file_permissions, config_optional
from plexdo.constants import CONFIG_PATH, DEFAULT_SECRETS_FILE, LOG

SERVICE = "plexdo"

Secrets = dict[str, str]

_T = TypeVar("_T")


class Store(Protocol):
    """What a place to keep secrets provides."""

    def describe(self) -> str:
        """Where the secrets are, for messages."""

    def read(self, kind: str) -> str | None:
        """The JSON text filed for kind, or None."""

    def write(self, kind: str, text: str) -> None:
        """File text for kind, replacing what was there."""

    def remove(self, kind: str) -> None:
        """Remove the entry for kind, if there is one."""


class KeyringStore:
    """Secrets in the system keyring."""

    def __init__(self, ring: keyring.backend.KeyringBackend) -> None:
        self._backend = ring

    def describe(self) -> str:
        """Where the secrets are, for messages."""
        return f"the system keyring ({self._backend.name})"

    def read(self, kind: str) -> str | None:
        """The JSON text filed for kind, or None."""
        return _keyring_call(lambda: self._backend.get_password(SERVICE, kind))

    def write(self, kind: str, text: str) -> None:
        """File text for kind, replacing what was there."""
        _keyring_call(lambda: self._backend.set_password(SERVICE, kind, text))

    def remove(self, kind: str) -> None:
        """Remove the entry for kind, if there is one."""
        try:
            _keyring_call(lambda: self._backend.delete_password(SERVICE, kind))
        except keyring.errors.PasswordDeleteError:
            pass


def _keyring_call(call: Callable[[], _T]) -> _T:
    """Run one keyring operation, turning a failure into advice.

    A keyring that is locked, or whose unlock prompt was dismissed, fails
    here; secret_store: file is the way out for a machine where that is
    the norm, such as one running plexdo from cron.
    """
    try:
        return call()
    except keyring.errors.PasswordDeleteError:
        raise
    except keyring.errors.KeyringError as exc:
        sys.exit(
            f"The system keyring could not be used: {exc}. Unlock it, "
            f"or set plex: secret_store: file in {CONFIG_PATH} to keep "
            "secrets in a private file instead."
        )


class FileStore:
    """Secrets in a JSON file readable by its owner alone."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def describe(self) -> str:
        """Where the secrets are, for messages."""
        return f"the secrets file {self.path}"

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        check_file_permissions(self.path, "secrets file")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            sys.exit(f"Could not read the secrets file {self.path}: {exc}")
        if not isinstance(data, dict):
            sys.exit(f"The secrets file {self.path} is not a JSON object.")
        return {str(kind): json.dumps(value) for kind, value in data.items()}

    def _save(self, entries: dict[str, str]) -> None:
        if not entries:
            if self.path.exists():
                self.path.unlink()
                LOG.debug("Secrets file %s is empty; removed it", self.path)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        # Created private rather than tightened after, so the secrets are
        # never readable by anyone else, not even for a moment.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            data = {kind: json.loads(text) for kind, text in entries.items()}
            handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        tmp.replace(self.path)
        LOG.debug("Secrets written to %s", self.path)

    def read(self, kind: str) -> str | None:
        """The JSON text filed for kind, or None."""
        return self._load().get(kind)

    def write(self, kind: str, text: str) -> None:
        """File text for kind, replacing what was there."""
        entries = self._load()
        entries[kind] = text
        self._save(entries)

    def remove(self, kind: str) -> None:
        """Remove the entry for kind, if there is one."""
        entries = self._load()
        if entries.pop(kind, None) is not None:
            self._save(entries)


def _usable(ring: keyring.backend.KeyringBackend) -> bool:
    """Whether keyring found a real keyring.

    Its stand-in for none, or a chain of no keyrings at all, is not one.
    """
    if isinstance(ring, fail.Keyring):
        return False
    if isinstance(ring, chainer.ChainerBackend):
        return bool(ring.backends)
    return True


def open_store(choice: str, path: Path) -> Store:
    """The store secret_store names: "keyring", "file", or "auto"."""
    if choice == "file":
        return FileStore(path)
    ring = keyring.get_keyring()
    if _usable(ring):
        return KeyringStore(ring)
    if choice == "keyring":
        sys.exit(
            "plex: secret_store is keyring, but no system keyring is "
            "available here. Start one, such as GNOME Keyring or "
            f"KWallet, or set secret_store: file in {CONFIG_PATH}."
        )
    LOG.warning(
        "No system keyring is available, so secrets are kept unencrypted in "
        "%s, readable by your account alone. Set plex: secret_store: file "
        "in %s to say that is intended and silence this warning.",
        path,
        CONFIG_PATH,
    )
    return FileStore(path)


@lru_cache(maxsize=1)
def backend() -> Store:
    """The store this run uses, chosen once.

    Works before the configuration exists, with the defaults, since the
    migration from plexdo 1.x saves secrets before writing the file.
    """
    choice, path = "auto", DEFAULT_SECRETS_FILE
    if CONFIG_PATH.exists():
        cfg = cached_config()
        choice = config_optional(cfg, "secret_store") or "auto"
        configured = config_optional(cfg, "secrets_file")
        if configured:
            path = Path(configured).expanduser()
    store = open_store(choice, path)
    LOG.debug("Secrets are kept in %s", store.describe())
    return store


def load(kind: str) -> Secrets:
    """Every secret of one kind, as name -> secret."""
    text = backend().read(kind)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        LOG.warning("The saved %s are not readable and are ignored.", kind)
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(name): str(value) for name, value in data.items() if value}


def save(kind: str, secrets: Secrets) -> None:
    """Replace every secret of one kind.

    None left removes the entry, so no secret outlives the last one.
    """
    if secrets:
        backend().write(kind, json.dumps(secrets, sort_keys=True))
    else:
        backend().remove(kind)


def describe() -> str:
    """Where this run's secrets are, for messages."""
    return backend().describe()
