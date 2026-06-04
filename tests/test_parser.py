"""Unit tests for lloyds_expense.parser — exercises parse_statement with PDF fixtures.

Fixtures are pre-generated synthetic PDFs in tests/fixtures/.  Each PDF is
a minimal but structurally valid Lloyds Classic statement created by
tests/fixtures/create_fixtures.py using reportlab.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lloyds_expense.errors import ParseError
from lloyds_expense.parser import parse_statement

# ---------------------------------------------------------------------------
# Fixture paths (absolute so they work regardless of invocation directory)
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"

MINIMAL = _FIXTURES / "statement_minimal.pdf"
FULL = _FIXTURES / "statement_full.pdf"
CROSS_YEAR = _FIXTURES / "statement_cross_year.pdf"
EMPTY_WITH_TOTALS = _FIXTURES / "statement_empty_with_totals.pdf"
BAD_BALANCE = _FIXTURES / "statement_bad_balance.pdf"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(path: Path):  # type: ignore[return]
    """Convenience wrapper — returns Statement or lets ParseError propagate."""
    return parse_statement(path)


# ---------------------------------------------------------------------------
# Tests for statement_minimal.pdf (3 transactions)
# ---------------------------------------------------------------------------


def test_minimal_transaction_count() -> None:
    """parse_statement on the minimal fixture returns exactly 3 transactions."""
    stmt = _parse(MINIMAL)
    assert len(stmt.transactions) == 3


def test_minimal_amounts_are_decimal() -> None:
    """Every transaction amount is a Decimal (not float or str)."""
    stmt = _parse(MINIMAL)
    for tx in stmt.transactions:
        assert isinstance(tx.amount, Decimal), f"Expected Decimal, got {type(tx.amount)}"


def test_minimal_directions() -> None:
    """First transaction is money-in; second and third are money-out."""
    stmt = _parse(MINIMAL)
    txs = stmt.transactions
    assert txs[0].direction == "in"
    assert txs[1].direction == "out"
    assert txs[2].direction == "out"


def test_minimal_thousand_separator_stripped() -> None:
    """Amount '1,500.00' in the PDF is parsed as Decimal('1500.00')."""
    stmt = _parse(MINIMAL)
    assert stmt.transactions[0].amount == Decimal("1500.00")


def test_minimal_dates() -> None:
    """Transaction dates are parsed correctly as date objects."""
    stmt = _parse(MINIMAL)
    txs = stmt.transactions
    assert txs[0].date == date(2026, 4, 1)
    assert txs[1].date == date(2026, 4, 15)
    assert txs[2].date == date(2026, 4, 20)


def test_minimal_metadata_sort_code_and_account() -> None:
    """Statement metadata contains the correct sort code and account number."""
    stmt = _parse(MINIMAL)
    assert stmt.sort_code == "12-34-56"
    assert stmt.account_number == "12345678"


def test_minimal_balance_equation() -> None:
    """opening_balance + money_in_total - money_out_total == closing_balance."""
    stmt = _parse(MINIMAL)
    computed = stmt.opening_balance + stmt.money_in_total - stmt.money_out_total
    assert computed == stmt.closing_balance


def test_minimal_balance_fields_are_decimal() -> None:
    """Statement monetary fields are all Decimal instances."""
    stmt = _parse(MINIMAL)
    for attr in ("opening_balance", "closing_balance", "money_in_total", "money_out_total"):
        value = getattr(stmt, attr)
        assert isinstance(value, Decimal), f"{attr} should be Decimal, got {type(value)}"


def test_minimal_document_order_preserved() -> None:
    """Transactions are returned in document order (Apr 1, Apr 15, Apr 20)."""
    stmt = _parse(MINIMAL)
    dates = [tx.date for tx in stmt.transactions]
    assert dates == [date(2026, 4, 1), date(2026, 4, 15), date(2026, 4, 20)]


# ---------------------------------------------------------------------------
# Tests for statement_full.pdf (2-page PDF, 12 transactions + legend table)
# ---------------------------------------------------------------------------


def test_full_transaction_count() -> None:
    """Full statement produces exactly 12 Transaction records.

    The legend table on page 2 uses different columns (Type | Description) and
    must NOT contribute any Transaction records.
    """
    stmt = _parse(FULL)
    assert len(stmt.transactions) == 12


def test_full_legend_table_produces_no_transactions() -> None:
    """The type-code legend table on page 2 is silently skipped."""
    stmt = _parse(FULL)
    # Legend table has 7 data rows (BGC, DEB, DD, FPI, FPO, SO, TFR).
    # If the legend were parsed as transactions the count would exceed 12.
    assert len(stmt.transactions) == 12


def test_full_metadata() -> None:
    """Full statement metadata matches the fixture values."""
    stmt = _parse(FULL)
    assert stmt.sort_code == "77-88-99"
    assert stmt.account_number == "87654321"
    assert stmt.money_in_total == Decimal("3200.00")
    assert stmt.money_out_total == Decimal("1800.00")


def test_full_balance_equation() -> None:
    """Balance equation holds for the full statement."""
    stmt = _parse(FULL)
    computed = stmt.opening_balance + stmt.money_in_total - stmt.money_out_total
    assert computed == stmt.closing_balance


# ---------------------------------------------------------------------------
# Tests for statement_cross_year.pdf (period spans Dec 25 - Jan 26)
# ---------------------------------------------------------------------------


def test_cross_year_transaction_count() -> None:
    """Cross-year statement returns exactly 3 transactions."""
    stmt = _parse(CROSS_YEAR)
    assert len(stmt.transactions) == 3


def test_cross_year_december_transactions_have_year_2025() -> None:
    """Transactions in December are assigned year 2025."""
    stmt = _parse(CROSS_YEAR)
    txs = stmt.transactions
    assert txs[0].date.year == 2025
    assert txs[0].date.month == 12
    assert txs[1].date.year == 2025
    assert txs[1].date.month == 12


def test_cross_year_january_transaction_has_year_2026() -> None:
    """Transaction in January is assigned year 2026."""
    stmt = _parse(CROSS_YEAR)
    txs = stmt.transactions
    assert txs[2].date.year == 2026
    assert txs[2].date.month == 1


def test_cross_year_dates_full() -> None:
    """All three cross-year transaction dates are exactly correct."""
    stmt = _parse(CROSS_YEAR)
    txs = stmt.transactions
    assert txs[0].date == date(2025, 12, 15)
    assert txs[1].date == date(2025, 12, 20)
    assert txs[2].date == date(2026, 1, 5)


# ---------------------------------------------------------------------------
# Error-case tests
# ---------------------------------------------------------------------------


def test_non_pdf_file_raises_parse_error() -> None:
    """Passing a non-PDF file (pyproject.toml) raises ParseError."""
    non_pdf = Path(__file__).parent.parent / "pyproject.toml"
    assert non_pdf.exists(), "pyproject.toml must exist for this test"
    with pytest.raises(ParseError):
        parse_statement(non_pdf)


def test_nonexistent_file_raises_parse_error() -> None:
    """Passing a path that does not exist raises ParseError."""
    with pytest.raises(ParseError):
        parse_statement(Path("nonexistent_file_that_does_not_exist.pdf"))


def test_empty_with_totals_raises_parse_error() -> None:
    """PDF with no transaction table but non-zero Money In total raises ParseError (R8.2)."""
    with pytest.raises(ParseError):
        parse_statement(EMPTY_WITH_TOTALS)


def test_bad_balance_raises_parse_error() -> None:
    """PDF whose balance equation fails raises ParseError (R6.3)."""
    with pytest.raises(ParseError):
        parse_statement(BAD_BALANCE)
