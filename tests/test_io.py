"""Tests for reading/writing CSV & JSON, delimiter sniffing and round-trips."""

from __future__ import annotations

import json

import pytest

from csv_json_cleaner.io import (
    parse_csv,
    parse_json,
    read_table,
    sniff_format,
    table_to_csv,
    table_to_json,
    write_table,
)
from csv_json_cleaner.table import Table


def test_sniff_format():
    assert sniff_format('[{"a": 1}]') == "json"
    assert sniff_format("  \n {\"a\": 1}") == "json"
    assert sniff_format("a,b,c\n1,2,3") == "csv"


def test_parse_csv_sniffs_comma_delimiter():
    table = parse_csv("a,b\n1,2\n3,4\n")
    assert table.headers == ["a", "b"]
    assert table.rows[0] == {"a": "1", "b": "2"}


def test_parse_csv_sniffs_semicolon_delimiter():
    table = parse_csv("a;b;c\n1;2;3\n")
    assert table.headers == ["a", "b", "c"]
    assert table.rows[0] == {"a": "1", "b": "2", "c": "3"}


def test_parse_csv_is_bom_safe():
    table = parse_csv("﻿a,b\n1,2\n")
    assert table.headers == ["a", "b"]


def test_parse_csv_dedupes_headers():
    table = parse_csv("id,id\n1,2\n")
    assert table.headers == ["id", "id_2"]


def test_parse_json_collects_union_of_keys():
    table = parse_json('[{"a": 1, "b": true}, {"a": 2, "c": null}]')
    assert table.headers == ["a", "b", "c"]
    assert table.rows[0] == {"a": "1", "b": "true", "c": ""}
    assert table.rows[1] == {"a": "2", "b": "", "c": ""}


def test_parse_json_rejects_non_array_of_objects():
    with pytest.raises(ValueError):
        parse_json('[1, 2, 3]')


def test_csv_json_round_trip():
    table = Table(["a", "b"], [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}])
    csv_text = table_to_csv(table)
    back = parse_csv(csv_text)
    assert back.headers == table.headers
    assert back.rows == table.rows

    json_text = table_to_json(table)
    back2 = parse_json(json_text)
    assert back2.rows == table.rows
    assert json.loads(json_text)[0] == {"a": "1", "b": "x"}


def test_read_and_write_files_infer_format(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n", encoding="utf-8")
    table = read_table(str(src))
    out = tmp_path / "out.json"
    write_table(table, str(out))
    assert json.loads(out.read_text(encoding="utf-8")) == [{"a": "1", "b": "2"}]


def test_read_table_force_format(tmp_path):
    src = tmp_path / "data.txt"
    src.write_text('[{"a": 1}]', encoding="utf-8")
    table = read_table(str(src), fmt="json")
    assert table.rows[0] == {"a": "1"}
