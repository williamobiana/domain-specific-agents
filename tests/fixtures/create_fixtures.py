"""Standalone script to generate synthetic Lloyds statement PDF fixtures for testing.

Run with: uv run python tests/fixtures/create_fixtures.py

Each fixture is a minimal but structurally valid PDF that pdfplumber can read.
Table cells are rendered with explicit GRID borders so pdfplumber detects them.
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
    """Return a TableStyle with GRID borders that pdfplumber can detect."""
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
    """Convert a list of text lines into Paragraph flowables."""
    return [Paragraph(line, styles["Normal"]) for line in lines]


# ---------------------------------------------------------------------------
# Fixture 1 — statement_minimal.pdf
# 3 transactions: 1 money-in (with thousand-separator comma), 2 money-out
# ---------------------------------------------------------------------------


def create_minimal(out: Path) -> None:
    """Single-page minimal statement with 3 transactions."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 12-34-56",
            "Account number: 12345678",
            "Statement period: 01 Apr 26 to 30 Apr 26",
            "Opening balance: 1000.00",
            "Money in: 1500.00",
            "Money out: 300.00",
            "Closing balance: 2200.00",
        ]
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        ["Date", "Description", "Type", "Money in", "Money out", "Balance"],
        ["01 Apr 26", "SALARY PAYMENT", "BGC", "1,500.00", "", "2,500.00"],
        ["15 Apr 26", "RENT PAYMENT", "SO", "", "200.00", "2,300.00"],
        ["20 Apr 26", "FOOD PURCHASE", "DEB", "", "100.00", "2,200.00"],
    ]
    t = Table(tx_data, colWidths=[2.5 * cm, 5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
    t.setStyle(_table_style())
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 2 — statement_full.pdf
# 2-page PDF: page 1 has 12 transactions, page 2 has a type-code legend table
# ---------------------------------------------------------------------------


def create_full(out: Path) -> None:
    """Two-page statement: 12 transactions on page 1, legend table on page 2."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 77-88-99",
            "Account number: 87654321",
            "Statement period: 01 Mar 26 to 31 Mar 26",
            "Opening balance: 5000.00",
            "Money in: 3200.00",
            "Money out: 1800.00",
            "Closing balance: 6400.00",
        ]
    )
    story.append(Spacer(1, 0.5 * cm))

    # 12 transaction rows: money_in = 3200 (2500+700), money_out = 1800 (sum of 10 outflows)
    tx_data = [
        ["Date", "Description", "Type", "Money in", "Money out", "Balance"],
        ["01 Mar 26", "SALARY", "BGC", "2500.00", "", "7500.00"],
        ["02 Mar 26", "RENT", "SO", "", "800.00", "6700.00"],
        ["03 Mar 26", "COUNCIL TAX", "DD", "", "150.00", "6550.00"],
        ["04 Mar 26", "ELECTRICITY", "DD", "", "80.00", "6470.00"],
        ["05 Mar 26", "PHONE BILL", "DD", "", "40.00", "6430.00"],
        ["06 Mar 26", "FOOD SHOP", "DEB", "", "120.00", "6310.00"],
        ["07 Mar 26", "SAVINGS", "SO", "", "200.00", "6110.00"],
        ["08 Mar 26", "TRANSPORT", "DEB", "", "50.00", "6060.00"],
        ["09 Mar 26", "GIFT", "DEB", "", "30.00", "6030.00"],
        ["10 Mar 26", "CHARITY", "SO", "", "20.00", "6010.00"],
        ["15 Mar 26", "REFUND", "FPI", "700.00", "", "6710.00"],
        ["20 Mar 26", "TRANSFER", "TFR", "", "310.00", "6400.00"],
    ]
    t = Table(tx_data, colWidths=[2.5 * cm, 5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
    t.setStyle(_table_style())
    story.append(t)

    # Page break before the legend table
    story.append(PageBreak())

    # Type-code legend table on page 2 (different columns — not a transaction table)
    legend_data = [
        ["Type", "Description"],
        ["BGC", "Bank Giro Credit"],
        ["DEB", "Debit Card"],
        ["DD", "Direct Debit"],
        ["FPI", "Faster Payment In"],
        ["FPO", "Faster Payment Out"],
        ["SO", "Standing Order"],
        ["TFR", "Transfer"],
    ]
    legend = Table(legend_data, colWidths=[3 * cm, 8 * cm])
    legend.setStyle(_table_style())
    story.append(legend)

    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 3 — statement_cross_year.pdf
# Period spans Dec 25 → Jan 26; transactions in both months
# ---------------------------------------------------------------------------


def create_cross_year(out: Path) -> None:
    """Statement spanning a year boundary (Dec 25 - Jan 26)."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 11-22-33",
            "Account number: 11223344",
            "Statement period: 15 Dec 25 to 14 Jan 26",
            "Opening balance: 2000.00",
            "Money in: 1500.00",
            "Money out: 500.00",
            "Closing balance: 3000.00",
        ]
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        ["Date", "Description", "Type", "Money in", "Money out", "Balance"],
        ["15 Dec 25", "DECEMBER SALARY", "BGC", "1500.00", "", "3500.00"],
        ["20 Dec 25", "DECEMBER FOOD", "DEB", "", "300.00", "3200.00"],
        ["05 Jan 26", "JANUARY RENT", "SO", "", "200.00", "3000.00"],
    ]
    t = Table(tx_data, colWidths=[2.5 * cm, 5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
    t.setStyle(_table_style())
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 4 — statement_empty_with_totals.pdf
# No transaction table, but non-zero Money In total → should raise ParseError (R8.2)
# ---------------------------------------------------------------------------


def create_empty_with_totals(out: Path) -> None:
    """Metadata-only statement (no transaction table) with non-zero Money In."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 44-55-66",
            "Account number: 44556677",
            "Statement period: 01 Feb 26 to 28 Feb 26",
            "Opening balance: 1000.00",
            "Money in: 250.00",
            "Money out: 0.00",
            "Closing balance: 1250.00",
        ]
    )
    doc.build(story)


# ---------------------------------------------------------------------------
# Fixture 5 — statement_bad_balance.pdf
# Balance equation is intentionally wrong: 1000 + 500 - 300 ≠ 9999
# ---------------------------------------------------------------------------


def create_bad_balance(out: Path) -> None:
    """Statement with an intentionally wrong closing balance."""
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    story: list = _meta(
        [
            "Sort code: 99-88-77",
            "Account number: 99887766",
            "Statement period: 01 May 26 to 31 May 26",
            "Opening balance: 1000.00",
            "Money in: 500.00",
            "Money out: 300.00",
            "Closing balance: 9999.00",
        ]
    )
    story.append(Spacer(1, 0.5 * cm))

    tx_data = [
        ["Date", "Description", "Type", "Money in", "Money out", "Balance"],
        ["01 May 26", "SALARY", "BGC", "500.00", "", "1500.00"],
        ["15 May 26", "RENT", "SO", "", "300.00", "1200.00"],
    ]
    t = Table(tx_data, colWidths=[2.5 * cm, 5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
    t.setStyle(_table_style())
    story.append(t)
    doc.build(story)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Create all fixture PDFs."""
    fixtures = [
        ("statement_minimal.pdf", create_minimal),
        ("statement_full.pdf", create_full),
        ("statement_cross_year.pdf", create_cross_year),
        ("statement_empty_with_totals.pdf", create_empty_with_totals),
        ("statement_bad_balance.pdf", create_bad_balance),
    ]

    for name, fn in fixtures:
        out = FIXTURES_DIR / name
        fn(out)
        print(f"Created: {out}")

    # Quick verification using pdfplumber
    try:
        import pdfplumber

        print("\nVerification:")
        for name in [
            "statement_minimal.pdf",
            "statement_full.pdf",
            "statement_cross_year.pdf",
        ]:
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
