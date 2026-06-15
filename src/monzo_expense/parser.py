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

# Real Monzo PDFs use DD/MM/YYYY format: "01/02/2026 - 30/04/2026"
_PERIOD_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4})\s*[-–]\s*(\d{1,2})/(\d{1,2})/(\d{4})",
)

# Total outgoings appears as "-£8,082.75\nTotal outgoings" (amount before label)
_TOTAL_OUTGOINGS_RE = re.compile(
    r"-£([\d,]+\.\d{2})\s+Total\s+outgoings",
    re.IGNORECASE,
)

# Total deposits appears as "+£8,057.90\n...\nTotal deposits" (amount before label,
# with "Account number: XXXXXXXX" potentially interleaved in pdfplumber's output)
_TOTAL_DEPOSITS_RE = re.compile(
    r"\+£([\d,]+\.\d{2})[\s\S]{0,120}?Total\s+deposits",
    re.IGNORECASE,
)

# Transaction date word: DD/MM/YYYY
_TX_DATE_WORD_RE = re.compile(r"^\d{1,2}/\d{2}/\d{4}$")

# ---------------------------------------------------------------------------
# Column x-coordinate boundaries
# Derived from real PDF word position analysis (pdfplumber extract_words):
#   Date column:        x0 ≈  70.5  → boundary < 135
#   Description column: x0 ≈ 152.9  → boundary 135–395
#   Amount column:      x0 ≈ 397–420 → boundary 395–460
#   Balance column:     x0 ≈ 486–505 → boundary ≥ 460
#
# NOTE: large balance values (e.g. £1,010.97) are right-aligned and start at
# x ≈ 485–486, which is closer to the amount column than small balances
# (x ≈ 499–505). A boundary of 460 cleanly separates all observed amounts
# (≤ 420) from all observed balances (≥ 486).
# ---------------------------------------------------------------------------

_DATE_COL_X_MAX: float = 135.0
_DESC_COL_X_MAX: float = 395.0
_AMT_COL_X_MAX: float = 460.0


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


def _is_pot_page(page_text: str) -> bool:
    """Return True when the first non-empty line of the page starts with 'Pot statement'.

    Real Monzo PDFs append one or more Pot statement pages after the personal-account
    section. These always begin with 'Pot statement' as the first meaningful line.
    """
    for line in page_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.lower().startswith("pot statement")
    return False


def _group_words_by_y(
    words: list[dict[str, Any]], y_tolerance: float = 3.0
) -> dict[float, list[dict[str, Any]]]:
    """Group pdfplumber word dicts by their top (y) coordinate.

    Words within y_tolerance of an existing bucket's key are merged into that
    bucket. Returns an ordered dict sorted ascending by y (top-to-bottom).
    """
    buckets: dict[float, list[dict[str, Any]]] = {}
    for w in words:
        y = w["top"]
        match_y = next((k for k in buckets if abs(k - y) <= y_tolerance), None)
        key = match_y if match_y is not None else y
        buckets.setdefault(key, []).append(w)
    for key in buckets:
        buckets[key].sort(key=lambda w: w["x0"])
    return dict(sorted(buckets.items()))


def _split_row(
    words_in_row: list[dict[str, Any]],
) -> tuple[str, str, str, str]:
    """Split a row's words into (date_text, desc_text, amount_text, balance_text)."""
    date_parts = [w["text"] for w in words_in_row if w["x0"] < _DATE_COL_X_MAX]
    desc_parts = [
        w["text"]
        for w in words_in_row
        if _DATE_COL_X_MAX <= w["x0"] < _DESC_COL_X_MAX
    ]
    amt_parts = [
        w["text"]
        for w in words_in_row
        if _DESC_COL_X_MAX <= w["x0"] < _AMT_COL_X_MAX
    ]
    bal_parts = [w["text"] for w in words_in_row if w["x0"] >= _AMT_COL_X_MAX]
    return (
        " ".join(date_parts).strip(),
        " ".join(desc_parts).strip(),
        " ".join(amt_parts).strip(),
        " ".join(bal_parts).strip(),
    )


def _find_table_start_y(
    words: list[dict[str, Any]],
) -> float | None:
    """Return the y-coordinate of the transaction table header row, or None.

    Detects the row containing 'Date' in the date column and 'Description'
    in the description column. Used to skip metadata content on page 1.
    """
    rows = _group_words_by_y(words)
    for y, row_words in rows.items():
        date_text, desc_text, _, _ = _split_row(row_words)
        if date_text.lower() == "date" and "description" in desc_text.lower():
            return y
    return None


def _extract_metadata(page_text: str) -> dict[str, Any]:
    """Parse Monzo first-page text and return statement metadata.

    Real Monzo PDFs present amounts BEFORE their labels (due to multi-column
    layout merging in pdfplumber). For example: '-£8,082.75\\nTotal outgoings'.
    Opening balance is derived from the balance equation rather than extracted
    directly, since Monzo does not label it explicitly.

    Raises:
        ParseError: when any required field cannot be located.
    """
    # --- Statement period (DD/MM/YYYY - DD/MM/YYYY) ---
    period_match = _PERIOD_RE.search(page_text)
    if period_match is None:
        raise ParseError("Cannot locate statement period on first page")

    period_start = date(
        int(period_match.group(3)),
        int(period_match.group(2)),
        int(period_match.group(1)),
    )
    period_end = date(
        int(period_match.group(6)),
        int(period_match.group(5)),
        int(period_match.group(4)),
    )

    # --- Sort code and account number ---
    sc_match = re.search(r"\b(\d{2}-\d{2}-\d{2})\b", page_text)
    sort_code = sc_match.group(1) if sc_match else ""

    an_match = re.search(r"Account\s+number:\s+(\d+)", page_text, re.IGNORECASE)
    account_number = an_match.group(1) if an_match else ""

    # --- Total outgoings: -£X.XX before the label ---
    out_match = _TOTAL_OUTGOINGS_RE.search(page_text)
    if out_match is None:
        raise ParseError("Cannot locate Total outgoings on first page")
    total_outgoings = Decimal(out_match.group(1).replace(",", ""))

    # --- Total deposits: +£X.XX before the label ---
    dep_match = _TOTAL_DEPOSITS_RE.search(page_text)
    if dep_match is None:
        raise ParseError("Cannot locate Total deposits on first page")
    total_deposits = Decimal(dep_match.group(1).replace(",", ""))

    # --- Closing balance: last £X.XX before "Personal Account balance" ---
    pab_match = re.search(r"Personal\s+Account\s+balance", page_text, re.IGNORECASE)
    if pab_match is None:
        raise ParseError("Cannot locate Personal Account balance on first page")
    text_before_pab = page_text[: pab_match.start()]
    balance_amounts = re.findall(r"£([\d,]+\.\d{2})", text_before_pab)
    if not balance_amounts:
        raise ParseError("Cannot extract closing balance from first page")
    closing_balance = Decimal(balance_amounts[-1].replace(",", ""))

    # --- Opening balance: derived from balance equation ---
    # Monzo does not label the opening balance explicitly; derive it.
    opening_balance = closing_balance - total_deposits + total_outgoings

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


def _parse_amount_and_direction(raw: str) -> tuple[Decimal, Literal["in", "out"]]:
    """Parse a signed amount string into (abs_amount, direction).

    Never uses float; strips thousand-separator commas before constructing Decimal.
    """
    cleaned = raw.replace(",", "")
    value = Decimal(cleaned)
    if value >= 0:
        return value, "in"
    return -value, "out"


def _extract_transactions_from_words(
    words: list[dict[str, Any]],
    page_num: int | None = None,
) -> list[Transaction]:
    """Build Transaction objects from a filtered list of pdfplumber word dicts.

    Uses word x-coordinates to classify each word into one of four columns
    (date, description, amount, balance), then groups rows by y-coordinate
    and assigns description-only continuation rows to their nearest transaction
    row using the midpoint rule.
    """
    rows = _group_words_by_y(words)

    # Classify each row
    tx_rows: dict[float, tuple[str, str, str, str]] = {}  # y → (date, desc, amt, bal)
    desc_rows: list[tuple[float, str]] = []  # (y, text) for desc-only continuation rows

    for y, row_words in rows.items():
        date_text, desc_text, amount_text, balance_text = _split_row(row_words)
        if _TX_DATE_WORD_RE.match(date_text) and amount_text and balance_text:
            tx_rows[y] = (date_text, desc_text, amount_text, balance_text)
        elif desc_text and not date_text and not amount_text and not balance_text:
            desc_rows.append((y, desc_text))

    if not tx_rows:
        return []

    tx_ys = sorted(tx_rows)

    # Assign each desc-only row to the nearest transaction row (midpoint rule).
    # For rows before the first transaction or after the last, assign to the
    # nearest endpoint.
    assignments: dict[float, list[tuple[float, str]]] = {y: [] for y in tx_ys}

    for desc_y, desc_text in desc_rows:
        before = [y for y in tx_ys if y <= desc_y]
        after = [y for y in tx_ys if y > desc_y]

        if not before:
            nearest = after[0]
        elif not after:
            nearest = before[-1]
        else:
            prev_y, next_y = before[-1], after[0]
            nearest = prev_y if desc_y <= (prev_y + next_y) / 2.0 else next_y

        assignments[nearest].append((desc_y, desc_text))

    # Build Transaction objects in top-to-bottom (document) order
    transactions: list[Transaction] = []
    for tx_y in tx_ys:
        date_text, inline_desc, amount_text, balance_text = tx_rows[tx_y]
        assigned = sorted(assignments[tx_y])  # ascending y within this tx's group

        pre_parts = [text for y, text in assigned if y < tx_y]
        post_parts = [text for y, text in assigned if y > tx_y]

        desc_parts = pre_parts + ([inline_desc] if inline_desc else []) + post_parts
        full_desc = " ".join(desc_parts).strip()

        try:
            tx_date = datetime.strptime(date_text, "%d/%m/%Y").date()
            amount, direction = _parse_amount_and_direction(amount_text)
            running_balance = Decimal(balance_text.replace(",", ""))
        except Exception as exc:
            raise ParseError(
                f"Cannot parse transaction row: date={date_text!r} "
                f"amount={amount_text!r} balance={balance_text!r}",
                page=page_num,
            ) from exc

        transactions.append(
            Transaction(
                date=tx_date,
                description=full_desc,
                amount=amount,
                direction=direction,
                running_balance=running_balance,
            )
        )

    return transactions


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_statement(path: Path) -> Statement:
    """Open a Monzo personal-account PDF and return a fully-parsed Statement.

    Uses word-position extraction (pdfplumber extract_words) rather than
    extract_tables, because real Monzo PDFs use a visual layout with no
    structural table borders that pdfplumber can detect.

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

        for page_index, page in enumerate(pdf.pages):
            page_num = page_index + 1
            page_text = page.extract_text() or ""

            if _is_pot_page(page_text):
                # Pot pages always trail the personal-account section; stop here.
                break

            words = page.extract_words()

            # On page 1 the metadata header occupies most of the page.
            # Find the transaction table header row and skip everything above it.
            skip_above_y: float | None = None
            if page_index == 0:
                skip_above_y = _find_table_start_y(words)

            if skip_above_y is not None:
                words = [w for w in words if w["top"] > skip_above_y]

            page_txs = _extract_transactions_from_words(words, page_num=page_num)
            transactions.extend(page_txs)

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
            f"PDF produced zero transaction rows but statement totals are non-zero "
            f"(total_deposits={total_deposits}, total_outgoings={total_outgoings})"
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
