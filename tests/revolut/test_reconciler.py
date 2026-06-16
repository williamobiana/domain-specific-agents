"""Tests for revolut_expense/reconciler.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from revolut_expense.classifier import ClassificationResult, ClassifiedTransaction
from revolut_expense.parser import Statement, Transaction
from revolut_expense.reconciler import ReconciliationReport, reconcile
from revolut_expense.schema import Category


def _tx(amount: str, direction: str = "out") -> Transaction:
    return Transaction(
        date=date(2026, 4, 1),
        description="test",
        amount=Decimal(amount),
        direction=direction,  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )


def _ct(tx: Transaction, category: Category) -> ClassifiedTransaction:
    return ClassifiedTransaction(transaction=tx, category=category)


def _stmt(money_in: str = "0.00", money_out: str = "0.00") -> Statement:
    return Statement(
        sort_code="04-00-04",
        account_number="12345678",
        iban="GB29REVO00997012345678",
        bic="REVOGB21",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1000.00") + Decimal(money_in) - Decimal(money_out),
        total_money_in=Decimal(money_in),
        total_money_out=Decimal(money_out),
        transactions=(),
    )


def test_ok_when_totals_match() -> None:
    salary_tx = _tx("1000.00", "in")
    food_tx = _tx("80.00", "out")
    result = ClassificationResult(
        matched=(
            _ct(salary_tx, Category.SALARY),
            _ct(food_tx, Category.FOOD_SUPPLIES),
        ),
        unmatched=(),
    )
    stmt = _stmt(money_in="1000.00", money_out="80.00")
    report = reconcile(result, stmt)
    assert report.ok is True


def test_fail_when_money_in_differs() -> None:
    salary_tx = _tx("999.99", "in")
    result = ClassificationResult(
        matched=(_ct(salary_tx, Category.SALARY),),
        unmatched=(),
    )
    stmt = _stmt(money_in="1000.00")
    report = reconcile(result, stmt)
    assert report.ok is False
    assert report.money_in_diff == Decimal("-0.01")


def test_fail_when_money_out_differs() -> None:
    food_tx = _tx("80.01", "out")
    result = ClassificationResult(
        matched=(_ct(food_tx, Category.FOOD_SUPPLIES),),
        unmatched=(),
    )
    stmt = _stmt(money_out="80.00")
    report = reconcile(result, stmt)
    assert report.ok is False
    assert report.money_out_diff == Decimal("0.01")


def test_reconciler_never_raises() -> None:
    stmt = Statement(
        sort_code="04-00-04",
        account_number="12345678",
        iban="",
        bic="",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("9999.00"),  # bad equation
        total_money_in=Decimal("500.00"),
        total_money_out=Decimal("200.00"),
        transactions=(),
    )
    result = ClassificationResult(matched=(), unmatched=())
    report = reconcile(result, stmt)
    assert isinstance(report, ReconciliationReport)


def test_report_uses_decimal_not_float() -> None:
    result = ClassificationResult(matched=(), unmatched=())
    stmt = _stmt()
    report = reconcile(result, stmt)
    assert isinstance(report.money_in_actual, Decimal)
    assert isinstance(report.money_out_actual, Decimal)
    assert isinstance(report.money_in_expected, Decimal)
    assert isinstance(report.money_out_expected, Decimal)


def test_main_account_inflow_contributes_to_money_in() -> None:
    tx = _tx("500.00", "in")
    result = ClassificationResult(
        matched=(_ct(tx, Category.MAIN_ACCOUNT_INFLOW),),
        unmatched=(),
    )
    stmt = _stmt(money_in="500.00")
    report = reconcile(result, stmt)
    assert report.ok is True
    assert report.money_in_actual == Decimal("500.00")


def test_money_in_diff_property() -> None:
    result = ClassificationResult(matched=(), unmatched=())
    stmt = _stmt(money_in="100.00")
    report = reconcile(result, stmt)
    assert report.money_in_diff == Decimal("-100.00")


def test_money_out_diff_property() -> None:
    result = ClassificationResult(matched=(), unmatched=())
    stmt = _stmt(money_out="50.00")
    report = reconcile(result, stmt)
    assert report.money_out_diff == Decimal("-50.00")


def test_asset_liquidation_categories_count_as_money_in() -> None:
    savings_tx = _tx("1000.00", "in")
    result = ClassificationResult(
        matched=(_ct(savings_tx, Category.SAVINGS),),
        unmatched=(),
    )
    stmt = _stmt(money_in="1000.00")
    report = reconcile(result, stmt)
    assert report.ok is True


def test_assets_categories_count_as_money_out() -> None:
    isa_tx = _tx("200.00", "out")
    result = ClassificationResult(
        matched=(_ct(isa_tx, Category.STOCKS_SHARES_ISA),),
        unmatched=(),
    )
    stmt = _stmt(money_out="200.00")
    report = reconcile(result, stmt)
    assert report.ok is True
