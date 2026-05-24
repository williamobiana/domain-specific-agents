from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.categories import INCOME_SECTIONS, OUTFLOW_SECTIONS, SCHEMA

if TYPE_CHECKING:
    from src.grouper import CategorisedItem


@dataclass
class CategoryTotal:
    category: str
    total: float


@dataclass
class SectionSummary:
    section: str
    categories: list[CategoryTotal]
    subtotal: float


def _build_category_totals(
    section_name: str,
    items: list[CategorisedItem],
) -> list[CategoryTotal]:
    """Return one CategoryTotal per category in the section, in canonical order."""
    section = next(s for s in SCHEMA if s.name == section_name)
    totals = []
    for category in section.categories:
        total = sum(item.amount for item in items if item.category == category)
        totals.append(CategoryTotal(category=category, total=total))
    return totals


def summarise(items: list[CategorisedItem]) -> list[SectionSummary]:
    """Aggregate CategorisedItems into SectionSummary objects in canonical order.
    Always includes every category from SCHEMA (zero-filled when no items match)."""
    summaries: list[SectionSummary] = []

    for section in SCHEMA:
        section_items = [i for i in items if i.section == section.name]
        category_totals = _build_category_totals(section.name, section_items)
        subtotal = sum(ct.total for ct in category_totals)
        summaries.append(SectionSummary(
            section=section.name,
            categories=category_totals,
            subtotal=subtotal,
        ))

    uncategorised = [i for i in items if i.section == "Uncategorised"]
    if uncategorised:
        category_totals = [
            CategoryTotal(category=i.category, total=i.amount)
            for i in uncategorised
        ]
        subtotal = sum(ct.total for ct in category_totals)
        summaries.append(SectionSummary(
            section="Uncategorised",
            categories=category_totals,
            subtotal=subtotal,
        ))

    return summaries


def compute_grand_totals(
    summaries: list[SectionSummary],
) -> tuple[float, float]:
    """Return (total_income, total_expenditure) by summing the relevant section subtotals."""
    total_income = sum(s.subtotal for s in summaries if s.section in INCOME_SECTIONS)
    total_expenditure = sum(s.subtotal for s in summaries if s.section in OUTFLOW_SECTIONS)
    return (total_income, total_expenditure)
