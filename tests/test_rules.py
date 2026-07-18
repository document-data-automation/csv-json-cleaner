"""Unit tests for each cleaning rule in isolation."""

from __future__ import annotations

from csv_json_cleaner.rules import (
    coerce_date,
    coerce_number,
    infer_column_type,
    make_unique,
    rule_coerce_numbers,
    rule_dedupe,
    rule_drop_empty,
    rule_normalize_dates,
    rule_normalize_headers,
    rule_standardize_booleans,
    rule_trim,
    to_snake_case,
)
from csv_json_cleaner.table import Table


def _table(headers, *rows):
    return Table(list(headers), [dict(zip(headers, r)) for r in rows])


# --- Rule 1: trim ---------------------------------------------------------- #

def test_trim_strips_whitespace_quotes_and_nbsp():
    table = _table(["a", "b"], ["  hi  ", '"quoted"'], ["x\xa0", "'q'"])
    cleaned, changed = rule_trim(table)
    assert cleaned.rows[0] == {"a": "hi", "b": "quoted"}
    assert cleaned.rows[1] == {"a": "x", "b": "q"}
    assert changed == 4


def test_trim_leaves_clean_cells_untouched():
    table = _table(["a"], ["clean"])
    cleaned, changed = rule_trim(table)
    assert changed == 0
    assert cleaned.rows[0]["a"] == "clean"


# --- Rule 2: header normalisation ----------------------------------------- #

def test_to_snake_case_variants():
    assert to_snake_case("Customer ID") == "customer_id"
    assert to_snake_case("firstName") == "first_name"
    assert to_snake_case("Email Address ") == "email_address"
    assert to_snake_case("Prix (€)") == "prix"
    assert to_snake_case("naïve café") == "naive_cafe"
    assert to_snake_case("!!!") == "column"


def test_make_unique_dedupes_collisions():
    assert make_unique(["col", "col", "col"]) == ["col", "col_2", "col_3"]
    assert make_unique(["a", "b", "a", "a_2"]) == ["a", "b", "a_2", "a_2_2"]


def test_normalize_headers_renames_and_rewires_rows():
    # Two distinct headers that collide only after snake_case normalisation.
    table = _table(["Full Name", "full_name", "E-mail"], ["Ada", "Ada2", "a@x"])
    cleaned, renamed = rule_normalize_headers(table)
    assert cleaned.headers == ["full_name", "full_name_2", "e_mail"]
    assert cleaned.rows[0] == {"full_name": "Ada", "full_name_2": "Ada2", "e_mail": "a@x"}
    assert renamed["Full Name"] == "full_name"


# --- Rule 3: drop empty ---------------------------------------------------- #

def test_drop_empty_rows_and_columns():
    table = _table(["a", "b", "c"], ["1", "", ""], ["", "", ""], ["2", "", ""])
    cleaned, (rows_dropped, cols_dropped) = rule_drop_empty(table)
    assert rows_dropped == 1
    assert cols_dropped == ["b", "c"]
    assert cleaned.headers == ["a"]
    assert [r["a"] for r in cleaned.rows] == ["1", "2"]


# --- Rule 4: number coercion ---------------------------------------------- #

def test_coerce_number_positive_cases():
    assert coerce_number("1,234.50") == "1234.50"
    assert coerce_number("$1,234") == "1234"
    assert coerce_number("€2,000") == "2000"
    assert coerce_number("£980") == "980"
    assert coerce_number("(1,234)") == "-1234"
    assert coerce_number("-42") == "-42"
    assert coerce_number("3.14") == "3.14"


def test_coerce_number_leaves_non_numbers_alone():
    assert coerce_number("1,2,3") is None
    assert coerce_number("12-34") is None
    assert coerce_number("555,1234") is None
    assert coerce_number("N/A") is None
    assert coerce_number("12,50") is None  # european decimal, not thousands
    assert coerce_number("") is None


def test_rule_coerce_numbers_counts_changes():
    table = _table(["amt", "name"], ["$1,000", "Ada"], ["50", "Grace"])
    cleaned, changed = rule_coerce_numbers(table)
    assert cleaned.rows[0]["amt"] == "1000"
    assert cleaned.rows[1]["amt"] == "50"
    assert cleaned.rows[0]["name"] == "Ada"
    assert changed == 1


# --- Rule 5: date normalisation ------------------------------------------- #

def test_coerce_date_common_formats():
    assert coerce_date("01/15/2021", ["%m/%d/%Y", "%d/%m/%Y"]) == "2021-01-15"
    assert coerce_date("March 5, 2021", ["%B %d, %Y"]) == "2021-03-05"
    assert coerce_date("15.06.2023", ["%d.%m.%Y"]) == "2023-06-15"
    assert coerce_date("not a date", ["%Y-%m-%d"]) is None


def test_rule_normalize_dates_leaves_unparseable():
    table = _table(["d"], ["01/15/2021"], ["whenever"])
    cleaned, changed = rule_normalize_dates(table)
    assert cleaned.rows[0]["d"] == "2021-01-15"
    assert cleaned.rows[1]["d"] == "whenever"
    assert changed == 1


# --- Rule 6: booleans ------------------------------------------------------ #

def test_standardize_booleans_column_aware():
    table = _table(["flag", "qty"], ["Yes", "1"], ["no", "5"], ["Y", "0"])
    cleaned, changed = rule_standardize_booleans(table)
    assert [r["flag"] for r in cleaned.rows] == ["true", "false", "true"]
    # qty is NOT all-boolean (has 5), so it is left numeric
    assert [r["qty"] for r in cleaned.rows] == ["1", "5", "0"]
    assert changed == 3


def test_standardize_booleans_pure_binary_stays_numeric():
    # A column of only 0/1 is ambiguous with numbers, so it is left untouched.
    table = _table(["active"], ["1"], ["0"], ["1"])
    cleaned, changed = rule_standardize_booleans(table)
    assert [r["active"] for r in cleaned.rows] == ["1", "0", "1"]
    assert changed == 0


def test_standardize_booleans_binary_with_textual_evidence_converts():
    # Once a textual token appears, the 0/1 values are read as booleans too.
    table = _table(["active"], ["1"], ["0"], ["yes"])
    cleaned, _ = rule_standardize_booleans(table)
    assert [r["active"] for r in cleaned.rows] == ["true", "false", "true"]


# --- Rule 7: dedupe -------------------------------------------------------- #

def test_dedupe_whole_row():
    table = _table(["a", "b"], ["1", "x"], ["1", "x"], ["2", "y"])
    cleaned, removed = rule_dedupe(table)
    assert removed == 1
    assert len(cleaned.rows) == 2


def test_dedupe_by_key_subset():
    table = _table(["id", "note"], ["1", "first"], ["1", "second"], ["2", "third"])
    cleaned, removed = rule_dedupe(table, key=["id"])
    assert removed == 1
    assert [r["note"] for r in cleaned.rows] == ["first", "third"]


# --- Rule 8: type inference ----------------------------------------------- #

def test_infer_column_type():
    assert infer_column_type(["1", "2", "3"]) == "integer"
    assert infer_column_type(["1", "2.5"]) == "float"
    assert infer_column_type(["true", "false"]) == "boolean"
    assert infer_column_type(["2021-01-01", "2022-12-31"]) == "date"
    assert infer_column_type(["a", "1"]) == "string"
    assert infer_column_type(["", ""]) == "empty"
    assert infer_column_type(["2021-13-40"]) == "string"  # not a real date
