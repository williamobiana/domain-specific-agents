"""CSV writer: transform monthly ClassificationResults into fixed-schema budget CSVs."""

from __future__ import annotations

import csv
from collections import defaultdict
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
        out_path = out_dir / f"{year_month.year}-{year_month.month:02d}.csv"
        category_totals = _build_category_totals(month_result)

        section_running: dict[Section, Decimal] = {}
        subtotals_by_group: dict[str, list[Decimal]] = defaultdict(list)
        grand_totals: dict[str, Decimal] = {}

        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

            writer.writerow(["Period start", str(statement.period_start)])
            writer.writerow(["Period end", str(statement.period_end)])

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

        written_paths.append(out_path)

    return written_paths
