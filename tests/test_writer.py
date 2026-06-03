"""Tests for lloyds_expense.writer — write_csv and _build_category_totals."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

from lloyds_expense.classifier import ClassificationResult, ClassifiedTransaction
from lloyds_expense.parser import Statement, Transaction
from lloyds_expense.schema import Category
from lloyds_expense.writer import write_csv

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"
_EXPECTED_CSV = _FIXTURES / "expected_output.csv"


def make_statement() -> Statement:
    """Return the Statement matching the golden expected_output.csv inputs."""
    return Statement(
        sort_code="12-34-56",
        account_number="12345678",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("2200.00"),
        money_in_total=Decimal("1500.00"),
        money_out_total=Decimal("300.00"),
        transactions=(),
    )


def make_result() -> ClassificationResult:
    """Return the ClassificationResult matching the golden expected_output.csv inputs."""

    def tx(desc: str, code: str, amount: str, direction: str) -> Transaction:
        return Transaction(
            date=date(2026, 4, 1),
            description=desc,
            type_code=code,
            amount=Decimal(amount),
            direction=direction,  # type: ignore[arg-type]
            running_balance=Decimal("100.00"),
        )

    cts = (
        ClassifiedTransaction(
            transaction=tx("SALARY PAYMENT", "BGC", "1500.00", "in"),
            category=Category.SALARY,
        ),
        ClassifiedTransaction(
            transaction=tx("RENT PAYMENT", "SO", "200.00", "out"),
            category=Category.RENT,
        ),
        ClassifiedTransaction(
            transaction=tx("FOOD PURCHASE", "DEB", "100.00", "out"),
            category=Category.FOOD_SUPPLIES,
        ),
    )
    return ClassificationResult(matched=cts, unmatched=())


# ---------------------------------------------------------------------------
# Test 1: Golden file — byte-for-byte match
# ---------------------------------------------------------------------------


def test_golden_file(tmp_path: Path) -> None:
    """write_csv output must be byte-identical to the committed golden file."""
    out = tmp_path / "actual.csv"
    write_csv(make_result(), make_statement(), out)
    expected = _EXPECTED_CSV.read_bytes()
    actual = out.read_bytes()
    assert actual == expected


# ---------------------------------------------------------------------------
# Test 2: Zero-fill — absent category emits "0.00"
# ---------------------------------------------------------------------------


def test_zero_fill(tmp_path: Path) -> None:
    """A category with no transactions must appear with value '0.00'."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    rows = {row[0]: row[1] for row in csv.reader(io.StringIO(content)) if len(row) == 2}
    # LOAN has no transactions in make_result(); it must emit 0.00.
    assert rows["Loan"] == "0.00"


# ---------------------------------------------------------------------------
# Test 3: Row count — 36 schema rows + 2 metadata rows = 38 total
# ---------------------------------------------------------------------------


def test_row_count(tmp_path: Path) -> None:
    """CSV must contain exactly 38 rows (36 schema rows + 2 metadata header rows)."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    rows = [r for r in content.split("\n") if r]
    assert len(rows) == 38


# ---------------------------------------------------------------------------
# Test 4: Line endings — LF only, no CRLF
# ---------------------------------------------------------------------------


def test_lf_line_endings(tmp_path: Path) -> None:
    """Output must use \\n line endings, not \\r\\n."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    raw_bytes = out.read_bytes()
    assert b"\r\n" not in raw_bytes
    assert b"\n" in raw_bytes


# ---------------------------------------------------------------------------
# Test 5: QUOTE_MINIMAL — plain labels must not be quoted
# ---------------------------------------------------------------------------


def test_quote_minimal(tmp_path: Path) -> None:
    """csv.QUOTE_MINIMAL must be used; labels without special chars are unquoted."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    # "Regular Inflows" contains no commas or quotes, so must not be quoted.
    assert '"Regular Inflows"' not in content


# ---------------------------------------------------------------------------
# Test 6: Determinism — two runs produce byte-identical output
# ---------------------------------------------------------------------------


def test_determinism(tmp_path: Path) -> None:
    """Running write_csv twice with the same inputs must yield identical files."""
    out1 = tmp_path / "first.csv"
    out2 = tmp_path / "second.csv"
    write_csv(make_result(), make_statement(), out1)
    write_csv(make_result(), make_statement(), out2)
    assert out1.read_bytes() == out2.read_bytes()


# ---------------------------------------------------------------------------
# Test 7: Subtotal computation — Regular Inflows subtotal = 1500.00
# ---------------------------------------------------------------------------


def test_subtotal_regular_inflows(tmp_path: Path) -> None:
    """Regular Inflows subtotal must equal the SALARY amount (1500.00)."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    rows = {row[0]: row[1] for row in csv.reader(io.StringIO(content)) if len(row) == 2}
    assert rows["Regular Inflows subtotal"] == "1500.00"


# ---------------------------------------------------------------------------
# Test 8: Grand total — Total Income = 1500.00 + 0.00 + 0.00
# ---------------------------------------------------------------------------


def test_grand_total_income(tmp_path: Path) -> None:
    """Total Income must equal the sum of all income-section subtotals (1500.00)."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    rows = {row[0]: row[1] for row in csv.reader(io.StringIO(content)) if len(row) == 2}
    # Regular Inflows 1500.00 + Irregular Inflows 0.00 + Asset Liquidation 0.00
    assert rows["Total Income"] == "1500.00"


# ---------------------------------------------------------------------------
# Test 9: Metadata rows — period dates appear in the first two rows
# ---------------------------------------------------------------------------


def test_metadata_period_dates(tmp_path: Path) -> None:
    """First two CSV rows must contain the statement period start and end dates."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    assert rows[0] == ["Period start", "2026-04-01"]
    assert rows[1] == ["Period end", "2026-04-30"]


# ---------------------------------------------------------------------------
# Test 10: Overwrite — writing to same path twice must succeed silently
# ---------------------------------------------------------------------------


def test_overwrite_existing_file(tmp_path: Path) -> None:
    """write_csv must silently overwrite an existing file at the same path."""
    out = tmp_path / "out.csv"
    # First write
    write_csv(make_result(), make_statement(), out)
    first_bytes = out.read_bytes()
    # Second write to same path
    write_csv(make_result(), make_statement(), out)
    second_bytes = out.read_bytes()
    # Both writes produce the same content, and no exception was raised.
    assert first_bytes == second_bytes


# ---------------------------------------------------------------------------
# Additional: Grand total expenditure — Total Expenditure = 300.00
# ---------------------------------------------------------------------------


def test_grand_total_expenditure(tmp_path: Path) -> None:
    """Total Expenditure must equal the sum of all expenditure-section subtotals."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    rows = {row[0]: row[1] for row in csv.reader(io.StringIO(content)) if len(row) == 2}
    # Regular Outflows 300.00 + Irregular Outflows 0.00 + Assets 0.00
    assert rows["Total Expenditure"] == "300.00"


# ---------------------------------------------------------------------------
# Additional: All 22 category labels present in output
# ---------------------------------------------------------------------------


def test_all_category_labels_present(tmp_path: Path) -> None:
    """Every Category enum member's display name must appear as a row label in the CSV."""
    out = tmp_path / "out.csv"
    write_csv(make_result(), make_statement(), out)
    content = out.read_text(encoding="utf-8")
    labels = {row[0] for row in csv.reader(io.StringIO(content))}
    for category in Category:
        assert category.value in labels, f"Missing label: {category.value!r}"
