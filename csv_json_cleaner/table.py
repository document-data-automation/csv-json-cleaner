"""Core in-memory table representation shared by every module.

A :class:`Table` is a light wrapper over an ordered list of column names and a
list of row dictionaries.  Every cell value is stored as a ``str`` so that the
cleaning rules can operate uniformly regardless of whether the data originated
from CSV (always strings) or JSON (mixed native types, stringified on load).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Table:
    """An ordered collection of columns and string-valued rows.

    Attributes:
        headers: Column names, in output order.
        rows: One ``dict`` per record.  Each dict is expected to contain every
            name in :attr:`headers`; missing keys are treated as empty strings.
    """

    headers: List[str] = field(default_factory=list)
    rows: List[Dict[str, str]] = field(default_factory=list)

    def copy(self) -> "Table":
        """Return a deep-enough copy (new row dicts) safe to mutate."""
        return Table(list(self.headers), [dict(r) for r in self.rows])

    def column(self, header: str) -> List[str]:
        """Return every value in ``header`` as a list, in row order."""
        return [row.get(header, "") for row in self.rows]
