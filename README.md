# csv-json-cleaner

**A no-nonsense cleaner for messy CSV/JSON tabular data, with a visible before/after diff report.**

## Why messy data is a real cost

Every analyst has lost an afternoon to a spreadsheet where dates are written five
different ways, prices carry stray `$` and `,` characters, headers are `Full Name`
in one export and `full_name` in the next, and half the rows are exact duplicates.
That mess quietly breaks joins, inflates totals, and poisons everything downstream.
`csv-json-cleaner` runs a pipeline of small, predictable fixes and then *shows you
what it changed*, so cleaning is auditable instead of a black box. It's the hands-on
companion to the CSV/JSON cleaning walkthrough at
<https://document-data-automation.com/python-for-excel-csv-data-processing>.

- Pure Python standard library — **no third-party dependencies**.
- Every fix is an independent rule you can toggle off.
- Reads and writes both CSV and JSON, and streams via stdin/stdout.
- Emits a before/after diff report to your terminal and, optionally, as JSON.

## Install

This tool is **not on PyPI**. Clone the repository and install from your local copy:

```bash
git clone https://github.com/document-data-automation/csv-json-cleaner.git
cd csv-json-cleaner
pip install .
```

You don't even need to install it — it runs straight from a clone:

```bash
python -m csv_json_cleaner --help
```

Requires Python 3.9+.

## Quickstart

Copy-paste against the bundled examples. Clean a messy CRM export and write JSON,
with the diff report printed to your terminal (stderr):

```bash
python -m csv_json_cleaner examples/crm_export.csv --out clean.json
```

The cleaned data (first two of five rows shown):

```json
[
  {
    "customer_id": "001",
    "full_name": "Ada Lovelace",
    "email_address": "ADA@example.com",
    "signup_date": "2021-01-15",
    "lifetime_value": "1234.50",
    "active": "true",
    "notes": ""
  },
  {
    "customer_id": "002",
    "full_name": "Grace Hopper",
    "email_address": "grace@example.com",
    "signup_date": "2021-03-04",
    "lifetime_value": "2000",
    "active": "true",
    "notes": "VIP"
  }
]
```

...and the report on stderr:

```text
=== csv-json-cleaner report ===

Summary:
  rows in                 7
  rows out                5
  empty rows dropped      1
  empty columns dropped   0
  duplicate rows removed  1

Cells changed per rule:
  trim                  5
  coerce_numbers        6
  normalize_dates       4
  standardize_booleans  6

Columns renamed:
  Customer ID     -> customer_id
  Full Name       -> full_name
  Email Address   -> email_address
  Signup Date     -> signup_date
  Lifetime Value  -> lifetime_value
  Active          -> active
  Notes           -> notes

Inferred column types:
  customer_id     integer
  full_name       string
  email_address   string
  signup_date     date
  lifetime_value  float
  active          boolean
  notes           string
```

The input format is auto-detected (CSV delimiter sniffed, BOM-safe) and the output
format is inferred from the `--out` extension. A few more shapes:

```bash
# JSON in, CSV out, de-duplicating on a key subset instead of the whole row
python -m csv_json_cleaner examples/orders.json --out orders.csv --key order_id

# Read stdin, write stdout, force JSON output, save the report as JSON
cat examples/crm_export.csv | python -m csv_json_cleaner - --out - --to json --report report.json

# Turn specific rules off
python -m csv_json_cleaner examples/crm_export.csv --out clean.csv --no-dates --no-dedupe
```

## The rules

Each rule is **on by default** and runs as a pure function over the rows. Disable any
of them with the matching flag.

| Rule | What it fixes | Flag to disable |
| --- | --- | --- |
| Trim | Strips whitespace, non-breaking spaces and one layer of wrapping quotes from every cell | `--no-trim` |
| Normalize headers | Rewrites headers to ascii `snake_case`; de-dupes collisions as `col`, `col_2`, ... | `--no-headers` |
| Drop empties | Removes fully-empty rows and fully-empty columns | `--no-drop-empty` |
| Coerce numbers | Strips currency symbols (`$ € £ ¥`) and thousands separators so `"$1,234.50"` becomes `"1234.50"`; leaves genuine non-numbers alone | `--no-numbers` |
| Normalize dates | Rewrites recognised dates to ISO 8601 (`YYYY-MM-DD`); leaves unparseable values alone | `--no-dates` |
| Standardize booleans | Maps `yes/no`, `y/n`, `true/false`, `t/f` (and `1/0` when a column also has textual booleans) to `true`/`false` | `--no-booleans` |
| De-duplicate rows | Drops duplicate rows, keeping the first; compares whole rows or a `--key` subset | `--no-dedupe` |
| Infer types | Adds a per-column type summary (`integer`, `float`, `date`, `boolean`, `string`, `empty`) to the report | `--no-types` |

A few deliberate design choices worth knowing:

- **Booleans are column-aware.** A column becomes boolean only when *every* non-empty
  value is a boolean token. A column made up purely of `0`/`1` is left numeric (it's
  indistinguishable from a count or an id); it converts only once a textual token like
  `yes` or `true` appears alongside.
- **Number coercion assumes US-style grouping.** `1,234.50` is a number; `12,50`
  (European decimal comma) and `1,2,3` are left untouched.
- **Ambiguous dates resolve in format order.** The default format list tries
  `MM/DD/YYYY` before `DD/MM/YYYY`. Override or extend it with `--date-format`
  (repeatable; your formats are tried first):

  ```bash
  python -m csv_json_cleaner data.csv --out clean.csv --date-format "%d/%m/%Y"
  ```

## The diff report explained

The report answers "what actually changed?". Fields:

| Field | Meaning |
| --- | --- |
| `rows_in` / `rows_out` | Row counts before and after cleaning |
| `rows_dropped_empty` | Fully-empty rows removed |
| `columns_dropped_empty` | Names of fully-empty columns removed |
| `duplicate_rows_removed` | Rows dropped by de-duplication |
| `columns_renamed` | `{original: normalized}` map of header changes |
| `cells_changed` | Number of cells each value rule modified (counted before de-duplication) |
| `inferred_types` | `{column: type}` summary of the cleaned data |

The human-readable table always prints to **stderr** (silence it with `--quiet`), so it
never contaminates piped data on stdout. Pass `--report report.json` to also write the
machine-readable version:

```json
{
  "rows_in": 7,
  "rows_out": 5,
  "rows_dropped_empty": 1,
  "columns_dropped_empty": [],
  "duplicate_rows_removed": 1,
  "columns_renamed": { "Customer ID": "customer_id" },
  "cells_changed": { "trim": 5, "coerce_numbers": 6, "normalize_dates": 4, "standardize_booleans": 6 },
  "inferred_types": { "customer_id": "integer", "signup_date": "date", "active": "boolean" }
}
```

## As a library

The pipeline is importable and every rule is a pure function, so you can compose or
inspect the process programmatically:

```python
from csv_json_cleaner import CleanConfig, clean, read_table, write_table

# Load from a path (or "-" for stdin); format is inferred or sniffed.
table = read_table("examples/crm_export.csv")

# Toggle rules and parameters via CleanConfig.
config = CleanConfig(dedupe=True, key=["customer_id"], normalize_dates=True)
cleaned, report = clean(table, config)

# The report is a dataclass with a JSON-ready dict.
print(report.to_dict()["duplicate_rows_removed"])
print(report.inferred_types)

# Write back out (format inferred from the extension, or pass fmt=...).
write_table(cleaned, "clean.json")
```

Working with in-memory data instead of files:

```python
from csv_json_cleaner import Table, clean

table = Table(
    headers=["Full Name", "Amount"],
    rows=[{"Full Name": "  Ada  ", "Amount": "$1,000"}],
)
cleaned, report = clean(table)
assert cleaned.rows[0] == {"full_name": "Ada", "amount": "1000"}
```

Individual rules live in `csv_json_cleaner.rules` (`rule_trim`, `rule_coerce_numbers`,
`coerce_number`, `coerce_date`, ...) if you want to reuse just one.

## Development

```bash
git clone https://github.com/document-data-automation/csv-json-cleaner.git
cd csv-json-cleaner
pip install -e ".[dev]"
pytest
```

The test suite is offline and pure-stdlib: it covers every rule independently, header
collision handling, delimiter sniffing, number/currency/date edge cases (including
values that must *not* be coerced), row de-duplication with and without `--key`, the
report counts, CSV↔JSON round-trips, and stdin/stdout. CI runs it on Python 3.9–3.12.

## License

MIT — see [LICENSE](LICENSE).

---

Maintained by [document-data-automation.com](https://document-data-automation.com) — practical Python workflows for document and data automation.
