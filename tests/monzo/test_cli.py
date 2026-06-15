"""Integration tests for monzo_expense/cli.py using typer.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from monzo_expense.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--out-dir" in result.output
    assert "--rules" in result.output


def test_missing_out_dir_exits_4() -> None:
    result = runner.invoke(
        app,
        [str(FIXTURES / "statement_minimal.pdf"), "--rules", str(FIXTURES / "rules_example.yaml")],
    )
    assert result.exit_code == 4


def test_nonexistent_pdf_exits_4(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            str(tmp_path / "no_such.pdf"),
            "--rules",
            str(FIXTURES / "rules_example.yaml"),
            "--out-dir",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 4


def test_happy_path_single_month(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(FIXTURES / "rules_example.yaml"),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0
    csvs = list(out.glob("*.csv"))
    assert len(csvs) == 1
    assert "2026-04.csv" in csvs[0].name
    # Rich may wrap long paths; join lines before checking
    flat = result.output.replace("\n", "")
    assert "2026-04.csv" in flat


def test_happy_path_two_months(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_multi_month.pdf"),
            "--rules",
            str(FIXTURES / "rules_example.yaml"),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0
    csvs = sorted(out.glob("*.csv"))
    assert len(csvs) == 2
    assert csvs[0].name == "2026-04.csv"
    assert csvs[1].name == "2026-05.csv"
    flat = result.output.replace("\n", "")
    assert "2026-04.csv" in flat
    assert "2026-05.csv" in flat


def test_unmatched_transactions_exit_1_no_csvs(tmp_path: Path) -> None:
    """Partial rules → unmatched transactions → exit 1, no CSVs written."""
    rules_path = tmp_path / "partial.yaml"
    rules_path.write_text(
        "rules:\n  - match: 'O Okwu-Boms'\n    category: 'Main Account Inflow'\n",
        encoding="utf-8",
    )
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
    assert result.exit_code == 1
    assert not out.exists() or not list(out.glob("*.csv"))


def test_report_unmatched_file_written(tmp_path: Path) -> None:
    rules_path = tmp_path / "partial.yaml"
    # Deliberately match nothing
    rules_path.write_text("rules:\n  - match: NOMATCH\n    category: Salary\n", encoding="utf-8")
    report_path = tmp_path / "unmatched.txt"
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(rules_path),
            "--out-dir",
            str(out),
            "--report-unmatched",
            str(report_path),
        ],
    )
    assert result.exit_code == 1
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "|" in content  # pipe-separated format


def test_rules_with_type_field_exits_4(tmp_path: Path) -> None:
    rules_path = tmp_path / "bad.yaml"
    rules_path.write_text(
        "rules:\n  - match: FOOD\n    type: DEB\n    category: 'Food Supplies'\n",
        encoding="utf-8",
    )
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
    assert result.exit_code == 4
    assert "monzo" in result.output.lower() or "type" in result.output.lower()


def test_zero_transaction_statement_exits_0(tmp_path: Path) -> None:
    """Empty statement (zero transactions, zero totals) → exit 0, one all-zero CSV."""
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("rules:\n  - match: NOMATCH\n    category: Salary\n", encoding="utf-8")
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
    assert result.exit_code == 0
    csvs = list(out.glob("*.csv"))
    assert len(csvs) == 1
    content = csvs[0].read_text()
    assert "Main Account Inflow,0.00" in content


def test_missing_rules_file_exits_4(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            str(FIXTURES / "statement_minimal.pdf"),
            "--rules",
            str(tmp_path / "no_rules.yaml"),
            "--out-dir",
            str(out),
        ],
    )
    assert result.exit_code == 4
