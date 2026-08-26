# SPDX-License-Identifier: GPL-3.0-or-later

"""Table rendering: alignment, encoding fallback, control characters, width."""

import os
import sys

import pytest

from plexdo.console import (_display_width as display_width, _pad as pad,
                            clean_text, output, print_table)


def test_clean_text_strips_the_carriage_returns_plex_metadata_carries():
    assert clean_text("Breaking Bad\r") == "Breaking Bad"


def test_display_width_counts_wide_glyphs_as_two_columns():
    assert display_width("ab") == 2
    assert display_width("\u5343\u3068") == 4          # CJK
    assert display_width("e\u0301") == 1               # combining acute


def test_pad_aligns_by_display_width_not_length():
    assert len(pad("\u5343", 4)) == 3                  # 2 columns + 2 spaces


def test_table_columns_line_up_with_mixed_width_titles(capsys):
    print_table([{"t": "Amelie"}, {"t": "\u5343\u3068\u5343\u5c0b"}, {"t": "Plain"}])
    lines = capsys.readouterr().out.splitlines()
    assert len({display_width(line) for line in lines}) == 1


def test_table_falls_back_to_ascii_when_the_console_cannot_encode_box_glyphs(
    capsys, monkeypatch
):
    """A legacy cp1252 console would otherwise abort with UnicodeEncodeError."""
    monkeypatch.setattr("plexdo.console._stdout_encoding", lambda: "cp1252")
    print_table([{"id": 1}])
    out = capsys.readouterr().out
    assert "+" in out and "\u250c" not in out


def test_unencodable_title_is_substituted_rather_than_crashing(capsys, monkeypatch):
    monkeypatch.setattr("plexdo.console._stdout_encoding", lambda: "ascii")
    print_table([{"t": "\u5343\u3068"}])
    assert "?" in capsys.readouterr().out


def test_output_dispatches_dict_to_the_metadata_renderer(capsys, args):
    args.format = "table"
    output({"a": 1}, args)
    assert "a" in capsys.readouterr().out


@pytest.mark.parametrize("fmt", ["json", "yaml", "csv"])
def test_output_honours_the_selected_format(capsys, args, fmt):
    args.format = fmt
    output([{"a": 1}], args)
    assert capsys.readouterr().out.strip()


# --- fitting tables to the terminal --------------------------------------

import argparse
import io

from plexdo.console import MIN_COLUMN_WIDTH, _truncate, table_limit

WIDE_ROWS = [{
    "ratingKey": 101,
    "title": "Breaking Bad - Cat's in the Bag and Then He's in the Bag",
    "studio": "Sony Pictures Television",
}]


def render_table(rows, limit):
    buffer = io.StringIO()
    original, sys.stdout = sys.stdout, buffer
    try:
        print_table(rows, limit)
    finally:
        sys.stdout = original
    return buffer.getvalue().splitlines()


@pytest.mark.parametrize("limit", [80, 60, 40, 30, 24, 20])
def test_a_table_never_exceeds_the_column_budget(limit):
    assert max(display_width(line) for line in render_table(WIDE_ROWS, limit)) <= limit


def test_every_line_is_the_same_width_after_fitting():
    assert len({display_width(line) for line in render_table(WIDE_ROWS, 60)}) == 1


def test_nothing_is_truncated_when_the_table_already_fits():
    lines = render_table([{"a": "x"}], 200)
    assert "..." not in "\n".join(lines)


def test_the_widest_column_is_the_one_shrunk(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="plexdo")
    render_table(WIDE_ROWS, 60)
    assert "title" in caplog.text and "--wide" in caplog.text


def test_no_limit_keeps_every_character():
    joined = "\n".join(render_table(WIDE_ROWS, None))
    assert "Then He's in the Bag" in joined


def test_truncation_is_display_width_aware():
    assert display_width(_truncate("\u5343\u3068\u5343\u5c0b\u306e", 8)) <= 8


def test_truncation_marks_that_something_was_removed():
    assert _truncate("Breaking Bad", 8).endswith("...")


def test_a_column_narrower_than_the_mark_degrades_to_it():
    assert _truncate("Breaking Bad", 2) == ".."


def test_wide_disables_the_budget():
    assert table_limit(argparse.Namespace(wide=True)) is None


def test_redirected_output_is_never_truncated(monkeypatch):
    """Piping to a file or grep should carry the whole value."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False, raising=False)
    assert table_limit(argparse.Namespace(wide=False)) is None


def test_a_terminal_supplies_its_width(monkeypatch):
    import shutil
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((97, 24)))
    assert table_limit(argparse.Namespace(wide=False)) == 97


def test_columns_stop_at_a_sensible_floor_before_the_last_resort():
    from plexdo.console import _fit_widths
    assert min(_fit_widths([40, 40, 40], 100)) >= MIN_COLUMN_WIDTH


def test_metadata_numbers_files_only_when_there_are_several():
    from plexdo.commands.metadata import _file_fields
    assert _file_fields(["/a.mkv"]) == {"file": "/a.mkv"}
    assert _file_fields(["/a.avi", "/b.avi"]) == {"file 1": "/a.avi", "file 2": "/b.avi"}
    assert _file_fields([]) == {}
