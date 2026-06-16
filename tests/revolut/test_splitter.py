"""Tests for revolut_expense/splitter.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from revolut_expense.classifier import ClassificationResult, ClassifiedTransaction
from revolut_expense.parser import Transaction
from revolut_expense.schema import Category
from revolut_expense.splitter import YearMonth, split_by_month


def _ct(tx_date: date, category: Category = Category.FOOD_SUPPLIES) -> ClassifiedTransaction:
    return ClassifiedTransaction(
        transaction=Transaction(
            date=tx_date,
            description="test",
            amount=Decimal("10.00"),
            direction="out",
            running_balance=Decimal("100.00"),
        ),
        category=category,
    )


def _result(*cts: ClassifiedTransaction) -> ClassificationResult:
    return ClassificationResult(matched=tuple(cts), unmatched=())


def test_single_month_produces_one_key() -> None:
    cts = [_ct(date(2026, 4, i)) for i in range(1, 5)]
    by_month = split_by_month(_result(*cts))
    assert len(by_month) == 1
    assert YearMonth(2026, 4) in by_month


def test_all_transactions_in_single_bucket() -> None:
    cts = [_ct(date(2026, 4, i)) for i in range(1, 5)]
    by_month = split_by_month(_result(*cts))
    bucket = by_month[YearMonth(2026, 4)]
    assert len(bucket.matched) == 4


def test_document_order_preserved_within_bucket() -> None:
    cts = [_ct(date(2026, 4, i)) for i in [10, 5, 20, 1]]
    by_month = split_by_month(_result(*cts))
    dates = [ct.transaction.date.day for ct in by_month[YearMonth(2026, 4)].matched]
    assert dates == [10, 5, 20, 1]


def test_two_months_produces_two_keys() -> None:
    cts = [_ct(date(2026, 4, 15)), _ct(date(2026, 5, 1))]
    by_month = split_by_month(_result(*cts))
    assert len(by_month) == 2
    assert YearMonth(2026, 4) in by_month
    assert YearMonth(2026, 5) in by_month


def test_ascending_chronological_order() -> None:
    cts = [_ct(date(2026, 5, 1)), _ct(date(2026, 4, 1))]
    by_month = split_by_month(_result(*cts))
    keys = list(by_month.keys())
    assert keys == [YearMonth(2026, 4), YearMonth(2026, 5)]


def test_each_bucket_contains_only_its_month() -> None:
    cts = [_ct(date(2026, 4, 15)), _ct(date(2026, 5, 1)), _ct(date(2026, 4, 30))]
    by_month = split_by_month(_result(*cts))
    for ct in by_month[YearMonth(2026, 4)].matched:
        assert ct.transaction.date.month == 4
    for ct in by_month[YearMonth(2026, 5)].matched:
        assert ct.transaction.date.month == 5


def test_total_count_preserved() -> None:
    cts = [_ct(date(2026, 4, 15)), _ct(date(2026, 5, 1)), _ct(date(2026, 4, 30))]
    by_month = split_by_month(_result(*cts))
    total = sum(len(v.matched) for v in by_month.values())
    assert total == 3


def test_last_day_of_month_and_first_day_of_next_are_separate() -> None:
    cts = [_ct(date(2026, 4, 30)), _ct(date(2026, 5, 1))]
    by_month = split_by_month(_result(*cts))
    assert len(by_month) == 2
    assert len(by_month[YearMonth(2026, 4)].matched) == 1
    assert len(by_month[YearMonth(2026, 5)].matched) == 1


def test_empty_result_returns_empty_dict() -> None:
    by_month = split_by_month(ClassificationResult(matched=(), unmatched=()))
    assert by_month == {}


def test_output_has_empty_unmatched() -> None:
    cts = [_ct(date(2026, 4, 1))]
    by_month = split_by_month(_result(*cts))
    for bucket in by_month.values():
        assert bucket.unmatched == ()
