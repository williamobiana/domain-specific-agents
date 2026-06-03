"""CSV writer: transform a ClassificationResult into the fixed-schema budget CSV."""

from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from lloyds_expense.classifier import ClassificationResult
from lloyds_expense.parser import Statement
from lloyds_expense.schema import SCHEMA_ORDER, Category, Section

# ---------------------------------------------------------------------------
# Task 8.1 — Category total accumulation
# ---------------------------------------------------------------------------


def _build_category_totals(result: ClassificationResult) -> dict[Category, Decimal]:
    """Sum transaction amounts grouped by category.

    Iterates all ClassifiedTransaction objects in result.matched and accumulates
    the transaction amount per category.  Categories with no transactions are
    NOT included in the returned dict; callers should use .get with a
    Decimal("0.00") default.

    Args:
        result: The classification result whose matched transactions are summed.

    Returns:
        A dict mapping each Category that has at least one matched transaction
        to the total Decimal amount for that category.
    """
    totals: dict[Category, Decimal] = {}
    for classified in result.matched:
        category = classified.category
        amount = classified.transaction.amount
        if category in totals:
            totals[category] = totals[category] + amount
        else:
            totals[category] = amount
    return totals


# ---------------------------------------------------------------------------
# Task 8.2 — write_csv entry point
# ---------------------------------------------------------------------------


def write_csv(result: ClassificationResult, statement: Statement, out: Path) -> None:
    """Write the classified transactions to a fixed-schema budget CSV file.

    The output format is:
      - Two metadata header rows (period_start, period_end).
      - All rows from SCHEMA_ORDER in their defined order:
          section_header rows   — label, empty value column.
          line_item rows        — label, category total (default 0.00).
          subtotal rows         — label, sum of line items in this section.
          grand_total rows      — label, sum of section subtotals for the group.

    All Decimal values are quantized to two decimal places at write time only.
    No float arithmetic is used anywhere in this function.

    Line endings are ``\\n`` (LF), not ``\\r\\n`` (CRLF), achieved via
    ``lineterminator="\\n"`` on the csv.writer.

    If ``out`` already exists it is silently overwritten (Python's default 'w'
    mode behaviour).

    Args:
        result:    The classification result providing per-category amounts.
        statement: The parsed statement providing the reporting period dates.
        out:       Destination path for the CSV file.
    """
    category_totals = _build_category_totals(result)

    # Running total of line-item amounts accumulated since the last section_header,
    # keyed by Section.  Reset when a new section_header is encountered.
    section_running: dict[Section, Decimal] = {}

    # Subtotals accumulated per group ("income" / "expenditure"), used when
    # writing grand_total rows.
    subtotals_by_group: dict[str, list[Decimal]] = defaultdict(list)

    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

        # --- Metadata header rows ---
        writer.writerow(["Period start", str(statement.period_start)])
        writer.writerow(["Period end", str(statement.period_end)])

        # --- Schema rows ---
        for row in SCHEMA_ORDER:
            if row.kind == "section_header":
                # Reset running total for this section.
                if row.section is not None:
                    section_running[row.section] = Decimal("0.00")
                writer.writerow([row.label, ""])

            elif row.kind == "line_item":
                # Look up the accumulated total; default to zero for empty categories.
                total = category_totals.get(row.category, Decimal("0.00"))  # type: ignore[arg-type]
                writer.writerow([row.label, str(total.quantize(Decimal("0.01")))])
                # Accumulate into the section running total.
                if row.section is not None:
                    section_running[row.section] = (
                        section_running.get(row.section, Decimal("0.00")) + total
                    )

            elif row.kind == "subtotal":
                subtotal_value = section_running.get(row.section, Decimal("0.00"))  # type: ignore[arg-type]
                writer.writerow([row.label, str(subtotal_value.quantize(Decimal("0.01")))])
                # Record this subtotal so the grand_total rows can sum across sections.
                if row.group is not None:
                    subtotals_by_group[row.group].append(subtotal_value)

            elif row.kind == "grand_total":
                grand_value = sum(
                    subtotals_by_group.get(row.group, []),  # type: ignore[arg-type]
                    Decimal("0.00"),
                )
                writer.writerow([row.label, str(grand_value.quantize(Decimal("0.01")))])
