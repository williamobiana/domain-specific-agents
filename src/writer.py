from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from src.categories import INCOME_SECTIONS, OUTFLOW_SECTIONS

if TYPE_CHECKING:
    from src.summariser import SectionSummary


def _fmt(amount: float) -> str:
    return f"{amount:.2f}"


def _write_section(writer: csv.writer, summary: SectionSummary) -> None:
    for ct in summary.categories:
        writer.writerow([summary.section, ct.category, _fmt(ct.total)])
    writer.writerow([summary.section, "Subtotal", _fmt(summary.subtotal)])


def write_csv(
    summaries: list[SectionSummary],
    total_income: float,
    total_expenditure: float,
    output_path: str,
) -> None:
    """Write the full CSV to output_path. Raises OSError on write failure."""
    by_section = {s.section: s for s in summaries}
    uncategorised = by_section.get("Uncategorised")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["section", "category", "total_amount"])

        for section_name in INCOME_SECTIONS:
            if section_name in by_section:
                _write_section(writer, by_section[section_name])
        writer.writerow(["", "Total Income", _fmt(total_income)])

        for section_name in OUTFLOW_SECTIONS:
            if section_name in by_section:
                _write_section(writer, by_section[section_name])
        writer.writerow(["", "Total Expenditure", _fmt(total_expenditure)])

        if uncategorised is not None:
            _write_section(writer, uncategorised)
