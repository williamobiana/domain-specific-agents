"""Arithmetic verification: compare classified totals against statement totals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from monzo_expense.classifier import ClassificationResult
from monzo_expense.parser import Statement
from monzo_expense.schema import Section, section_for_category

_INFLOW_SECTIONS: frozenset[Section] = frozenset(
    {
        Section.REGULAR_INFLOWS,
        Section.IRREGULAR_INFLOWS,
        Section.ASSET_LIQUIDATION,
    }
)

_OUTFLOW_SECTIONS: frozenset[Section] = frozenset(
    {
        Section.REGULAR_OUTFLOWS,
        Section.IRREGULAR_OUTFLOWS,
        Section.ASSETS,
    }
)


@dataclass(frozen=True)
class ReconciliationReport:
    """Structured result of a reconcile() call."""

    ok: bool
    deposits_expected: Decimal
    deposits_actual: Decimal
    outgoings_expected: Decimal
    outgoings_actual: Decimal

    @property
    def deposits_diff(self) -> Decimal:
        """Signed difference: actual minus expected for deposits."""
        return self.deposits_actual - self.deposits_expected

    @property
    def outgoings_diff(self) -> Decimal:
        """Signed difference: actual minus expected for outgoings."""
        return self.outgoings_actual - self.outgoings_expected


def reconcile(result: ClassificationResult, statement: Statement) -> ReconciliationReport:
    """Compare classified transaction totals against the statement's reported totals.

    Operates over the entire statement period (all months combined) because
    Monzo PDFs only print period-level totals, not per-month totals.

    This function never raises; it always returns a ReconciliationReport.
    The balance equation check belongs in the parser, not here.
    """
    actual_deposits: Decimal = sum(
        (
            ct.transaction.amount
            for ct in result.matched
            if section_for_category(ct.category) in _INFLOW_SECTIONS
        ),
        Decimal("0.00"),
    )

    actual_outgoings: Decimal = sum(
        (
            ct.transaction.amount
            for ct in result.matched
            if section_for_category(ct.category) in _OUTFLOW_SECTIONS
        ),
        Decimal("0.00"),
    )

    ok = (
        actual_deposits == statement.total_deposits
        and actual_outgoings == statement.total_outgoings
    )

    return ReconciliationReport(
        ok=ok,
        deposits_expected=statement.total_deposits,
        deposits_actual=actual_deposits,
        outgoings_expected=statement.total_outgoings,
        outgoings_actual=actual_outgoings,
    )
