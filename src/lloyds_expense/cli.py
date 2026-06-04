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

from lloyds_expense.classifier import classify
from lloyds_expense.errors import ParseError, RulesConfigError
from lloyds_expense.parser import parse_statement
from lloyds_expense.reconciler import reconcile
from lloyds_expense.rules import load_rules
from lloyds_expense.writer import write_csv

_console = Console()

# The default rules file location.
_DEFAULT_RULES_PATH = Path.cwd() / "rules" / "rules.yaml"

# Typer application object — imported by __main__.py and referenced in pyproject.toml.
app = typer.Typer(
    name="lloyds-expense",
    help="Transform a Lloyds Bank Classic statement PDF into a categorised monthly cash-flow CSV.",
    add_completion=False,
)


@app.command()
def main(
    statement_pdf: Annotated[
        Path,
        typer.Argument(help="Path to Lloyds Classic statement PDF"),
    ],
    rules: Annotated[
        Path | None,
        typer.Option("--rules", help="Path to YAML rules file"),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output CSV path (default: <pdf-stem>.csv in current directory)"),
    ] = None,
    report_unmatched: Annotated[
        Path | None,
        typer.Option("--report-unmatched", help="Write unmatched transactions to this file"),
    ] = None,
) -> None:
    """Process a Lloyds Bank Classic statement PDF and produce a categorised CSV.

    Exit codes:
      0 — success, CSV written.
      1 — one or more unmatched transactions; no CSV written.
      2 — reconciliation mismatch; no CSV written.
      3 — PDF parse failure.
      4 — bad input (missing file, bad rules).
    """
    # ------------------------------------------------------------------
    # Input validation (exit code 4 for all failures here)
    # ------------------------------------------------------------------

    # Default output path: <pdf-stem>.csv in the current working directory.
    if out is None:
        out = Path.cwd() / (statement_pdf.stem + ".csv")

    # R1.2 / task 9.1: statement_pdf must exist and be readable.
    if not statement_pdf.exists():
        _console.print(f"[red]Error:[/red] PDF file not found: {statement_pdf}")
        raise typer.Exit(code=4)
    if not statement_pdf.is_file():
        _console.print(f"[red]Error:[/red] Not a file: {statement_pdf}")
        raise typer.Exit(code=4)

    # R3.2 / task 9.1: resolve default rules path.
    effective_rules: Path = rules if rules is not None else _DEFAULT_RULES_PATH

    # ------------------------------------------------------------------
    # Stage 1: Parse the PDF statement (exit code 3 on failure)
    # ------------------------------------------------------------------
    try:
        statement = parse_statement(statement_pdf)
    except ParseError as exc:
        page_info = f" (page {exc.page})" if exc.page is not None else ""
        _console.print(f"[red]Error:[/red] PDF parse failed{page_info}: {exc.message}")
        raise typer.Exit(code=3)

    # ------------------------------------------------------------------
    # Stage 2: Load classification rules (exit code 4 on failure)
    # ------------------------------------------------------------------
    try:
        rule_list = load_rules(effective_rules)
    except RulesConfigError as exc:
        _console.print(f"[red]Error:[/red] Rules configuration error: {exc.message}")
        if exc.violations:
            for violation in exc.violations:
                _console.print(f"  - {violation}")
        raise typer.Exit(code=4)

    # ------------------------------------------------------------------
    # Stage 3: Classify transactions
    # ------------------------------------------------------------------
    result = classify(statement.transactions, rule_list)

    # R5.1-R5.3 / task 9.2: handle unmatched transactions (exit code 1).
    if result.unmatched:
        # Build and print a rich table to stderr.
        table = Table(
            title="Unmatched Transactions",
            show_header=True,
            header_style="bold yellow",
        )
        table.add_column("Date", style="cyan")
        table.add_column("Description")
        table.add_column("Type", style="magenta")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Direction", style="bold")

        for tx in result.unmatched:
            table.add_row(
                str(tx.date),
                tx.description,
                tx.type_code,
                str(tx.amount),
                tx.direction,
            )

        _console.print(table)

        # Write plain-text report if --report-unmatched was supplied.
        if report_unmatched is not None:
            lines = [
                f"{tx.date} | {tx.description} | {tx.type_code} | {tx.amount} | {tx.direction}"
                for tx in result.unmatched
            ]
            report_unmatched.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Do NOT write the output CSV.
        raise typer.Exit(code=1)

    # ------------------------------------------------------------------
    # Stage 4: Reconcile classified totals against statement totals
    # ------------------------------------------------------------------
    report = reconcile(result, statement)

    # R6.4 / task 9.2: handle reconciliation mismatch (exit code 2).
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
            "Money In",
            str(report.money_in_expected),
            str(report.money_in_actual),
            str(report.money_in_diff),
        )
        recon_table.add_row(
            "Money Out",
            str(report.money_out_expected),
            str(report.money_out_actual),
            str(report.money_out_diff),
        )

        _console.print(recon_table)
        raise typer.Exit(code=2)

    # ------------------------------------------------------------------
    # Stage 5: Write the output CSV (exit code 0 on success)
    # ------------------------------------------------------------------
    write_csv(result, statement, out)
    # Typer defaults to exit 0 when the command function returns normally.
