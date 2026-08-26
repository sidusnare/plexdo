# SPDX-License-Identifier: GPL-3.0-or-later

"""Pacing of operations that issue one request per element."""

import argparse
import time

from plexdo.throttle import (DEFAULT_THROTTLE, THROTTLE_THRESHOLD, paced,
                             throttle_delay)


def ns(**kw):
    return argparse.Namespace(**kw)


def test_default_delay_is_a_quarter_second():
    assert DEFAULT_THROTTLE == 0.25
    assert throttle_delay(ns()) == 0.25


def test_an_explicit_delay_is_used():
    assert throttle_delay(ns(throttle=1.5)) == 1.5


def test_a_negative_delay_is_treated_as_none():
    assert throttle_delay(ns(throttle=-5)) == 0.0


def test_a_small_run_is_not_paced(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    items = list(range(THROTTLE_THRESHOLD))
    assert list(paced(items, ns(throttle=10))) == items
    assert slept == []


def test_a_run_past_the_threshold_is_paced(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    items = list(range(THROTTLE_THRESHOLD + 1))
    assert list(paced(items, ns(throttle=0.25))) == items
    # One pause between elements, so n-1 for n items.
    assert slept == [0.25] * THROTTLE_THRESHOLD


def test_zero_disables_pacing_however_large_the_run(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    items = list(range(500))
    assert list(paced(items, ns(throttle=0))) == items
    assert slept == []


def test_pacing_announces_itself_once(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.INFO, logger="plexdo")
    monkeypatch.setattr(time, "sleep", lambda _: None)
    list(paced(list(range(200)), ns(throttle=0.25)))
    assert caplog.text.count("Pacing") == 1
    assert "--throttle 0" in caplog.text


def test_every_element_is_yielded_in_order(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)
    items = list(range(120))
    assert list(paced(items, ns(throttle=0.01))) == items


def test_missing_attribute_falls_back_to_the_default(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    list(paced(list(range(60)), argparse.Namespace()))
    assert slept and slept[0] == DEFAULT_THROTTLE
