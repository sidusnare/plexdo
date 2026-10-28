# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Output serialisers."""

import csv
import io
import json
import xml.etree.ElementTree as ET

import pytest

from plexdo.formats import OUTPUT_FORMATS, render

ROWS = [
    {"id": 1, "type": "movie", "title": 'Movies "HD" & <tags>'},
    {"id": 3, "type": "show", "title": "TV Shows"},
]
NS = {"p": "http://schemas.microsoft.com/powershell/2004/04"}


def test_json_round_trips():
    assert json.loads(render(ROWS, "json")) == ROWS


def test_json_escapes_non_ascii_so_any_console_can_print_it():
    out = render([{"t": "\u5343\u3068"}], "json")
    assert out.isascii()


def test_csv_round_trips_including_quotes_and_commas():
    rows = list(csv.DictReader(io.StringIO(render(ROWS, "csv"))))
    assert rows[0]["title"] == ROWS[0]["title"]


def test_csv_uses_newline_not_crlf():
    assert "\r" not in render(ROWS, "csv")


@pytest.mark.parametrize("value", ["NO", "yes", "1.10", "0755", "null", "~"])
def test_yaml_keeps_ambiguous_strings_as_strings(value):
    """Plain style would let YAML read these as bools, floats, or null."""
    yaml = pytest.importorskip("yaml")
    assert yaml.safe_load(render([{"v": value}], "yaml")) == [{"v": value}]


def test_yaml_handles_nested_sections():
    yaml = pytest.importorskip("yaml")
    payload = {"server": {"name": "x"}, "sessions": ROWS, "empty": []}
    assert yaml.safe_load(render(payload, "yaml")) == payload


def test_clixml_is_valid_xml_with_typed_properties():
    root = ET.fromstring(render(ROWS, "clixml"))
    objs = root.findall("p:Obj", NS)
    assert len(objs) == 2
    first = objs[0].find("p:MS", NS)
    assert first.find("p:I32[@N='id']", NS).text == "1"
    assert first.find("p:S[@N='title']", NS).text == ROWS[0]["title"]


def test_clixml_later_objects_reference_the_first_type_definition():
    root = ET.fromstring(render(ROWS, "clixml"))
    objs = root.findall("p:Obj", NS)
    assert objs[0].find("p:TN", NS) is not None
    assert objs[1].find("p:TNRef", NS) is not None


def test_single_record_is_accepted_everywhere():
    for fmt in ("json", "yaml", "csv", "clixml"):
        assert render({"a": 1}, fmt)


@pytest.mark.parametrize("fmt", ["json", "yaml", "csv", "clixml"])
def test_empty_payload_never_raises(fmt):
    render([], fmt)


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError):
        render([], "xml")


def test_table_is_not_a_renderer_here():
    assert "table" in OUTPUT_FORMATS
    with pytest.raises(ValueError):
        render([], "table")
