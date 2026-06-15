"""Tests for monzo_expense/reconciler.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from monzo_expense.classifier import ClassificationResult, ClassifiedTransaction
from monzo_expense.parser import Statement, Transaction
from monzo_expense.reconciler import ReconciliationReport, reconcile
from monzo_expense.schema import Category


def _tx(amount: str, direction: str = "out") -> Transaction:
    return Transaction(
        date=date(2026, 4, 1),
        description="TX",
        amount=Decimal(amount),
        direction=direction,  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )


def _ct(amount: str, direction: str, category: Category) -> ClassifiedTransaction:
    return ClassifiedTransaction(transaction=_tx(amount, direction), category=category)


def _stmt(deposits: str, outgoings: str) -> Statement:
    return Statement(
        sort_code="04-00-04",
        account_number="12345678",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1000.00") + Decimal(deposits) - Decimal(outgoings),
        total_deposits=Decimal(deposits),
        total_outgoings=Decimal(outgoings),
        transactions=(),
    )


def _result(*cts: ClassifiedTransaction) -> ClassificationResult:
    return ClassificationResult(matched=cts, unmatched=())


def test_ok_true_when_totals_match() -> None:
    stmt = _stmt("100.00", "50.00")
    result = _result(
        _ct("100.00", "in", Category.SALARY),
        _ct("50.00", "out", Category.FOOD_SUPPLIES),
    )
    report = reconcile(result, stmt)
    assert report.ok is True


def test_ok_false_when_deposit_off_by_one_cent() -> None:
    stmt = _stmt("100.01", "50.00")
    result = _result(
        _ct("100.00", "in", Category.SALARY),
        _ct("50.00", "out", Category.FOOD_SUPPLIES),
    )
    report = reconcile(result, stmt)
    assert report.ok is False
    assert report.deposits_diff == Decimal("-0.01")


def test_ok_false_when_outgoings_off() -> None:
    stmt = _stmt("100.00", "50.01")
    result = _result(
        _ct("100.00", "in", Category.SALARY),
        _ct("50.00", "out", Category.FOOD_SUPPLIES),
    )
    report = reconcile(result, stmt)
    assert report.ok is False
    assert report.outgoings_diff == Decimal("-0.01")


def test_reconcile_never_raises() -> None:
    """Reconciler must return a report even when the statement balance equation is wrong."""
    stmt = Statement(
        sort_code="04-00-04",
        account_number="12345678",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("9999.00"),  # intentionally wrong
        total_deposits=Decimal("100.00"),
        total_outgoings=Decimal("50.00"),
        transactions=(),
    )
    result = _result(_ct("100.00", "in", Category.SALARY))
    # Must not raise, even though the balance equation is wrong
    report = reconcile(result, stmt)
    assert isinstance(report, ReconciliationReport)


def test_all_arithmetic_uses_decimal() -> None:
    stmt = _stmt("100.00", "50.00")
    result = _result(
        _ct("100.00", "in", Category.SALARY),
        _ct("50.00", "out", Category.FOOD_SUPPLIES),
    )
    report = reconcile(result, stmt)
    assert isinstance(report.deposits_expected, Decimal)
    assert isinstance(report.deposits_actual, Decimal)
    assert isinstance(report.outgoings_expected, Decimal)
    assert isinstance(report.outgoings_actual, Decimal)
    assert not isinstance(report.deposits_actual, float)


def test_main_account_inflow_counts_as_deposit() -> None:
    """MAIN_ACCOUNT_INFLOW is in IRREGULAR_INFLOWS (inflow section)."""
    stmt = _stmt("500.00", "0.00")
    result = _result(_ct("500.00", "in", Category.MAIN_ACCOUNT_INFLOW))
    report = reconcile(result, stmt)
    assert report.ok is True
    assert report.deposits_actual == Decimal("500.00")


def test_reconciliation_report_is_frozen() -> None:
    stmt = _stmt("0.00", "0.00")
    report = reconcile(_result(), stmt)
    with pytest.raises(AttributeError):
        report.ok = False  # type: ignore[misc]


def test_deposits_diff_and_outgoings_diff_properties() -> None:
    stmt = _stmt("100.00", "50.00")
    result = _result(_ct("90.00", "in", Category.SALARY))
    report = reconcile(result, stmt)
    assert report.deposits_diff == Decimal("90.00") - Decimal("100.00")
    assert report.outgoings_diff == Decimal("0.00") - Decimal("50.00")


def test_period_level_not_per_month() -> None:
    """Reconciliation operates on the full result, not per-month subsets."""
    # Two inflow transactions from different months combined
    stmt = _stmt("200.00", "0.00")
    result = _result(
        _ct("100.00", "in", Category.SALARY),
        _ct("100.00", "in", Category.MAIN_ACCOUNT_INFLOW),
    )
    report = reconcile(result, stmt)
    assert report.ok is True
