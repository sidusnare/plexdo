# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""metadata --update: what it changes, skips, and refuses."""

import argparse
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from plexapi.mixins import EditTagsMixin

from plexdo.cli import build_parser, parse_arguments
from plexdo.commands import metadata


class FakeMovie:
    """A movie that records the edits plexapi would send."""

    type = "movie"
    _tagHelper = staticmethod(EditTagsMixin._tagHelper)

    def __init__(self) -> None:
        self.ratingKey = 881
        self.title = "Old Title"
        self.year = 1999
        self.contentRating = "PG"
        self.rating = 7.0
        self.duration = 5400000
        self.addedAt = datetime(2024, 1, 2, 3, 4, 5)
        self.updatedAt = datetime(2024, 2, 3, 4, 5, 6)
        self.summary = "A summary."
        self.studio = "Studio"
        self.originallyAvailableAt = datetime(1999, 5, 1)
        self.tagline = ""
        self.genres = [SimpleNamespace(tag="Drama"), SimpleNamespace(tag="War")]
        self.directors = []
        self._data = None
        part = SimpleNamespace(file="/media/old.mkv", selected=False)
        self.media = [SimpleNamespace(parts=[part], selected=False)]
        self.sent: list[dict] = []
        self.batch: dict | None = None
        self.saved = False

    def batchEdits(self):
        self.batch = {}
        return self

    def saveEdits(self):
        self.sent.append(self.batch)
        self.batch = None
        self.saved = True
        return self

    def _edit(self, **edits):
        assert self.batch is not None, "edits must be batched"
        self.batch.update(edits)
        return self

    def _field(self, field, value):
        return self._edit(
            **{f"{field}.value": value or "", f"{field}.locked": 1}
        )

    def editTitle(self, value):
        return self._field("title", value)

    def editSummary(self, value):
        return self._field("summary", value)

    def editContentRating(self, value):
        return self._field("contentRating", value)

    def editCriticRating(self, value):
        return self._field("rating", value)

    def editAddedAt(self, value):
        return self._field("addedAt", int(value.timestamp()))

    def editOriginallyAvailable(self, value):
        return self._field("originallyAvailableAt", value)

    def editStudio(self, value):
        return self._field("studio", value)

    def editTagline(self, value):
        return self._field("tagline", value)

    def addGenre(self, genres):  # only its presence matters
        raise AssertionError("tags go through _tagHelper")

    def addDirector(self, directors):
        raise AssertionError("tags go through _tagHelper")


class FakeEpisode(FakeMovie):
    """An episode: no tagline, studio, or genres to edit."""

    type = "episode"
    editTagline = editStudio = addGenre = None

    def __init__(self) -> None:
        super().__init__()
        self.grandparentTitle = "The Show"
        self.seasonNumber = 2
        self.index = 5
        self.title = "Pilot"

    def __getattribute__(self, name):
        if name in ("editTagline", "editStudio", "addGenre"):
            raise AttributeError(name)
        return super().__getattribute__(name)


def shown(item) -> dict:
    """What metadata --json prints for the item."""
    record = metadata._metadata_record(item)
    record["files"] = metadata.file_paths(item)
    return json.loads(json.dumps(record, default=str))


def run(monkeypatch, item, fields, dry_run=False, path="edit.json"):
    monkeypatch.setattr(metadata, "fetch_item", lambda plex, key: item)
    args = argparse.Namespace(
        rating_key=str(item.ratingKey),
        update=path,
        update_fields=fields,
        dry_run=dry_run,
        format="json",
        json=True,
        wide=False,
    )
    metadata.cmd_show_metadata(None, args)


def test_unchanged_file_changes_nothing(monkeypatch, capsys):
    movie = FakeMovie()
    run(monkeypatch, movie, shown(movie))
    assert movie.sent == []
    assert "Nothing to change" in capsys.readouterr().err


def test_changed_fields_are_sent_in_one_batch(monkeypatch, capsys):
    movie = FakeMovie()
    fields = shown(movie)
    fields.update(title="New Title", rating=8.5, airDate="2001-02-03")
    run(monkeypatch, movie, fields)
    (sent,) = movie.sent
    assert sent["title.value"] == "New Title"
    assert sent["rating.value"] == 8.5
    assert sent["originallyAvailableAt.value"] == "2001-02-03"
    assert "summary.value" not in sent
    err = capsys.readouterr().err
    assert "Changing title: 'Old Title' -> 'New Title'" in err


def test_missing_keys_are_left_alone(monkeypatch):
    movie = FakeMovie()
    run(monkeypatch, movie, {"summary": "Rewritten."})
    assert movie.sent == [{"summary.value": "Rewritten.", "summary.locked": 1}]


def test_unchangeable_field_with_the_same_value_is_skipped(monkeypatch):
    movie = FakeMovie()
    run(
        monkeypatch,
        movie,
        {
            "ratingKey": "881",
            "duration": "1:30:00",
            "year": 1999,
            "files": ["/media/old.mkv"],
            "tagline": None,
        },
    )
    assert movie.sent == []


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("year", 2001, "change airDate"),
        ("duration", "2:00:00", "measured from the media"),
        ("ratingKey", 12, "different one"),
        ("files", ["/elsewhere.mkv"], "media on disk"),
    ],
)
def test_changed_unchangeable_field_stops_everything(
    monkeypatch, field, value, reason
):
    movie = FakeMovie()
    with pytest.raises(SystemExit) as stop:
        run(monkeypatch, movie, {"title": "New", field: value})
    assert movie.sent == []
    assert f"{field}: cannot be changed" in str(stop.value)
    assert reason in str(stop.value)


def test_every_problem_is_reported_at_once(monkeypatch):
    movie = FakeMovie()
    with pytest.raises(SystemExit) as stop:
        run(monkeypatch, movie, {"year": 1, "rating": 11, "colour": "red"})
    message = str(stop.value)
    assert "year: cannot be changed" in message
    assert "rating: must be from 0 to 10" in message
    assert "colour: not a field metadata shows for a movie" in message
    assert "edit.json" in message


def test_field_the_type_cannot_edit_is_refused(monkeypatch):
    episode = FakeEpisode()
    with pytest.raises(SystemExit) as stop:
        run(monkeypatch, episode, {"studio": "Elsewhere"})
    assert "Plex cannot edit it on an episode" in str(stop.value)


def test_episode_title_drops_the_show_prefix(monkeypatch):
    episode = FakeEpisode()
    run(monkeypatch, episode, {"title": "The Show - Pilot"})
    assert episode.sent == []
    run(monkeypatch, episode, {"title": "The Show - Second Pilot"})
    assert episode.sent[0]["title.value"] == "Second Pilot"


def test_genres_are_set_and_dropped_ones_removed(monkeypatch):
    movie = FakeMovie()
    run(monkeypatch, movie, {"genres": "War, History"})
    (sent,) = movie.sent
    assert sent["genre[0].tag.tag"] == "War"
    assert sent["genre[1].tag.tag"] == "History"
    assert sent["genre[].tag.tag-"] == "Drama"


def test_genre_order_alone_is_no_change(monkeypatch):
    movie = FakeMovie()
    run(monkeypatch, movie, {"genres": ["War", "Drama"]})
    assert movie.sent == []


def test_clearing_every_genre_sends_only_the_removal(monkeypatch):
    movie = FakeMovie()
    run(monkeypatch, movie, {"genres": ""})
    (sent,) = movie.sent
    assert sent["genre[].tag.tag-"] == "Drama,War"
    assert not any(key.startswith("genre[0]") for key in sent)


def test_dry_run_reports_without_sending(monkeypatch, capsys):
    movie = FakeMovie()
    run(monkeypatch, movie, {"tagline": "Now with one."}, dry_run=True)
    assert movie.sent == []
    captured = capsys.readouterr()
    assert "Would change tagline: (empty) -> 'Now with one.'" in captured.err
    assert captured.out == ""


def test_added_at_cannot_be_cleared(monkeypatch):
    with pytest.raises(SystemExit, match="addedAt: cannot be empty"):
        run(monkeypatch, FakeMovie(), {"addedAt": ""})


def test_update_file_is_read_before_connecting(tmp_path):
    path = tmp_path / "edit.json"
    path.write_text('{"title": "X"}', encoding="utf-8")
    args = parse_arguments(
        build_parser(), ["metadata", "881", "--update", str(path)]
    )
    assert args.update_fields == {"title": "X"}


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "is not valid JSON"),
        ('[{"title": "X"}]', "must hold one JSON object"),
    ],
)
def test_unusable_update_file_is_refused(tmp_path, content, message):
    path = tmp_path / "edit.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit, match=message):
        parse_arguments(build_parser(), ["metadata", "1", "-u", str(path)])


def test_missing_update_file_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="Cannot read"):
        parse_arguments(
            build_parser(), ["metadata", "1", "-u", str(tmp_path / "none")]
        )
