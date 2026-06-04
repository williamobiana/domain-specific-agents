"""Two-pass transaction classification engine."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lloyds_expense.parser import Transaction
from lloyds_expense.rules import ExactMatch, RegexMatch, Rule
from lloyds_expense.schema import Category

# ---------------------------------------------------------------------------
# Unicode hyphen/dash variants (U+2010 to U+2014) -> ASCII hyphen-minus (U+002D).
# Using raw-string Unicode escapes avoids embedding literal ambiguous chars (RUF001).
# ---------------------------------------------------------------------------

_HYPHEN_VARIANT_RE: re.Pattern[str] = re.compile(r"[\u2010-\u2014]")


# ---------------------------------------------------------------------------
# Task 6.1 -- Description normalisation helper
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Normalise a transaction description for matching.

    Steps applied in order:
    1. Strip leading/trailing whitespace.
    2. Collapse internal whitespace runs to a single space.
    3. Replace Unicode hyphen/dash variants (U+2010 to U+2014) with ASCII hyphen-minus.
    """
    normalised = text.strip()
    normalised = re.sub(r"\s+", " ", normalised)
    normalised = _HYPHEN_VARIANT_RE.sub("-", normalised)
    return normalised


# ---------------------------------------------------------------------------
# Task 6.2 -- ClassifiedTransaction and ClassificationResult dataclasses
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Task 6.3 -- classify() -- two-pass transaction matching
# ---------------------------------------------------------------------------


def classify(
    transactions: tuple[Transaction, ...],
    rules: list[Rule],
) -> ClassificationResult:
    """Classify each transaction using a two-pass exact-then-regex strategy.

    Pass 1 (Exact):  Iterate exact-match rules in file order; assign category
                     on the first rule whose normalised value equals the
                     normalised description AND whose optional type_code /
                     direction filters (when present) match the transaction.

    Pass 2 (Regex):  Run only when Pass 1 produced no match.  Iterate
                     regex-match rules in file order; assign category on the
                     first rule whose pattern.search() succeeds AND whose
                     optional filters match.

    Transactions that survive both passes without a match are added to the
    ``unmatched`` list.  Document order is preserved in both output tuples.

    Args:
        transactions: All transactions from the parsed statement, in document order.
        rules:        Validated Rule objects in YAML file order.

    Returns:
        ClassificationResult with document-ordered matched and unmatched tuples.
    """
    # Pre-split rules into two ordered lists, preserving file order within each.
    exact_rules = [r for r in rules if isinstance(r.matcher, ExactMatch)]
    regex_rules = [r for r in rules if isinstance(r.matcher, RegexMatch)]

    matched: list[ClassifiedTransaction] = []
    unmatched: list[Transaction] = []

    for tx in transactions:
        normalised_desc = _normalise(tx.description)
        assigned_category: Category | None = None

        # ------------------------------------------------------------------
        # Pass 1 -- Exact matching
        # ------------------------------------------------------------------
        for rule in exact_rules:
            # rule.matcher is always ExactMatch here, but mypy needs the guard.
            assert isinstance(rule.matcher, ExactMatch)

            if normalised_desc != rule.matcher.value:
                continue
            if rule.type_code is not None and rule.type_code != tx.type_code:
                continue
            if rule.direction is not None and rule.direction != tx.direction:
                continue

            assigned_category = rule.category
            break

        # ------------------------------------------------------------------
        # Pass 2 -- Regex matching (only if Pass 1 found no match)
        # ------------------------------------------------------------------
        if assigned_category is None:
            for rule in regex_rules:
                # rule.matcher is always RegexMatch here.
                assert isinstance(rule.matcher, RegexMatch)

                if rule.matcher.pattern.search(normalised_desc) is None:
                    continue
                if rule.type_code is not None and rule.type_code != tx.type_code:
                    continue
                if rule.direction is not None and rule.direction != tx.direction:
                    continue

                assigned_category = rule.category
                break

        # ------------------------------------------------------------------
        # Collect result
        # ------------------------------------------------------------------
        if assigned_category is not None:
            matched.append(ClassifiedTransaction(transaction=tx, category=assigned_category))
        else:
            unmatched.append(tx)

    return ClassificationResult(
        matched=tuple(matched),
        unmatched=tuple(unmatched),
    )
