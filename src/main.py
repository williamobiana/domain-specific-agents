from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING

from src.errors import ConversionError, GroupingError, ParseError
from src.grouper import group_items
from src.parser import parse_items
from src.pdf_converter import convert_pdf
from src.summariser import compute_grand_totals, summarise
from src.writer import write_csv

if TYPE_CHECKING:
    from src.parser import ExpenseItem


def validate_paths(input_path: str, output_path: str) -> None:
    """Raise SystemExit with a descriptive message if either path is invalid."""
    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if not input_path.lower().endswith(".pdf"):
        print(f"Error: input file must have a .pdf extension: {input_path}", file=sys.stderr)
        sys.exit(1)
    output_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    if not os.path.isdir(output_dir) or not os.access(output_dir, os.W_OK):
        print(
            f"Error: output directory does not exist or is not writable: {output_dir}",
            file=sys.stderr,
        )
        sys.exit(1)


def run_pipeline(input_path: str, output_path: str) -> list[ExpenseItem]:
    """Orchestrate the full conversion pipeline. Returns list of unmatched ExpenseItems.
    Raises ConversionError, ParseError, or GroupingError on failure."""
    temp_path = convert_pdf(input_path)
    try:
        with open(temp_path, encoding="utf-8") as f:
            markdown_text = f.read()
        items = parse_items(markdown_text)
        categorised, unmatched = group_items(items)
        summaries = summarise(categorised)
        total_income, total_expenditure = compute_grand_totals(summaries)
        write_csv(summaries, total_income, total_expenditure, output_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return unmatched


def main() -> None:
    """CLI entry point: parse args, validate, run pipeline, handle errors."""
    arg_parser = argparse.ArgumentParser(
        description="Convert a PDF expense report to a structured CSV file."
    )
    arg_parser.add_argument("input_pdf", help="Path to the input PDF file.")
    arg_parser.add_argument("output_csv", help="Path for the output CSV file.")
    args = arg_parser.parse_args()

    validate_paths(args.input_pdf, args.output_csv)

    try:
        unmatched = run_pipeline(args.input_pdf, args.output_csv)
    except ConversionError as exc:
        print(f"Error: could not convert PDF: {exc}", file=sys.stderr)
        sys.exit(1)
    except ParseError as exc:
        print(f"Error: could not parse expenses: {exc}", file=sys.stderr)
        sys.exit(1)
    except GroupingError as exc:
        print(f"Error: could not group expenses: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if unmatched:
        print(
            f"Warning: {len(unmatched)} item(s) could not be matched to a known category:",
            file=sys.stderr,
        )
        for item in unmatched:
            print(f'  - "{item.raw_text}" (£{item.amount:.2f})', file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
