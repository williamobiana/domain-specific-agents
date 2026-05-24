from __future__ import annotations

import re
from dataclasses import dataclass

from src.errors import ParseError


@dataclass
class ExpenseItem:
    raw_text: str
    amount: float


_AMOUNT_RE = re.compile(r'[£$€]?\s*[\d,]+(?:\.\d{1,2})?')


def _normalise_amount(raw: str) -> float:
    """Strip currency symbols, commas, and whitespace then convert to float."""
    cleaned = re.sub(r'[£$€,\s]', '', raw)
    return float(cleaned)


def _parse_line(line: str) -> ExpenseItem | None:
    """Extract a description and amount from a single line; return None if no valid pattern found."""
    match = _AMOUNT_RE.search(line)
    if not match:
        return None
    raw_amount = match.group()
    description = (line[: match.start()] + line[match.end() :]).strip()
    if not description:
        return None
    try:
        amount = _normalise_amount(raw_amount)
    except ValueError:
        return None
    return ExpenseItem(raw_text=description, amount=amount)


def parse_items(markdown_text: str) -> list[ExpenseItem]:
    """Parse a Markdown string into a list of ExpenseItem objects.
    Raises ParseError if the result is empty."""
    items = [item for line in markdown_text.splitlines() if (item := _parse_line(line)) is not None]
    if not items:
        raise ParseError("No expense items found in the provided text.")
    return items
