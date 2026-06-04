"""Unit tests for classifier.py — two-pass transaction classification engine.

Covers requirements R4.1-R4.7:
  R4.1  Description normalisation (whitespace, Unicode hyphens → ASCII hyphen).
  R4.2  Pass 1: normalised exact match attempted first.
  R4.3  Pass 2: regex match attempted only when Pass 1 fails, in file order.
  R4.4  type_code filter applied during both passes.
  R4.5  direction filter applied during both passes.
  R4.6  Matched transaction assigned to the rule's category.
  R4.7  Unmatched transactions collected in result.unmatched.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from lloyds_expense.classifier import (
    ClassificationResult,
    _normalise,
    classify,
)
from lloyds_expense.parser import Transaction
from lloyds_expense.rules import ExactMatch, RegexMatch, Rule
from lloyds_expense.schema import Category

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def tx(
    description: str,
    type_code: str = "DEB",
    direction: str = "out",
) -> Transaction:
    """Build a minimal Transaction with the given description, type, and direction."""
    return Transaction(
        date=date(2026, 4, 1),
        description=description,
        type_code=type_code,
        amount=Decimal("10.00"),
        direction=direction,  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )


def exact_rule(
    value: str,
    category: Category,
    type_code: str | None = None,
    direction: str | None = None,
) -> Rule:
    """Build a Rule with an ExactMatch matcher."""
    return Rule(
        matcher=ExactMatch(value=value),
        type_code=type_code,
        direction=direction,  # type: ignore[arg-type]
        category=category,
        line_number=1,
    )


def regex_rule(
    pattern: str,
    category: Category,
    type_code: str | None = None,
    direction: str | None = None,
) -> Rule:
    """Build a Rule with a RegexMatch matcher."""
    return Rule(
        matcher=RegexMatch(pattern=re.compile(pattern), source=pattern),
        type_code=type_code,
        direction=direction,  # type: ignore[arg-type]
        category=category,
        line_number=1,
    )


# ---------------------------------------------------------------------------
# Tests for _normalise()
# ---------------------------------------------------------------------------


def test_normalise_strips_leading_trailing_whitespace() -> None:
    """R4.1: _normalise strips leading and trailing whitespace."""
    assert _normalise("  ACME CORP  ") == "ACME CORP"


def test_normalise_collapses_internal_whitespace() -> None:
    """R4.1: _normalise collapses multiple internal spaces to a single space."""
    assert _normalise("ACME   CORP") == "ACME CORP"


def test_normalise_collapses_tab_and_spaces() -> None:
    """R4.1: _normalise collapses mixed whitespace runs (tabs + spaces) to a single space."""
    assert _normalise("ACME\t CORP") == "ACME CORP"


def test_normalise_replaces_en_dash_with_ascii_hyphen() -> None:
    """R4.1: _normalise replaces en-dash U+2013 with ASCII hyphen-minus U+002D."""
    # U+2013 is the en-dash; after normalisation it should become ASCII hyphen (-)
    assert _normalise("OMASIRICHI OKWU\u2013BO") == "OMASIRICHI OKWU-BO"


def test_normalise_preserves_ascii_hyphen() -> None:
    """R4.1: _normalise leaves an existing ASCII hyphen unchanged."""
    assert _normalise("OMASIRICHI OKWU-BO") == "OMASIRICHI OKWU-BO"


# ---------------------------------------------------------------------------
# Tests for classify() — exact match priority
# ---------------------------------------------------------------------------


def test_exact_match_takes_priority_over_regex_regardless_of_yaml_order() -> None:
    """R4.2: Exact match wins even when a regex rule appears before the exact rule in file order.

    The classifier separates rules into exact_rules and regex_rules lists and
    always tries all exact rules first (Pass 1), regardless of their position
    relative to regex rules in the original rules list.
    """
    # A regex rule appears first in the list (simulating YAML order),
    # followed by an exact rule for the same description.
    regex_first = regex_rule("GROCERY", Category.FOOD_SUPPLIES)
    exact_second = exact_rule("GROCERY STORE", Category.SALARY)

    transaction = tx("GROCERY STORE")
    result = classify((transaction,), [regex_first, exact_second])

    assert len(result.matched) == 1
    assert result.matched[0].category == Category.SALARY  # exact rule wins
    assert result.unmatched == ()


# ---------------------------------------------------------------------------
# Tests for classify() — type_code filter
# ---------------------------------------------------------------------------


def test_type_filter_rejects_mismatched_type_code() -> None:
    """R4.4: A rule with type_code='DD' does not match a transaction with type_code='BGC'."""
    rule = exact_rule("RENT PAYMENT", Category.RENT, type_code="DD")
    transaction = tx("RENT PAYMENT", type_code="BGC")

    result = classify((transaction,), [rule])

    assert result.matched == ()
    assert len(result.unmatched) == 1
    assert result.unmatched[0] == transaction


def test_type_filter_matches_correct_type_code() -> None:
    """R4.4: A rule with a type_code filter matches a transaction with the same type code."""
    rule = exact_rule("RENT PAYMENT", Category.RENT, type_code="DD")
    transaction = tx("RENT PAYMENT", type_code="DD")

    result = classify((transaction,), [rule])

    assert len(result.matched) == 1
    assert result.matched[0].category == Category.RENT


# ---------------------------------------------------------------------------
# Tests for classify() — direction filter
# ---------------------------------------------------------------------------


def test_direction_filter_rejects_mismatched_direction() -> None:
    """R4.5: A rule with direction='out' does not match a money-in transaction."""
    rule = exact_rule("SALARY PAYMENT", Category.SALARY, direction="out")
    transaction = tx("SALARY PAYMENT", direction="in")

    result = classify((transaction,), [rule])

    assert result.matched == ()
    assert len(result.unmatched) == 1
    assert result.unmatched[0] == transaction


def test_direction_filter_matches_correct_direction() -> None:
    """R4.5: A rule with direction='in' matches a money-in transaction."""
    rule = exact_rule("SALARY PAYMENT", Category.SALARY, direction="in")
    transaction = tx("SALARY PAYMENT", direction="in")

    result = classify((transaction,), [rule])

    assert len(result.matched) == 1
    assert result.matched[0].category == Category.SALARY


# ---------------------------------------------------------------------------
# Tests for classify() — regex pass ordering
# ---------------------------------------------------------------------------


def test_first_regex_in_file_order_wins_when_multiple_match() -> None:
    """R4.3: When multiple regex rules match the same description, the first in file order wins."""
    # Both patterns match "AMAZON PRIME"; the first rule in the list should win.
    rule_food = regex_rule("AMAZON", Category.FOOD_SUPPLIES)
    rule_entertainment = regex_rule("AMAZON PRIME", Category.GIFTS_ENTERTAINMENT_MISC)

    transaction = tx("AMAZON PRIME")
    result = classify((transaction,), [rule_food, rule_entertainment])

    assert len(result.matched) == 1
    assert result.matched[0].category == Category.FOOD_SUPPLIES  # first rule wins


# ---------------------------------------------------------------------------
# Tests for classify() — unmatched transactions
# ---------------------------------------------------------------------------


def test_unmatched_transaction_appears_in_result_unmatched() -> None:
    """R4.7: A transaction with no matching rule is added to result.unmatched."""
    rule = exact_rule("RENT PAYMENT", Category.RENT)
    transaction = tx("UNKNOWN MERCHANT")

    result = classify((transaction,), [rule])

    assert result.matched == ()
    assert len(result.unmatched) == 1
    assert result.unmatched[0] == transaction


def test_all_transactions_matched_produces_empty_unmatched() -> None:
    """R4.6/R4.7: When every transaction matches a rule, result.unmatched is an empty tuple."""
    rule_a = exact_rule("COFFEE SHOP", Category.EATING_OUT)
    rule_b = exact_rule("TESCO", Category.FOOD_SUPPLIES)

    transactions = (tx("COFFEE SHOP"), tx("TESCO"))
    result = classify(transactions, [rule_a, rule_b])

    assert len(result.matched) == 2
    assert result.unmatched == ()


# ---------------------------------------------------------------------------
# Tests for classify() — hyphen normalisation
# ---------------------------------------------------------------------------


def test_en_dash_in_description_matches_rule_with_ascii_hyphen() -> None:
    """R4.1: En-dash in tx description normalises to ASCII hyphen, matching a rule with '-'.

    Transaction description "OMASIRICHI OKWU\u2013BO" (U+2013 en-dash) normalises to
    "OMASIRICHI OKWU-BO" (ASCII hyphen).  A rule with value "OMASIRICHI OKWU-BO"
    (ASCII hyphen) also normalises to "OMASIRICHI OKWU-BO", so they match.
    """
    # Rule value with ASCII hyphen (as stored after load_rules normalisation)
    rule = exact_rule("OMASIRICHI OKWU-BO", Category.FOOD_SUPPLIES)
    # Transaction description uses the en-dash U+2013
    transaction = tx("OMASIRICHI OKWU\u2013BO")

    result = classify((transaction,), [rule])

    assert len(result.matched) == 1
    assert result.matched[0].category == Category.FOOD_SUPPLIES


def test_ascii_hyphen_in_description_does_not_match_rule_with_space() -> None:
    """R4.1: ASCII hyphen in description does NOT normalise to a space.

    "OMASIRICHI OKWU-BO" remains "OMASIRICHI OKWU-BO" after normalisation,
    which is not equal to a rule value of "OMASIRICHI OKWU BO" (space instead of hyphen).
    """
    # Rule value with a space (not a hyphen)
    rule = exact_rule("OMASIRICHI OKWU BO", Category.FOOD_SUPPLIES)
    # Transaction description with ASCII hyphen
    transaction = tx("OMASIRICHI OKWU-BO")

    result = classify((transaction,), [rule])

    # No match — hyphen ≠ space
    assert result.matched == ()
    assert len(result.unmatched) == 1


# ---------------------------------------------------------------------------
# Tests for classify() — document order preservation
# ---------------------------------------------------------------------------


def test_document_order_preserved_in_matched() -> None:
    """R4.6: result.matched preserves document order of transactions."""
    rule_a = exact_rule("ALPHA", Category.SALARY)
    rule_b = exact_rule("BETA", Category.RENT)
    rule_c = exact_rule("GAMMA", Category.FOOD_SUPPLIES)

    tx_a = tx("ALPHA")
    tx_b = tx("BETA")
    tx_c = tx("GAMMA")

    result = classify((tx_a, tx_b, tx_c), [rule_a, rule_b, rule_c])

    assert len(result.matched) == 3
    assert result.matched[0].transaction == tx_a
    assert result.matched[1].transaction == tx_b
    assert result.matched[2].transaction == tx_c


def test_document_order_preserved_with_mixed_matched_and_unmatched() -> None:
    """R4.6/R4.7: document order is maintained across matched and unmatched transactions."""
    rule_a = exact_rule("ALPHA", Category.SALARY)
    rule_c = exact_rule("GAMMA", Category.FOOD_SUPPLIES)
    # No rule for BETA — it will be unmatched.

    tx_a = tx("ALPHA")
    tx_b = tx("BETA")
    tx_c = tx("GAMMA")

    result = classify((tx_a, tx_b, tx_c), [rule_a, rule_c])

    # Matched: ALPHA then GAMMA (document order)
    assert len(result.matched) == 2
    assert result.matched[0].transaction == tx_a
    assert result.matched[1].transaction == tx_c
    # Unmatched: only BETA
    assert len(result.unmatched) == 1
    assert result.unmatched[0] == tx_b


# ---------------------------------------------------------------------------
# Tests for classify() — edge cases
# ---------------------------------------------------------------------------


def test_empty_transactions_returns_empty_result() -> None:
    """Edge case: an empty transactions tuple produces an empty ClassificationResult."""
    rule = exact_rule("ANYTHING", Category.SALARY)
    result = classify((), [rule])

    assert result.matched == ()
    assert result.unmatched == ()
    assert isinstance(result, ClassificationResult)


def test_empty_rules_produces_all_unmatched() -> None:
    """Edge case: no rules means every transaction is unmatched."""
    transactions = (tx("COFFEE SHOP"), tx("TESCO"))
    result = classify(transactions, [])

    assert result.matched == ()
    assert len(result.unmatched) == 2


def test_classification_result_is_frozen_dataclass() -> None:
    """ClassificationResult and ClassifiedTransaction must be immutable (frozen=True)."""
    rule = exact_rule("TESCO", Category.FOOD_SUPPLIES)
    transaction = tx("TESCO")
    result = classify((transaction,), [rule])

    with pytest.raises(Exception):
        result.matched = ()  # type: ignore[misc]

    with pytest.raises(Exception):
        result.matched[0].category = Category.SALARY  # type: ignore[misc]


def test_regex_pass_skipped_when_exact_matches() -> None:
    """R4.2/R4.3: Pass 2 (regex) is skipped entirely when Pass 1 (exact) succeeds.

    The exact rule assigns SALARY; the regex rule would assign FOOD_SUPPLIES if reached.
    The result must be SALARY, confirming regex pass was not executed.
    """
    exact = exact_rule("TESCO", Category.SALARY)
    regex = regex_rule("TESCO", Category.FOOD_SUPPLIES)

    transaction = tx("TESCO")
    result = classify((transaction,), [exact, regex])

    assert len(result.matched) == 1
    assert result.matched[0].category == Category.SALARY


def test_regex_applied_to_normalised_description() -> None:
    """R4.3: Regex match is applied against the normalised description.

    The regex '^COFFEE' should match a description '  COFFEE HOUSE  ' after
    normalisation strips leading/trailing spaces, yielding 'COFFEE HOUSE'.
    """
    rule = regex_rule("^COFFEE", Category.EATING_OUT)
    transaction = tx("  COFFEE HOUSE  ")

    result = classify((transaction,), [rule])

    assert len(result.matched) == 1
    assert result.matched[0].category == Category.EATING_OUT
