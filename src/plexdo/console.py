# SPDX-License-Identifier: GPL-3.0-or-later

"""Terminal output: JSON, box-drawn tables, and metadata records."""

from typing import Any, Dict, List, Optional
import shutil
import sys
import unicodedata

from plexdo.constants import LOG
from plexdo.formats import render


def output_format(args: "argparse.Namespace") -> str:
    """Return the selected output format, defaulting to the table renderer."""
    return getattr(args, "format", None) or "table"


def output(data: Any, args: "argparse.Namespace") -> None:
    """Emit a payload in the selected format.

    Accepts a single record or a list of them, so commands emitting one object
    and commands emitting many share this one path.
    """
    chosen = output_format(args)
    if chosen != "table":
        rendered = render(data, chosen)
        if rendered:
            print(rendered)
        return
    limit = table_limit(args)
    if isinstance(data, dict):
        print_metadata(data, limit)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        print_table(data, limit)
    elif data or not isinstance(data, list):
        print(data)


def clean_text(value: Any) -> str:
    """Convert a table cell value to a clean string, stripping control characters."""
    return str(value).strip()


def _display_width(text: str) -> int:
    """Return terminal display width, accounting for wide and combining glyphs.

    len() is wrong for alignment: CJK glyphs occupy two columns and combining
    marks occupy none, so a len()-padded table drifts out of line on any
    library containing non-Latin titles.
    """
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def _pad(text: str, width: int) -> str:
    """Left-align text padded to the given display width."""
    return text + " " * max(0, width - _display_width(text))


# Box-drawing glyphs, with an ASCII fallback. A legacy Windows console
# (cp1252, or a redirected ASCII stream) cannot encode U+2500 and friends, so
# printing them raises UnicodeEncodeError and the command emits nothing at all.
_BOX_UNICODE = {
    "h": "\u2500", "v": "\u2502",
    "tl": "\u250c", "tm": "\u252c", "tr": "\u2510",
    "ml": "\u251c", "mm": "\u253c", "mr": "\u2524",
    "bl": "\u2514", "bm": "\u2534", "br": "\u2518",
}
_BOX_ASCII = {
    "h": "-", "v": "|",
    "tl": "+", "tm": "+", "tr": "+",
    "ml": "+", "mm": "+", "mr": "+",
    "bl": "+", "bm": "+", "br": "+",
}


def _stdout_encoding() -> str:
    """Return the encoding stdout will use, defaulting to UTF-8."""
    return getattr(sys.stdout, "encoding", None) or "utf-8"


def _box() -> Dict[str, str]:
    """Return box-drawing glyphs stdout can actually encode."""
    try:
        "".join(_BOX_UNICODE.values()).encode(_stdout_encoding())
    except (UnicodeEncodeError, LookupError):
        return _BOX_ASCII
    return _BOX_UNICODE


def _printable(text: str) -> str:
    """Replace characters stdout cannot encode so a table never crashes.

    Applied only when rendering tables, never to values used for matching:
    a title mangled to "Ren?e" must not be compared against real Plex data.
    JSON output needs no equivalent because json.dumps escapes non-ASCII.
    """
    encoding = _stdout_encoding()
    try:
        text.encode(encoding)
        return text
    except (UnicodeEncodeError, LookupError):
        return text.encode(encoding, "replace").decode(encoding, "replace")


def _rule(widths: List[int], left: str, mid: str, right: str) -> str:
    """Build a horizontal box-drawing rule for the given column widths."""
    return left + mid.join(_box()["h"] * (w + 2) for w in widths) + right


# Narrower than this a column carries nothing but the ellipsis.
MIN_COLUMN_WIDTH = 8
TRUNCATION_MARK = "..."


def table_limit(args: "argparse.Namespace") -> Optional[int]:
    """Column budget for table output, or None to keep every character.

    Only an interactive terminal is measured: piping to a file or to grep
    should carry the whole value, and a redirected stream has no width of its
    own to respect.
    """
    if getattr(args, "wide", False):
        return None
    if not sys.stdout.isatty():
        return None
    return shutil.get_terminal_size().columns


def _table_width(widths: List[int]) -> int:
    """Rendered width of a table with the given column widths."""
    return sum(width + 2 for width in widths) + len(widths) + 1


def _fit_widths(widths: List[int], limit: Optional[int]) -> List[int]:
    """Shrink the widest column repeatedly until the table fits.

    Columns stop at MIN_COLUMN_WIDTH first, since a narrower one carries
    little but the ellipsis. If that is still too wide the floor drops to the
    ellipsis itself, so a very narrow terminal degrades rather than overflows.
    """
    if limit is None:
        return widths
    fitted = list(widths)
    for floor in (MIN_COLUMN_WIDTH, len(TRUNCATION_MARK)):
        while _table_width(fitted) > limit:
            widest = max(range(len(fitted)), key=lambda i: fitted[i])
            if fitted[widest] <= floor:
                break      # every column is at this floor
            fitted[widest] -= 1
    return fitted


def _truncate(text: str, width: int) -> str:
    """Cut text to a display width, marking that something was removed."""
    if _display_width(text) <= width:
        return text
    if width <= len(TRUNCATION_MARK):
        return TRUNCATION_MARK[:width]
    budget = width - len(TRUNCATION_MARK)
    kept, used = [], 0
    for char in text:
        step = _display_width(char)
        if used + step > budget:
            break
        kept.append(char)
        used += step
    return "".join(kept) + TRUNCATION_MARK


def _report_narrowing(
    headers: List[str], natural: List[int], fitted: List[int], limit: int
) -> None:
    """Say which columns were shrunk, and how to stop it happening."""
    shrunk = [
        f"{name} {was}->{now}"
        for name, was, now in zip(headers, natural, fitted) if now < was
    ]
    if shrunk:
        LOG.info(
            "Narrowed %s to fit a %d-column terminal; use --wide to keep "
            "every character.", ", ".join(shrunk), limit,
        )


def print_table(rows: List[Dict[str, Any]], limit: Optional[int] = None) -> None:
    """Print a list of dicts as a box-drawn, display-width-aligned table."""
    if not rows:
        return
    headers = list(rows[0].keys())
    cells = [[_printable(clean_text(row.get(h, ""))) for h in headers] for row in rows]
    widths = [
        max([_display_width(h)] + [_display_width(r[i]) for r in cells])
        for i, h in enumerate(headers)
    ]

    fitted = _fit_widths(widths, limit)
    if fitted != widths and limit is not None:
        _report_narrowing(headers, widths, fitted, limit)

    box = _box()
    vline = box["v"]
    print(_rule(fitted, box["tl"], box["tm"], box["tr"]))
    print(vline + vline.join(
        f" {_pad(_truncate(h, w), w)} " for h, w in zip(headers, fitted)) + vline)
    print(_rule(fitted, box["ml"], box["mm"], box["mr"]))
    for row_cells in cells:
        print(vline + vline.join(
            f" {_pad(_truncate(c, w), w)} " for c, w in zip(row_cells, fitted)) + vline)
    print(_rule(fitted, box["bl"], box["bm"], box["br"]))


def print_metadata(
    record: Dict[str, Any], limit: Optional[int] = None
) -> None:
    """Print a key-value metadata record as a box-drawn, aligned table."""
    if not record:
        return
    pairs = [(_printable(k), _printable(clean_text(v))) for k, v in record.items()]
    widths = [
        max(_display_width(k) for k, _ in pairs),
        max(_display_width(v) for _, v in pairs),
    ]

    fitted = _fit_widths(widths, limit)
    if fitted != widths and limit is not None:
        _report_narrowing(["field", "value"], widths, fitted, limit)

    box = _box()
    vline = box["v"]
    print(_rule(fitted, box["tl"], box["tm"], box["tr"]))
    for key, value in pairs:
        print(f"{vline} {_pad(_truncate(key, fitted[0]), fitted[0])} "
              f"{vline} {_pad(_truncate(value, fitted[1]), fitted[1])} {vline}")
    print(_rule(fitted, box["bl"], box["bm"], box["br"]))
