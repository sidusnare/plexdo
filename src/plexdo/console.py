# SPDX-License-Identifier: GPL-3.0-or-later

"""Terminal output: JSON, box-drawn tables, and metadata records."""

from typing import Any, Dict, List
import sys
import unicodedata

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
    if isinstance(data, dict):
        print_metadata(data)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        print_table(data)
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


def print_table(rows: List[Dict[str, Any]]) -> None:
    """Print a list of dicts as a box-drawn, display-width-aligned table."""
    if not rows:
        return
    headers = list(rows[0].keys())
    cells = [[_printable(clean_text(row.get(h, ""))) for h in headers] for row in rows]
    widths = [
        max([_display_width(h)] + [_display_width(r[i]) for r in cells])
        for i, h in enumerate(headers)
    ]

    box = _box()
    vline = box["v"]
    print(_rule(widths, box["tl"], box["tm"], box["tr"]))
    print(vline + vline.join(f" {_pad(h, w)} " for h, w in zip(headers, widths)) + vline)
    print(_rule(widths, box["ml"], box["mm"], box["mr"]))
    for row_cells in cells:
        print(vline + vline.join(f" {_pad(c, w)} " for c, w in zip(row_cells, widths)) + vline)
    print(_rule(widths, box["bl"], box["bm"], box["br"]))


def print_metadata(record: Dict[str, Any]) -> None:
    """Print a key-value metadata record as a box-drawn, aligned table."""
    if not record:
        return
    pairs = [(_printable(k), _printable(clean_text(v))) for k, v in record.items()]
    widths = [
        max(_display_width(k) for k, _ in pairs),
        max(_display_width(v) for _, v in pairs),
    ]

    box = _box()
    vline = box["v"]
    print(_rule(widths, box["tl"], box["tm"], box["tr"]))
    for key, value in pairs:
        print(f"{vline} {_pad(key, widths[0])} {vline} {_pad(value, widths[1])} {vline}")
    print(_rule(widths, box["bl"], box["bm"], box["br"]))
