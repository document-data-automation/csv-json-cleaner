"""Command-line interface for csv-json-cleaner.

Clean output (the transformed data) goes to the chosen destination; the diff
report and any warnings go to stderr.  Exit codes: ``0`` success, ``1`` runtime
error, ``2`` usage/IO error.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence

from . import __version__
from .io import read_table, write_table
from .pipeline import CleanConfig, clean
from .report import format_report
from .rules import DEFAULT_DATE_FORMATS

_FORMAT_CHOICES = ("csv", "json")


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="csv-json-cleaner",
        description="Clean messy CSV/JSON tabular data with a before/after diff report.",
    )
    parser.add_argument("input", nargs="?", help="Input file, or '-' for stdin.")
    parser.add_argument("--in", dest="in_", metavar="PATH", help="Input file (alias of the positional argument).")
    parser.add_argument("--out", default="-", metavar="PATH", help="Output file, or '-' for stdout (default).")
    parser.add_argument("--from", dest="from_", choices=_FORMAT_CHOICES, help="Force input format (else inferred/sniffed).")
    parser.add_argument("--to", choices=_FORMAT_CHOICES, help="Force output format (else inferred from --out).")
    parser.add_argument("--report", metavar="PATH", help="Also write the diff report as JSON to this path.")
    parser.add_argument("--key", metavar="COLS", help="Comma-separated columns to de-duplicate on (default: whole row).")
    parser.add_argument(
        "--date-format",
        dest="date_formats",
        action="append",
        metavar="FMT",
        help="Additional strptime date format to try (repeatable, tried first).",
    )
    parser.add_argument("--quiet", action="store_true", help="Do not print the report table to stderr.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    disable = parser.add_argument_group("rule toggles (each rule is on by default)")
    disable.add_argument("--no-trim", dest="trim", action="store_false", help="Do not trim whitespace/quotes.")
    disable.add_argument("--no-headers", dest="normalize_headers", action="store_false", help="Do not normalise headers to snake_case.")
    disable.add_argument("--no-drop-empty", dest="drop_empty", action="store_false", help="Keep fully-empty rows and columns.")
    disable.add_argument("--no-numbers", dest="coerce_numbers", action="store_false", help="Do not coerce currency/grouped numbers.")
    disable.add_argument("--no-dates", dest="normalize_dates", action="store_false", help="Do not normalise dates to ISO 8601.")
    disable.add_argument("--no-booleans", dest="standardize_booleans", action="store_false", help="Do not standardise booleans.")
    disable.add_argument("--no-dedupe", dest="dedupe", action="store_false", help="Do not remove duplicate rows.")
    disable.add_argument("--no-types", dest="infer_types", action="store_false", help="Do not infer per-column types.")
    return parser


def _config_from_args(args: argparse.Namespace) -> CleanConfig:
    key = [k.strip() for k in args.key.split(",") if k.strip()] if args.key else None
    date_formats = tuple(args.date_formats) + DEFAULT_DATE_FORMATS if args.date_formats else DEFAULT_DATE_FORMATS
    return CleanConfig(
        trim=args.trim,
        normalize_headers=args.normalize_headers,
        drop_empty=args.drop_empty,
        coerce_numbers=args.coerce_numbers,
        normalize_dates=args.normalize_dates,
        standardize_booleans=args.standardize_booleans,
        dedupe=args.dedupe,
        infer_types=args.infer_types,
        key=key,
        date_formats=date_formats,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point.  Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    source = args.in_ or args.input or "-"
    config = _config_from_args(args)

    try:
        table = read_table(source, fmt=args.from_)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"csv-json-cleaner: cannot read input: {exc}", file=sys.stderr)
        return 2

    try:
        cleaned, report = clean(table, config)
    except ValueError as exc:
        print(f"csv-json-cleaner: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive
        print(f"csv-json-cleaner: unexpected error: {exc}", file=sys.stderr)
        return 1

    try:
        write_table(cleaned, args.out, fmt=args.to)
        if args.report:
            with open(args.report, "w", encoding="utf-8") as handle:
                json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
    except OSError as exc:
        print(f"csv-json-cleaner: cannot write output: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(format_report(report), file=sys.stderr)

    return 0
