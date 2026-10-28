# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Value coercion helpers for rating keys and dates."""

import datetime

from plexdo.constants import DateInput


def parse_date(value: DateInput) -> datetime.datetime | None:
    """Normalize a date-like value to datetime.datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date string: {value!r}")
    raise TypeError(f"Unsupported date type: {type(value)}")


def format_duration(milliseconds: int | None) -> str:
    """Convert milliseconds to a human-readable H:MM:SS string."""
    if milliseconds is None:
        return ""
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"
