# SPDX-License-Identifier: GPL-3.0-or-later

"""Pacing for operations that issue one request per element.

Walking a library season by season, or applying watched state item by item,
means one round trip each. On a large library that is enough traffic to slow
a server down or trip its rate limiting, so those loops are paced. Small runs
are left alone: the delay would be pure latency for no benefit.
"""

from typing import Any, Iterator, Sequence, TypeVar
import time

from plexdo.constants import LOG


T = TypeVar("T")

# Below this many elements a run is short enough not to be worth pacing.
THROTTLE_THRESHOLD = 50

# Seconds between requests once the threshold is passed.
DEFAULT_THROTTLE = 0.25


def throttle_delay(args: Any) -> float:
    """Return the configured delay in seconds, never negative."""
    return max(0.0, float(getattr(args, "throttle", DEFAULT_THROTTLE)))


def _describe(seconds: float) -> str:
    """Render an expected duration the way a person would say it."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes}m{remainder:02d}s"


def paced(items: Sequence[T], args: Any, what: str = "requests") -> Iterator[T]:
    """Yield items, pausing between them when the run is large enough.

    The pause goes between elements rather than before the first, so a run of
    n elements waits n-1 times. Pass --throttle 0 to disable it.
    """
    total = len(items)
    delay = throttle_delay(args)
    if total <= THROTTLE_THRESHOLD or delay <= 0:
        yield from items
        return

    LOG.info(
        "Pacing %d %s %.3gs apart to go easy on the server; about %s, or "
        "--throttle 0 to disable.",
        total, what, delay, _describe(delay * (total - 1)),
    )
    for index, item in enumerate(items):
        if index:
            time.sleep(delay)
        yield item
