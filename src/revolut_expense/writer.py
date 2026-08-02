"""CSV writer: transform monthly ClassificationResults into fixed-schema budget CSVs."""

from __future__ import annotations

import calendar
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from revolut_expense.classifier import ClassificationResult
from revolut_expense.parser import Statement
from revolut_expense.schema import SCHEMA_ORDER, Category, Section
from revolut_expense.splitter import YearMonth


def _build_category_totals(result: ClassificationResult) -> dict[Category, Decimal]:
    """Sum transaction amounts grouped by category.

    Categories with no transactions are not included; callers should use
    .get(cat, Decimal("0.00")).
    """
    totals: dict[Category, Decimal] = {}
    for ct in result.matched:
        category = ct.category
        amount = ct.transaction.amount
        totals[category] = totals.get(category, Decimal("0")) + amount
    return totals


def _balances_for_month(
    statement: Statement, year_month: YearMonth
) -> tuple[Decimal, Decimal]:
    """Return (opening, closing) account balance for one calendar month.

    Derived from each transaction's own running_balance (the figure Revolut
    printed on the statement next to that transaction) rather than the
    statement-level opening/closing balance. This stays correct both for
    statements spanning multiple calendar months and for statements that
    concatenate multiple sub-statements (e.g. an account migration
    mid-period) — running_balance already carries continuously across those
    boundaries.
    """
    all_tx = statement.transactions
    month_indices = [
        i
        for i, tx in enumerate(all_tx)
        if tx.date.year == year_month.year and tx.date.month == year_month.month
    ]
    if not month_indices:
        return statement.opening_balance, statement.closing_balance

    first_idx = month_indices[0]
    last_idx = month_indices[-1]
    opening = (
        all_tx[first_idx - 1].running_balance
        if first_idx > 0
        else statement.opening_balance
    )
    closing = all_tx[last_idx].running_balance
    return opening, closing


def _period_bounds_for_month(statement: Statement, year_month: YearMonth) -> tuple[date, date]:
    """Return (period_start, period_end) for one calendar month within *statement*.

    Clamped to the statement's own period at the first/last covered month, so
    a statement that starts or ends mid-month reports its true partial range
    rather than the full calendar month.
    """
    last_day = calendar.monthrange(year_month.year, year_month.month)[1]
    month_start = date(year_month.year, year_month.month, 1)
    month_end = date(year_month.year, year_month.month, last_day)

    period_start = max(month_start, statement.period_start)
    period_end = min(month_end, statement.period_end)
    return period_start, period_end


def write_csvs(
    by_month: dict[YearMonth, ClassificationResult],
    statement: Statement,
    out_dir: Path,
) -> list[Path]:
    """Write one CSV per calendar month to *out_dir*.

    Creates *out_dir* (and any missing parents) if absent. Silently overwrites
    existing files. Returns written paths in ascending chronological order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []

    for year_month, month_result in sorted(by_month.items()):
        out_path = out_dir / f"revolut-{year_month.year}-{year_month.month:02d}.csv"
        category_totals = _build_category_totals(month_result)
        period_start, period_end = _period_bounds_for_month(statement, year_month)
        opening_balance, closing_balance = _balances_for_month(statement, year_month)

        section_running: dict[Section, Decimal] = {}
        subtotals_by_group: dict[str, list[Decimal]] = defaultdict(list)
        grand_totals: dict[str, Decimal] = {}

        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

            writer.writerow(["Period start", str(period_start)])
            writer.writerow(["Period end", str(period_end)])
            writer.writerow(["Opening Balance", str(opening_balance.quantize(Decimal("0.01")))])

            for row in SCHEMA_ORDER:
                if row.kind == "section_header":
                    if row.section is not None:
                        section_running[row.section] = Decimal("0.00")
                    writer.writerow([row.label, ""])

                elif row.kind == "line_item":
                    total = category_totals.get(row.category, Decimal("0.00"))  # type: ignore[arg-type]
                    writer.writerow([row.label, str(total.quantize(Decimal("0.01")))])
                    if row.section is not None:
                        section_running[row.section] = (
                            section_running.get(row.section, Decimal("0.00")) + total
                        )

                elif row.kind == "subtotal":
                    subtotal_value = section_running.get(row.section, Decimal("0.00"))  # type: ignore[arg-type]
                    writer.writerow([row.label, str(subtotal_value.quantize(Decimal("0.01")))])
                    if row.group is not None:
                        subtotals_by_group[row.group].append(subtotal_value)

                elif row.kind == "grand_total":
                    grand_value = sum(
                        subtotals_by_group.get(row.group, []),  # type: ignore[arg-type]
                        Decimal("0.00"),
                    )
                    writer.writerow([row.label, str(grand_value.quantize(Decimal("0.01")))])
                    if row.group is not None:
                        grand_totals[row.group] = grand_value

                elif row.kind == "balance":
                    balance = grand_totals.get("income", Decimal("0.00")) - grand_totals.get(
                        "expenditure", Decimal("0.00")
                    )
                    writer.writerow([row.label, str(balance.quantize(Decimal("0.01")))])

            writer.writerow(["Closing Balance", str(closing_balance.quantize(Decimal("0.01")))])

        written_paths.append(out_path)

    return written_paths
