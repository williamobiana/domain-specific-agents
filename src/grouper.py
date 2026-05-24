from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.categories import SCHEMA

if TYPE_CHECKING:
    from src.parser import ExpenseItem


@dataclass
class CategorisedItem:
    section: str
    category: str
    amount: float


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation."""
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return re.sub(r'\s+', ' ', text).strip()


def _exact_match(normalised_text: str) -> tuple[str, str] | None:
    """Compare normalised item text against each normalised category name."""
    for section in SCHEMA:
        for category in section.categories:
            if _normalise(category) == normalised_text:
                return (section.name, category)
    return None


def _fuzzy_match(normalised_text: str) -> tuple[str, str] | None:
    """Token overlap and substring heuristics — pure Python, no third-party libs."""
    item_tokens = set(normalised_text.split())
    if not item_tokens:
        return None

    best: tuple[str, str] | None = None
    best_ratio = -1.0

    for section in SCHEMA:
        for category in section.categories:
            norm_cat = _normalise(category)
            cat_tokens = set(norm_cat.split())
            if not cat_tokens:
                continue

            overlap = item_tokens & cat_tokens
            ratio = len(overlap) / len(cat_tokens)

            token_match = len(overlap) >= 1 and ratio >= 0.5
            substring_match = norm_cat in normalised_text or normalised_text in norm_cat

            if token_match or substring_match:
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = (section.name, category)

    return best


def match_category(item_text: str) -> tuple[str, str] | None:
    """Return (section_name, category_name) or None if no match found.
    Pass 1: exact normalised match. Pass 2: fuzzy token/substring match."""
    normalised = _normalise(item_text)
    result = _exact_match(normalised)
    if result is not None:
        return result
    return _fuzzy_match(normalised)


def group_items(
    items: list[ExpenseItem],
) -> tuple[list[CategorisedItem], list[ExpenseItem]]:
    """Match each ExpenseItem to a (section, category) pair.
    Returns (all_categorised, unmatched_items).
    Unmatched items are assigned to 'Uncategorised' in the first list."""
    categorised: list[CategorisedItem] = []
    unmatched: list[ExpenseItem] = []

    for item in items:
        match = match_category(item.raw_text)
        if match is not None:
            section_name, category_name = match
            categorised.append(
                CategorisedItem(section=section_name, category=category_name, amount=item.amount)
            )
        else:
            unmatched.append(item)
            categorised.append(
                CategorisedItem(section="Uncategorised", category="Uncategorised", amount=item.amount)
            )

    return (categorised, unmatched)
