# SPDX-License-Identifier: GPL-3.0-or-later

"""Air-date estimation, sorting, titles, and account classification."""

import datetime

import pytest

from plexdo.accounts import _is_restricted, account_type
from plexdo.airdates import _collect_neighbors, _estimate_date, _median_interval
from plexdo.convert import format_duration, parse_date


class Ep:
    def __init__(self, index, date, season=1):
        self.index, self.originallyAvailableAt = index, date
        self.ratingKey, self.seasonNumber = index, season


SEASON = [Ep(1, "2024-01-01"), Ep(2, "2024-01-08"),
          Ep(3, "2024-01-15"), Ep(5, "2024-01-29")]


def test_neighbours_are_gathered_from_both_sides():
    prev, nxt = _collect_neighbors(Ep(4, None), SEASON)
    assert [d.date().isoformat() for d in prev] == \
        ["2024-01-15", "2024-01-08", "2024-01-01"]
    assert [d.date().isoformat() for d in nxt] == ["2024-01-29"]


def test_a_missing_date_is_estimated_from_the_median_interval():
    prev, nxt = _collect_neighbors(Ep(4, None), SEASON)
    assert _estimate_date(prev, nxt).date() == datetime.date(2024, 1, 22)


def test_fewer_than_three_known_dates_cannot_yield_a_median():
    assert _median_interval([datetime.datetime(2024, 1, 1)]) is None
    assert _median_interval([datetime.datetime(2024, 1, 1),
                             datetime.datetime(2024, 1, 8)]) is None


def test_three_known_dates_are_enough():
    assert _median_interval([datetime.datetime(2024, 1, d) for d in (1, 8, 15)]) \
        == datetime.timedelta(days=7)


def test_estimation_gives_up_without_enough_neighbours():
    assert _estimate_date([datetime.datetime(2024, 1, 1)], []) is None


# --- dates and durations -------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, None),
    ("2024-03-05", datetime.datetime(2024, 3, 5)),
    ("2024-03-05 12:30:00", datetime.datetime(2024, 3, 5, 12, 30)),
    (datetime.date(2024, 3, 5), datetime.datetime(2024, 3, 5)),
])
def test_parse_date_normalises_every_accepted_form(value, expected):
    assert parse_date(value) == expected


def test_parse_date_rejects_nonsense():
    with pytest.raises(ValueError):
        parse_date("not a date")


@pytest.mark.parametrize("ms,expected", [
    (None, ""), (0, "0:00"), (63_000, "1:03"), (9_780_000, "2:43:00"),
])
def test_format_duration(ms, expected):
    """None means unknown and renders empty; 0 is a real zero duration."""
    assert format_duration(ms) == expected


# --- account classification ----------------------------------------------

class User:
    def __init__(self, restricted=None, home=False, friend=False):
        self.restricted, self.home, self.friend = restricted, home, friend


def test_restricted_is_a_string_not_a_bool_in_plexapi():
    """"0" is truthy, so a naive check labels every account managed."""
    assert _is_restricted(User(restricted="1")) is True
    assert _is_restricted(User(restricted="0")) is False
    assert _is_restricted(User(restricted="")) is False


@pytest.mark.parametrize("user,expected", [
    (User(restricted="1", home=True), "managed"),
    (User(restricted="0", home=True), "home"),
    (User(restricted="0", friend=True), "friend"),
    (User(restricted="0"), "shared"),
])
def test_account_type(user, expected):
    assert account_type(user) == expected
