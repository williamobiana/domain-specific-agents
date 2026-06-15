"""Tests for monzo_expense/splitter.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from monzo_expense.classifier import ClassificationResult, ClassifiedTransaction
from monzo_expense.parser import Transaction
from monzo_expense.schema import Category
from monzo_expense.splitter import YearMonth, split_by_month


def _tx(tx_date: date, description: str = "TX") -> Transaction:
    return Transaction(
        date=tx_date,
        description=description,
        amount=Decimal("10.00"),
        direction="out",
        running_balance=Decimal("100.00"),
    )


def _ct(tx_date: date, description: str = "TX") -> ClassifiedTransaction:
    return ClassifiedTransaction(
        transaction=_tx(tx_date, description),
        category=Category.FOOD_SUPPLIES,
    )


def _result(*cts: ClassifiedTransaction) -> ClassificationResult:
    return ClassificationResult(matched=cts, unmatched=())


def test_single_month_produces_one_key() -> None:
    cts = [_ct(date(2026, 4, i)) for i in range(1, 4)]
    by_month = split_by_month(_result(*cts))
    assert len(by_month) == 1
    assert YearMonth(2026, 4) in by_month


def test_single_month_document_order_preserved() -> None:
    cts = [_ct(date(2026, 4, i), f"TX{i}") for i in range(1, 4)]
    by_month = split_by_month(_result(*cts))
    bucket = by_month[YearMonth(2026, 4)]
    assert [ct.transaction.description for ct in bucket.matched] == ["TX1", "TX2", "TX3"]


def test_two_months_produces_two_keys_ascending() -> None:
    cts = [_ct(date(2026, 4, 1)), _ct(date(2026, 5, 1))]
    by_month = split_by_month(_result(*cts))
    keys = list(by_month.keys())
    assert keys == [YearMonth(2026, 4), YearMonth(2026, 5)]


def test_each_bucket_contains_only_its_month() -> None:
    apr_ct = _ct(date(2026, 4, 30))
    may_ct = _ct(date(2026, 5, 1))
    by_month = split_by_month(_result(apr_ct, may_ct))

    apr_bucket = by_month[YearMonth(2026, 4)]
    may_bucket = by_month[YearMonth(2026, 5)]

    assert all(ct.transaction.date.month == 4 for ct in apr_bucket.matched)
    assert all(ct.transaction.date.month == 5 for ct in may_bucket.matched)


def test_total_transaction_count_preserved() -> None:
    cts = [_ct(date(2026, 4, i)) for i in range(1, 5)] + [
        _ct(date(2026, 5, i)) for i in range(1, 5)
    ]
    by_month = split_by_month(_result(*cts))
    total = sum(len(v.matched) for v in by_month.values())
    assert total == len(cts)


def test_last_day_of_month_and_first_day_next_in_separate_buckets() -> None:
    end_apr = _ct(date(2026, 4, 30))
    start_may = _ct(date(2026, 5, 1))
    by_month = split_by_month(_result(end_apr, start_may))
    assert YearMonth(2026, 4) in by_month
    assert YearMonth(2026, 5) in by_month
    assert len(by_month[YearMonth(2026, 4)].matched) == 1
    assert len(by_month[YearMonth(2026, 5)].matched) == 1


def test_empty_result_returns_empty_dict() -> None:
    by_month = split_by_month(ClassificationResult(matched=(), unmatched=()))
    assert by_month == {}


def test_output_unmatched_is_empty_tuple() -> None:
    cts = [_ct(date(2026, 4, 1))]
    by_month = split_by_month(_result(*cts))
    for v in by_month.values():
        assert v.unmatched == ()


def test_year_month_is_named_tuple() -> None:
    ym = YearMonth(2026, 4)
    assert ym.year == 2026
    assert ym.month == 4
    assert ym[0] == 2026
    assert ym[1] == 4
