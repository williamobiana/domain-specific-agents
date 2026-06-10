"""Tests for monzo_expense/classifier.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from monzo_expense.classifier import (
    ClassificationResult,
    ClassifiedTransaction,
    _normalise,
    classify,
)
from monzo_expense.parser import Transaction
from monzo_expense.rules import ExactMatch, RegexMatch, Rule
from monzo_expense.schema import Category


def _tx(
    description: str,
    direction: str = "out",
    amount: str = "10.00",
    tx_date: date = date(2026, 4, 1),
) -> Transaction:
    return Transaction(
        date=tx_date,
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


def test_exact_match_assigns_category() -> None:
    tx = _tx("TESCO STORES", direction="out")
    rules = [_exact("TESCO STORES", Category.FOOD_SUPPLIES)]
    result = classify((tx,), rules)
    assert len(result.matched) == 1
    assert result.matched[0].category == Category.FOOD_SUPPLIES


def test_no_match_goes_to_unmatched() -> None:
    tx = _tx("UNKNOWN MERCHANT")
    rules = [_exact("TESCO", Category.FOOD_SUPPLIES)]
    result = classify((tx,), rules)
    assert len(result.unmatched) == 1
    assert len(result.matched) == 0


def test_exact_takes_priority_over_regex_regardless_of_yaml_order() -> None:
    """Exact match must always beat a regex match for the same description."""
    tx = _tx("TESCO STORES")
    rules = [
        _regex("TESCO", Category.SUNDRY),  # listed first
        _exact("TESCO STORES", Category.FOOD_SUPPLIES),  # listed second
    ]
    result = classify((tx,), rules)
    assert result.matched[0].category == Category.FOOD_SUPPLIES


def test_direction_filter_rejects_mismatched_direction() -> None:
    in_tx = _tx("SALARY", direction="in")
    rule = _exact("SALARY", Category.SALARY, direction="out")
    result = classify((in_tx,), [rule])
    assert len(result.unmatched) == 1


def test_direction_filter_accepts_matching_direction() -> None:
    in_tx = _tx("SALARY", direction="in")
    rule = _exact("SALARY", Category.SALARY, direction="in")
    result = classify((in_tx,), [rule])
    assert len(result.matched) == 1


def test_no_direction_filter_matches_either_direction() -> None:
    in_tx = _tx("FOOD", direction="in")
    out_tx = _tx("FOOD", direction="out")
    rule = _exact("FOOD", Category.FOOD_SUPPLIES)
    result = classify((in_tx, out_tx), [rule])
    assert len(result.matched) == 2


def test_first_regex_in_file_order_wins() -> None:
    tx = _tx("SOME VENDOR")
    rules = [
        _regex("SOME", Category.SUNDRY),
        _regex("VENDOR", Category.GIFTS_ENTERTAINMENT_MISC),
    ]
    result = classify((tx,), rules)
    assert result.matched[0].category == Category.SUNDRY


def test_document_order_preserved_in_matched() -> None:
    txs = tuple(_tx(f"TX{i}", tx_date=date(2026, 4, i + 1)) for i in range(3))
    rules = [_exact(f"TX{i}", Category.FOOD_SUPPLIES) for i in range(3)]
    result = classify(txs, rules)
    assert [ct.transaction for ct in result.matched] == list(txs)


def test_hyphen_normalisation_in_matching() -> None:
    """Unicode en-dash in description should match a rule with ASCII hyphen-minus."""
    tx = _tx("O Okwu–Boms")  # en-dash
    rule = _exact("O Okwu-Boms", Category.MAIN_ACCOUNT_INFLOW, direction="out")
    result = classify((tx,), [rule])
    assert len(result.matched) == 1


def test_normalise_strips_whitespace() -> None:
    assert _normalise("  hello  ") == "hello"


def test_normalise_collapses_internal_whitespace() -> None:
    assert _normalise("hello   world") == "hello world"


def test_normalise_replaces_unicode_dashes() -> None:
    for dash in ["‐", "‑", "‒", "–", "—"]:
        assert _normalise(f"A{dash}B") == "A-B"


def test_classifier_does_not_check_type_code() -> None:
    """Transaction has no type_code; the classifier must not access one."""
    tx = _tx("FOOD")
    assert not hasattr(tx, "type_code")
    rule = _exact("FOOD", Category.FOOD_SUPPLIES)
    result = classify((tx,), [rule])
    assert len(result.matched) == 1


def test_classification_result_is_frozen() -> None:
    result = ClassificationResult(matched=(), unmatched=())
    with pytest.raises(AttributeError):
        result.matched = ()  # type: ignore[misc]


def test_empty_transactions_returns_empty_result() -> None:
    result = classify((), [])
    assert result.matched == ()
    assert result.unmatched == ()
