# Requirements Document

## Introduction

The `expense-summary` tool is a local command-line utility that converts a personal PDF expense report into a structured CSV summary. It reads a PDF, extracts expense line items from unstructured text, maps each item to a fixed canonical category schema (covering inflows, outflows, and asset movements), computes per-category totals, section subtotals, and two grand totals (Total Income, Total Expenditure), then writes the result to a CSV file. The category schema is fixed and not user-configurable. The tool runs entirely offline with no GUI, no networking, and no database.

---

## Requirements

### Requirement 1 — CLI Entry Point

**User Story:** As a user, I want to run a single command with an input PDF and output CSV path, so that I can produce my expense summary without learning multiple commands or configuration options.

#### Acceptance Criteria

1. WHEN the user runs `expense-summary input.pdf output.csv` THEN the system SHALL accept exactly two positional arguments: the input PDF path and the output CSV path.
2. WHEN the command completes successfully THEN the system SHALL exit with code `0`.
3. WHEN the command fails for any reason THEN the system SHALL exit with a non-zero code and print a human-readable error message to stderr.
4. WHERE no subcommands or additional flags are required THEN the system SHALL NOT expose subcommands or optional flags beyond what is strictly necessary for the two positional arguments.

---

### Requirement 2 — PDF to Markdown Conversion

**User Story:** As a user, I want the tool to accept any standard PDF expense report, so that I don't have to pre-process the file before running the tool.

#### Acceptance Criteria

1. WHEN a valid `.pdf` file path is provided THEN the system SHALL convert the PDF to an intermediate Markdown representation preserving all text content and numeric values.
2. WHEN the input file path does not exist THEN the system SHALL print a clear error message and exit with a non-zero code without attempting conversion.
3. WHEN the input file exists but is not a `.pdf` (by extension) THEN the system SHALL print a clear error message and exit with a non-zero code.
4. WHEN the PDF exists but cannot be read or parsed THEN the system SHALL raise a `ConversionError` which `main.py` catches and presents as a human-readable message.
5. WHILE the intermediate Markdown file exists on disk THEN the system SHALL store it in the system temporary directory, not alongside the input file.
6. WHEN the pipeline completes (success or failure after conversion) THEN the system SHALL clean up the intermediate Markdown file.

---

### Requirement 3 — Expense Line Item Parsing

**User Story:** As a user, I want the tool to extract individual expense entries from the converted Markdown, so that each transaction is available for categorisation.

#### Acceptance Criteria

1. WHEN the Markdown content is processed THEN the system SHALL produce a list of `ExpenseItem` objects, each containing a `raw_text` string (the item description as extracted from the PDF) and an `amount` float.
2. WHEN no expense rows can be detected in the Markdown THEN the system SHALL raise a `ParseError` which `main.py` presents as a human-readable message and exits non-zero.
3. WHEN a line contains text but no parseable numeric amount THEN the system SHALL skip that line and continue parsing remaining lines.
4. WHEN an amount string contains currency symbols (e.g. `£`, `$`) or thousands separators (e.g. commas) THEN the system SHALL strip those characters before parsing the float.
5. IF the PDF contains explicit subtotal or total rows (e.g. "Total Regular Inflows") THEN the system SHALL parse them as raw items but SHALL NOT use their values as authoritative totals — totals are always recomputed by the tool.

---

### Requirement 4 — Category Matching

**User Story:** As a user, I want each expense item automatically assigned to the correct category from my fixed schema, so that I don't have to manually classify transactions.

#### Acceptance Criteria

1. WHEN an `ExpenseItem` is processed THEN the system SHALL attempt to match its `raw_text` to a canonical category defined in `categories.py` using the two-pass strategy: exact normalised match first, then substring/token overlap.
2. WHEN a match is found THEN the system SHALL assign the item a `section` and `category` from the canonical schema and produce a `CategorisedItem`.
3. WHEN no match is found for an item THEN the system SHALL assign it to an `"Uncategorised"` bucket, emit a warning to stderr, and continue processing remaining items — it SHALL NOT crash.
4. WHERE normalisation is applied THEN the system SHALL lowercase the text, collapse all whitespace, and strip punctuation before comparison.
5. WHEN category names are referenced in matching logic THEN the system SHALL import them exclusively from `categories.py` — no category string SHALL be hard-coded in `grouper.py`.
6. IF all items are unmatched THEN the system SHALL still write a CSV (with only an `Uncategorised` section) and warn the user rather than exiting with an error.

---

### Requirement 5 — Canonical Category Schema

**User Story:** As a user, I want my specific income and expense categories to appear in the output in the correct order every time, so that the CSV is consistent and easy to review.

#### Acceptance Criteria

1. WHEN the CSV is produced THEN the system SHALL include all of the following sections in this exact order:
   - Regular Inflows (Salary)
   - Irregular Inflows (Carry Over; Unexpected / Refund; Loan)
   - Asset Liquidation (Savings; Stocks & Shares)
   - Regular Outflows (Rent; Bill - Council Tax; Bill - Electricity & Gas; Bill - Phone & Internet; Food Supplies; Debt; Car & Gas)
   - Irregular Outflows (Charity / Donations; Gifts, Entertainment & Misc; Sundry; Holidays & Travel; Education; Eating Out)
   - Assets (Active Savings; Lifetime ISA; Stocks & Shares ISA; Dividend Portfolio)
2. WHEN a category receives no matched items THEN the system SHALL still include that category row in the CSV with a `total_amount` of `0.00`.
3. WHERE the schema is defined THEN the system SHALL define it only in `categories.py` — no other module SHALL declare or duplicate category or section names.

---

### Requirement 6 — Summarisation and Totals

**User Story:** As a user, I want each category, section, and grand total computed accurately, so that I can trust the CSV figures without manually checking sums.

#### Acceptance Criteria

1. WHEN `CategorisedItem` objects are summarised THEN the system SHALL sum all amounts sharing the same `category` to produce a `CategoryTotal`.
2. WHEN all `CategoryTotal` values within a section are known THEN the system SHALL compute a section subtotal as their sum and include it as a row named `Total <Section Name>` (e.g. `Total Regular Inflows`).
3. WHEN all inflow section subtotals are known THEN the system SHALL compute `Total Income` as the sum of subtotals for `Regular Inflows`, `Irregular Inflows`, and `Asset Liquidation`.
4. WHEN all outflow section subtotals are known THEN the system SHALL compute `Total Expenditure` as the sum of subtotals for `Regular Outflows`, `Irregular Outflows`, and `Assets`.
5. IF the source PDF contains subtotal rows THEN the system SHALL use the tool-computed totals as authoritative and MAY optionally log a warning if the PDF value differs by more than a rounding threshold.

---

### Requirement 7 — CSV Output

**User Story:** As a user, I want a clean, consistently formatted CSV file, so that I can open it in a spreadsheet or import it into other tools without reformatting.

#### Acceptance Criteria

1. WHEN the pipeline succeeds THEN the system SHALL write a CSV to the output path with exactly three columns: `section`, `category`, `total_amount`.
2. WHEN rows are written THEN the system SHALL output them in the canonical schema order defined in `categories.py`.
3. WHEN a section subtotal row is written THEN the system SHALL repeat the section name in the `section` column and use `Total <Section Name>` in the `category` column.
4. WHEN a grand total row (`Total Income` or `Total Expenditure`) is written THEN the system SHALL leave the `section` column empty and place the label in the `category` column.
5. WHEN amounts are written THEN the system SHALL format all `total_amount` values to exactly 2 decimal places.
6. WHEN the output path cannot be written (e.g. permissions, missing directory) THEN the system SHALL print a clear error message and exit non-zero.

---

### Requirement 8 — Error Reporting and Warnings

**User Story:** As a user, I want clear feedback when something goes wrong or is ambiguous, so that I can diagnose and fix problems without reading source code.

#### Acceptance Criteria

1. WHEN any fatal error occurs THEN the system SHALL print a single human-readable sentence to stderr describing the problem, and SHALL NOT print a raw Python traceback.
2. WHEN one or more items cannot be matched to a category THEN the system SHALL print a warning block to stderr after processing, listing each unmatched item's `raw_text` and amount.
3. WHEN warnings are emitted THEN the system SHALL still write the CSV and exit with code `0` (warnings are non-fatal).
4. WHEN the user provides fewer or more than two positional arguments THEN the system SHALL print usage instructions and exit non-zero.

---

### Requirement 9 — Non-functional Constraints

**User Story:** As a user, I want the tool to run locally without any external services, so that my personal financial data never leaves my machine.

#### Acceptance Criteria

1. WHILE the tool is running THEN the system SHALL NOT make any network requests.
2. WHEN the tool is installed THEN the system SHALL run as a single executable entry point with no GUI, web server, or database dependency.
3. WHEN dependencies are evaluated THEN the system SHALL use only `pdfplumber` (with `pdfminer.six` as a documented fallback), `argparse`, and `csv` from the standard library, plus `pytest` for testing.
4. IF `pdfplumber` fails to extract usable text THEN the system SHALL fall back to `pdfminer.six` and document this fallback in a code comment.