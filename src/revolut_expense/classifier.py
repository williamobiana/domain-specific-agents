"""Two-pass transaction classification engine."""

from __future__ import annotations

import re
from dataclasses import dataclass

from revolut_expense.parser import Transaction
from revolut_expense.rules import ExactMatch, RegexMatch, Rule
from revolut_expense.schema import Category

_HYPHEN_VARIANT_RE: re.Pattern[str] = re.compile(r"[\u2010-\u2014]")


def _normalise(text: str) -> str:
    """Normalise a transaction description for matching.

    1. Strip leading/trailing whitespace.
    2. Collapse internal whitespace runs to a single space.
    3. Replace Unicode hyphen/dash variants with ASCII hyphen-minus.
    """
    normalised = text.strip()
    normalised = re.sub(r"\s+", " ", normalised)
    normalised = _HYPHEN_VARIANT_RE.sub("-", normalised)
    return normalised


@dataclass(frozen=True)
class ClassifiedTransaction:
    """A transaction that has been assigned to a budget category."""

    transaction: Transaction
    category: Category


@dataclass(frozen=True)
class ClassificationResult:
    """The outcome of a classify() call: matched and unmatched transactions."""

    matched: tuple[ClassifiedTransaction, ...]
    unmatched: tuple[Transaction, ...]


def classify(
    transactions: tuple[Transaction, ...],
    rules: list[Rule],
) -> ClassificationResult:
    """Classify each transaction using a two-pass exact-then-regex strategy.

    Pass 1 (Exact):  Iterate exact-match rules in file order; assign on the first
                     rule whose normalised value equals the normalised description
                     AND whose optional direction filter (when present) matches.

    Pass 2 (Regex):  Run only when Pass 1 found no match. Iterate regex-match rules
                     in file order; assign on first pattern.search() match with
                     direction filter satisfied.

    No type-code filter — Revolut transactions carry no type codes.
    """
    exact_rules = [r for r in rules if isinstance(r.matcher, ExactMatch)]
    regex_rules = [r for r in rules if isinstance(r.matcher, RegexMatch)]

    matched: list[ClassifiedTransaction] = []
    unmatched: list[Transaction] = []

    for tx in transactions:
        normalised_desc = _normalise(tx.description)
        assigned_category: Category | None = None

        for rule in exact_rules:
            assert isinstance(rule.matcher, ExactMatch)
            if normalised_desc != rule.matcher.value:
                continue
            if rule.direction is not None and rule.direction != tx.direction:
                continue
            assigned_category = rule.category
            break

        if assigned_category is None:
            for rule in regex_rules:
                assert isinstance(rule.matcher, RegexMatch)
                if rule.matcher.pattern.search(normalised_desc) is None:
                    continue
                if rule.direction is not None and rule.direction != tx.direction:
                    continue
                assigned_category = rule.category
                break

        if assigned_category is not None:
            matched.append(ClassifiedTransaction(transaction=tx, category=assigned_category))
        else:
            unmatched.append(tx)

    return ClassificationResult(
        matched=tuple(matched),
        unmatched=tuple(unmatched),
    )
