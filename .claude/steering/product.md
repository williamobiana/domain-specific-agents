---
description: Product scope and constraints for the expense summary CLI tool. Apply to all planning, design, and implementation decisions.
---

## Product

A single, local CLI tool that reads a PDF expense report and produces a grouped CSV summary.

## Goal

Convert a messy PDF expense report into a clean two-column CSV: one row per expense group, with the group name and its summed total.

## CLI interface

```
expense-summary input.pdf output.csv
```

No subcommands. No flags beyond what is strictly needed. Exit 0 on success, non-zero on failure.

## Required behaviour

1. **PDF → Markdown**: Accept a `.pdf` file. Convert it to an intermediate `.md` file preserving all text and numeric values.
2. **Parse expenses**: Read the `.md` file. Detect individual expense line items.
3. **Group expenses**: Assign each line item to a named group (by category, merchant, or inferred label). Grouping logic must live in one place.
4. **Summarise to CSV**: Sum all amounts per group. Write a `.csv` with exactly two columns: `group_name`, `total_amount`.
5. **Error messages**: Print clear, human-readable errors when:
   - Input file is missing or not a `.pdf`
   - PDF cannot be read or converted
   - No expense rows can be parsed
   - Output path cannot be written

## Hard constraints

- Local execution only — no network calls, no cloud services
- No GUI, no web server, no database
- No user accounts or authentication
- One executable entry point
- Intermediate files (e.g. the `.md`) are temporary; clean them up or make their location obvious

## Non-goals

- Real-time processing or streaming
- Multi-currency conversion
- Receipt image OCR
- Any UI beyond the terminal
