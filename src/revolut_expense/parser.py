"""PDF to typed transactions: Transaction and Statement frozen dataclasses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pdfplumber

from revolut_expense.errors import ParseError

# ---------------------------------------------------------------------------
# Column x-coordinate boundaries (derived from header word positions in a
# real Revolut GBP statement PDF).
#
#   Date       : x0 <  120   (e.g. 'Apr' at 42.7, '1,' at 57.5, '2026' at 65.8)
#   Description: 120 ≤ x0 < 330   (e.g. 'Shell' at 124.8)
#   Money out  : 330 ≤ x0 < 415   (header 'Money' at 335.1; amounts start at 335.1)
#   Money in   : 415 ≤ x0 < 510   (header 'Money' at 417.1; amounts start at 417.1)
#   Balance    : x0 ≥ 510         (header 'Balance' at 526.3; amounts right-aligned
#                                   to right edge ~555.6, so x0 ≥ 513 for 10-char values)
# ---------------------------------------------------------------------------
_DATE_COL_X_MAX: float = 120.0
_DESC_COL_X_MAX: float = 330.0
_MONEY_OUT_COL_X_MAX: float = 415.0
_BALANCE_COL_X_MIN: float = 510.0

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Balance summary "Total" row: "Total £open £money_out £money_in £close"
# Values appear in sequence (opening balance, money out total, money in total,
# closing balance) because the column headers are on a separate preceding row.
#
# A single PDF may contain more than one such block: Revolut splits a
# statement into consecutive sub-statements whenever the underlying product
# changes mid-period (e.g. an e-money account migrated to a Revolut Bank UK
# Ltd current account). Each sub-statement has its own "Balance summary" and
# "Account transactions from ... to ..." header, on its own page. All blocks
# in the document are aggregated to reconcile against the full transaction
# list, which spans every sub-statement.
_TOTAL_ROW_RE = re.compile(
    r"Total\s+"
    r"£([\d,]+\.\d{2})\s+"  # group 1: opening balance
    r"£([\d,]+\.\d{2})\s+"  # group 2: money out total
    r"£([\d,]+\.\d{2})\s+"  # group 3: money in total
    r"£([\d,]+\.\d{2})",    # group 4: closing balance
)

# Period header uses full month names: "April 1, 2026 to May 24, 2026"
_PERIOD_RE = re.compile(
    r"Account transactions from\s+(\w+ \d{1,2}, \d{4})\s+to\s+(\w+ \d{1,2}, \d{4})",
    re.IGNORECASE,
)

# Transaction dates use 3-letter abbreviated month names: "Apr 1, 2026"
_TX_DATE_RE = re.compile(r"^[A-Za-z]{3} \d{1,2}, \d{4}$")

# Valid first-token prefixes for description continuation rows.  Lines that do
# not start with one of these (e.g. footer "Reference 900562)." without a
# colon) are silently ignored even when they appear in the description column.
_CONTINUATION_PREFIXES = (
    "To:",
    "From:",
    "Card:",
    "Reference:",
    "Revolut Rate",
    "Fee: £",
)


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Transaction:
    """A single parsed transaction from a Revolut personal-account statement."""

    date: date
    description: str
    amount: Decimal
    direction: Literal["in", "out"]
    running_balance: Decimal


@dataclass(frozen=True)
class Statement:
    """A parsed Revolut bank statement with metadata and transactions."""

    sort_code: str
    account_number: str
    iban: str
    bic: str
    period_start: date
    period_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_money_in: Decimal
    total_money_out: Decimal
    transactions: tuple[Transaction, ...]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_metadata(page_texts: list[str]) -> dict[str, object]:
    """Parse Revolut statement text and return aggregated statement metadata.

    Scans every page for "Balance summary" Total rows and "Account
    transactions from ... to ..." period headers, since a single PDF may
    concatenate multiple sub-statements (see _TOTAL_ROW_RE). Money in/out
    totals are summed across all blocks; the opening balance is taken from
    the first block and the closing balance from the last, so the balance
    equation holds across the full document.

    Raises:
        ParseError: when any required field cannot be located.
    """
    total_matches = [m for text in page_texts for m in _TOTAL_ROW_RE.finditer(text)]
    if not total_matches:
        raise ParseError("Cannot locate any 'Total' balance summary row in statement")

    opening_balance = Decimal(total_matches[0].group(1).replace(",", ""))
    closing_balance = Decimal(total_matches[-1].group(4).replace(",", ""))
    total_money_out = sum(
        (Decimal(m.group(2).replace(",", "")) for m in total_matches), Decimal("0.00")
    )
    total_money_in = sum(
        (Decimal(m.group(3).replace(",", "")) for m in total_matches), Decimal("0.00")
    )

    # Statement period from every "Account transactions" header (full month names),
    # spanning the earliest start and latest end across all sub-statements.
    period_matches = [m for text in page_texts for m in _PERIOD_RE.finditer(text)]
    if not period_matches:
        raise ParseError("Cannot locate statement period in statement")
    period_start = min(
        datetime.strptime(m.group(1), "%B %d, %Y").date() for m in period_matches
    )
    period_end = max(
        datetime.strptime(m.group(2), "%B %d, %Y").date() for m in period_matches
    )

    # Account metadata — informational only; absence does not fail the parse
    first_page_text = page_texts[0]
    sc_match = re.search(r"Sort Code\s+(\d+)", first_page_text, re.IGNORECASE)
    if sc_match:
        raw = sc_match.group(1)
        sort_code = f"{raw[:2]}-{raw[2:4]}-{raw[4:6]}" if len(raw) == 6 else raw
    else:
        sort_code = ""

    an_match = re.search(r"Account Number\s+(\d+)", first_page_text, re.IGNORECASE)
    account_number = an_match.group(1) if an_match else ""

    iban_match = re.search(r"IBAN\s+(GB\w+)", first_page_text, re.IGNORECASE)
    iban = iban_match.group(1) if iban_match else ""

    bic_match = re.search(r"BIC\s+([A-Z0-9]{4,11})", first_page_text, re.IGNORECASE)
    bic = bic_match.group(1) if bic_match else ""

    return {
        "sort_code": sort_code,
        "account_number": account_number,
        "iban": iban,
        "bic": bic,
        "period_start": period_start,
        "period_end": period_end,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "total_money_in": total_money_in,
        "total_money_out": total_money_out,
    }


def _group_words_by_y(
    words: list[dict],  # type: ignore[type-arg]
    y_tolerance: float = 3.0,
) -> list[list[dict]]:  # type: ignore[type-arg]
    """Group pdfplumber word dicts into rows by 'top' coordinate.

    Words within y_tolerance of the row's first word are merged into the same
    row; otherwise a new row is started. Returns rows in top-to-bottom order,
    each row sorted by x0 (left-to-right).
    """
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: w["top"])
    rows: list[list[dict]] = []  # type: ignore[type-arg]
    current_row: list[dict] = [sorted_words[0]]  # type: ignore[type-arg]
    current_top = sorted_words[0]["top"]

    for word in sorted_words[1:]:
        if abs(word["top"] - current_top) <= y_tolerance:
            current_row.append(word)
        else:
            rows.append(sorted(current_row, key=lambda w: w["x0"]))
            current_row = [word]
            current_top = word["top"]
    rows.append(sorted(current_row, key=lambda w: w["x0"]))
    return rows


def _detect_section(
    row_text: str,
) -> Literal["pending", "account_transactions", "reverted"] | None:
    """Return section name if the full row text is a section header, else None."""
    lower = row_text.strip().lower()
    if lower.startswith("pending from"):
        return "pending"
    if lower.startswith("account transactions from"):
        return "account_transactions"
    if lower.startswith("reverted from"):
        return "reverted"
    return None


def _is_valid_continuation(desc_text: str) -> bool:
    """Return True for recognised description continuation-row prefixes.

    Filters out footer lines like "Reference 900562). Registered address:" that
    appear in the description column but are not part of any transaction.
    """
    return any(desc_text.startswith(prefix) for prefix in _CONTINUATION_PREFIXES) or bool(
        re.match(r"^\d", desc_text)  # currency-amount lines after "Revolut Rate …"
    )


def _parse_amount_columns(
    money_out: str, money_in: str
) -> tuple[Decimal, Literal["in", "out"]]:
    """Parse the two amount columns and return (abs_amount, direction).

    Never uses float; strips £ prefix and thousand-separator commas.
    Raises ParseError if both columns are populated (R2.4).
    """
    out_str = money_out.lstrip("£").replace(",", "").strip()
    in_str = money_in.lstrip("£").replace(",", "").strip()

    if out_str and not in_str:
        return Decimal(out_str), "out"
    if in_str and not out_str:
        return Decimal(in_str), "in"
    raise ParseError("Row has values in both Money out and Money in columns")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_statement(path: Path) -> Statement:
    """Open a Revolut personal-account PDF and return a fully-parsed Statement.

    Revolut PDFs do not produce usable table structures via extract_tables().
    This parser uses:
      - extract_text() on every page to extract balance summary and period
        metadata, aggregated across any concatenated sub-statements
      - extract_words() on all pages with x-coordinate column detection to
        extract transactions, section boundaries, and description continuations

    Raises:
        ParseError: on any parse failure including unreadable files, missing
            metadata, malformed rows, or a failed balance equation.
    """
    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:
        raise ParseError(f"Cannot open PDF: {exc}", page=None) from exc

    with pdf:
        # Extract metadata across all pages (a PDF may concatenate multiple
        # sub-statements, each with its own balance summary and period header)
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        meta = _extract_metadata(page_texts)

        period_start: date = meta["period_start"]  # type: ignore[assignment]
        period_end: date = meta["period_end"]  # type: ignore[assignment]
        opening_balance: Decimal = meta["opening_balance"]  # type: ignore[assignment]
        closing_balance: Decimal = meta["closing_balance"]  # type: ignore[assignment]
        total_money_in: Decimal = meta["total_money_in"]  # type: ignore[assignment]
        total_money_out: Decimal = meta["total_money_out"]  # type: ignore[assignment]
        sort_code: str = meta["sort_code"]  # type: ignore[assignment]
        account_number: str = meta["account_number"]  # type: ignore[assignment]
        iban: str = meta["iban"]  # type: ignore[assignment]
        bic: str = meta["bic"]  # type: ignore[assignment]

        # Verify balance equation before parsing any transactions (R7.3)
        computed = opening_balance + total_money_in - total_money_out
        if computed != closing_balance:
            diff = computed - closing_balance
            raise ParseError(
                f"Balance equation failed: {opening_balance} + {total_money_in}"
                f" - {total_money_out} = {computed} ≠ {closing_balance}"
                f" (diff={diff})"
            )

        transactions: list[Transaction] = []

        # Section state machine — maintained across all pages
        current_section: str | None = None

        # Pending-row accumulator for description joining across continuation rows
        pending_date: date | None = None
        pending_desc_parts: list[str] = []
        pending_money_out: str = ""
        pending_money_in: str = ""
        pending_balance: str = ""

        def _emit_pending() -> None:
            nonlocal pending_date, pending_desc_parts
            nonlocal pending_money_out, pending_money_in, pending_balance
            if pending_date is None:
                return
            try:
                amount, direction = _parse_amount_columns(
                    pending_money_out, pending_money_in
                )
                balance = Decimal(pending_balance.lstrip("£").replace(",", ""))
            except Exception as exc:
                raise ParseError(f"Cannot parse transaction: {exc}") from exc
            transactions.append(
                Transaction(
                    date=pending_date,
                    description=" ".join(pending_desc_parts),
                    amount=amount,
                    direction=direction,
                    running_balance=balance,
                )
            )
            pending_date = None
            pending_desc_parts = []
            pending_money_out = ""
            pending_money_in = ""
            pending_balance = ""

        for page_index, page in enumerate(pdf.pages):
            page_num = page_index + 1
            words = page.extract_words()
            rows = _group_words_by_y(words)

            for row_words in rows:
                if not row_words:
                    continue

                # Full row text for section detection (checked before column split
                # because section headers span the full width)
                row_text = " ".join(w["text"] for w in row_words)
                section = _detect_section(row_text)
                if section is not None:
                    _emit_pending()
                    current_section = section
                    continue

                # Skip rows outside the Account transactions section
                if current_section != "account_transactions":
                    continue

                # Split words into columns by x0 position
                date_words = [w for w in row_words if w["x0"] < _DATE_COL_X_MAX]
                desc_words = [
                    w for w in row_words
                    if _DATE_COL_X_MAX <= w["x0"] < _DESC_COL_X_MAX
                ]
                money_out_words = [
                    w for w in row_words
                    if _DESC_COL_X_MAX <= w["x0"] < _MONEY_OUT_COL_X_MAX
                ]
                money_in_words = [
                    w for w in row_words
                    if _MONEY_OUT_COL_X_MAX <= w["x0"] < _BALANCE_COL_X_MIN
                ]
                balance_words = [
                    w for w in row_words if w["x0"] >= _BALANCE_COL_X_MIN
                ]

                # New transaction row: date column has words matching "MMM D, YYYY"
                date_text = " ".join(w["text"] for w in date_words)
                if _TX_DATE_RE.match(date_text):
                    _emit_pending()
                    try:
                        tx_date = datetime.strptime(date_text, "%b %d, %Y").date()
                    except ValueError as exc:
                        raise ParseError(
                            f"Cannot parse transaction date: {date_text!r}",
                            page=page_num,
                        ) from exc
                    pending_date = tx_date
                    pending_desc_parts = (
                        [" ".join(w["text"] for w in desc_words)] if desc_words else []
                    )
                    pending_money_out = " ".join(w["text"] for w in money_out_words)
                    pending_money_in = " ".join(w["text"] for w in money_in_words)
                    pending_balance = " ".join(w["text"] for w in balance_words)
                    continue

                # Continuation row: no date words, has description words,
                # and a pending transaction is open
                if not date_words and desc_words and pending_date is not None:
                    desc_text = " ".join(w["text"] for w in desc_words)
                    # Guard against footer lines (e.g. "Reference 900562).")
                    # that appear in the description column but lack a colon
                    if _is_valid_continuation(desc_text):
                        pending_desc_parts.append(desc_text)
                    continue

                # All other rows (column headers, account summaries, footers,
                # page headers) are silently ignored

        # Emit the final pending transaction
        _emit_pending()

    # Zero-transaction edge cases
    zero_totals = (
        total_money_in == Decimal("0.00") and total_money_out == Decimal("0.00")
    )

    if len(transactions) == 0 and zero_totals:
        return Statement(
            sort_code=sort_code,
            account_number=account_number,
            iban=iban,
            bic=bic,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_money_in=total_money_in,
            total_money_out=total_money_out,
            transactions=(),
        )

    if len(transactions) == 0:
        raise ParseError(
            f"PDF produced zero transaction rows but statement totals are non-zero "
            f"(total_money_in={total_money_in}, total_money_out={total_money_out})"
        )

    return Statement(
        sort_code=sort_code,
        account_number=account_number,
        iban=iban,
        bic=bic,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_money_in=total_money_in,
        total_money_out=total_money_out,
        transactions=tuple(transactions),
    )
