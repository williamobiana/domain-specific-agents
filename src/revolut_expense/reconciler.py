"""Arithmetic verification: compare classified totals against statement totals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from revolut_expense.classifier import ClassificationResult
from revolut_expense.parser import Statement
from revolut_expense.schema import Section, section_for_category

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
    money_in_expected: Decimal
    money_in_actual: Decimal
    money_out_expected: Decimal
    money_out_actual: Decimal

    @property
    def money_in_diff(self) -> Decimal:
        """Signed difference: actual minus expected for money in."""
        return self.money_in_actual - self.money_in_expected

    @property
    def money_out_diff(self) -> Decimal:
        """Signed difference: actual minus expected for money out."""
        return self.money_out_actual - self.money_out_expected


def reconcile(result: ClassificationResult, statement: Statement) -> ReconciliationReport:
    """Compare classified transaction totals against the statement's reported totals.

    Operates over the entire statement period (all months combined) because
    Revolut PDFs only print period-level totals, not per-month totals.

    This function never raises; it always returns a ReconciliationReport.
    The balance equation check belongs in the parser, not here.
    """
    actual_money_in: Decimal = sum(
        (
            ct.transaction.amount
            for ct in result.matched
            if section_for_category(ct.category) in _INFLOW_SECTIONS
        ),
        Decimal("0.00"),
    )

    actual_money_out: Decimal = sum(
        (
            ct.transaction.amount
            for ct in result.matched
            if section_for_category(ct.category) in _OUTFLOW_SECTIONS
        ),
        Decimal("0.00"),
    )

    ok = (
        actual_money_in == statement.total_money_in
        and actual_money_out == statement.total_money_out
    )

    return ReconciliationReport(
        ok=ok,
        money_in_expected=statement.total_money_in,
        money_in_actual=actual_money_in,
        money_out_expected=statement.total_money_out,
        money_out_actual=actual_money_out,
    )
