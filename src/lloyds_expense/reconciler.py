"""Arithmetic verification: compare classified totals against statement totals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from lloyds_expense.classifier import ClassificationResult
from lloyds_expense.parser import Statement
from lloyds_expense.schema import Section, section_for_category

# ---------------------------------------------------------------------------
# Module-level section sets for inflow / outflow classification
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 7.1 -- ReconciliationReport dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReconciliationReport:
    """Structured result of a reconcile() call.

    Attributes:
        ok:                 True when classified totals match statement totals exactly.
        money_in_expected:  The statement's reported Money In total.
        money_in_actual:    The sum of all matched inflow transaction amounts.
        money_out_expected: The statement's reported Money Out total.
        money_out_actual:   The sum of all matched outflow transaction amounts.
    """

    ok: bool
    money_in_expected: Decimal
    money_in_actual: Decimal
    money_out_expected: Decimal
    money_out_actual: Decimal

    @property
    def money_in_diff(self) -> Decimal:
        """Signed difference: actual minus expected for money-in (positive = surplus)."""
        return self.money_in_actual - self.money_in_expected

    @property
    def money_out_diff(self) -> Decimal:
        """Signed difference: actual minus expected for money-out (positive = surplus)."""
        return self.money_out_actual - self.money_out_expected


# ---------------------------------------------------------------------------
# Task 7.2 -- reconcile() -- arithmetic verification
# ---------------------------------------------------------------------------


def reconcile(result: ClassificationResult, statement: Statement) -> ReconciliationReport:
    """Compare classified transaction totals against the statement's reported totals.

    This function never raises exceptions; it always returns a ReconciliationReport.
    The balance equation check (opening + in - out == closing) belongs in the parser,
    not here — a balance mismatch indicates a parser fault, not a classification fault.

    Inflow sections:  REGULAR_INFLOWS, IRREGULAR_INFLOWS, ASSET_LIQUIDATION.
    Outflow sections: REGULAR_OUTFLOWS, IRREGULAR_OUTFLOWS, ASSETS.

    Args:
        result:    The ClassificationResult produced by classifier.classify().
        statement: The Statement produced by parser.parse_statement().

    Returns:
        ReconciliationReport with ok=True when both totals match exactly,
        or ok=False with the expected/actual values when they diverge.
    """
    # Sum inflow amounts: transactions whose category maps to an inflow section.
    actual_in: Decimal = sum(
        (
            ct.transaction.amount
            for ct in result.matched
            if section_for_category(ct.category) in _INFLOW_SECTIONS
        ),
        Decimal("0.00"),
    )

    # Sum outflow amounts: transactions whose category maps to an outflow section.
    actual_out: Decimal = sum(
        (
            ct.transaction.amount
            for ct in result.matched
            if section_for_category(ct.category) in _OUTFLOW_SECTIONS
        ),
        Decimal("0.00"),
    )

    ok = actual_in == statement.money_in_total and actual_out == statement.money_out_total

    return ReconciliationReport(
        ok=ok,
        money_in_expected=statement.money_in_total,
        money_in_actual=actual_in,
        money_out_expected=statement.money_out_total,
        money_out_actual=actual_out,
    )
