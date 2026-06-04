"""Typed exception hierarchy for the Lloyds Expense Tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lloyds_expense.parser import Transaction
    from lloyds_expense.reconciler import ReconciliationReport


class StatementToCsvError(Exception):
    """Base class for all Lloyds Expense Tool errors."""


class ParseError(StatementToCsvError):
    """Raised by parser.py for any PDF parse failure; maps to exit code 3."""

    def __init__(self, message: str, page: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.page = page


class RulesConfigError(StatementToCsvError):
    """Raised by rules.py for invalid or unloadable rules; maps to exit code 4."""

    def __init__(
        self,
        message: str,
        line_number: int | None = None,
        violations: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.line_number = line_number
        self.violations: list[str] = violations if violations is not None else []


class UnmatchedTransactionsError(StatementToCsvError):
    """Raised when one or more transactions could not be classified; maps to exit code 1."""

    def __init__(self, unmatched: tuple[Transaction, ...]) -> None:
        super().__init__(f"{len(unmatched)} unmatched transaction(s)")
        self.unmatched = unmatched


class ReconciliationError(StatementToCsvError):
    """Raised when classified totals do not match statement totals; maps to exit code 2."""

    def __init__(self, report: ReconciliationReport) -> None:
        super().__init__("Reconciliation failed: computed totals do not match statement totals")
        self.report = report


class InputError(StatementToCsvError):
    """Raised for invalid command-line arguments; maps to exit code 4."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
