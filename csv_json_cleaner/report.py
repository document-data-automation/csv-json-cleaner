"""The before/after diff report and its rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Report:
    """A summary of what the pipeline changed, ready for JSON or a table."""

    rows_in: int = 0
    rows_out: int = 0
    rows_dropped_empty: int = 0
    columns_dropped_empty: List[str] = field(default_factory=list)
    duplicate_rows_removed: int = 0
    columns_renamed: Dict[str, str] = field(default_factory=dict)
    cells_changed: Dict[str, int] = field(default_factory=dict)
    inferred_types: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serialisable dict of the report."""
        return {
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "rows_dropped_empty": self.rows_dropped_empty,
            "columns_dropped_empty": list(self.columns_dropped_empty),
            "duplicate_rows_removed": self.duplicate_rows_removed,
            "columns_renamed": dict(self.columns_renamed),
            "cells_changed": dict(self.cells_changed),
            "inferred_types": dict(self.inferred_types),
        }


def _kv_table(title: str, pairs: List[tuple]) -> List[str]:
    """Render a two-column key/value block with a title underline."""
    lines = [title]
    if not pairs:
        lines.append("  (none)")
        return lines
    width = max(len(str(k)) for k, _ in pairs)
    for key, value in pairs:
        lines.append(f"  {str(key).ljust(width)}  {value}")
    return lines


def format_report(report: Report) -> str:
    """Render ``report`` as a human-readable multi-section table."""
    lines: List[str] = ["", "=== csv-json-cleaner report ===", ""]

    summary = [
        ("rows in", report.rows_in),
        ("rows out", report.rows_out),
        ("empty rows dropped", report.rows_dropped_empty),
        ("empty columns dropped", len(report.columns_dropped_empty)),
        ("duplicate rows removed", report.duplicate_rows_removed),
    ]
    lines += _kv_table("Summary:", summary)
    lines.append("")

    cells = [(rule, count) for rule, count in report.cells_changed.items()]
    lines += _kv_table("Cells changed per rule:", cells)
    lines.append("")

    renamed = [(old, f"-> {new}") for old, new in report.columns_renamed.items()]
    lines += _kv_table("Columns renamed:", renamed)
    lines.append("")

    if report.columns_dropped_empty:
        lines.append("Empty columns dropped:")
        lines.append("  " + ", ".join(report.columns_dropped_empty))
        lines.append("")

    types = [(col, kind) for col, kind in report.inferred_types.items()]
    lines += _kv_table("Inferred column types:", types)
    lines.append("")

    return "\n".join(lines)
