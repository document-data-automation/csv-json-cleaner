"""The cleaning pipeline: configuration + orchestration of the rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import rules
from .report import Report
from .table import Table


@dataclass
class CleanConfig:
    """Which rules run, and their parameters.

    Every rule is enabled by default and individually toggleable.
    """

    trim: bool = True
    normalize_headers: bool = True
    drop_empty: bool = True
    coerce_numbers: bool = True
    normalize_dates: bool = True
    standardize_booleans: bool = True
    dedupe: bool = True
    infer_types: bool = True
    key: Optional[List[str]] = None
    date_formats: Tuple[str, ...] = rules.DEFAULT_DATE_FORMATS


def clean(table: Table, config: Optional[CleanConfig] = None) -> Tuple[Table, Report]:
    """Run the enabled rules over ``table`` and return ``(cleaned, report)``.

    Rules run in a fixed, sensible order: structural fixes (trim, headers, drop
    empties) first, then value coercions (numbers, dates, booleans), then row
    de-duplication, then a non-mutating type-inference summary.

    Raises:
        ValueError: if ``config.key`` names a column absent after cleaning.
    """
    config = config or CleanConfig()
    report = Report(rows_in=len(table.rows))
    current = table

    if config.trim:
        current, report.cells_changed["trim"] = rules.rule_trim(current)

    if config.normalize_headers:
        current, report.columns_renamed = rules.rule_normalize_headers(current)

    if config.drop_empty:
        current, (dropped_rows, dropped_cols) = rules.rule_drop_empty(current)
        report.rows_dropped_empty = dropped_rows
        report.columns_dropped_empty = dropped_cols

    if config.coerce_numbers:
        current, report.cells_changed["coerce_numbers"] = rules.rule_coerce_numbers(current)

    if config.normalize_dates:
        current, report.cells_changed["normalize_dates"] = rules.rule_normalize_dates(
            current, config.date_formats
        )

    if config.standardize_booleans:
        current, report.cells_changed["standardize_booleans"] = rules.rule_standardize_booleans(
            current
        )

    if config.dedupe:
        if config.key:
            missing = [k for k in config.key if k not in current.headers]
            if missing:
                raise ValueError(
                    "--key column(s) not found after cleaning: "
                    + ", ".join(missing)
                    + f" (available: {', '.join(current.headers)})"
                )
        current, report.duplicate_rows_removed = rules.rule_dedupe(current, config.key)

    if config.infer_types:
        report.inferred_types = rules.rule_infer_types(current)

    report.rows_out = len(current.rows)
    return current, report
