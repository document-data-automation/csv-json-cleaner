"""Reading and writing tables as CSV or JSON.

Formats are inferred from file extensions but can be overridden.  Reading is
BOM-safe and sniffs the CSV delimiter; JSON input must be an array of objects.
All values are normalised to strings on load so the rules see uniform data.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from typing import List, Optional

from .rules import make_unique
from .table import Table

_CSV_EXTENSIONS = {".csv", ".tsv", ".txt"}
_JSON_EXTENSIONS = {".json"}


def _cell_to_str(value: object) -> str:
    """Normalise a JSON scalar to the string form the rules expect."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        # Avoid trailing ".0" noise for integral floats.
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, (int, str)):
        return str(value)
    # Lists/dicts inside a cell: preserve as compact JSON.
    return json.dumps(value, ensure_ascii=False)


def sniff_format(text: str) -> str:
    """Guess ``"json"`` or ``"csv"`` from the leading non-space character."""
    stripped = text.lstrip("﻿ \t\r\n")
    return "json" if stripped[:1] in "[{" else "csv"


def _format_from_path(path: str) -> Optional[str]:
    lower = path.lower()
    if any(lower.endswith(ext) for ext in _JSON_EXTENSIONS):
        return "json"
    if any(lower.endswith(ext) for ext in _CSV_EXTENSIONS):
        return "csv"
    return None


def parse_csv(text: str) -> Table:
    """Parse CSV ``text`` into a :class:`Table`, sniffing the delimiter."""
    text = text.lstrip("﻿")
    if not text.strip():
        return Table([], [])
    sample = text[:8192]
    try:
        dialect: object = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.get_dialect("excel")
    reader = csv.reader(io.StringIO(text), dialect)  # type: ignore[arg-type]
    records = [row for row in reader if row != []]
    if not records:
        return Table([], [])
    raw_headers = [(h.strip() or f"column_{i + 1}") for i, h in enumerate(records[0])]
    headers = make_unique(raw_headers)
    rows: List[dict] = []
    for record in records[1:]:
        rows.append(
            {header: (record[i] if i < len(record) else "") for i, header in enumerate(headers)}
        )
    return Table(headers, rows)


def parse_json(text: str) -> Table:
    """Parse a JSON array of objects into a :class:`Table`.

    Raises:
        ValueError: if the top-level value is not an array/object of objects.
    """
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON input must be an array of objects")
    headers: List[str] = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("JSON array must contain only objects")
        for key in item:
            if key not in seen:
                seen.add(key)
                headers.append(key)
    rows = [{h: _cell_to_str(item.get(h, "")) for h in headers} for item in data]
    return Table(headers, rows)


def _read_source_text(source: str) -> str:
    """Read raw text from a path, or stdin when ``source`` is ``"-"``."""
    if source == "-":
        return sys.stdin.read()
    with open(source, "r", encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def read_table(source: str, fmt: Optional[str] = None) -> Table:
    """Read a :class:`Table` from a path (or ``"-"`` for stdin).

    Args:
        source: File path, or ``"-"`` to read stdin.
        fmt: ``"csv"`` or ``"json"`` to force a format; otherwise inferred from
            the extension, then sniffed from the content.
    """
    text = _read_source_text(source)
    resolved = fmt or (_format_from_path(source) if source != "-" else None) or sniff_format(text)
    if resolved == "json":
        return parse_json(text)
    return parse_csv(text)


def table_to_csv(table: Table) -> str:
    """Serialise ``table`` to CSV text (LF line endings)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(table.headers)
    for row in table.rows:
        writer.writerow([row.get(header, "") for header in table.headers])
    return buffer.getvalue()


def table_to_json(table: Table) -> str:
    """Serialise ``table`` to a JSON array of objects (2-space indent)."""
    records = [{header: row.get(header, "") for header in table.headers} for row in table.rows]
    return json.dumps(records, ensure_ascii=False, indent=2) + "\n"


def write_table(table: Table, dest: str, fmt: Optional[str] = None) -> None:
    """Write ``table`` to a path (or ``"-"`` for stdout) as CSV or JSON."""
    resolved = fmt or (_format_from_path(dest) if dest != "-" else None) or "csv"
    text = table_to_json(table) if resolved == "json" else table_to_csv(table)
    if dest == "-":
        sys.stdout.write(text)
    else:
        with open(dest, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
