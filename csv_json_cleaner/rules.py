"""The cleaning rules.

Each rule is a small, independent, pure function over a :class:`Table`.  A rule
never mutates its input; it returns a *new* ``Table`` plus a lightweight summary
of what it changed (a count, a rename map, ...).  The pipeline in
:mod:`csv_json_cleaner.pipeline` decides which rules run and in what order.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from typing import Dict, List, Optional, Sequence, Tuple

from .table import Table

# --------------------------------------------------------------------------- #
# Shared constants
# --------------------------------------------------------------------------- #

#: Input date formats tried (in order) when normalising to ISO 8601.  Earlier
#: entries win, which is how the ambiguous ``MM/DD`` vs ``DD/MM`` case is
#: resolved: the US-style format is listed first.
DEFAULT_DATE_FORMATS: Tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%m/%d/%y",
    "%d.%m.%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)

_CURRENCY_SYMBOLS = "$€£¥"
_TRUE_TOKENS = frozenset({"true", "t", "yes", "y", "1"})
_FALSE_TOKENS = frozenset({"false", "f", "no", "n", "0"})
_BOOL_TOKENS = _TRUE_TOKENS | _FALSE_TOKENS
#: Bare ``0``/``1`` are also valid numbers, so a column made up *only* of these
#: is treated as numeric, not boolean.  A column needs at least one textual
#: token (yes/no/true/...) before its ``0``/``1`` values are read as booleans.
_AMBIGUOUS_BOOL_TOKENS = frozenset({"0", "1"})

_INT_RE = re.compile(r"-?\d+")
_FLOAT_RE = re.compile(r"-?\d+\.\d+")
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PLAIN_NUMBER_RE = re.compile(r"\d+(\.\d+)?")
_GROUPED_NUMBER_RE = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")


# --------------------------------------------------------------------------- #
# Rule 1: trim whitespace / surrounding quotes / nbsp
# --------------------------------------------------------------------------- #

def _trim_cell(value: str) -> str:
    """Strip whitespace, non-breaking spaces and one layer of wrapping quotes."""
    s = value.replace("\xa0", " ").strip()
    while len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def rule_trim(table: Table) -> Tuple[Table, int]:
    """Trim every string cell.  Returns the new table and cells-changed count."""
    changed = 0
    new_rows: List[Dict[str, str]] = []
    for row in table.rows:
        new_row = dict(row)
        for header in table.headers:
            original = row.get(header, "")
            trimmed = _trim_cell(original)
            if trimmed != original:
                changed += 1
            new_row[header] = trimmed
        new_rows.append(new_row)
    return Table(list(table.headers), new_rows), changed


# --------------------------------------------------------------------------- #
# Rule 2: normalise headers to unique snake_case ascii
# --------------------------------------------------------------------------- #

def to_snake_case(name: str) -> str:
    """Return an ascii ``snake_case`` version of ``name`` (never empty)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # Split camelCase / PascalCase boundaries before lower-casing.
    ascii_name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", ascii_name)
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9]+", "_", ascii_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("_")
    return ascii_name or "column"


def make_unique(names: Sequence[str]) -> List[str]:
    """De-duplicate collided names by appending ``_2``, ``_3`` ... suffixes."""
    seen: Dict[str, int] = {}
    result: List[str] = []
    for name in names:
        if name not in seen:
            seen[name] = 1
            result.append(name)
        else:
            seen[name] += 1
            candidate = f"{name}_{seen[name]}"
            while candidate in seen:
                seen[name] += 1
                candidate = f"{name}_{seen[name]}"
            seen[candidate] = 1
            result.append(candidate)
    return result


def rule_normalize_headers(table: Table) -> Tuple[Table, Dict[str, str]]:
    """Rewrite headers to unique snake_case.  Returns ``{old: new}`` for changes."""
    new_headers = make_unique([to_snake_case(h) for h in table.headers])
    rename_map = {
        old: new for old, new in zip(table.headers, new_headers) if old != new
    }
    if not rename_map:
        return Table(list(table.headers), [dict(r) for r in table.rows]), {}
    new_rows: List[Dict[str, str]] = []
    for row in table.rows:
        new_rows.append({new: row.get(old, "") for old, new in zip(table.headers, new_headers)})
    return Table(new_headers, new_rows), rename_map


# --------------------------------------------------------------------------- #
# Rule 3: drop fully-empty rows and columns
# --------------------------------------------------------------------------- #

def rule_drop_empty(table: Table) -> Tuple[Table, Tuple[int, List[str]]]:
    """Drop all-empty rows and all-empty columns.

    Returns the new table plus ``(rows_dropped, [dropped_column_names])``.
    """
    kept_rows = [row for row in table.rows if any(row.get(h, "") != "" for h in table.headers)]
    rows_dropped = len(table.rows) - len(kept_rows)

    dropped_columns = [
        h for h in table.headers if all(row.get(h, "") == "" for row in kept_rows)
    ] if kept_rows else []
    kept_headers = [h for h in table.headers if h not in dropped_columns]

    new_rows = [{h: row.get(h, "") for h in kept_headers} for row in kept_rows]
    return Table(kept_headers, new_rows), (rows_dropped, dropped_columns)


# --------------------------------------------------------------------------- #
# Rule 4: coerce numbers (strip thousands separators / currency)
# --------------------------------------------------------------------------- #

def coerce_number(value: str) -> Optional[str]:
    """Return a bare numeric string, or ``None`` if ``value`` is not numeric.

    Handles surrounding currency symbols, grouped thousands (``1,234``),
    accounting-style negatives (``(1,234)``) and explicit signs.  Genuinely
    non-numeric text (phone numbers, ``1,2,3``, ``12-34``) returns ``None`` and
    is left untouched by the rule.
    """
    s = value.strip()
    if not s:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()
    for symbol in _CURRENCY_SYMBOLS:
        s = s.replace(symbol, "")
    s = s.strip()
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("-"):
        negative = True
        s = s[1:]
    s = s.strip()
    if not s:
        return None
    if _GROUPED_NUMBER_RE.fullmatch(s) or _PLAIN_NUMBER_RE.fullmatch(s):
        s = s.replace(",", "")
    else:
        return None
    return f"-{s}" if negative and s != "0" else s


def rule_coerce_numbers(table: Table) -> Tuple[Table, int]:
    """Coerce currency/grouped numbers to bare numeric strings."""
    changed = 0
    new_rows: List[Dict[str, str]] = []
    for row in table.rows:
        new_row = dict(row)
        for header in table.headers:
            original = row.get(header, "")
            coerced = coerce_number(original)
            if coerced is not None and coerced != original:
                new_row[header] = coerced
                changed += 1
        new_rows.append(new_row)
    return Table(list(table.headers), new_rows), changed


# --------------------------------------------------------------------------- #
# Rule 5: normalise dates to ISO 8601
# --------------------------------------------------------------------------- #

def coerce_date(value: str, formats: Sequence[str]) -> Optional[str]:
    """Return ``YYYY-MM-DD`` if ``value`` parses under any format, else ``None``."""
    s = value.strip()
    if not s:
        return None
    for fmt in formats:
        try:
            parsed = _dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
        return parsed.strftime("%Y-%m-%d")
    return None


def rule_normalize_dates(
    table: Table, formats: Sequence[str] = DEFAULT_DATE_FORMATS
) -> Tuple[Table, int]:
    """Rewrite parseable dates to ISO 8601; leave everything else alone."""
    changed = 0
    new_rows: List[Dict[str, str]] = []
    for row in table.rows:
        new_row = dict(row)
        for header in table.headers:
            original = row.get(header, "")
            iso = coerce_date(original, formats)
            if iso is not None and iso != original:
                new_row[header] = iso
                changed += 1
        new_rows.append(new_row)
    return Table(list(table.headers), new_rows), changed


# --------------------------------------------------------------------------- #
# Rule 6: standardise booleans (column-aware)
# --------------------------------------------------------------------------- #

def rule_standardize_booleans(table: Table) -> Tuple[Table, int]:
    """Normalise boolean-like values to ``true``/``false``.

    A column is treated as boolean only when *every* non-empty value in it is a
    recognised boolean token.  This keeps genuine numeric columns (whose values
    happen to include ``0``/``1``) from being clobbered.
    """
    boolean_columns = []
    for header in table.headers:
        non_empty = [v.strip().lower() for v in table.column(header) if v != ""]
        if not non_empty or not all(v in _BOOL_TOKENS for v in non_empty):
            continue
        # Skip columns that are purely 0/1 (indistinguishable from numbers).
        if all(v in _AMBIGUOUS_BOOL_TOKENS for v in non_empty):
            continue
        boolean_columns.append(header)

    changed = 0
    new_rows: List[Dict[str, str]] = []
    for row in table.rows:
        new_row = dict(row)
        for header in boolean_columns:
            original = row.get(header, "")
            if original == "":
                continue
            normalized = "true" if original.strip().lower() in _TRUE_TOKENS else "false"
            if normalized != original:
                changed += 1
            new_row[header] = normalized
        new_rows.append(new_row)
    return Table(list(table.headers), new_rows), changed


# --------------------------------------------------------------------------- #
# Rule 7: de-duplicate rows
# --------------------------------------------------------------------------- #

def rule_dedupe(table: Table, key: Optional[Sequence[str]] = None) -> Tuple[Table, int]:
    """Drop duplicate rows, keeping the first occurrence.

    With ``key`` given, rows are compared on that subset of columns only;
    otherwise the whole row is used as the signature.
    """
    columns = list(key) if key else list(table.headers)
    seen = set()
    kept: List[Dict[str, str]] = []
    removed = 0
    for row in table.rows:
        signature = tuple(row.get(c, "") for c in columns)
        if signature in seen:
            removed += 1
            continue
        seen.add(signature)
        kept.append(row)
    return Table(list(table.headers), kept), removed


# --------------------------------------------------------------------------- #
# Rule 8: per-column type inference summary (non-mutating)
# --------------------------------------------------------------------------- #

def infer_column_type(values: Sequence[str]) -> str:
    """Infer a coarse type for a column's values.

    Returns one of ``empty``, ``boolean``, ``integer``, ``float``, ``date`` or
    ``string``.
    """
    non_empty = [v for v in values if v != ""]
    if not non_empty:
        return "empty"
    if all(v.strip().lower() in {"true", "false"} for v in non_empty):
        return "boolean"
    if all(_INT_RE.fullmatch(v) for v in non_empty):
        return "integer"
    if all(_INT_RE.fullmatch(v) or _FLOAT_RE.fullmatch(v) for v in non_empty):
        return "float"
    if all(_ISO_DATE_RE.fullmatch(v) and coerce_date(v, ("%Y-%m-%d",)) for v in non_empty):
        return "date"
    return "string"


def rule_infer_types(table: Table) -> Dict[str, str]:
    """Return ``{column: inferred_type}`` for every column."""
    return {header: infer_column_type(table.column(header)) for header in table.headers}
