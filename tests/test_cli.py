"""End-to-end tests for the CLI, including stdin/stdout and exit codes."""

from __future__ import annotations

import json

from csv_json_cleaner.cli import main


def test_cli_version(capsys):
    code = None
    try:
        main(["--version"])
    except SystemExit as exc:
        code = exc.code
    out = capsys.readouterr().out
    assert code == 0
    assert "0.1.0" in out


def test_cli_stdin_to_stdout(capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("a,b\n 1 ,x\n"))
    code = main(["-", "--out", "-", "--to", "json", "--quiet"])
    out = capsys.readouterr().out
    assert code == 0
    assert json.loads(out) == [{"a": "1", "b": "x"}]


def test_cli_file_roundtrip_and_report(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text('id,Amount\n1,"$1,000"\n1,"$1,000"\n', encoding="utf-8")
    out = tmp_path / "out.json"
    report = tmp_path / "report.json"
    code = main([str(src), "--out", str(out), "--report", str(report)])
    assert code == 0

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == [{"id": "1", "amount": "1000"}]

    rep = json.loads(report.read_text(encoding="utf-8"))
    assert rep["rows_in"] == 2
    assert rep["rows_out"] == 1
    assert rep["duplicate_rows_removed"] == 1

    err = capsys.readouterr().err
    assert "csv-json-cleaner report" in err


def test_cli_quiet_suppresses_report(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a\n1\n", encoding="utf-8")
    main([str(src), "--out", "-", "--quiet"])
    err = capsys.readouterr().err
    assert err == ""


def test_cli_missing_file_returns_2(capsys):
    code = main(["does-not-exist.csv"])
    assert code == 2
    assert "cannot read input" in capsys.readouterr().err


def test_cli_bad_key_returns_2(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a\n1\n", encoding="utf-8")
    code = main([str(src), "--key", "missing", "--out", "-", "--quiet"])
    assert code == 2
    assert "key" in capsys.readouterr().err.lower()


def test_cli_no_flags_disable_rules(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a\n x \n x \n", encoding="utf-8")
    main([str(src), "--out", "-", "--no-trim", "--no-dedupe", "--quiet"])
    out = capsys.readouterr().out
    # trimming disabled -> whitespace kept; dedupe disabled -> both rows kept
    assert out.count(" x ") == 2
