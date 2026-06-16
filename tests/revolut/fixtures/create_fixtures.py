"""Standalone script to generate synthetic Revolut statement PDF fixtures for testing.

Run with: uv run python tests/revolut/fixtures/create_fixtures.py

Revolut PDF layout (table columns): Date | Description | Money out | Money in | Balance
Three section headers:
  - "Pending from <start> to <end>"
  - "Account transactions from <start> to <end>"
  - "Reverted from <start> to <end>"

Page 1 must contain a Balance summary block with labelled values and the period header.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FIXTURES_DIR = Path(__file__).parent

styles = getSampleStyleSheet()

_COL_WIDTHS = [2.5 * cm, 8.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]

_TX_HEADER = ["Date", "Description", "Money out", "Money in", "Balance"]


def _table_style(section_row_indices: list[int] | None = None) -> TableStyle:
    commands: list[tuple] = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]
    if section_row_indices:
        for idx in section_row_indices:
            # Span section header across all 5 columns so pdfplumber sees full text
            commands.append(("SPAN", (0, idx), (-1, idx)))
            commands.append(("BACKGROUND", (0, idx), (-1, idx), colors.lightblue))
    return TableStyle(commands)


def _section_row(header: str) -> list[str]:
    """A section header row — first cell contains the header phrase (will be spanned)."""
    return [header, "", "", "", ""]


def _meta(lines: list[str]) -> list[Paragraph]:
    return [Paragraph(line, styles["Normal"]) for line in lines]


def _page1_meta(
    sort_code: str,
    account_number: str,
    iban: str,
    bic: str,
    period_start_long: str,
    period_end_long: str,
    opening: str,
    money_out: str,
    money_in: str,
    closing: str,
) -> list[Paragraph]:
    """Generate page-1 metadata lines matching Revolut's layout."""
    return _meta(
        [
            f"Sort code: {sort_code}",
            f"Account number: {account_number}",
            f"IBAN: {iban}",
            f"BIC: {bic}",
            # Period header — must match _PERIOD_RE in parser.py
            f"Account transactions from {period_start_long} to {period_end_long}",
            # Balance summary block — labels with £ values
            f"Opening balance £{opening}",
            f"Money out £{money_out}",
            f"Money in £{money_in}",
            f"Closing balance £{closing}",
        ]
    )


# ---------------------------------------------------------------------------
# Fixture 1 — statement_minimal.pdf
# Single month April 2026, 4 transactions, continuation rows, thousand-separator
# ---------------------------------------------------------------------------


def create_minimal(out: Path) -> None:
    """Single-month April 2026 statement with 4 transactions.

    Transactions:
      1. £1,500.00 in (Salary, with Reference: continuation)  → direction=in
      2. £80.00 out (Morrisons)                               → direction=out
      3. £50.00 out (To: address continuation)                → direction=out
      4. £30.00 out (Lebara)                                  → direction=out

    Totals: money_in=1500.00, money_out=160.00
    Opening=500.00, Closing=500+1500-160=1840.00
    """
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _page1_meta(
        sort_code="04-00-04",
        account_number="12345678",
        iban="GB29REVO00997012345678",
        bic="REVOGB21",
        period_start_long="April 1, 2026",
        period_end_long="April 30, 2026",
        opening="500.00",
        money_out="160.00",
        money_in="1,500.00",
        closing="1840.00",
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        _TX_HEADER,
        _section_row("Account transactions from April 1, 2026 to April 30, 2026"),
        ["Apr 1, 2026", "Payment from NATWEST HRPS PAYRO", "", "£1,500.00", "£2,000.00"],
        ["", "Reference: Salary April 2026", "", "", ""],
        ["Apr 10, 2026", "Morrisons", "£80.00", "", "£1,920.00"],
        ["", "To: 8 Glasgow Road, Dumfries", "", "", ""],
        ["Apr 20, 2026", "Lebara", "£50.00", "", "£1,870.00"],
        ["Apr 25, 2026", "Dghb Catering", "£30.00", "", "£1,840.00"],
    ]
    t = Table(tx_data, colWidths=_COL_WIDTHS)
    t.setStyle(_table_style(section_row_indices=[1]))
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 2 — statement_multi_month.pdf
# April and May 2026, ~8 transactions per month, continuation rows
# ---------------------------------------------------------------------------


def create_multi_month(out: Path) -> None:
    """Two-month April–May 2026 statement.

    April:  money_in=3000.00, money_out=480.00
    May:    money_in=1500.00, money_out=280.00
    Total:  money_in=4500.00, money_out=760.00
    Opening=1000.00, Closing=1000+4500-760=4740.00
    """
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _page1_meta(
        sort_code="04-00-04",
        account_number="12345678",
        iban="GB29REVO00997012345678",
        bic="REVOGB21",
        period_start_long="April 1, 2026",
        period_end_long="May 31, 2026",
        opening="1000.00",
        money_out="760.00",
        money_in="4500.00",
        closing="4740.00",
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        _TX_HEADER,
        _section_row("Account transactions from April 1, 2026 to May 31, 2026"),
        # April transactions (money_in=3000, money_out=480)
        ["Apr 1, 2026", "Payment from NATWEST HRPS PAYRO", "", "£3,000.00", "£4,000.00"],
        ["", "Reference: Salary April 2026", "", "", ""],
        ["Apr 5, 2026", "Morrisons", "£80.00", "", "£3,920.00"],
        ["", "To: 8 Glasgow Road, Dumfries", "", "", ""],
        ["Apr 10, 2026", "Tesco", "£60.00", "", "£3,860.00"],
        ["Apr 15, 2026", "Lebara", "£20.00", "", "£3,840.00"],
        ["", "Reference: April mobile bill", "", "", ""],
        ["Apr 20, 2026", "Dghb Catering", "£30.00", "", "£3,810.00"],
        ["Apr 25, 2026", "Hargreaves Lansdown", "£200.00", "", "£3,610.00"],
        ["", "To: 1 College Road, Bristol", "", "", ""],
        ["Apr 28, 2026", "Trainline", "£45.00", "", "£3,565.00"],
        ["", "Reference: Manchester trip", "", "", ""],
        ["Apr 30, 2026", "Lidl", "£45.00", "", "£3,520.00"],
        # May transactions (money_in=1500, money_out=280)
        ["May 1, 2026", "Payment from NATWEST HRPS PAYRO", "", "£1,500.00", "£5,020.00"],
        ["", "Reference: Salary May 2026", "", "", ""],
        ["May 5, 2026", "Morrisons", "£70.00", "", "£4,950.00"],
        ["", "To: 15 High Street, Dumfries", "", "", ""],
        ["May 10, 2026", "Lebara", "£20.00", "", "£4,930.00"],
        ["May 15, 2026", "Greggs", "£25.00", "", "£4,905.00"],
        ["May 20, 2026", "Shell", "£100.00", "", "£4,805.00"],
        ["", "To: 42 Main Road, Dumfries", "", "", ""],
        ["May 25, 2026", "Anthropic", "£65.00", "", "£4,740.00"],
    ]
    t = Table(tx_data, colWidths=_COL_WIDTHS)
    t.setStyle(_table_style(section_row_indices=[1]))
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 3 — statement_with_pending_and_reverted.pdf
# Contains Pending, Account transactions, and Reverted sections
# ---------------------------------------------------------------------------


def create_with_pending_and_reverted(out: Path) -> None:
    """Statement with Pending, Account transactions, and Reverted sections.

    Account transactions only: money_in=500.00, money_out=80.00
    Opening=1000.00, Closing=1000+500-80=1420.00
    Pending and Reverted rows must be excluded.
    """
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _page1_meta(
        sort_code="04-00-04",
        account_number="12345678",
        iban="GB29REVO00997012345678",
        bic="REVOGB21",
        period_start_long="April 1, 2026",
        period_end_long="April 30, 2026",
        opening="1000.00",
        money_out="80.00",
        money_in="500.00",
        closing="1420.00",
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        _TX_HEADER,
        # Pending section — must be excluded
        _section_row("Pending from April 28, 2026 to April 30, 2026"),
        ["Apr 29, 2026", "PENDING PAYMENT", "£999.00", "", "£1.00"],
        # Account transactions section — only these are included
        _section_row("Account transactions from April 1, 2026 to April 27, 2026"),
        ["Apr 1, 2026", "Payment from NATWEST HRPS PAYRO", "", "£500.00", "£1,500.00"],
        ["", "Reference: Salary", "", "", ""],
        ["Apr 15, 2026", "Morrisons", "£80.00", "", "£1,420.00"],
        # Reverted section — must be excluded
        _section_row("Reverted from April 10, 2026 to April 10, 2026"),
        ["Apr 10, 2026", "REVERTED PAYMENT", "", "£50.00", "£1,420.00"],
    ]
    t = Table(tx_data, colWidths=_COL_WIDTHS)
    t.setStyle(_table_style(section_row_indices=[1, 3, 7]))
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 4 — statement_empty.pdf
# Zero transactions, zero totals → should return Statement with empty tuple
# ---------------------------------------------------------------------------


def create_empty(out: Path) -> None:
    """Statement with zero transactions and zero totals."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _page1_meta(
        sort_code="04-00-04",
        account_number="12345678",
        iban="GB29REVO00997012345678",
        bic="REVOGB21",
        period_start_long="April 1, 2026",
        period_end_long="April 30, 2026",
        opening="0.00",
        money_out="0.00",
        money_in="0.00",
        closing="0.00",
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        _TX_HEADER,
        _section_row("Account transactions from April 1, 2026 to April 30, 2026"),
    ]
    t = Table(tx_data, colWidths=_COL_WIDTHS)
    t.setStyle(_table_style(section_row_indices=[1]))
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 5 — statement_bad_balance.pdf
# Balance equation intentionally wrong
# ---------------------------------------------------------------------------


def create_bad_balance(out: Path) -> None:
    """Statement where opening + money_in - money_out ≠ closing balance."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _page1_meta(
        sort_code="04-00-04",
        account_number="12345678",
        iban="GB29REVO00997012345678",
        bic="REVOGB21",
        period_start_long="April 1, 2026",
        period_end_long="April 30, 2026",
        opening="1000.00",
        money_out="200.00",
        money_in="500.00",
        closing="9999.00",  # should be 1300.00
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        _TX_HEADER,
        _section_row("Account transactions from April 1, 2026 to April 30, 2026"),
        ["Apr 1, 2026", "Payment from NATWEST HRPS PAYRO", "", "£500.00", "£1,500.00"],
        ["Apr 15, 2026", "Morrisons", "£200.00", "", "£1,300.00"],
    ]
    t = Table(tx_data, colWidths=_COL_WIDTHS)
    t.setStyle(_table_style(section_row_indices=[1]))
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Rules fixture — rules_example.yaml
# Covers all transactions in the fixture PDFs
# ---------------------------------------------------------------------------


def create_rules_yaml(out: Path) -> None:
    """Write a rules YAML file that matches all fixture transactions."""
    content = """\
rules:
  # Salary / inflows
  - match_regex: "^Payment from NATWEST HRPS PAYRO"
    direction: in
    category: "Salary"

  # Food supplies
  - match_regex: "^Morrisons"
    category: "Food Supplies"
  - match_regex: "^Tesco"
    category: "Food Supplies"
  - match_regex: "^Lidl"
    category: "Food Supplies"

  # Eating out
  - match_regex: "^Dghb Catering"
    category: "Eating Out"
  - match_regex: "^Greggs"
    category: "Eating Out"

  # Phone & Internet
  - match_regex: "^Lebara"
    category: "Bill - Phone & Internet"

  # Stocks & Shares ISA
  - match_regex: "^Hargreaves Lansdown"
    direction: out
    category: "Stocks & Shares ISA"

  # Holidays & Travel
  - match_regex: "^Trainline"
    category: "Holidays & Travel"

  # Car & Gas
  - match_regex: "^Shell"
    category: "Car & Gas"

  # Sundry
  - match_regex: "^Anthropic"
    category: "Sundry"
"""
    out.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    fixtures = [
        ("statement_minimal.pdf", create_minimal),
        ("statement_multi_month.pdf", create_multi_month),
        ("statement_with_pending_and_reverted.pdf", create_with_pending_and_reverted),
        ("statement_empty.pdf", create_empty),
        ("statement_bad_balance.pdf", create_bad_balance),
    ]

    for name, fn in fixtures:
        out = FIXTURES_DIR / name
        fn(out)
        print(f"Created: {out}")

    create_rules_yaml(FIXTURES_DIR / "rules_example.yaml")
    print(f"Created: {FIXTURES_DIR / 'rules_example.yaml'}")

    try:
        import pdfplumber  # noqa: PLC0415

        print("\nVerification:")
        for name, _ in fixtures:
            path = FIXTURES_DIR / name
            with pdfplumber.open(path) as pdf:
                tables = []
                for page in pdf.pages:
                    tbls = page.extract_tables()
                    if tbls:
                        tables.extend(tbls)
                print(f"  {name}: {len(tables)} tables")
                if tables:
                    print(f"    First row: {tables[0][0]}")
    except ImportError:
        print("pdfplumber not available for verification")


if __name__ == "__main__":
    main()
