# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Shared fixtures.

Everything here is a stand-in for plexapi objects: the tests cover the
project's own decision logic, so nothing touches a network or a real server.
"""

import pathlib
import sys
from typing import Any

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

# pylint: disable-next=wrong-import-position  (needs the sys.path entry above)
from plexdo import secret_store  # noqa: E402


class MemoryStore:
    """The secret store, held in memory.

    No test reads or writes the keyring, or the secrets file, of whoever
    runs it.
    """

    def __init__(self) -> None:
        self.entries: dict = {}

    def describe(self) -> str:
        return "the test keyring"

    def read(self, kind: str):
        return self.entries.get(kind)

    def write(self, kind: str, text: str) -> None:
        self.entries[kind] = text

    def remove(self, kind: str) -> None:
        self.entries.pop(kind, None)


# The real chooser, for the tests of it, before the fixture replaces it.
REAL_BACKEND = secret_store.backend


@pytest.fixture(autouse=True)
def secrets(monkeypatch):
    """Every test gets an empty secret store of its own."""
    store = MemoryStore()
    monkeypatch.setattr(secret_store, "backend", lambda: store)
    return store


class FakeItem:
    """Minimal stand-in for a playable item."""

    def __init__(
        self, rating_key: int = 1, title: str = "A Title", **kw: Any
    ) -> None:
        self.ratingKey = rating_key
        self.title = title
        self.type = kw.pop("type", "movie")
        self.duration = kw.pop("duration", 0)
        self.media = kw.pop("media", [])
        for key, value in kw.items():
            setattr(self, key, value)


class FakePart:
    """One file backing a media version."""

    def __init__(self, file: str | None, **kw: Any) -> None:
        self.file = file
        self.size = kw.pop("size", 100)
        self.container = kw.pop("container", "mkv")
        self._server = object()  # private: must never be reported


class FakeMedia:
    """One media version, which may span several parts."""

    def __init__(self, *files: str | None, **kw: Any) -> None:
        self.parts = [FakePart(f) for f in files]
        self.videoResolution = kw.pop("videoResolution", "1080")


class FakeSection:
    def __init__(
        self,
        key: int,
        title: str,
        locations: list[str] | None = None,
        stype: str = "movie",
    ) -> None:
        self.key, self.title, self.type = key, title, stype
        self.locations = locations or []


class FakeLibrary:
    def __init__(self, sections: list[FakeSection]) -> None:
        self._sections = sections

    def sections(self) -> list[FakeSection]:
        return self._sections


class FakePlex:
    """Stand-in for PlexServer, carrying only what the tests need."""

    def __init__(
        self,
        sections: list[FakeSection] | None = None,
        playlists: list[Any] | None = None,
    ) -> None:
        self.library = FakeLibrary(sections or [])
        self._playlists = playlists or []
        self.created: list[Any] = []

    def playlists(self) -> list[Any]:
        return self._playlists

    def createPlaylist(self, name: str, items: Any = None) -> None:
        self.created.append((name, list(items or [])))


class FakePlaylist:
    def __init__(self, title: str, rating_key: int = 900) -> None:
        self.title, self.ratingKey = title, rating_key
        self.deleted = False

    def delete(self) -> None:
        self.deleted = True


@pytest.fixture
def args():
    """A Namespace with the global flags every command expects."""
    import argparse

    return argparse.Namespace(
        format="json",
        dry_run=False,
        verbose=False,
        debug=False,
        overwrite=False,
    )
