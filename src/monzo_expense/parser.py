"""PDF to typed transactions: Transaction and Statement frozen dataclasses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pdfplumber

from monzo_expense.errors import ParseError

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

_MONTH_PAT = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)

# Monzo PDFs always use four-digit years: "01 Apr 2026 to 30 Apr 2026"
_PERIOD_RE = re.compile(
    r"(\d{1,2})\s+(" + _MONTH_PAT + r")\s+(\d{4})\s+to\s+"
    r"(\d{1,2})\s+(" + _MONTH_PAT + r")\s+(\d{4})",
    re.IGNORECASE,
)

_SORT_CODE_RE = re.compile(r"\b(\d{2}-\d{2}-\d{2})\b")
_ACCOUNT_NUM_RE = re.compile(r"\b(\d{8})\b")

# Transaction date in table rows: "01 Apr 2026" (four-digit year)
_TX_DATE_RE = re.compile(
    r"^\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}$",
    re.IGNORECASE,
)

# Expected Monzo transaction table headers
_EXPECTED_HEADERS: frozenset[str] = frozenset({"date", "description", "amount", "balance"})

# Pot page markers
_POT_HEADING_RE = re.compile(r"^[A-Z][A-Za-z\s]+ Pot\b", re.MULTILINE)
_POTS_RE = re.compile(r"^Pots$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Transaction:
    """A single parsed transaction from a Monzo personal-account statement."""

    date: date
    description: str
    amount: Decimal
    direction: Literal["in", "out"]
    running_balance: Decimal


@dataclass(frozen=True)
class Statement:
    """A parsed Monzo bank statement with metadata and transactions."""

    sort_code: str
    account_number: str
    period_start: date
    period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_deposits: Decimal
    total_outgoings: Decimal
    transactions: tuple[Transaction, ...]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _month_to_int(month_str: str) -> int:
    abbrs = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    return abbrs[month_str[:3].lower()]


def _parse_labeled_amount(page_text: str, label: str) -> Decimal | None:
    pattern = re.compile(
        re.escape(label) + r"\s*[:\s]\s*£?([\d,]+\.\d{2})",
        re.IGNORECASE,
    )
    match = pattern.search(page_text)
    if match is None:
        return None
    return Decimal(match.group(1).replace(",", ""))


def _extract_metadata(page_text: str) -> dict[str, Any]:
    """Parse Monzo first-page text and return statement metadata.

    Raises:
        ParseError: when any required field cannot be located.
    """
    period_match = _PERIOD_RE.search(page_text)
    if period_match is None:
        raise ParseError("Cannot locate statement period on first page")

    start_day = int(period_match.group(1))
    start_mon = period_match.group(2)
    start_year = int(period_match.group(3))
    end_day = int(period_match.group(4))
    end_mon = period_match.group(5)
    end_year = int(period_match.group(6))

    period_start = date(start_year, _month_to_int(start_mon), start_day)
    period_end = date(end_year, _month_to_int(end_mon), end_day)

    sort_code_match = _SORT_CODE_RE.search(page_text)
    sort_code = sort_code_match.group(1) if sort_code_match else ""

    account_num_match = _ACCOUNT_NUM_RE.search(page_text)
    account_number = account_num_match.group(1) if account_num_match else ""

    opening_balance = _parse_labeled_amount(page_text, "opening balance")
    if opening_balance is None:
        raise ParseError("Cannot locate opening balance on first page")

    closing_balance = _parse_labeled_amount(page_text, "closing balance")
    if closing_balance is None:
        raise ParseError("Cannot locate closing balance on first page")

    total_deposits = _parse_labeled_amount(page_text, "total deposits")
    if total_deposits is None:
        raise ParseError("Cannot locate Total deposits on first page")

    total_outgoings = _parse_labeled_amount(page_text, "total outgoings")
    if total_outgoings is None:
        raise ParseError("Cannot locate Total outgoings on first page")

    return {
        "sort_code": sort_code,
        "account_number": account_number,
        "period_start": period_start,
        "period_end": period_end,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "total_deposits": total_deposits,
        "total_outgoings": total_outgoings,
    }


def _is_pot_page(page_text: str) -> bool:
    """Return True when the page text contains a Pot-section marker."""
    lines = page_text.splitlines()
    threshold = max(1, len(lines) // 5)
    first_lines = "\n".join(lines[:threshold])
    return bool(_POT_HEADING_RE.search(first_lines) or _POTS_RE.search(first_lines))


def _is_transaction_table(table: list[list[str | None]]) -> bool:
    """Return True when the table's first row matches Monzo transaction column headers."""
    if not table:
        return False
    header_row = table[0]
    normalised = {(cell or "").strip().lower() for cell in header_row}
    return _EXPECTED_HEADERS.issubset(normalised) and len(normalised) == len(_EXPECTED_HEADERS)


def _is_continuation_row(row: list[str | None]) -> bool:
    """Return True for description-continuation rows.

    A continuation row has an empty date cell, non-empty description cell,
    and empty amount and balance cells.
    """
    date_cell = (row[0] or "").strip()
    desc_cell = (row[1] or "").strip() if len(row) > 1 else ""
    amount_cell = (row[2] or "").strip() if len(row) > 2 else ""
    balance_cell = (row[3] or "").strip() if len(row) > 3 else ""
    return not date_cell and bool(desc_cell) and not amount_cell and not balance_cell


def _parse_amount_and_direction(raw: str) -> tuple[Decimal, Literal["in", "out"]]:
    """Parse a signed amount string into (abs_amount, direction).

    Never uses float; strips thousand-separator commas before constructing Decimal.
    """
    cleaned = raw.replace(",", "")
    value = Decimal(cleaned)
    if value >= 0:
        return value, "in"
    return -value, "out"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_statement(path: Path) -> Statement:
    """Open a Monzo personal-account PDF and return a fully-parsed Statement.

    Raises:
        ParseError: on any parse failure including unreadable files, missing
            metadata, malformed rows, or a failed balance equation.
    """
    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:
        raise ParseError(f"Cannot open PDF: {exc}", page=None) from exc

    with pdf:
        first_page_text = pdf.pages[0].extract_text() or ""
        meta = _extract_metadata(first_page_text)

        period_start: date = meta["period_start"]
        period_end: date = meta["period_end"]
        opening_balance: Decimal = meta["opening_balance"]
        closing_balance: Decimal = meta["closing_balance"]
        total_deposits: Decimal = meta["total_deposits"]
        total_outgoings: Decimal = meta["total_outgoings"]
        sort_code: str = meta["sort_code"]
        account_number: str = meta["account_number"]

        transactions: list[Transaction] = []

        # Pending-row accumulator for description-joining
        pending_date: date | None = None
        pending_desc_parts: list[str] = []
        pending_amount: Decimal = Decimal("0")
        pending_direction: Literal["in", "out"] = "in"
        pending_balance: Decimal = Decimal("0")

        def _emit_pending() -> None:
            if pending_date is not None:
                transactions.append(
                    Transaction(
                        date=pending_date,
                        description=" ".join(pending_desc_parts),
                        amount=pending_amount,
                        direction=pending_direction,
                        running_balance=pending_balance,
                    )
                )

        in_pot_section = False

        for page_index, page in enumerate(pdf.pages):
            if in_pot_section:
                break

            page_num = page_index + 1
            page_text = page.extract_text() or ""

            if _is_pot_page(page_text):
                in_pot_section = True
                _emit_pending()
                pending_date = None
                break

            tables = page.extract_tables()
            for table in tables:
                if not _is_transaction_table(table):
                    continue

                for row in table[1:]:
                    date_cell = (row[0] or "").strip()

                    if _TX_DATE_RE.match(date_cell):
                        # New transaction row — emit any pending first
                        _emit_pending()
                        pending_date = None

                        try:
                            tx_date = datetime.strptime(date_cell, "%d %b %Y").date()
                            amount_str = (row[2] or "").strip()
                            balance_str = (row[3] or "").strip()
                            parsed_amount, direction = _parse_amount_and_direction(amount_str)
                            run_bal = Decimal(balance_str.replace(",", ""))
                        except Exception as exc:
                            raise ParseError(
                                f"Cannot parse transaction row: {row}", page=page_num
                            ) from exc

                        pending_date = tx_date
                        pending_desc_parts = [(row[1] or "").strip()]
                        pending_amount = parsed_amount
                        pending_direction = direction
                        pending_balance = run_bal

                    elif _is_continuation_row(row):
                        desc_text = (row[1] or "").strip()
                        if desc_text:
                            pending_desc_parts.append(desc_text)

        # Emit the last pending transaction
        _emit_pending()

    # Zero-transaction edge cases
    zero_totals = (
        total_deposits == Decimal("0.00") and total_outgoings == Decimal("0.00")
    )

    if len(transactions) == 0 and zero_totals:
        return Statement(
            sort_code=sort_code,
            account_number=account_number,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_deposits=total_deposits,
            total_outgoings=total_outgoings,
            transactions=(),
        )

    if len(transactions) == 0 and not zero_totals:
        raise ParseError(
            f"PDF produced zero transaction rows but statement totals are non-zero"
            f" (total_deposits={total_deposits}, total_outgoings={total_outgoings})"
        )

    # Verify balance equation
    computed = opening_balance + total_deposits - total_outgoings
    if computed != closing_balance:
        diff = computed - closing_balance
        raise ParseError(
            f"Balance equation failed: {opening_balance} + {total_deposits}"
            f" - {total_outgoings} = {computed} ≠ {closing_balance}"
            f" (diff={diff})"
        )

    return Statement(
        sort_code=sort_code,
        account_number=account_number,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_deposits=total_deposits,
        total_outgoings=total_outgoings,
        transactions=tuple(transactions),
    )
