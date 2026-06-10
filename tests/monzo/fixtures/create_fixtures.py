"""Standalone script to generate synthetic Monzo statement PDF fixtures for testing.

Run with: uv run python tests/monzo/fixtures/create_fixtures.py
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


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]
    )


def _meta(lines: list[str]) -> list[Paragraph]:
    return [Paragraph(line, styles["Normal"]) for line in lines]


# ---------------------------------------------------------------------------
# Fixture 1 — statement_minimal.pdf
# Single month April 2026, 4 transactions, one continuation row, thousand-separator
# ---------------------------------------------------------------------------


def create_minimal(out: Path) -> None:
    """Single-month April 2026 statement with 4 transactions."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 04-00-04",
            "Account number: 12345678",
            "Statement period: 01 Apr 2026 to 30 Apr 2026",
            "Opening balance: 1000.00",
            "Total deposits: 1500.00",
            "Total outgoings: 160.00",
            "Closing balance: 2340.00",
        ]
    )
    story.append(Spacer(1, 0.5 * cm))

    # Row 2 is a continuation row for row 1 (empty date, description only)
    tx_data = [
        ["Date", "Description", "Amount", "Balance"],
        ["01 Apr 2026", "O Okwu-Boms (Faster Payments)", "1,500.00", "2500.00"],
        ["", "Reference: April transfer", "", ""],
        ["10 Apr 2026", "TESCO STORES 2388 DUMFRIES GBR", "-80.00", "2420.00"],
        ["20 Apr 2026", "AMAZON.CO.UK LONDON GBR", "-50.00", "2370.00"],
        ["25 Apr 2026", "Lebara Mobile Limited London GBR", "-30.00", "2340.00"],
    ]
    t = Table(tx_data, colWidths=[2.5 * cm, 9 * cm, 2.5 * cm, 2.5 * cm])
    t.setStyle(_table_style())
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 2 — statement_multi_month.pdf
# April and May 2026, ~8 transactions per month, continuation rows, trailing Pot page
# ---------------------------------------------------------------------------


def create_multi_month(out: Path) -> None:
    """Two-month April–May 2026 statement with a trailing Pot page."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 04-00-04",
            "Account number: 12345678",
            "Statement period: 01 Apr 2026 to 31 May 2026",
            "Opening balance: 1000.00",
            "Total deposits: 7500.00",
            "Total outgoings: 1460.00",
            "Closing balance: 7040.00",
        ]
    )
    story.append(Spacer(1, 0.5 * cm))

    # April: deposits=3000, outgoings=480
    # May: deposits=4500, outgoings=980
    # Total deposits: 7500, Total outgoings: 1460, Closing: 1000+7500-1460=7040 ✓
    tx_data = [
        ["Date", "Description", "Amount", "Balance"],
        # April transactions
        ["01 Apr 2026", "O Okwu-Boms (Faster Payments)", "3000.00", "4000.00"],
        ["", "Reference: Salary April 2026", "", ""],
        ["05 Apr 2026", "TESCO STORES 2388 DUMFRIES GBR", "-80.00", "3920.00"],
        ["10 Apr 2026", "W M MORRISONS DUMFRIES GBR", "-60.00", "3860.00"],
        ["15 Apr 2026", "AMAZON.CO.UK LONDON GBR", "-50.00", "3810.00"],
        ["18 Apr 2026", "Lebara Mobile Limited London GBR", "-20.00", "3790.00"],
        ["20 Apr 2026", "UBER *TRIP London GBR", "-30.00", "3760.00"],
        ["25 Apr 2026", "Transfer to Pot", "-200.00", "3560.00"],
        ["30 Apr 2026", "Lidl GB DUMFRIES GBR", "-40.00", "3520.00"],
        # May transactions
        ["01 May 2026", "O Okwu-Boms (Faster Payments)", "3000.00", "6520.00"],
        ["", "Reference: Salary May 2026", "", ""],
        ["05 May 2026", "Lebara Mobile Limited London GBR", "-20.00", "6500.00"],
        ["", "Reference: May mobile bill", "", ""],
        ["08 May 2026", "TESCO STORES 2388 DUMFRIES GBR", "-90.00", "6410.00"],
        ["12 May 2026", "WWW.HL.CO.UK BRISTOL GBR", "1000.00", "7410.00"],
        ["15 May 2026", "AMAZON.CO.UK LONDON GBR", "-45.00", "7365.00"],
        ["20 May 2026", "DGHB CATERING DUMFRIES GBR", "-25.00", "7340.00"],
        ["25 May 2026", "WWW.HL.CO.UK BRISTOL GBR", "-800.00", "6540.00"],
        [
            "31 May 2026",
            "Somtochukwu Nchekwubechukwu Obiana (Faster Payments)",
            "500.00",
            "7040.00",
        ],
    ]
    t = Table(tx_data, colWidths=[2.5 * cm, 10 * cm, 2.5 * cm, 2.5 * cm])
    t.setStyle(_table_style())
    story.append(t)

    # Trailing Pot page — must be skipped by the parser
    story.append(PageBreak())
    for para in _meta(["Savings Pot", "Balance: 500.00"]):
        story.append(para)
    pot_data = [
        ["Date", "Description", "Amount", "Balance"],
        ["01 Apr 2026", "Pot deposit", "200.00", "500.00"],
    ]
    pot_table = Table(pot_data, colWidths=[2.5 * cm, 10 * cm, 2.5 * cm, 2.5 * cm])
    pot_table.setStyle(_table_style())
    story.append(pot_table)

    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 3 — statement_empty.pdf
# Zero transactions, zero totals → should return Statement with empty tuple
# ---------------------------------------------------------------------------


def create_empty(out: Path) -> None:
    """Statement with zero transactions and zero totals."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 04-00-04",
            "Account number: 12345678",
            "Statement period: 01 Apr 2026 to 30 Apr 2026",
            "Opening balance: 0.00",
            "Total deposits: 0.00",
            "Total outgoings: 0.00",
            "Closing balance: 0.00",
        ]
    )
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 4 — statement_bad_balance.pdf
# Balance equation intentionally wrong: 1000 + 500 - 200 ≠ 9999
# ---------------------------------------------------------------------------


def create_bad_balance(out: Path) -> None:
    """Statement where opening + deposits - outgoings ≠ closing balance."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 04-00-04",
            "Account number: 12345678",
            "Statement period: 01 Apr 2026 to 30 Apr 2026",
            "Opening balance: 1000.00",
            "Total deposits: 500.00",
            "Total outgoings: 200.00",
            "Closing balance: 9999.00",
        ]
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        ["Date", "Description", "Amount", "Balance"],
        ["01 Apr 2026", "O Okwu-Boms (Faster Payments)", "500.00", "1500.00"],
        ["15 Apr 2026", "TESCO STORES 2388 DUMFRIES GBR", "-200.00", "1300.00"],
    ]
    t = Table(tx_data, colWidths=[2.5 * cm, 10 * cm, 2.5 * cm, 2.5 * cm])
    t.setStyle(_table_style())
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Rules fixture — rules_example.yaml
# Covers all transactions in the fixture PDFs with deliberate gaps for testing
# ---------------------------------------------------------------------------


def create_rules_yaml(out: Path) -> None:
    """Write a rules YAML file that matches all fixture transactions.

    Transactions with continuation rows produce joined descriptions, so those
    rules use match_regex with a prefix pattern rather than exact match.
    """
    content = """\
rules:
  # O Okwu-Boms may have a joined continuation "Reference: ..." suffix
  - match_regex: "^O Okwu-Boms"
    direction: in
    category: "Main Account Inflow"
  - match: "TESCO STORES 2388 DUMFRIES GBR"
    category: "Food Supplies"
  - match: "AMAZON.CO.UK LONDON GBR"
    category: "Gifts/Entertainment/Misc"
  # Lebara may have a joined continuation "Reference: ..." suffix
  - match_regex: "^Lebara Mobile Limited London GBR"
    category: "Bill - Phone & Internet"
  - match: "W M MORRISONS DUMFRIES GBR"
    category: "Food Supplies"
  - match: "UBER *TRIP London GBR"
    category: "Holidays & Travel"
  - match: "Transfer to Pot"
    category: "Active Savings"
  - match: "Lidl GB DUMFRIES GBR"
    category: "Food Supplies"
  - match: "WWW.HL.CO.UK BRISTOL GBR"
    direction: in
    category: "Stocks & Shares"
  - match: "DGHB CATERING DUMFRIES GBR"
    category: "Eating Out"
  - match: "WWW.HL.CO.UK BRISTOL GBR"
    direction: out
    category: "Stocks & Shares ISA"
  - match: "Somtochukwu Nchekwubechukwu Obiana (Faster Payments)"
    direction: in
    category: "Unexpected / Refund"
  - match: "Somtochukwu Nchekwubechukwu Obiana (Faster Payments)"
    direction: out
    category: "Charity / Donations"
"""
    out.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    fixtures = [
        ("statement_minimal.pdf", create_minimal),
        ("statement_multi_month.pdf", create_multi_month),
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
        for name in ["statement_minimal.pdf", "statement_multi_month.pdf"]:
            with pdfplumber.open(FIXTURES_DIR / name) as pdf:
                tables = []
                for page in pdf.pages:
                    tables.extend(page.extract_tables())
                print(f"  {name}: {len(tables)} tables found")
                if tables:
                    print(f"    First table header: {tables[0][0]}")
    except ImportError:
        print("pdfplumber not available for verification")


if __name__ == "__main__":
    main()
