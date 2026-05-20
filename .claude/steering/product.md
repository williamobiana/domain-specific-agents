---
description: Product scope and constraints for the expense summary CLI tool. Apply to all planning, design, and implementation decisions.
---

## Product

A single, local CLI tool that reads a PDF expense report and produces a grouped CSV summary, structured around a fixed set of known categories.

## Goal

Convert a personal PDF expense report into a clean CSV: one row per category, with the category name and its summed total — organised by section in a defined order.

## CLI interface

```
expense-summary input.pdf output.csv
```

No subcommands. No flags beyond what is strictly needed. Exit 0 on success, non-zero on failure.

## Required behaviour

1. **PDF → Markdown**: Accept a `.pdf` file. Convert it to an intermediate `.md` file preserving all text and numeric values.
2. **Parse expenses**: Read the `.md` file. Detect individual expense line items with their label and amount.
3. **Map to categories**: Match each line item to one of the known categories below. Matching logic lives in one place (`grouper.py`).
4. **Summarise to CSV**: Sum all amounts per category. Write a `.csv` with columns: `section`, `category`, `total_amount`. Rows appear in the canonical order defined below.
5. **Error messages**: Print clear, human-readable errors when:
   - Input file is missing or not a `.pdf`
   - PDF cannot be read or converted
   - No expense rows can be parsed
   - A parsed row cannot be matched to any known category (warn, do not crash)
   - Output path cannot be written

## Canonical category schema

The report always uses this structure. Categories and section totals must appear in this exact order in the CSV output.

```
Section: Regular Inflows
  - Salary
  - Total Regular Inflows       ← section subtotal row

Section: Irregular Inflows
  - Carry Over
  - Unexpected / Refund
  - Loan
  - Total Irregular Inflows     ← section subtotal row

Section: Asset Liquidation
  - Savings
  - Stocks & Shares
  - Total Asset Liquidation     ← section subtotal row

  Total Income                  ← grand total of all inflow sections

Section: Regular Outflows
  - Rent
  - Bill - Council Tax
  - Bill - Electricity & Gas
  - Bill - Phone & Internet
  - Food Supplies
  - Debt
  - Car & Gas
  - Total Regular Outflows      ← section subtotal row

Section: Irregular Outflows
  - Charity / Donations
  - Gifts, Entertainment & Misc
  - Sundry
  - Holidays & Travel
  - Education
  - Eating Out
  - Total Irregular Outflows    ← section subtotal row

Section: Assets
  - Active Savings
  - Lifetime ISA
  - Stocks & Shares ISA
  - Dividend Portfolio
  - Total Asset Expenditure     ← section subtotal row

  Total Expenditure             ← grand total of all outflow sections
```

Section subtotals and grand totals are **computed by the tool**, not read from the PDF. If the PDF contains its own subtotal rows, they are used only for validation (optional), not as the authoritative value.

## Hard constraints

- Local execution only — no network calls, no cloud services
- No GUI, no web server, no database
- No user accounts or authentication
- One executable entry point
- Intermediate files (e.g. the `.md`) are temporary; clean them up or make their location obvious

## Non-goals

- Dynamic or user-configurable categories — the schema above is fixed
- Multi-currency conversion
- Receipt image OCR
- Any UI beyond the terminal
