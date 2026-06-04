"""Tests for reconciler.py — arithmetic verification of classified totals."""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest

from lloyds_expense.classifier import ClassificationResult, ClassifiedTransaction
from lloyds_expense.parser import Statement, Transaction
from lloyds_expense.reconciler import ReconciliationReport, reconcile
from lloyds_expense.schema import Category

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_statement(
    money_in: str = "0.00",
    money_out: str = "0.00",
    opening: str = "1000.00",
    closing: str | None = None,
) -> Statement:
    """Construct a minimal Statement for use in reconciler tests.

    The closing balance defaults to ``opening + money_in - money_out`` so the
    balance equation holds by default.  Pass an explicit *closing* to break it.
    """
    mi = Decimal(money_in)
    mo = Decimal(money_out)
    op = Decimal(opening)
    cl = Decimal(closing) if closing else op + mi - mo
    return Statement(
        sort_code="12-34-56",
        account_number="12345678",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        opening_balance=op,
        closing_balance=cl,
        money_in_total=mi,
        money_out_total=mo,
        transactions=(),
    )


def make_ct(category: Category, amount: str, direction: str = "out") -> ClassifiedTransaction:
    """Construct a ClassifiedTransaction with a minimal Transaction."""
    tx = Transaction(
        date=date(2026, 4, 1),
        description="TEST",
        type_code="DEB",
        amount=Decimal(amount),
        direction=direction,  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )
    return ClassifiedTransaction(transaction=tx, category=category)


def make_result(cts: list[ClassifiedTransaction]) -> ClassificationResult:
    """Construct a ClassificationResult from a list of ClassifiedTransactions."""
    return ClassificationResult(matched=tuple(cts), unmatched=())


# ---------------------------------------------------------------------------
# Case 1: ok=True when actual totals match statement totals exactly
# ---------------------------------------------------------------------------


def test_reconcile_ok_when_totals_match_exactly() -> None:
    """reconcile returns ok=True when actual_in == money_in_total AND actual_out == money_out_total.

    This is the happy-path check: all classified totals agree with the statement.
    """
    statement = make_statement(money_in="500.00", money_out="200.00")
    cts = [
        make_ct(Category.SALARY, "500.00", direction="in"),
        make_ct(Category.RENT, "200.00", direction="out"),
    ]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.ok is True


# ---------------------------------------------------------------------------
# Case 2: ok=False with correct money_in_diff when in-total differs by 0.01
# ---------------------------------------------------------------------------


def test_reconcile_fails_when_in_total_off_by_one_penny() -> None:
    """reconcile returns ok=False and correct money_in_diff when actual_in differs by 0.01."""
    statement = make_statement(money_in="500.00", money_out="0.00")
    # actual_in will be 500.01 — one penny more than the statement total
    cts = [make_ct(Category.SALARY, "500.01", direction="in")]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.ok is False
    assert report.money_in_diff == Decimal("0.01")


# ---------------------------------------------------------------------------
# Case 3: ok=False with correct money_out_diff when out-total differs by 0.01
# ---------------------------------------------------------------------------


def test_reconcile_fails_when_out_total_off_by_one_penny() -> None:
    """reconcile returns ok=False and correct money_out_diff when actual_out differs by 0.01."""
    statement = make_statement(money_in="0.00", money_out="200.00")
    # actual_out will be 200.01 — one penny more than the statement total
    cts = [make_ct(Category.RENT, "200.01", direction="out")]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.ok is False
    assert report.money_out_diff == Decimal("0.01")


# ---------------------------------------------------------------------------
# Case 4: reconcile NEVER raises — bad balance equation is the parser's problem
# ---------------------------------------------------------------------------


def test_reconcile_never_raises_on_broken_balance_equation() -> None:
    """reconcile returns a ReconciliationReport even when opening+in-out≠closing."""
    # Deliberately break the balance equation: closing should be 1300.00 but is set to 9999.99
    statement = make_statement(money_in="500.00", money_out="200.00", closing="9999.99")
    cts = [
        make_ct(Category.SALARY, "500.00", direction="in"),
        make_ct(Category.RENT, "200.00", direction="out"),
    ]
    result = make_result(cts)
    # Must not raise — the parser is responsible for catching balance failures
    report = reconcile(result, statement)
    assert isinstance(report, ReconciliationReport)


# ---------------------------------------------------------------------------
# Case 5: All arithmetic uses Decimal — no float types in the report
# ---------------------------------------------------------------------------


def test_reconcile_report_fields_are_decimal() -> None:
    """All monetary fields in ReconciliationReport are Decimal instances."""
    statement = make_statement(money_in="100.00", money_out="50.00")
    cts = [
        make_ct(Category.SALARY, "100.00", direction="in"),
        make_ct(Category.FOOD_SUPPLIES, "50.00", direction="out"),
    ]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert isinstance(report.money_in_expected, Decimal)
    assert isinstance(report.money_in_actual, Decimal)
    assert isinstance(report.money_out_expected, Decimal)
    assert isinstance(report.money_out_actual, Decimal)
    assert isinstance(report.money_in_diff, Decimal)
    assert isinstance(report.money_out_diff, Decimal)


# ---------------------------------------------------------------------------
# Case 6: money_in_diff sign — positive when actual > expected
# ---------------------------------------------------------------------------


def test_money_in_diff_positive_when_actual_exceeds_expected() -> None:
    """money_in_diff = actual - expected, so if actual > expected, diff is positive."""
    statement = make_statement(money_in="100.00", money_out="0.00")
    # actual_in = 110.00, expected = 100.00  →  diff = +10.00
    cts = [make_ct(Category.SALARY, "110.00", direction="in")]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_in_diff == Decimal("10.00")
    assert report.money_in_diff > Decimal("0")


def test_money_in_diff_negative_when_actual_below_expected() -> None:
    """money_in_diff is negative when actual < expected."""
    statement = make_statement(money_in="100.00", money_out="0.00")
    # actual_in = 90.00, expected = 100.00  →  diff = -10.00
    cts = [make_ct(Category.SALARY, "90.00", direction="in")]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_in_diff == Decimal("-10.00")
    assert report.money_in_diff < Decimal("0")


# ---------------------------------------------------------------------------
# Case 7: money_out_diff sign — positive when actual > expected
# ---------------------------------------------------------------------------


def test_money_out_diff_positive_when_actual_exceeds_expected() -> None:
    """money_out_diff = actual - expected, so if actual > expected, diff is positive."""
    statement = make_statement(money_in="0.00", money_out="50.00")
    # actual_out = 60.00, expected = 50.00  →  diff = +10.00
    cts = [make_ct(Category.RENT, "60.00", direction="out")]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_out_diff == Decimal("10.00")
    assert report.money_out_diff > Decimal("0")


def test_money_out_diff_negative_when_actual_below_expected() -> None:
    """money_out_diff is negative when actual < expected."""
    statement = make_statement(money_in="0.00", money_out="50.00")
    # actual_out = 40.00, expected = 50.00  →  diff = -10.00
    cts = [make_ct(Category.RENT, "40.00", direction="out")]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_out_diff == Decimal("-10.00")


# ---------------------------------------------------------------------------
# Case 8: ReconciliationReport is frozen (immutable after construction)
# ---------------------------------------------------------------------------


def test_reconciliation_report_is_frozen() -> None:
    """ReconciliationReport raises FrozenInstanceError on field assignment."""
    statement = make_statement(money_in="0.00", money_out="0.00")
    result = make_result([])
    report = reconcile(result, statement)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        report.ok = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Case 9: Inflow categories contribute to actual_in
# ---------------------------------------------------------------------------


def test_inflow_categories_contribute_to_actual_in() -> None:
    """Categories in inflow sections (SALARY, SAVINGS, etc.) sum into actual_in."""
    statement = make_statement(money_in="900.00", money_out="0.00")
    cts = [
        make_ct(Category.SALARY, "500.00", direction="in"),  # REGULAR_INFLOWS
        make_ct(Category.UNEXPECTED_REFUND, "200.00", direction="in"),  # IRREGULAR_INFLOWS
        make_ct(Category.SAVINGS, "200.00", direction="in"),  # ASSET_LIQUIDATION
    ]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_in_actual == Decimal("900.00")
    assert report.ok is True


def test_all_inflow_section_categories_are_counted_as_in() -> None:
    """Categories from all three inflow sections are counted in actual_in."""
    statement = make_statement(money_in="1500.00", money_out="0.00")
    cts = [
        # REGULAR_INFLOWS
        make_ct(Category.SALARY, "500.00", direction="in"),
        # IRREGULAR_INFLOWS
        make_ct(Category.UNEXPECTED_REFUND, "300.00", direction="in"),
        make_ct(Category.LOAN, "200.00", direction="in"),
        # ASSET_LIQUIDATION
        make_ct(Category.SAVINGS, "300.00", direction="in"),
        make_ct(Category.STOCKS_AND_SHARES, "200.00", direction="in"),
    ]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_in_actual == Decimal("1500.00")
    assert report.ok is True


# ---------------------------------------------------------------------------
# Case 10: Outflow categories contribute to actual_out
# ---------------------------------------------------------------------------


def test_outflow_categories_contribute_to_actual_out() -> None:
    """Categories in outflow sections (RENT, FOOD_SUPPLIES, etc.) sum into actual_out."""
    statement = make_statement(money_in="0.00", money_out="350.00")
    cts = [
        make_ct(Category.RENT, "200.00", direction="out"),  # REGULAR_OUTFLOWS
        make_ct(Category.CHARITY_DONATIONS, "50.00", direction="out"),  # IRREGULAR_OUTFLOWS
        make_ct(Category.ACTIVE_SAVINGS, "100.00", direction="out"),  # ASSETS
    ]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_out_actual == Decimal("350.00")
    assert report.ok is True


def test_all_outflow_section_categories_are_counted_as_out() -> None:
    """Categories from all three outflow sections are counted in actual_out."""
    statement = make_statement(money_in="0.00", money_out="700.00")
    cts = [
        # REGULAR_OUTFLOWS
        make_ct(Category.RENT, "200.00", direction="out"),
        make_ct(Category.FOOD_SUPPLIES, "100.00", direction="out"),
        # IRREGULAR_OUTFLOWS
        make_ct(Category.GIFTS_ENTERTAINMENT_MISC, "150.00", direction="out"),
        make_ct(Category.EATING_OUT, "50.00", direction="out"),
        # ASSETS
        make_ct(Category.ACTIVE_SAVINGS, "100.00", direction="out"),
        make_ct(Category.STOCKS_SHARES_ISA, "100.00", direction="out"),
    ]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.money_out_actual == Decimal("700.00")
    assert report.ok is True


# ---------------------------------------------------------------------------
# Case 11: Empty ClassificationResult → actual_in = actual_out = 0.00
# ---------------------------------------------------------------------------


def test_empty_result_yields_zero_actuals() -> None:
    """No matched transactions means both actual_in and actual_out are Decimal('0.00')."""
    statement = make_statement(money_in="0.00", money_out="0.00")
    result = make_result([])
    report = reconcile(result, statement)
    assert report.money_in_actual == Decimal("0.00")
    assert report.money_out_actual == Decimal("0.00")
    assert report.ok is True


# ---------------------------------------------------------------------------
# Case 12: Unmatched transactions are ignored by the reconciler
# ---------------------------------------------------------------------------


def test_reconcile_ignores_unmatched_transactions() -> None:
    """reconcile uses only matched transactions; unmatched entries do not affect the report."""
    statement = make_statement(money_in="500.00", money_out="200.00")

    # Matched transactions that sum to the statement totals
    matched_cts = [
        make_ct(Category.SALARY, "500.00", direction="in"),
        make_ct(Category.RENT, "200.00", direction="out"),
    ]

    # Build an unmatched transaction directly (not classified)
    unmatched_tx = Transaction(
        date=date(2026, 4, 15),
        description="UNKNOWN MERCHANT",
        type_code="DEB",
        amount=Decimal("999.99"),
        direction="out",
        running_balance=Decimal("1.00"),
    )

    result = ClassificationResult(
        matched=tuple(matched_cts),
        unmatched=(unmatched_tx,),
    )
    report = reconcile(result, statement)
    # Unmatched amount must NOT be included in actual_out
    assert report.money_out_actual == Decimal("200.00")
    assert report.ok is True


# ---------------------------------------------------------------------------
# Additional edge-case: report expected fields mirror statement totals
# ---------------------------------------------------------------------------


def test_reconcile_expected_fields_match_statement_totals() -> None:
    """money_in_expected and money_out_expected are taken from the statement."""
    statement = make_statement(money_in="123.45", money_out="67.89")
    result = make_result([])
    report = reconcile(result, statement)
    assert report.money_in_expected == Decimal("123.45")
    assert report.money_out_expected == Decimal("67.89")


def test_reconcile_both_totals_must_match_for_ok_true() -> None:
    """ok is True only when BOTH in and out totals match; one mismatch → ok=False."""
    # In matches but out does not
    statement = make_statement(money_in="500.00", money_out="200.00")
    cts = [
        make_ct(Category.SALARY, "500.00", direction="in"),
        make_ct(Category.RENT, "199.99", direction="out"),  # 0.01 short
    ]
    result = make_result(cts)
    report = reconcile(result, statement)
    assert report.ok is False
