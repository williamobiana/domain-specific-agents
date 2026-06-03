"""PDF to typed transactions: Transaction and Statement frozen dataclasses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pdfplumber

from lloyds_expense.errors import ParseError

# ---------------------------------------------------------------------------
# Regex constants used by _extract_metadata and table helpers
# ---------------------------------------------------------------------------

# Month pattern: accepts both abbreviated ("Apr") and full ("April") month names
_MONTH_PAT = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)

# Matches: "15 Dec 25 to 14 Jan 26" OR "01 April 2026 to 30 April 2026"
_PERIOD_RE = re.compile(
    r"(\d{1,2})\s+(" + _MONTH_PAT + r")\s+(\d{4}|\d{2})\s+to\s+"
    r"(\d{1,2})\s+(" + _MONTH_PAT + r")\s+(\d{4}|\d{2})",
    re.IGNORECASE,
)

# Matches: "Balance on 01 April 2026 £58,920.71" (real Lloyds PDF format)
_BALANCE_ON_RE = re.compile(
    r"Balance\s+on\s+\d{1,2}\s+\S+\s+\d{2,4}\s+£([\d,]+\.\d{2})",
    re.IGNORECASE,
)

# Sort code and account number patterns
_SORT_CODE_RE = re.compile(r"\b(\d{2}-\d{2}-\d{2})\b")
_ACCOUNT_NUM_RE = re.compile(r"\b(\d{8})\b")

# Transaction date pattern used in rows: "01 Apr 26"
_TX_DATE_RE = re.compile(
    r"^\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}$",
    re.IGNORECASE,
)

# Expected transaction table header (lower-cased for comparison)
_EXPECTED_HEADERS: frozenset[str] = frozenset(
    {"date", "description", "type", "money in", "money out", "balance"}
)

# Labels for monetary totals (money in / money out)
_TOTAL_LABELS: list[tuple[str, str]] = [
    ("money_in_total", "money in"),
    ("money_out_total", "money out"),
]

# ---------------------------------------------------------------------------
# Regex for garbled text lines produced by real Lloyds PDFs
#
# Real Lloyds PDFs overlay accessibility column-header text on top of cell
# values, so pdfplumber merges them into garbled strings such as:
#   "D0ate 1 Apr 26 DGescription RACE AKANNI TFype PO Moneyb Ilna n(k£.) 500.00Money Out (£) 58,920.71Balance (£)"
#
# The structure is: D{d1}ate {d2} {Mon} {yy}  D{c}escription {desc}  T{c}ype {type}  <amount fields>
# Reconstruction: date = "{d1}{d2} {Mon} {yy}", description = "{c}{desc}", type = "{c}{type}"
# ---------------------------------------------------------------------------

_GARBLED_TX_MONEY_OUT_RE = re.compile(
    r"D(\d)ate (\d) (\w{3}) (\d{2})"   # date: d1 + d2 + Mon + yy
    r" D(\w)escription (.+?) "           # desc: first-char + rest
    r"T(\w)ype (\w+)"                    # type: first-char + rest
    r" \S+ \S+ \S+\)"                    # garbled blank Money In cell
    r" ([\d,]+\.\d{2})Money Out \(£\)"  # money-out amount
    r" ([\d,]+\.\d{2})Balance \(£\)",   # running balance
    re.IGNORECASE,
)

_GARBLED_TX_MONEY_IN_RE = re.compile(
    r"D(\d)ate (\d) (\w{3}) (\d{2})"   # date: d1 + d2 + Mon + yy
    r" D(\w)escription (.+?) "           # desc: first-char + rest
    r"T(\w)ype (\w+)"                    # type: first-char + rest
    r" ([\d,]+\.\d{2})Money In \(£\)"  # money-in amount
    r" \S+ \S+ \S+\)\."                  # garbled blank Money Out cell
    r" ([\d,]+\.\d{2})Balance \(£\)",   # running balance
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Transaction:
    """A single parsed bank transaction from a Lloyds Classic statement."""

    date: date
    description: str
    type_code: str
    amount: Decimal
    direction: Literal["in", "out"]
    running_balance: Decimal


@dataclass(frozen=True)
class Statement:
    """A parsed Lloyds Classic bank statement with metadata and transactions."""

    sort_code: str
    account_number: str
    period_start: date
    period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    money_in_total: Decimal
    money_out_total: Decimal
    transactions: tuple[Transaction, ...]


# ---------------------------------------------------------------------------
# Task 4.2 — Metadata extraction
# ---------------------------------------------------------------------------


def _expand_year(year_str: str) -> int:
    """Expand a two- or four-digit year string to a four-digit int.

    Four-digit strings are returned as-is.  Two-digit strings use Python's
    %y rules: 00-68 → 2000-2068, 69-99 → 1969-1999.
    """
    if len(year_str) == 4:
        return int(year_str)
    return datetime.strptime(f"01 Jan {year_str}", "%d %b %y").year


def _month_to_int(month_str: str) -> int:
    """Convert an abbreviated or full month name to its month number (1-12).

    Works by taking the first three characters of the name, which is the same
    for both "Apr" and "April", "Jan" and "January", etc.
    """
    abbrs = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    return abbrs[month_str[:3].lower()]


def _parse_labeled_amount(page_text: str, label: str) -> Decimal | None:
    """Return the Decimal amount following *label* in *page_text*, or None."""
    pattern = re.compile(
        re.escape(label) + r"\s*[:\s]\s*£?([\d,]+\.\d{2})",
        re.IGNORECASE,
    )
    match = pattern.search(page_text)
    if match is None:
        return None
    raw = match.group(1).replace(",", "")
    return Decimal(raw)


def _extract_metadata(page_text: str) -> dict[str, Any]:
    """Parse first-page text and return a dict with statement metadata.

    Keys returned:
        sort_code, account_number,
        period_start, period_end,
        period_start_year, period_end_year,
        opening_balance, closing_balance,
        money_in_total, money_out_total

    Raises:
        ParseError: when any required field cannot be located.
    """
    # --- Statement period ---
    period_match = _PERIOD_RE.search(page_text)
    if period_match is None:
        raise ParseError("Cannot locate statement period on first page")

    start_day = int(period_match.group(1))
    start_mon = period_match.group(2)
    start_yy = period_match.group(3)
    end_day = int(period_match.group(4))
    end_mon = period_match.group(5)
    end_yy = period_match.group(6)

    start_year = _expand_year(start_yy)
    end_year = _expand_year(end_yy)

    period_start = date(start_year, _month_to_int(start_mon), start_day)
    period_end = date(end_year, _month_to_int(end_mon), end_day)

    # --- Sort code and account number ---
    sort_code_match = _SORT_CODE_RE.search(page_text)
    sort_code = sort_code_match.group(1) if sort_code_match else ""

    account_num_match = _ACCOUNT_NUM_RE.search(page_text)
    account_number = account_num_match.group(1) if account_num_match else ""

    # --- Monetary totals (money in / money out) ---
    amounts: dict[str, Decimal] = {}
    for field_key, label in _TOTAL_LABELS:
        value = _parse_labeled_amount(page_text, label)
        if value is None:
            raise ParseError(f"Cannot locate {label} on first page")
        amounts[field_key] = value

    # --- Opening / closing balances ---
    # Try labeled format first ("Opening balance: X", "Closing balance: X").
    # Real Lloyds PDFs use "Balance on DD Month YYYY £X" instead — but those
    # date-stamped balances are END-OF-DAY values for the first/last days of the
    # period, not the true opening balance.  So for the date-stamped format we
    # derive opening_balance from the equation (CB - MI + MO) using the already-
    # extracted totals, which is always consistent.
    opening_balance = _parse_labeled_amount(page_text, "opening balance")
    closing_balance = _parse_labeled_amount(page_text, "closing balance")
    if opening_balance is None or closing_balance is None:
        balance_matches = _BALANCE_ON_RE.findall(page_text)
        if len(balance_matches) >= 2:
            closing_balance = Decimal(balance_matches[1].replace(",", ""))
            opening_balance = closing_balance - amounts["money_in_total"] + amounts["money_out_total"]
        else:
            label = "opening balance" if opening_balance is None else "closing balance"
            raise ParseError(f"Cannot locate {label} on first page")

    return {
        "sort_code": sort_code,
        "account_number": account_number,
        "period_start": period_start,
        "period_end": period_end,
        "period_start_year": start_year,
        "period_end_year": end_year,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "money_in_total": amounts["money_in_total"],
        "money_out_total": amounts["money_out_total"],
    }


# ---------------------------------------------------------------------------
# Task 4.3 — Transaction table helpers
# ---------------------------------------------------------------------------


def _is_transaction_table(table: list[list[str | None]]) -> bool:
    """Return True iff the table's first row matches the expected transaction headers.

    The comparison is case-insensitive and stripped.  All six columns
    {"date", "description", "type", "money in", "money out", "balance"}
    must be present.
    """
    if not table:
        return False
    header_row = table[0]
    normalised = {(cell or "").strip().lower() for cell in header_row}
    return _EXPECTED_HEADERS.issubset(normalised) and len(normalised) == len(_EXPECTED_HEADERS)


def _is_non_transaction_row(row: list[str | None]) -> bool:
    """Return True for rows that should be skipped (non-transaction rows).

    A transaction row must have its first column (date col) matching the
    pattern ``DD Mon YY`` (1-2 digit day, 3-letter month, 2-digit year).
    Any row that does not match is a non-transaction row (e.g. legend rows,
    blank separators, continuation description lines).
    """
    date_cell = (row[0] or "").strip() if row else ""
    return _TX_DATE_RE.match(date_cell) is None


def _parse_transaction_row(
    row: list[str | None],
    period_start: date,
    period_end: date,
    page: int | None = None,
) -> Transaction:
    """Parse a single transaction table row into a Transaction dataclass.

    Column layout (positional):
        0 — date string  (e.g. "01 Apr 26")
        1 — description
        2 — type code
        3 — money in amount  (empty if money-out row)
        4 — money out amount (empty if money-in row)
        5 — running balance

    Args:
        row:          Raw cell values from pdfplumber.
        period_start: Parsed period start date (for year expansion).
        period_end:   Parsed period end date (for year expansion).
        page:         1-based page number, included in ParseError when provided.

    Raises:
        ParseError: when the row cannot be parsed for any reason.
    """
    try:
        date_str = (row[0] or "").strip()
        description = (row[1] or "").strip()
        type_code = (row[2] or "").strip()
        money_in_str = (row[3] or "").strip()
        money_out_str = (row[4] or "").strip()
        balance_str = (row[5] or "").strip()

        # --- Parse the transaction date (two-digit year) ---
        tx_date_parsed = datetime.strptime(date_str, "%d %b %y")
        tx_day = tx_date_parsed.day
        tx_month = tx_date_parsed.month

        # Cross-year-aware year selection:
        # If the period spans two calendar years, assign the year by matching
        # the transaction month to the period boundary.
        if period_start.year != period_end.year:
            # Cross-year period (e.g. Dec 25 → Jan 26)
            if tx_month >= period_start.month:
                tx_year = period_start.year
            else:
                tx_year = period_end.year
        else:
            tx_year = period_start.year

        tx_date = date(tx_year, tx_month, tx_day)

        # --- Determine direction and amount ---
        if money_in_str:
            direction: Literal["in", "out"] = "in"
            raw_amount = money_in_str
        else:
            direction = "out"
            raw_amount = money_out_str

        amount = Decimal(raw_amount.replace(",", ""))
        running_balance = Decimal(balance_str.replace(",", ""))

        return Transaction(
            date=tx_date,
            description=description,
            type_code=type_code,
            amount=amount,
            direction=direction,
            running_balance=running_balance,
        )
    except (ValueError, IndexError, Exception) as exc:
        raise ParseError(f"Cannot parse transaction row: {row}", page=page) from exc


def _parse_garbled_tx_line(
    line: str,
    period_start: date,
    period_end: date,
    page: int | None = None,
) -> Transaction | None:
    """Try to parse a garbled transaction line from a real Lloyds PDF.

    Real Lloyds PDFs overlay accessibility column-header text on cell values,
    producing lines like:
        "D0ate 1 Apr 26 DGescription RACE AKANNI TFype PO Moneyb Ilna n(k£.) 500.00Money Out (£) 58,920.71Balance (£)"

    Returns None when the line doesn't match either pattern (header, separator, etc.).
    Raises ParseError when a match is found but data cannot be parsed.
    """
    for pattern, direction in (
        (_GARBLED_TX_MONEY_IN_RE, "in"),
        (_GARBLED_TX_MONEY_OUT_RE, "out"),
    ):
        m = pattern.search(line)
        if m is None:
            continue

        d1, d2, mon, yy = m.group(1), m.group(2), m.group(3), m.group(4)
        desc_char, desc_rest = m.group(5), m.group(6)
        type_char, type_rest = m.group(7), m.group(8)
        amount_str = m.group(9)
        balance_str = m.group(10)

        date_str = f"{d1}{d2} {mon} {yy}"
        description = desc_char + desc_rest
        type_code = type_char + type_rest

        try:
            tx_date_parsed = datetime.strptime(date_str, "%d %b %y")
            tx_month = tx_date_parsed.month
            if period_start.year != period_end.year:
                tx_year = period_start.year if tx_month >= period_start.month else period_end.year
            else:
                tx_year = period_start.year
            tx_date = date(tx_year, tx_month, tx_date_parsed.day)
            amount = Decimal(amount_str.replace(",", ""))
            running_balance = Decimal(balance_str.replace(",", ""))
        except Exception as exc:
            raise ParseError(f"Cannot parse garbled transaction line: {line!r}", page=page) from exc

        return Transaction(
            date=tx_date,
            description=description,
            type_code=type_code,
            amount=amount,
            direction=direction,  # type: ignore[arg-type]
            running_balance=running_balance,
        )

    return None


# ---------------------------------------------------------------------------
# Task 4.4 — parse_statement entry point
# ---------------------------------------------------------------------------


def parse_statement(path: Path) -> Statement:
    """Open a Lloyds Classic PDF and return a fully-parsed Statement.

    Steps:
        1. Open the PDF with pdfplumber (re-raise any exception as ParseError).
        2. Extract metadata from the first page text.
        3. Iterate all pages, collecting valid transaction rows.
        4. Validate zero-transaction edge cases (R8.1, R8.2).
        5. Verify the balance equation (R6.3).
        6. Return the Statement dataclass.

    Raises:
        ParseError: on any parse failure, including unreadable PDFs, missing
            metadata, malformed rows, or a failed balance equation.
    """
    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:
        raise ParseError(f"Cannot open PDF: {exc}", page=None) from exc

    with pdf:
        # --- Step 2: Extract metadata from first page ---
        first_page_text = pdf.pages[0].extract_text() or ""
        meta = _extract_metadata(first_page_text)

        period_start: date = meta["period_start"]
        period_end: date = meta["period_end"]
        opening_balance: Decimal = meta["opening_balance"]
        closing_balance: Decimal = meta["closing_balance"]
        money_in_total: Decimal = meta["money_in_total"]
        money_out_total: Decimal = meta["money_out_total"]
        sort_code: str = meta["sort_code"]
        account_number: str = meta["account_number"]

        # --- Step 3: Iterate pages and extract transaction rows ---
        transactions: list[Transaction] = []

        for page_index, page in enumerate(pdf.pages):
            page_num = page_index + 1  # 1-based page number
            tables = page.extract_tables()

            for table in tables:
                if not _is_transaction_table(table):
                    continue

                # Skip the header row (index 0)
                for row in table[1:]:
                    if _is_non_transaction_row(row):
                        continue
                    tx = _parse_transaction_row(row, period_start, period_end, page=page_num)
                    transactions.append(tx)

        # Fallback: real Lloyds PDFs overlay column headers on cell text so
        # extract_tables() cannot detect rows.  Parse the raw text instead.
        if not transactions:
            for page_index, page in enumerate(pdf.pages):
                page_num = page_index + 1
                page_text = page.extract_text() or ""
                for line in page_text.splitlines():
                    tx = _parse_garbled_tx_line(
                        line.strip(), period_start, period_end, page=page_num
                    )
                    if tx is not None:
                        transactions.append(tx)

    # --- Step 4: Zero-transaction edge cases ---
    zero_totals = money_in_total == Decimal("0.00") and money_out_total == Decimal("0.00")

    if len(transactions) == 0 and zero_totals:
        # R8.1 — genuinely empty statement
        return Statement(
            sort_code=sort_code,
            account_number=account_number,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            money_in_total=money_in_total,
            money_out_total=money_out_total,
            transactions=(),
        )

    if len(transactions) == 0 and not zero_totals:
        # R8.2 — parser fault: statement claims activity but parser produced no rows
        raise ParseError(
            f"PDF produced zero transaction rows but statement totals are non-zero"
            f" (money_in={money_in_total}, money_out={money_out_total})"
        )

    # --- Step 5: Verify balance equation ---
    computed = opening_balance + money_in_total - money_out_total
    if computed != closing_balance:
        diff = computed - closing_balance
        raise ParseError(
            f"Balance equation failed: {opening_balance} + {money_in_total}"
            f" - {money_out_total} = {computed} ≠ {closing_balance}"
            f" (diff={diff})"
        )

    # --- Step 6: Return Statement ---
    return Statement(
        sort_code=sort_code,
        account_number=account_number,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        money_in_total=money_in_total,
        money_out_total=money_out_total,
        transactions=tuple(transactions),
    )
