"""Tests for monzo_expense/parser.py."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from monzo_expense.errors import ParseError
from monzo_expense.parser import Transaction, parse_statement

FIXTURES = Path(__file__).parent / "fixtures"


def test_minimal_transaction_count() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    assert len(stmt.transactions) == 4


def test_minimal_period() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    assert str(stmt.period_start) == "2026-04-01"
    assert str(stmt.period_end) == "2026-04-30"


def test_minimal_balance_equation() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    computed = stmt.opening_balance + stmt.total_deposits - stmt.total_outgoings
    assert computed == stmt.closing_balance


def test_minimal_continuation_row_joined() -> None:
    """The first transaction has a continuation row; description must be joined, not split."""
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    first = stmt.transactions[0]
    # The continuation "Reference: April transfer" must be in the description
    assert "Reference: April transfer" in first.description
    # It should be one transaction, not two
    assert stmt.transactions[0].date.month == 4
    assert stmt.transactions[0].date.day == 1


def test_minimal_no_separate_continuation_transaction() -> None:
    """No Transaction should be created from a continuation row alone."""
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    # If continuation row were misread as a transaction, we'd have 5 transactions
    assert len(stmt.transactions) == 4


def test_thousand_separator_amount() -> None:
    """Amount '1,500.00' must parse as Decimal('1500.00'), not raise."""
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    # First transaction is the deposit of 1500
    deposit = stmt.transactions[0]
    assert deposit.amount == Decimal("1500.00")
    assert deposit.direction == "in"


def test_negative_amount_gives_direction_out() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    out_txs = [tx for tx in stmt.transactions if tx.direction == "out"]
    assert len(out_txs) == 3
    for tx in out_txs:
        assert tx.amount > 0  # stored as positive Decimal


def test_no_float_in_amounts() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    for tx in stmt.transactions:
        assert isinstance(tx.amount, Decimal)
        assert isinstance(tx.running_balance, Decimal)


def test_transactions_are_frozen() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    with pytest.raises(AttributeError):
        stmt.transactions[0].description = "changed"  # type: ignore[misc]


def test_document_order_preserved() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    dates = [tx.date for tx in stmt.transactions]
    assert dates == sorted(dates)


def test_no_type_code_field() -> None:
    """Transaction must not have a type_code attribute."""
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    assert not hasattr(stmt.transactions[0], "type_code")


def test_multi_month_transaction_count() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    assert len(stmt.transactions) == 16


def test_multi_month_both_months_present() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    months = {tx.date.month for tx in stmt.transactions}
    assert 4 in months  # April
    assert 5 in months  # May


def test_multi_month_pot_page_produces_no_extra_transactions() -> None:
    """The trailing Pot page must be skipped; no transactions from it."""
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    # If the Pot page table was parsed, we'd see "Pot deposit" as a transaction
    descriptions = [tx.description for tx in stmt.transactions]
    assert not any("Pot deposit" in d for d in descriptions)


def test_multi_month_balance_equation() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    computed = stmt.opening_balance + stmt.total_deposits - stmt.total_outgoings
    assert computed == stmt.closing_balance


def test_multi_month_continuation_rows_joined() -> None:
    """Continuation rows from multi-month fixture are joined, not separate transactions."""
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    # First April transaction has continuation "Reference: Salary April 2026"
    apr_txs = [tx for tx in stmt.transactions if tx.date.month == 4]
    first_apr = apr_txs[0]
    assert "Reference: Salary April 2026" in first_apr.description


def test_empty_statement_returns_empty_tuple() -> None:
    stmt = parse_statement(FIXTURES / "statement_empty.pdf")
    assert stmt.transactions == ()
    assert stmt.total_deposits == Decimal("0.00")
    assert stmt.total_outgoings == Decimal("0.00")


def test_bad_balance_raises_parse_error() -> None:
    with pytest.raises(ParseError) as exc_info:
        parse_statement(FIXTURES / "statement_bad_balance.pdf")
    assert "balance equation" in exc_info.value.message.lower()


def test_non_pdf_file_raises_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "not_a_pdf.pdf"
    bad.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_statement(bad)


def test_statement_is_frozen() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    with pytest.raises(AttributeError):
        stmt.sort_code = "changed"  # type: ignore[misc]


def test_four_digit_year_parsed_correctly() -> None:
    """Dates use four-digit years from the PDF, not expanded from two-digit."""
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    for tx in stmt.transactions:
        assert tx.date.year == 2026
