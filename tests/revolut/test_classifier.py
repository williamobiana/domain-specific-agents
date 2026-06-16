"""Tests for revolut_expense/classifier.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from revolut_expense.classifier import ClassificationResult, classify
from revolut_expense.parser import Transaction
from revolut_expense.rules import ExactMatch, RegexMatch, Rule
from revolut_expense.schema import Category


def _tx(
    description: str,
    direction: str = "out",
    amount: str = "10.00",
    tx_date: date | None = None,
) -> Transaction:
    return Transaction(
        date=tx_date or date(2026, 4, 1),
        description=description,
        amount=Decimal(amount),
        direction=direction,  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )


def _exact(value: str, category: Category, direction: str | None = None) -> Rule:
    return Rule(
        matcher=ExactMatch(value=value),
        direction=direction,  # type: ignore[arg-type]
        category=category,
        line_number=1,
    )


def _regex(pattern: str, category: Category, direction: str | None = None) -> Rule:
    import re

    return Rule(
        matcher=RegexMatch(pattern=re.compile(pattern), source=pattern),
        direction=direction,  # type: ignore[arg-type]
        category=category,
        line_number=1,
    )


def test_exact_match_takes_priority_over_regex() -> None:
    tx = _tx("Payment from NATWEST")
    rules = [
        _regex("^Payment from NATWEST", Category.UNEXPECTED_REFUND),
        _exact("Payment from NATWEST", Category.SALARY),
    ]
    result = classify((tx,), rules)
    assert len(result.matched) == 1
    assert result.matched[0].category == Category.SALARY


def test_direction_filter_rejects_mismatch() -> None:
    tx = _tx("Lebara Mobile", direction="in")
    rules = [_regex("^Lebara", Category.BILL_PHONE_INTERNET, direction="out")]
    result = classify((tx,), rules)
    assert len(result.unmatched) == 1


def test_direction_filter_accepts_match() -> None:
    tx = _tx("Lebara Mobile", direction="out")
    rules = [_regex("^Lebara", Category.BILL_PHONE_INTERNET, direction="out")]
    result = classify((tx,), rules)
    assert len(result.matched) == 1


def test_first_regex_in_file_order_wins() -> None:
    tx = _tx("Morrisons To: 8 Glasgow Road")
    rules = [
        _regex("^Morrisons", Category.FOOD_SUPPLIES),
        _regex("^Morrisons To", Category.GIFTS_ENTERTAINMENT_MISC),
    ]
    result = classify((tx,), rules)
    assert result.matched[0].category == Category.FOOD_SUPPLIES


def test_unmatched_transaction_in_unmatched() -> None:
    tx = _tx("Unknown Merchant")
    result = classify((tx,), [])
    assert len(result.unmatched) == 1
    assert result.unmatched[0] is tx


def test_anchored_regex_matches_joined_description() -> None:
    tx = _tx("Morrisons To: 8 Glasgow Road, Dumfries")
    rules = [_regex("^Morrisons ", Category.FOOD_SUPPLIES)]
    result = classify((tx,), rules)
    assert len(result.matched) == 1
    assert result.matched[0].category == Category.FOOD_SUPPLIES


def test_document_order_preserved() -> None:
    txs = tuple(_tx(f"Merchant {i}") for i in range(3))
    rules = [_regex(f"^Merchant {i}", Category.FOOD_SUPPLIES) for i in range(3)]
    result = classify(txs, rules)
    assert [ct.transaction for ct in result.matched] == list(txs)


def test_no_type_code_attribute_on_transaction() -> None:
    tx = _tx("Payment from NATWEST")
    assert not hasattr(tx, "type_code")


def test_no_direction_filter_matches_both_directions() -> None:
    tx_in = _tx("Morrisons", direction="in")
    tx_out = _tx("Morrisons", direction="out")
    rules = [_exact("Morrisons", Category.FOOD_SUPPLIES)]
    result = classify((tx_in, tx_out), rules)
    assert len(result.matched) == 2


def test_unicode_hyphen_normalisation() -> None:
    tx = _tx("O Okwu–Boms")
    rules = [_exact("O Okwu-Boms", Category.MAIN_ACCOUNT_INFLOW)]
    result = classify((tx,), rules)
    assert len(result.matched) == 1


def test_whitespace_collapse_normalisation() -> None:
    tx = _tx("Lebara  Mobile  London")
    rules = [_exact("Lebara Mobile London", Category.BILL_PHONE_INTERNET)]
    result = classify((tx,), rules)
    assert len(result.matched) == 1


def test_classification_result_is_frozen() -> None:
    result = classify((), [])
    with pytest.raises(AttributeError):
        result.matched = ()  # type: ignore[misc]
