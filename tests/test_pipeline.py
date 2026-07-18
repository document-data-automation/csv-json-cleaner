"""Tests for the full pipeline and the diff report counts."""

from __future__ import annotations

import pytest

from csv_json_cleaner import CleanConfig, Table, clean


def _messy_table():
    headers = ["Customer ID", "Full Name", "Amount", "Active", "Empty"]
    rows = [
        {"Customer ID": " 001 ", "Full Name": '"Ada"', "Amount": "$1,234.50", "Active": "Yes", "Empty": ""},
        {"Customer ID": "002", "Full Name": "Grace", "Amount": "€2,000", "Active": "no", "Empty": ""},
        {"Customer ID": "002", "Full Name": "Grace", "Amount": "€2,000", "Active": "no", "Empty": ""},
        {"Customer ID": "", "Full Name": "", "Amount": "", "Active": "", "Empty": ""},
    ]
    return Table(headers, rows)


def test_full_pipeline_report_counts():
    cleaned, report = clean(_messy_table())
    assert report.rows_in == 4
    assert report.rows_out == 2
    assert report.rows_dropped_empty == 1
    assert report.duplicate_rows_removed == 1
    assert "empty" in report.columns_dropped_empty
    assert report.columns_renamed["Customer ID"] == "customer_id"
    assert report.cells_changed["trim"] >= 2
    assert report.cells_changed["coerce_numbers"] == 3  # counted before dedupe
    assert report.inferred_types["amount"] == "float"
    assert report.inferred_types["active"] == "boolean"


def test_disabling_rules_via_config():
    cleaned, report = clean(
        _messy_table(),
        CleanConfig(dedupe=False, normalize_headers=False, coerce_numbers=False),
    )
    assert report.duplicate_rows_removed == 0
    assert report.columns_renamed == {}
    assert "coerce_numbers" not in report.cells_changed
    assert "Customer ID" in cleaned.headers  # header untouched


def test_key_dedupe_in_pipeline():
    table = Table(["id", "note"], [
        {"id": "1", "note": "a"},
        {"id": "1", "note": "b"},
        {"id": "2", "note": "c"},
    ])
    cleaned, report = clean(table, CleanConfig(key=["id"]))
    assert report.duplicate_rows_removed == 1
    assert [r["note"] for r in cleaned.rows] == ["a", "c"]


def test_missing_key_column_raises():
    table = Table(["id"], [{"id": "1"}])
    with pytest.raises(ValueError):
        clean(table, CleanConfig(key=["nope"]))


def test_pipeline_is_non_mutating():
    original = _messy_table()
    snapshot = [dict(r) for r in original.rows]
    clean(original)
    assert [dict(r) for r in original.rows] == snapshot
