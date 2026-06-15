"""Tests for monzo_expense/writer.py."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from monzo_expense.classifier import ClassificationResult, ClassifiedTransaction
from monzo_expense.parser import Statement, Transaction
from monzo_expense.schema import Category, SCHEMA_ORDER
from monzo_expense.splitter import YearMonth, split_by_month
from monzo_expense.writer import write_csvs

FIXTURES = Path(__file__).parent / "fixtures"


def _tx(tx_date: date, amount: str, direction: str = "out") -> Transaction:
    return Transaction(
        date=tx_date,
        description="TX",
        amount=Decimal(amount),
        direction=direction,  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )


def _ct(tx_date: date, amount: str, direction: str, category: Category) -> ClassifiedTransaction:
    return ClassifiedTransaction(transaction=_tx(tx_date, amount, direction), category=category)


def _stmt(
    deposits: str = "0.00",
    outgoings: str = "0.00",
    start: date = date(2026, 4, 1),
    end: date = date(2026, 4, 30),
) -> Statement:
    return Statement(
        sort_code="04-00-04",
        account_number="12345678",
        period_start=start,
        period_end=end,
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1000.00") + Decimal(deposits) - Decimal(outgoings),
        total_deposits=Decimal(deposits),
        total_outgoings=Decimal(outgoings),
        transactions=(),
    )


def test_golden_file_april(tmp_path: Path) -> None:
    """Full-pipeline golden-file test for April 2026."""
    from monzo_expense.parser import parse_statement
    from monzo_expense.rules import load_rules
    from monzo_expense.classifier import classify

    rules = load_rules(FIXTURES / "rules_example.yaml")
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    result = classify(stmt.transactions, rules)
    by_month = split_by_month(result)
    write_csvs(by_month, stmt, tmp_path)

    written = tmp_path / "2026-04.csv"
    expected = FIXTURES / "expected_april.csv"
    assert written.read_bytes() == expected.read_bytes()


def test_golden_file_may(tmp_path: Path) -> None:
    """Full-pipeline golden-file test for May 2026."""
    from monzo_expense.parser import parse_statement
    from monzo_expense.rules import load_rules
    from monzo_expense.classifier import classify

    rules = load_rules(FIXTURES / "rules_example.yaml")
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    result = classify(stmt.transactions, rules)
    by_month = split_by_month(result)
    write_csvs(by_month, stmt, tmp_path)

    written = tmp_path / "2026-05.csv"
    expected = FIXTURES / "expected_may.csv"
    assert written.read_bytes() == expected.read_bytes()


def test_zero_fill_for_absent_category(tmp_path: Path) -> None:
    """A month with no transactions for a category still emits 0.00."""
    stmt = _stmt()
    result = ClassificationResult(matched=(), unmatched=())
    by_month = {YearMonth(2026, 4): result}
    write_csvs(by_month, stmt, tmp_path)

    rows = list(csv.reader((tmp_path / "2026-04.csv").read_text().splitlines()))
    # Find any line_item row (after the 2 metadata rows)
    line_items = {r[0]: r[1] for r in rows if len(r) == 2 and r[0] not in ("Period start", "Period end")}
    assert line_items.get("Salary") == "0.00"
    assert line_items.get("Main Account Inflow") == "0.00"
    assert line_items.get("Food Supplies") == "0.00"


def test_schema_row_count(tmp_path: Path) -> None:
    """Each output file must have 38 schema rows + 2 metadata rows = 40 rows."""
    stmt = _stmt()
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=())}
    write_csvs(by_month, stmt, tmp_path)

    content = (tmp_path / "2026-04.csv").read_text()
    rows = [r for r in content.splitlines() if r]
    assert len(rows) == 40


def test_main_account_inflow_row_present(tmp_path: Path) -> None:
    stmt = _stmt()
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=())}
    write_csvs(by_month, stmt, tmp_path)

    content = (tmp_path / "2026-04.csv").read_text()
    assert "Main Account Inflow" in content


def test_lf_line_endings(tmp_path: Path) -> None:
    stmt = _stmt()
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=())}
    write_csvs(by_month, stmt, tmp_path)

    raw = (tmp_path / "2026-04.csv").read_bytes()
    assert b"\r\n" not in raw
    assert b"\n" in raw


def test_no_unnecessary_quoting(tmp_path: Path) -> None:
    stmt = _stmt()
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=())}
    write_csvs(by_month, stmt, tmp_path)

    content = (tmp_path / "2026-04.csv").read_text()
    # csv.QUOTE_MINIMAL: values that don't need quoting must not be quoted
    assert '"Salary"' not in content
    assert '"Food Supplies"' not in content


def test_out_dir_created_if_absent(tmp_path: Path) -> None:
    out_dir = tmp_path / "deeply" / "nested" / "dir"
    assert not out_dir.exists()
    stmt = _stmt()
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=())}
    write_csvs(by_month, stmt, out_dir)
    assert out_dir.exists()


def test_overwrite_produces_identical_file(tmp_path: Path) -> None:
    stmt = _stmt()
    ct = _ct(date(2026, 4, 1), "100.00", "in", Category.MAIN_ACCOUNT_INFLOW)
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(ct,), unmatched=())}
    write_csvs(by_month, stmt, tmp_path)
    first = (tmp_path / "2026-04.csv").read_bytes()
    write_csvs(by_month, stmt, tmp_path)
    second = (tmp_path / "2026-04.csv").read_bytes()
    assert first == second


def test_returned_paths_in_chronological_order(tmp_path: Path) -> None:
    stmt = _stmt(start=date(2026, 4, 1), end=date(2026, 5, 31))
    by_month = {
        YearMonth(2026, 5): ClassificationResult(matched=(), unmatched=()),
        YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=()),
    }
    paths = write_csvs(by_month, stmt, tmp_path)
    assert paths[0].name == "2026-04.csv"
    assert paths[1].name == "2026-05.csv"


def test_files_named_yyyy_mm_with_zero_padded_month(tmp_path: Path) -> None:
    stmt = _stmt()
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=())}
    paths = write_csvs(by_month, stmt, tmp_path)
    assert paths[0].name == "2026-04.csv"


def test_determinism(tmp_path: Path) -> None:
    """Running write_csvs twice with same inputs produces byte-identical files."""
    from monzo_expense.parser import parse_statement
    from monzo_expense.rules import load_rules
    from monzo_expense.classifier import classify

    rules = load_rules(FIXTURES / "rules_example.yaml")
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    result = classify(stmt.transactions, rules)
    by_month = split_by_month(result)

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    write_csvs(by_month, stmt, out1)
    write_csvs(by_month, stmt, out2)

    for name in ["2026-04.csv", "2026-05.csv"]:
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()


def test_metadata_header_records_full_period(tmp_path: Path) -> None:
    """Period start/end in CSV must come from statement, not the month."""
    stmt = _stmt(start=date(2026, 4, 1), end=date(2026, 5, 31))
    by_month = {YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=())}
    write_csvs(by_month, stmt, tmp_path)

    rows = list(csv.reader((tmp_path / "2026-04.csv").read_text().splitlines()))
    assert rows[0] == ["Period start", "2026-04-01"]
    assert rows[1] == ["Period end", "2026-05-31"]
