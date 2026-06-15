"""CLI entry point: parse arguments, orchestrate the pipeline, and map errors to exit codes.

This is the only module in the package that:
- accesses sys.argv (via typer)
- writes to stdout/stderr directly
- calls sys.exit (via typer.Exit)
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from monzo_expense.classifier import ClassificationResult, classify
from monzo_expense.errors import ParseError, RulesConfigError
from monzo_expense.parser import parse_statement
from monzo_expense.reconciler import reconcile
from monzo_expense.rules import load_rules
from monzo_expense.splitter import YearMonth, split_by_month
from monzo_expense.writer import write_csvs

_stderr = Console(stderr=True)
_stdout = Console()

# Project-local default (mirrors how lloyds-expense resolves rules).
_DEFAULT_RULES_PATH_LOCAL = Path.cwd() / "rules" / "monzo_rules.yaml"
# XDG-style fallback for when the tool is installed outside the project tree.
_DEFAULT_RULES_PATH_USER = Path.home() / ".config" / "monzo-expense" / "rules.yaml"

app = typer.Typer(
    name="monzo-expense",
    help="Transform a Monzo account statement PDF into categorised monthly cash-flow CSVs.",
    add_completion=False,
)


@app.command()
def main(
    statement_pdf: Annotated[
        Path,
        typer.Argument(help="Path to Monzo account statement PDF"),
    ],
    rules: Annotated[
        Path | None,
        typer.Option("--rules", help="Path to YAML rules file"),
    ] = None,
    out_dir: Annotated[
        Path | None,
        typer.Option(
            "--out-dir",
            help="Directory to write output CSVs into (default: ./output)",
        ),
    ] = None,
    report_unmatched: Annotated[
        Path | None,
        typer.Option("--report-unmatched", help="Write unmatched transactions to this file"),
    ] = None,
) -> None:
    """Process a Monzo account statement PDF and produce categorised monthly CSVs.

    Exit codes:
      0 — success, CSV(s) written.
      1 — one or more unmatched transactions; no CSVs written.
      2 — reconciliation mismatch; no CSVs written.
      3 — PDF parse failure.
      4 — bad input (missing file, bad rules).
    """
    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    if out_dir is None:
        out_dir = Path.cwd() / "output"

    if not statement_pdf.exists():
        _stderr.print(f"[red]Error:[/red] PDF file not found: {statement_pdf}")
        raise typer.Exit(code=4)
    if not statement_pdf.is_file():
        _stderr.print(f"[red]Error:[/red] Not a file: {statement_pdf}")
        raise typer.Exit(code=4)

    if rules is not None:
        effective_rules: Path = rules
    elif _DEFAULT_RULES_PATH_LOCAL.exists():
        effective_rules = _DEFAULT_RULES_PATH_LOCAL
    elif _DEFAULT_RULES_PATH_USER.exists():
        effective_rules = _DEFAULT_RULES_PATH_USER
    else:
        _stderr.print(
            f"[red]Error:[/red] No rules file found. Supply --rules or place a rules file at "
            f"{_DEFAULT_RULES_PATH_LOCAL} or {_DEFAULT_RULES_PATH_USER}"
        )
        raise typer.Exit(code=4)

    # ------------------------------------------------------------------
    # Stage 1: Parse PDF
    # ------------------------------------------------------------------
    try:
        statement = parse_statement(statement_pdf)
    except ParseError as exc:
        page_info = f" (page {exc.page})" if exc.page is not None else ""
        _stderr.print(f"[red]Error:[/red] PDF parse failed{page_info}: {exc.message}")
        raise typer.Exit(code=3)

    # ------------------------------------------------------------------
    # Stage 2: Load rules
    # ------------------------------------------------------------------
    try:
        rule_list = load_rules(effective_rules)
    except RulesConfigError as exc:
        _stderr.print(f"[red]Error:[/red] Rules configuration error: {exc.message}")
        if exc.violations:
            for violation in exc.violations:
                _stderr.print(f"  - {violation}")
        raise typer.Exit(code=4)

    # ------------------------------------------------------------------
    # Stage 3: Classify
    # ------------------------------------------------------------------
    result = classify(statement.transactions, rule_list)

    if result.unmatched:
        table = Table(
            title="Unmatched Transactions",
            show_header=True,
            header_style="bold yellow",
        )
        table.add_column("Date", style="cyan")
        table.add_column("Description")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Direction", style="bold")

        for tx in result.unmatched:
            table.add_row(str(tx.date), tx.description, str(tx.amount), tx.direction)

        _stderr.print(table)

        if report_unmatched is not None:
            lines = [
                f"{tx.date} | {tx.description} | {tx.amount} | {tx.direction}"
                for tx in result.unmatched
            ]
            report_unmatched.write_text("\n".join(lines) + "\n", encoding="utf-8")

        raise typer.Exit(code=1)

    # ------------------------------------------------------------------
    # Stage 4: Split by month
    # ------------------------------------------------------------------
    by_month = split_by_month(result)

    # R9.1: zero-transaction statement → emit one all-zero CSV for the start month
    if not by_month:
        start_ym = YearMonth(statement.period_start.year, statement.period_start.month)
        by_month = {start_ym: ClassificationResult(matched=(), unmatched=())}

    # ------------------------------------------------------------------
    # Stage 5: Reconcile (full period, pre-split result)
    # ------------------------------------------------------------------
    report = reconcile(result, statement)

    if not report.ok:
        recon_table = Table(
            title="Reconciliation Mismatch",
            show_header=True,
            header_style="bold red",
        )
        recon_table.add_column("Field", style="bold")
        recon_table.add_column("Expected", justify="right")
        recon_table.add_column("Actual", justify="right")
        recon_table.add_column("Difference", justify="right")

        recon_table.add_row(
            "Deposits",
            str(report.deposits_expected),
            str(report.deposits_actual),
            str(report.deposits_diff),
        )
        recon_table.add_row(
            "Outgoings",
            str(report.outgoings_expected),
            str(report.outgoings_actual),
            str(report.outgoings_diff),
        )

        _stderr.print(recon_table)
        raise typer.Exit(code=2)

    # ------------------------------------------------------------------
    # Stage 6: Write CSVs
    # ------------------------------------------------------------------
    written = write_csvs(by_month, statement, out_dir)
    for p in written:
        _stdout.print(str(p))
