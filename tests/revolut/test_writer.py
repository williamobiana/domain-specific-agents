"""Tests for revolut_expense/writer.py."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from revolut_expense.classifier import ClassificationResult, ClassifiedTransaction
from revolut_expense.parser import Statement, Transaction
from revolut_expense.schema import Category
from revolut_expense.splitter import YearMonth
from revolut_expense.writer import write_csvs

FIXTURES = Path(__file__).parent / "fixtures"


def _tx(amount: str, direction: str = "out", tx_date: date | None = None) -> Transaction:
    return Transaction(
        date=tx_date or date(2026, 4, 1),
        description="test",
        amount=Decimal(amount),
        direction=direction,  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )


def _ct(tx: Transaction, category: Category) -> ClassifiedTransaction:
    return ClassifiedTransaction(transaction=tx, category=category)


def _stmt(period_start: date | None = None, period_end: date | None = None) -> Statement:
    return Statement(
        sort_code="04-00-04",
        account_number="12345678",
        iban="GB29REVO00997012345678",
        bic="REVOGB21",
        period_start=period_start or date(2026, 4, 1),
        period_end=period_end or date(2026, 4, 30),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1000.00"),
        total_money_in=Decimal("0.00"),
        total_money_out=Decimal("0.00"),
        transactions=(),
    )


def _all_zero_by_month() -> dict[YearMonth, ClassificationResult]:
    return {
        YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=()),
    }


def test_golden_file_month1(tmp_path: Path) -> None:
    from revolut_expense.parser import parse_statement
    from revolut_expense.rules import load_rules
    from revolut_expense.classifier import classify
    from revolut_expense.splitter import split_by_month

    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    rules = load_rules(FIXTURES / "rules_example.yaml")
    result = classify(stmt.transactions, rules)
    by_month = split_by_month(result)
    written = write_csvs(by_month, stmt, tmp_path / "out")
    assert len(written) == 2
    expected = (FIXTURES / "expected_month1.csv").read_bytes()
    actual = written[0].read_bytes()
    assert actual == expected


def test_golden_file_month2(tmp_path: Path) -> None:
    from revolut_expense.parser import parse_statement
    from revolut_expense.rules import load_rules
    from revolut_expense.classifier import classify
    from revolut_expense.splitter import split_by_month

    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    rules = load_rules(FIXTURES / "rules_example.yaml")
    result = classify(stmt.transactions, rules)
    by_month = split_by_month(result)
    written = write_csvs(by_month, stmt, tmp_path / "out")
    expected = (FIXTURES / "expected_month2.csv").read_bytes()
    actual = written[1].read_bytes()
    assert actual == expected


def test_zero_fill_category(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    written = write_csvs(by_month, stmt, tmp_path / "out")
    content = written[0].read_text(encoding="utf-8")
    assert "Rent,0.00" in content
    assert "Salary,0.00" in content
    assert "Main Account Inflow,0.00" in content


def test_schema_row_count(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    written = write_csvs(by_month, stmt, tmp_path / "out")
    rows = list(csv.reader(written[0].open(encoding="utf-8")))
    # 2 metadata header rows + 38 schema rows = 40
    assert len(rows) == 40


def test_main_account_inflow_row_present(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    written = write_csvs(by_month, stmt, tmp_path / "out")
    content = written[0].read_text(encoding="utf-8")
    assert "Main Account Inflow" in content


def test_closing_balance_row_is_last(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    written = write_csvs(by_month, stmt, tmp_path / "out")
    rows = list(csv.reader(written[0].open(encoding="utf-8")))
    assert rows[-1][0] == "Closing Balance"
    assert rows[-2][0] == "Balance"


def test_lf_line_endings(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    written = write_csvs(by_month, stmt, tmp_path / "out")
    raw = written[0].read_bytes()
    assert b"\r\n" not in raw
    assert b"\n" in raw


def test_no_unnecessary_quoting(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    written = write_csvs(by_month, stmt, tmp_path / "out")
    content = written[0].read_text(encoding="utf-8")
    # QUOTE_MINIMAL means simple values shouldn't be quoted
    assert '"Salary"' not in content


def test_out_dir_created_if_absent(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    out = tmp_path / "new" / "dir" / "output"
    assert not out.exists()
    write_csvs(by_month, stmt, out)
    assert out.exists()


def test_overwrite_produces_identical_files(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt()
    out = tmp_path / "out"
    written1 = write_csvs(by_month, stmt, out)
    content1 = written1[0].read_bytes()
    written2 = write_csvs(by_month, stmt, out)
    content2 = written2[0].read_bytes()
    assert content1 == content2


def test_files_named_yyyy_mm_with_zero_padded_month(tmp_path: Path) -> None:
    by_month = {
        YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=()),
        YearMonth(2026, 5): ClassificationResult(matched=(), unmatched=()),
    }
    stmt = _stmt(period_start=date(2026, 4, 1), period_end=date(2026, 5, 31))
    written = write_csvs(by_month, stmt, tmp_path / "out")
    assert written[0].name == "2026-04.csv"
    assert written[1].name == "2026-05.csv"


def test_returned_list_in_ascending_order(tmp_path: Path) -> None:
    by_month = {
        YearMonth(2026, 5): ClassificationResult(matched=(), unmatched=()),
        YearMonth(2026, 4): ClassificationResult(matched=(), unmatched=()),
    }
    stmt = _stmt(period_start=date(2026, 4, 1), period_end=date(2026, 5, 31))
    written = write_csvs(by_month, stmt, tmp_path / "out")
    assert written[0].name == "2026-04.csv"
    assert written[1].name == "2026-05.csv"


def test_metadata_header_rows(tmp_path: Path) -> None:
    by_month = _all_zero_by_month()
    stmt = _stmt(period_start=date(2026, 4, 1), period_end=date(2026, 4, 30))
    written = write_csvs(by_month, stmt, tmp_path / "out")
    rows = list(csv.reader(written[0].open(encoding="utf-8")))
    assert rows[0] == ["Period start", "2026-04-01"]
    assert rows[1] == ["Period end", "2026-04-30"]


def test_determinism(tmp_path: Path) -> None:
    from revolut_expense.parser import parse_statement
    from revolut_expense.rules import load_rules
    from revolut_expense.classifier import classify
    from revolut_expense.splitter import split_by_month

    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    rules = load_rules(FIXTURES / "rules_example.yaml")
    result = classify(stmt.transactions, rules)
    by_month = split_by_month(result)

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    written1 = write_csvs(by_month, stmt, out1)
    written2 = write_csvs(by_month, stmt, out2)

    for p1, p2 in zip(written1, written2):
        assert p1.read_bytes() == p2.read_bytes()
