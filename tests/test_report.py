"""Tests for the Report data object and its rendering."""

from __future__ import annotations

from csv_json_cleaner.report import Report, format_report


def test_report_to_dict_is_serialisable():
    report = Report(
        rows_in=10,
        rows_out=7,
        rows_dropped_empty=1,
        columns_dropped_empty=["notes"],
        duplicate_rows_removed=2,
        columns_renamed={"Full Name": "full_name"},
        cells_changed={"trim": 3},
        inferred_types={"id": "integer"},
    )
    data = report.to_dict()
    assert data["rows_in"] == 10
    assert data["columns_dropped_empty"] == ["notes"]
    assert data["columns_renamed"] == {"Full Name": "full_name"}


def test_format_report_contains_key_sections():
    report = Report(rows_in=2, rows_out=1, duplicate_rows_removed=1,
                    cells_changed={"trim": 1}, inferred_types={"a": "integer"})
    text = format_report(report)
    assert "csv-json-cleaner report" in text
    assert "rows in" in text
    assert "Cells changed per rule" in text
    assert "Inferred column types" in text
