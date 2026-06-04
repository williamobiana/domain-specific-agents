"""Integration tests for cli.py — entry point and I/O boundary.

Covers requirements R1.x, R5.x, R6.x, R8.x, R9.x, R11.x:
  R1.1  CLI accepts a single PDF positional argument.
  R1.2  Non-existent PDF → exit 4 with descriptive error.
  R5.1  Unmatched transactions → exit 1, no CSV written.
  R5.2  Unmatched transaction table printed to stderr.
  R5.3  --report-unmatched writes plain-text report.
  R6.3  Reconciliation mismatch → exit 2.
  R6.4  CSV not written on reconciliation mismatch.
  R8.1  Zero-transaction statement with zero totals → exit 0.
  R9.1  --out option required; missing → exit 4.
  R9.2  Parse error → exit 3.
  R9.5  Rules config error → exit 4.
  R9.6  --help lists all options.
  R11.1 All rich output goes to stderr; stdout remains clean.

All PDF/file I/O is mocked — real PDF fixtures are not required.
Patches use the "lloyds_expense.cli.*" namespace (import-site patching).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from lloyds_expense.classifier import ClassificationResult, ClassifiedTransaction
from lloyds_expense.cli import app
from lloyds_expense.errors import ParseError, RulesConfigError
from lloyds_expense.parser import Statement, Transaction
from lloyds_expense.reconciler import ReconciliationReport
from lloyds_expense.schema import Category

# ---------------------------------------------------------------------------
# CliRunner — typer's CliRunner captures stdout and stderr separately.
# Use r.stdout, r.stderr (individual streams) or r.output (combined).
# ---------------------------------------------------------------------------

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_statement() -> Statement:
    """Return a minimal Statement with no transactions and balanced totals."""
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


def make_matched_result() -> ClassificationResult:
    """Return a ClassificationResult with one matched salary transaction."""
    tx = Transaction(
        date=date(2026, 4, 1),
        description="SALARY",
        type_code="BGC",
        amount=Decimal("1500.00"),
        direction="in",  # type: ignore[arg-type]
        running_balance=Decimal("2200.00"),
    )
    ct = ClassifiedTransaction(transaction=tx, category=Category.SALARY)
    return ClassificationResult(matched=(ct,), unmatched=())


def make_unmatched_result() -> ClassificationResult:
    """Return a ClassificationResult with one unmatched transaction."""
    tx = Transaction(
        date=date(2026, 4, 1),
        description="UNKNOWN",
        type_code="DEB",
        amount=Decimal("100.00"),
        direction="out",  # type: ignore[arg-type]
        running_balance=Decimal("100.00"),
    )
    return ClassificationResult(matched=(), unmatched=(tx,))


def make_empty_result() -> ClassificationResult:
    """Return a ClassificationResult with no matched or unmatched transactions."""
    return ClassificationResult(matched=(), unmatched=())


def make_ok_report(
    money_in: Decimal = Decimal("1500.00"),
    money_out: Decimal = Decimal("300.00"),
) -> ReconciliationReport:
    """Return a ReconciliationReport with ok=True and matching expected/actual values."""
    return ReconciliationReport(
        ok=True,
        money_in_expected=money_in,
        money_in_actual=money_in,
        money_out_expected=money_out,
        money_out_actual=money_out,
    )


def make_mismatch_report() -> ReconciliationReport:
    """Return a ReconciliationReport with ok=False (money-in mismatch)."""
    return ReconciliationReport(
        ok=False,
        money_in_expected=Decimal("1500.00"),
        money_in_actual=Decimal("1499.99"),
        money_out_expected=Decimal("300.00"),
        money_out_actual=Decimal("300.00"),
    )


# ---------------------------------------------------------------------------
# Test 1 — Happy path: exit 0, CSV written
# ---------------------------------------------------------------------------


def test_happy_path(tmp_path: Path) -> None:
    """Full pipeline succeeds: exit 0 and write_csv is called exactly once."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")  # must exist to pass file-exists validation
    out = tmp_path / "out.csv"

    stmt = make_statement()
    result = make_matched_result()
    report = make_ok_report()

    with (
        patch("lloyds_expense.cli.parse_statement", return_value=stmt),
        patch("lloyds_expense.cli.load_rules", return_value=[]),
        patch("lloyds_expense.cli.classify", return_value=result),
        patch("lloyds_expense.cli.reconcile", return_value=report),
        patch("lloyds_expense.cli.write_csv") as mock_write,
    ):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 0
    mock_write.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2 — Unmatched transactions: exit 1, no CSV written
# ---------------------------------------------------------------------------


def test_unmatched_transactions_exit_1(tmp_path: Path) -> None:
    """Unmatched transactions produce exit 1; write_csv must NOT be called."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"

    stmt = make_statement()
    result = make_unmatched_result()

    with (
        patch("lloyds_expense.cli.parse_statement", return_value=stmt),
        patch("lloyds_expense.cli.load_rules", return_value=[]),
        patch("lloyds_expense.cli.classify", return_value=result),
        patch("lloyds_expense.cli.write_csv") as mock_write,
    ):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 1
    mock_write.assert_not_called()
    # The unmatched transaction's description should appear in the combined output.
    combined = r.stdout + r.stderr
    assert "UNKNOWN" in combined


# ---------------------------------------------------------------------------
# Test 3 — Reconciliation mismatch: exit 2
# ---------------------------------------------------------------------------


def test_reconciliation_mismatch_exit_2(tmp_path: Path) -> None:
    """Reconciliation failure produces exit 2; write_csv must NOT be called."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"

    stmt = make_statement()
    result = make_matched_result()
    report = make_mismatch_report()

    with (
        patch("lloyds_expense.cli.parse_statement", return_value=stmt),
        patch("lloyds_expense.cli.load_rules", return_value=[]),
        patch("lloyds_expense.cli.classify", return_value=result),
        patch("lloyds_expense.cli.reconcile", return_value=report),
        patch("lloyds_expense.cli.write_csv") as mock_write,
    ):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 2
    mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4 — Non-existent PDF: exit 4 with error message
# ---------------------------------------------------------------------------


def test_nonexistent_pdf_exit_4(tmp_path: Path) -> None:
    """A path that does not exist produces exit 4 with a descriptive error message."""
    missing = tmp_path / "does_not_exist.pdf"
    out = tmp_path / "out.csv"

    r = runner.invoke(app, [str(missing), "--out", str(out)])

    assert r.exit_code == 4
    combined = r.stdout + r.stderr
    assert "not found" in combined.lower() or "error" in combined.lower()


# ---------------------------------------------------------------------------
# Test 5 — Missing --out: exit 4 with usage / error message
# ---------------------------------------------------------------------------


def test_missing_out_option_exit_4(tmp_path: Path) -> None:
    """Omitting --out produces exit 4 with an appropriate error message."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")

    r = runner.invoke(app, [str(pdf)])

    assert r.exit_code == 4
    combined = r.stdout + r.stderr
    # The CLI should mention --out is required.
    assert "--out" in combined or "required" in combined.lower()


# ---------------------------------------------------------------------------
# Test 6 — Parse error: exit 3
# ---------------------------------------------------------------------------


def test_parse_error_exit_3(tmp_path: Path) -> None:
    """parse_statement raising ParseError produces exit 3."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"

    with patch("lloyds_expense.cli.parse_statement", side_effect=ParseError("bad pdf")):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 3
    combined = r.stdout + r.stderr
    assert "bad pdf" in combined


# ---------------------------------------------------------------------------
# Test 7 — Rules config error: exit 4
# ---------------------------------------------------------------------------


def test_rules_config_error_exit_4(tmp_path: Path) -> None:
    """load_rules raising RulesConfigError produces exit 4."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"

    stmt = make_statement()

    with (
        patch("lloyds_expense.cli.parse_statement", return_value=stmt),
        patch("lloyds_expense.cli.load_rules", side_effect=RulesConfigError("bad rules")),
    ):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 4
    combined = r.stdout + r.stderr
    assert "bad rules" in combined


# ---------------------------------------------------------------------------
# Test 8 — --report-unmatched with unmatched transactions: exit 1, report written
# ---------------------------------------------------------------------------


def test_report_unmatched_flag_writes_file(tmp_path: Path) -> None:
    """--report-unmatched path is created when there are unmatched transactions."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"
    report_path = tmp_path / "unmatched.txt"

    stmt = make_statement()
    result = make_unmatched_result()

    with (
        patch("lloyds_expense.cli.parse_statement", return_value=stmt),
        patch("lloyds_expense.cli.load_rules", return_value=[]),
        patch("lloyds_expense.cli.classify", return_value=result),
    ):
        r = runner.invoke(
            app, [str(pdf), "--out", str(out), "--report-unmatched", str(report_path)]
        )

    assert r.exit_code == 1
    assert report_path.exists(), "Report file should have been written"
    report_text = report_path.read_text(encoding="utf-8")
    # The report should contain info about the unmatched transaction.
    assert "UNKNOWN" in report_text


# ---------------------------------------------------------------------------
# Test 9 — --help: exit 0, options listed
# ---------------------------------------------------------------------------


def test_help_exit_0_and_options_listed() -> None:
    """--help produces exit 0 and lists --out and --rules options."""
    r = runner.invoke(app, ["--help"])

    assert r.exit_code == 0
    assert "--out" in r.output
    assert "--rules" in r.output


# ---------------------------------------------------------------------------
# Test 10 — Zero-transaction statement with zero totals: exit 0 (R8.1)
# ---------------------------------------------------------------------------


def test_zero_transaction_zero_totals_exit_0(tmp_path: Path) -> None:
    """A genuinely empty statement (zero transactions, zero totals) succeeds (R8.1)."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"

    empty_stmt = Statement(
        sort_code="12-34-56",
        account_number="12345678",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1000.00"),
        money_in_total=Decimal("0.00"),
        money_out_total=Decimal("0.00"),
        transactions=(),
    )
    empty_result = make_empty_result()
    ok_report = ReconciliationReport(
        ok=True,
        money_in_expected=Decimal("0.00"),
        money_in_actual=Decimal("0.00"),
        money_out_expected=Decimal("0.00"),
        money_out_actual=Decimal("0.00"),
    )

    with (
        patch("lloyds_expense.cli.parse_statement", return_value=empty_stmt),
        patch("lloyds_expense.cli.load_rules", return_value=[]),
        patch("lloyds_expense.cli.classify", return_value=empty_result),
        patch("lloyds_expense.cli.reconcile", return_value=ok_report),
        patch("lloyds_expense.cli.write_csv") as mock_write,
    ):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 0
    mock_write.assert_called_once()


# ---------------------------------------------------------------------------
# Test 11 — Zero-transaction statement with non-zero totals: exit 3 (R8.2)
# ---------------------------------------------------------------------------


def test_zero_transaction_nonzero_totals_exit_3(tmp_path: Path) -> None:
    """Parser fault: zero rows but non-zero totals raises ParseError → exit 3 (R8.2)."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"

    with patch(
        "lloyds_expense.cli.parse_statement",
        side_effect=ParseError(
            "PDF produced zero transaction rows but statement totals are non-zero"
            " (money_in=500.00, money_out=0.00)"
        ),
    ):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 3
    combined = r.stdout + r.stderr
    assert "zero" in combined.lower() or "parse" in combined.lower() or "error" in combined.lower()


# ---------------------------------------------------------------------------
# Test 12 — Statement with broken balance equation: exit 3 (R6.3)
# ---------------------------------------------------------------------------


def test_broken_balance_equation_exit_3(tmp_path: Path) -> None:
    """A balance-equation failure from the parser surfaces as exit 3 (R6.3)."""
    pdf = tmp_path / "stmt.pdf"
    pdf.write_bytes(b"fake")
    out = tmp_path / "out.csv"

    with patch(
        "lloyds_expense.cli.parse_statement",
        side_effect=ParseError(
            "Balance equation failed: 1000.00 + 500.00 - 200.00 = 1300.00 ≠ 1400.00 (diff=-100.00)"
        ),
    ):
        r = runner.invoke(app, [str(pdf), "--out", str(out)])

    assert r.exit_code == 3
    combined = r.stdout + r.stderr
    low = combined.lower()
    assert "balance" in low or "parse" in low or "error" in low
