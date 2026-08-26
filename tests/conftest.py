# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared fixtures.

Everything here is a stand-in for plexapi objects: the tests cover the
project's own decision logic, so nothing touches a network or a real server.
"""

import pathlib
import sys
from typing import Any, List

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


class FakeItem:
    """Minimal stand-in for a playable item."""

    def __init__(self, rating_key: int = 1, title: str = "A Title",
                 **kw: Any) -> None:
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
        self._server = object()          # private: must never be reported


class FakeMedia:
    """One media version, which may span several parts."""

    def __init__(self, *files: str | None, **kw: Any) -> None:
        self.parts = [FakePart(f) for f in files]
        self.videoResolution = kw.pop("videoResolution", "1080")


class FakeSection:
    def __init__(self, key: int, title: str, locations: List[str] | None = None,
                 stype: str = "movie") -> None:
        self.key, self.title, self.type = key, title, stype
        self.locations = locations or []


class FakeLibrary:
    def __init__(self, sections: List[FakeSection]) -> None:
        self._sections = sections

    def sections(self) -> List[FakeSection]:
        return self._sections


class FakePlex:
    """Stand-in for PlexServer, carrying only what the tests need."""

    def __init__(self, sections: List[FakeSection] | None = None,
                 playlists: List[Any] | None = None) -> None:
        self.library = FakeLibrary(sections or [])
        self._playlists = playlists or []
        self.created: List[Any] = []

    def playlists(self) -> List[Any]:
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
        format="json", dry_run=False, verbose=False, debug=False, overwrite=False,
    )
