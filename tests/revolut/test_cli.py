"""Integration tests for revolut_expense/cli.py."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from revolut_expense.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


def _rules(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(content, encoding="utf-8")
    return p


FULL_RULES = """\
rules:
  - match_regex: "^Payment from NATWEST HRPS PAYRO"
    direction: in
    category: "Salary"
  - match_regex: "^Morrisons"
    category: "Food Supplies"
  - match_regex: "^Tesco"
    category: "Food Supplies"
  - match_regex: "^Lidl"
    category: "Food Supplies"
  - match_regex: "^Dghb Catering"
    category: "Eating Out"
  - match_regex: "^Greggs"
    category: "Eating Out"
  - match_regex: "^Lebara"
    category: "Bill - Phone & Internet"
  - match_regex: "^Hargreaves Lansdown"
    direction: out
    category: "Stocks & Shares ISA"
  - match_regex: "^Trainline"
    category: "Holidays & Travel"
  - match_regex: "^Shell"
    category: "Car & Gas"
  - match_regex: "^Anthropic"
    category: "Sundry"
"""

PENDING_REVERTED_RULES = """\
rules:
  - match_regex: "^Payment from NATWEST HRPS PAYRO"
    direction: in
    category: "Salary"
  - match_regex: "^Morrisons"
    category: "Food Supplies"
"""


def test_happy_path_single_month(tmp_path: Path) -> None:
    rules_path = _rules(tmp_path, FULL_RULES)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(rules_path),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    csvs = list(out.glob("*.csv"))
    assert len(csvs) == 1
    assert str(csvs[0]) in result.output


def test_happy_path_two_months(tmp_path: Path) -> None:
    rules_path = _rules(tmp_path, FULL_RULES)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_multi_month.pdf"),
            "--rules",
            str(rules_path),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    csvs = sorted(out.glob("*.csv"))
    assert len(csvs) == 2
    assert csvs[0].name == "2026-04.csv"
    assert csvs[1].name == "2026-05.csv"
    assert "2026-04.csv" in result.output
    assert "2026-05.csv" in result.output


def test_unmatched_transactions_exit_1(tmp_path: Path) -> None:
    partial_rules = _rules(tmp_path, "rules:\n  - match_regex: \"^NOTHING_MATCHES\"\n    category: Salary\n")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(partial_rules),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 1
    assert not list(out.glob("*.csv"))


def test_unmatched_table_has_no_type_code_column(tmp_path: Path) -> None:
    partial_rules = _rules(tmp_path, "rules:\n  - match_regex: \"^NOTHING_MATCHES\"\n    category: Salary\n")
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(partial_rules),
            "--out-dir",
            str(tmp_path / "out"),
        ],
    )
    assert "Type Code" not in result.output


def test_report_unmatched_file_written(tmp_path: Path) -> None:
    partial_rules = _rules(tmp_path, "rules:\n  - match_regex: \"^NOTHING_MATCHES\"\n    category: Salary\n")
    report_file = tmp_path / "unmatched.txt"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(partial_rules),
            "--out-dir",
            str(tmp_path / "out"),
            "--report-unmatched",
            str(report_file),
        ],
    )
    assert result.exit_code == 1
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "|" in content


def test_nonexistent_pdf_exit_4(tmp_path: Path) -> None:
    rules_path = _rules(tmp_path, FULL_RULES)
    result = runner.invoke(
        app,
        [
            str(tmp_path / "nonexistent.pdf"),
            "--rules",
            str(rules_path),
        ],
    )
    assert result.exit_code == 4


def test_rules_with_type_field_exit_4(tmp_path: Path) -> None:
    bad_rules = _rules(
        tmp_path,
        "rules:\n  - match: SALARY\n    type: BGC\n    category: Salary\n",
    )
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(bad_rules),
        ],
    )
    assert result.exit_code == 4
    assert "revolut" in result.output.lower()


def test_zero_transaction_statement_exit_0(tmp_path: Path) -> None:
    rules_path = _rules(tmp_path, FULL_RULES)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_empty.pdf"),
            "--rules",
            str(rules_path),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    csvs = list(out.glob("*.csv"))
    assert len(csvs) == 1
    content = csvs[0].read_text(encoding="utf-8")
    assert "Salary,0.00" in content


def test_pending_and_reverted_rows_excluded(tmp_path: Path) -> None:
    rules_path = _rules(tmp_path, PENDING_REVERTED_RULES)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_with_pending_and_reverted.pdf"),
            "--rules",
            str(rules_path),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    csvs = list(out.glob("*.csv"))
    assert len(csvs) == 1


def test_help_exit_0() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--rules" in result.output
    assert "--out-dir" in result.output
