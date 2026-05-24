from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.categories import INCOME_SECTIONS, OUTFLOW_SECTIONS, SCHEMA

if TYPE_CHECKING:
    from src.parser import ExpenseItem


@dataclass
class CategorisedItem:
    section: str
    category: str
    amount: float


def _normalise(text: str) -> str:
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return re.sub(r'\s+', ' ', text).strip()


def _exact_match(normalised_text: str) -> tuple[str, str] | None:
    for section in SCHEMA:
        for category in section.categories:
            if _normalise(category) == normalised_text:
                return (section.name, category)
    return None


# (substring_to_find_in_normalised_text, section_name, category_name)
_KEYWORD_PATTERNS: list[tuple[str, str, str]] = [
    # Regular Inflows
    ("salary",          "Regular Inflows",    "Salary"),
    ("payroll",         "Regular Inflows",    "Salary"),
    ("wages",           "Regular Inflows",    "Salary"),
    ("national serv",   "Regular Inflows",    "Salary"),
    # Irregular Inflows
    ("carry over",      "Irregular Inflows",  "Carry Over"),
    ("carryover",       "Irregular Inflows",  "Carry Over"),
    ("refund",          "Irregular Inflows",  "Unexpected / Refund"),
    ("cashback",        "Irregular Inflows",  "Unexpected / Refund"),
    # Asset Liquidation
    ("trading 212",     "Asset Liquidation",  "Stocks & Shares"),
    ("freetrade",       "Asset Liquidation",  "Stocks & Shares"),
    # Regular Outflows
    ("council tax",     "Regular Outflows",   "Bill - Council Tax"),
    ("octopus energy",  "Regular Outflows",   "Bill - Electricity & Gas"),
    ("british gas",     "Regular Outflows",   "Bill - Electricity & Gas"),
    ("e on",            "Regular Outflows",   "Bill - Electricity & Gas"),
    ("scottish power",  "Regular Outflows",   "Bill - Electricity & Gas"),
    ("broadband",       "Regular Outflows",   "Bill - Phone & Internet"),
    ("vodafone",        "Regular Outflows",   "Bill - Phone & Internet"),
    ("virgin media",    "Regular Outflows",   "Bill - Phone & Internet"),
    ("bt group",        "Regular Outflows",   "Bill - Phone & Internet"),
    ("three mobile",    "Regular Outflows",   "Bill - Phone & Internet"),
    ("tesco",           "Regular Outflows",   "Food Supplies"),
    ("sainsbury",       "Regular Outflows",   "Food Supplies"),
    ("asda",            "Regular Outflows",   "Food Supplies"),
    ("morrisons",       "Regular Outflows",   "Food Supplies"),
    ("waitrose",        "Regular Outflows",   "Food Supplies"),
    ("aldi",            "Regular Outflows",   "Food Supplies"),
    ("lidl",            "Regular Outflows",   "Food Supplies"),
    ("food supplies",   "Regular Outflows",   "Food Supplies"),
    ("grocery",         "Regular Outflows",   "Food Supplies"),
    ("credit card",     "Regular Outflows",   "Debt"),
    ("loan repay",      "Regular Outflows",   "Debt"),
    ("petrol",          "Regular Outflows",   "Car & Gas"),
    ("fuel",            "Regular Outflows",   "Car & Gas"),
    ("parking",         "Regular Outflows",   "Car & Gas"),
    ("ulez",            "Regular Outflows",   "Car & Gas"),
    ("congestion",      "Regular Outflows",   "Car & Gas"),
    # Irregular Outflows
    ("charity",         "Irregular Outflows", "Charity / Donations"),
    ("donation",        "Irregular Outflows", "Charity / Donations"),
    ("justgiving",      "Irregular Outflows", "Charity / Donations"),
    ("spotify",         "Irregular Outflows", "Gifts Entertainment & Misc"),
    ("netflix",         "Irregular Outflows", "Gifts Entertainment & Misc"),
    ("cinema",          "Irregular Outflows", "Gifts Entertainment & Misc"),
    ("amazon prime",    "Irregular Outflows", "Gifts Entertainment & Misc"),
    ("airbnb",          "Irregular Outflows", "Holidays & Travel"),
    ("booking com",     "Irregular Outflows", "Holidays & Travel"),
    ("ryanair",         "Irregular Outflows", "Holidays & Travel"),
    ("easyjet",         "Irregular Outflows", "Holidays & Travel"),
    ("trainline",       "Irregular Outflows", "Holidays & Travel"),
    ("udemy",           "Irregular Outflows", "Education"),
    ("coursera",        "Irregular Outflows", "Education"),
    ("tuition",         "Irregular Outflows", "Education"),
    ("restaurant",      "Irregular Outflows", "Eating Out"),
    ("takeaway",        "Irregular Outflows", "Eating Out"),
    ("uber eats",       "Irregular Outflows", "Eating Out"),
    ("deliveroo",       "Irregular Outflows", "Eating Out"),
    ("just eat",        "Irregular Outflows", "Eating Out"),
    # Assets
    ("active saving",   "Assets",             "Active Savings"),
    ("lifetime isa",    "Assets",             "Lifetime ISA"),
    ("stocks shares isa", "Assets",           "Stocks & Shares ISA"),
    ("dividend",        "Assets",             "Dividend Portfolio"),
]


def _keyword_match(normalised_text: str) -> tuple[str, str] | None:
    for keyword, section, category in _KEYWORD_PATTERNS:
        if keyword in normalised_text:
            return (section, category)
    return None


def _fuzzy_match(normalised_text: str, direction: str = 'out') -> tuple[str, str] | None:
    """Token overlap / substring heuristics — checks direction-aligned sections first."""
    item_tokens = set(normalised_text.split())
    if not item_tokens:
        return None

    priority_names = set(INCOME_SECTIONS if direction == 'in' else OUTFLOW_SECTIONS)
    other_names = set(OUTFLOW_SECTIONS if direction == 'in' else INCOME_SECTIONS)
    priority = [s for s in SCHEMA if s.name in priority_names]
    other = [s for s in SCHEMA if s.name in other_names]

    best: tuple[str, str] | None = None
    best_ratio = -1.0

    for section in priority + other:
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


def match_category(item_text: str, direction: str = 'out') -> tuple[str, str] | None:
    """Return (section_name, category_name) or None.
    Pass 1: exact normalised. Pass 2: keyword pattern. Pass 3: direction-biased fuzzy."""
    normalised = _normalise(item_text)
    result = _exact_match(normalised)
    if result is not None:
        return result
    result = _keyword_match(normalised)
    if result is not None:
        return result
    return _fuzzy_match(normalised, direction)


def group_items(
    items: list[ExpenseItem],
) -> tuple[list[CategorisedItem], list[ExpenseItem]]:
    """Match each ExpenseItem to a (section, category) pair.
    Returns (all_categorised, unmatched_items).
    Unmatched items are also placed in 'Uncategorised' in the first list."""
    categorised: list[CategorisedItem] = []
    unmatched: list[ExpenseItem] = []

    for item in items:
        match = match_category(item.raw_text, item.direction)
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
