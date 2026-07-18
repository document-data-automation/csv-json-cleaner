"""csv-json-cleaner: a no-nonsense cleaner for messy CSV/JSON tabular data.

The public API mirrors the pipeline: build a :class:`Table` (usually via
:func:`read_table`), run :func:`clean` with a :class:`CleanConfig`, then inspect
the returned :class:`Report` or write the table back out.
"""

from __future__ import annotations

from .io import (
    parse_csv,
    parse_json,
    read_table,
    table_to_csv,
    table_to_json,
    write_table,
)
from .pipeline import CleanConfig, clean
from .report import Report, format_report
from .rules import DEFAULT_DATE_FORMATS
from .table import Table

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Table",
    "CleanConfig",
    "clean",
    "Report",
    "format_report",
    "read_table",
    "write_table",
    "parse_csv",
    "parse_json",
    "table_to_csv",
    "table_to_json",
    "DEFAULT_DATE_FORMATS",
]
