"""Calendar month grouping: split a ClassificationResult by (year, month)."""

from __future__ import annotations

from typing import NamedTuple

from monzo_expense.classifier import ClassificationResult, ClassifiedTransaction


class YearMonth(NamedTuple):
    """A calendar month identified by its year and month number."""

    year: int
    month: int


def split_by_month(result: ClassificationResult) -> dict[YearMonth, ClassificationResult]:
    """Group matched transactions by calendar month of their transaction date.

    Pure function: no I/O, no mutation of the input.

    Each output ClassificationResult has unmatched=() because unmatched
    transactions are handled before the split stage.

    Returns a dict with keys in ascending chronological order.
    """
    buckets: dict[YearMonth, list[ClassifiedTransaction]] = {}
    for ct in result.matched:
        key = YearMonth(ct.transaction.date.year, ct.transaction.date.month)
        buckets.setdefault(key, []).append(ct)
    return {
        key: ClassificationResult(matched=tuple(cts), unmatched=())
        for key, cts in sorted(buckets.items())
    }
