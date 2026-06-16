"""Tests for revolut_expense/parser.py."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from revolut_expense.errors import ParseError
from revolut_expense.parser import Transaction, parse_statement

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
    computed = stmt.opening_balance + stmt.total_money_in - stmt.total_money_out
    assert computed == stmt.closing_balance


def test_minimal_iban_and_bic_present() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    assert stmt.iban != ""
    assert stmt.bic != ""


def test_minimal_continuation_row_joined() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    first = stmt.transactions[0]
    assert "Reference: Salary April 2026" in first.description
    assert first.date.month == 4
    assert first.date.day == 1


def test_to_continuation_row_joined() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    morrisons = next(tx for tx in stmt.transactions if "Morrisons" in tx.description)
    assert "To: 8 Glasgow Road, Dumfries" in morrisons.description


def test_minimal_no_separate_continuation_transaction() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    assert len(stmt.transactions) == 4


def test_thousand_separator_amount() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    deposit = stmt.transactions[0]
    assert deposit.amount == Decimal("1500.00")
    assert deposit.direction == "in"


def test_money_in_column_gives_direction_in() -> None:
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    in_txs = [tx for tx in stmt.transactions if tx.direction == "in"]
    assert len(in_txs) == 1
    assert in_txs[0].amount > 0


def test_money_out_column_gives_direction_out() -> None:
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
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    assert not hasattr(stmt.transactions[0], "type_code")


def test_transaction_has_no_type_code_attribute() -> None:
    from datetime import date as date_type

    tx = Transaction(
        date=date_type(2026, 4, 1),
        description="test",
        amount=Decimal("100.00"),
        direction="in",
        running_balance=Decimal("1100.00"),
    )
    assert not hasattr(tx, "type_code")


def test_multi_month_transaction_count() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    assert len(stmt.transactions) == 14


def test_multi_month_both_months_present() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    months = {tx.date.month for tx in stmt.transactions}
    assert 4 in months  # April
    assert 5 in months  # May


def test_multi_month_april_transaction_count() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    april = [tx for tx in stmt.transactions if tx.date.month == 4]
    assert len(april) == 8


def test_multi_month_may_transaction_count() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    may = [tx for tx in stmt.transactions if tx.date.month == 5]
    assert len(may) == 6


def test_multi_month_balance_equation() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    computed = stmt.opening_balance + stmt.total_money_in - stmt.total_money_out
    assert computed == stmt.closing_balance


def test_multi_month_continuation_rows_joined() -> None:
    stmt = parse_statement(FIXTURES / "statement_multi_month.pdf")
    apr_txs = [tx for tx in stmt.transactions if tx.date.month == 4]
    first_apr = apr_txs[0]
    assert "Reference: Salary April 2026" in first_apr.description


def test_pending_rows_produce_zero_transactions() -> None:
    stmt = parse_statement(FIXTURES / "statement_with_pending_and_reverted.pdf")
    # Only Account transactions are counted; Pending and Reverted are excluded
    assert len(stmt.transactions) == 2
    descriptions = [tx.description for tx in stmt.transactions]
    assert not any("PENDING" in d for d in descriptions)
    assert not any("REVERTED" in d for d in descriptions)


def test_reverted_rows_produce_zero_transactions() -> None:
    stmt = parse_statement(FIXTURES / "statement_with_pending_and_reverted.pdf")
    descriptions = [tx.description for tx in stmt.transactions]
    assert not any("REVERTED" in d for d in descriptions)


def test_pending_reverted_fixture_balance_equation() -> None:
    stmt = parse_statement(FIXTURES / "statement_with_pending_and_reverted.pdf")
    computed = stmt.opening_balance + stmt.total_money_in - stmt.total_money_out
    assert computed == stmt.closing_balance


def test_empty_statement_returns_empty_tuple() -> None:
    stmt = parse_statement(FIXTURES / "statement_empty.pdf")
    assert stmt.transactions == ()
    assert stmt.total_money_in == Decimal("0.00")
    assert stmt.total_money_out == Decimal("0.00")


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
    stmt = parse_statement(FIXTURES / "statement_minimal.pdf")
    for tx in stmt.transactions:
        assert tx.date.year == 2026
