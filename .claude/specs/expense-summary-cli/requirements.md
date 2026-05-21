# Requirements Document

## Introduction

`expense-summary` is a local command-line tool that converts a personal PDF expense report into a structured CSV file. It accepts a single PDF input, extracts expense line items by parsing text content, maps each item to a fixed set of canonical categories using keyword and heuristic matching, computes section subtotals and grand totals, and writes the result as a clean CSV grouped in canonical order. The tool operates entirely offline with no network access, external APIs, LLMs, or databases. All category definitions are fixed and not user-configurable.

## Requirements

### Requirement 1: CLI Interface

**User Story:** As a user, I want to run a single command with an input PDF and an output CSV path so that I can convert my expense report without learning subcommands or flags.

#### Acceptance Criteria

1. WHEN the user invokes `expense-summary input.pdf output.csv` THEN the system SHALL accept exactly two positional arguments: the input PDF path and the output CSV path.
2. WHEN the tool completes successfully THEN the system SHALL exit with code 0.
3. WHEN the tool encounters any error THEN the system SHALL exit with a non-zero exit code.
4. WHERE CLI argument parsing is concerned, the system SHALL use Python's `argparse` stdlib module and SHALL NOT introduce subcommands or optional flags beyond strict necessity.
5. WHEN any message is printed to stdout or stderr THEN the system SHALL do so only from `main.py`; no other module SHALL print to stdout or stderr or call `sys.exit`.

---

### Requirement 2: Input Validation

**User Story:** As a user, I want the tool to tell me clearly when my input is wrong so that I can fix it before wasting time on a failed run.

#### Acceptance Criteria

1. WHEN the input file path does not exist or is not a `.pdf` file THEN the system SHALL print a descriptive error message to stderr and exit with a non-zero code.
2. WHEN the output file path points to a location that cannot be written (e.g., read-only directory, insufficient permissions) THEN the system SHALL print a descriptive error message to stderr and exit with a non-zero code.
3. IF input validation fails THEN the system SHALL NOT attempt PDF conversion or any downstream processing.

---

### Requirement 3: PDF-to-Markdown Conversion

**User Story:** As a developer, I want the PDF content to be converted to an intermediate Markdown string so that the parsing step works on a consistent text format regardless of PDF structure.

#### Acceptance Criteria

1. WHEN a valid PDF file is provided THEN the system SHALL attempt to convert it to a Markdown string using `pdfplumber` as the primary library.
2. IF `pdfplumber` fails to extract usable text from the PDF THEN the system SHALL fall back to `pdfminer.six` to perform the conversion.
3. IF both `pdfplumber` and `pdfminer.six` fail to extract usable text THEN the system SHALL raise a `ConversionError`.
4. WHEN the intermediate Markdown string is produced THEN the system SHALL write it to a temporary file in the system temp directory.
5. WHEN processing is complete (whether successful or not) THEN the system SHALL delete the temporary Markdown file, ensuring no leftover files remain.
6. WHERE PDF conversion logic is concerned, it SHALL reside exclusively in `src/pdf_converter.py`.

---

### Requirement 4: Expense Line Item Parsing

**User Story:** As a developer, I want raw expense line items extracted from the Markdown text so that downstream steps can operate on structured data rather than unstructured text.

#### Acceptance Criteria

1. WHEN the Markdown string is parsed THEN the system SHALL extract individual expense line items, each represented as a `raw_text` description (string) and an `amount` (float).
2. IF no line items are found after parsing the entire Markdown string THEN the system SHALL raise a `ParseError`.
3. WHERE parsing logic is concerned, it SHALL reside exclusively in `src/parser.py`.
4. WHEN parsing amounts, the system SHALL handle common numeric formats (e.g., values with commas, currency symbols) and convert them to Python floats.
5. IF a line in the Markdown does not contain both a recognisable description and a numeric amount THEN the system SHALL skip that line without raising an error.

---

### Requirement 5: Category Mapping

**User Story:** As a user, I want each extracted expense item to be assigned to a canonical category so that my spending is organised in a consistent, meaningful structure.

#### Acceptance Criteria

1. WHEN a line item's `raw_text` is evaluated THEN the system SHALL first attempt exact keyword matching against known category keywords.
2. IF exact matching does not produce a match THEN the system SHALL attempt fuzzy heuristic matching using pure Python (no third-party fuzzy matching libraries, no LLMs).
3. IF neither exact nor fuzzy matching produces a match THEN the system SHALL assign the item to an "Uncategorised" bucket and emit a warning (not raise an error or crash).
4. WHERE all matching logic is concerned, it SHALL reside exclusively in `src/grouper.py`.
5. WHERE all canonical category names and section names are defined, they SHALL reside exclusively in `src/categories.py`, which is the single source of truth.
6. No other module SHALL hardcode category or section names; all references SHALL import from `src/categories.py`.

---

### Requirement 6: Canonical Category Schema

**User Story:** As a user, I want my expenses grouped into a fixed, predictable category structure so that I can compare reports over time without category drift.

#### Acceptance Criteria

1. WHEN grouping items, the system SHALL recognise exactly the following sections and categories in the order listed:

   - **Section: Regular Inflows** → Salary
   - **Section: Irregular Inflows** → Carry Over, Unexpected / Refund, Loan
   - **Section: Asset Liquidation** → Savings, Stocks & Shares
   - *(Grand Total: Total Income — sum of all inflow sections)*
   - **Section: Regular Outflows** → Rent, Bill - Council Tax, Bill - Electricity & Gas, Bill - Phone & Internet, Food Supplies, Debt, Car & Gas
   - **Section: Irregular Outflows** → Charity / Donations, Gifts Entertainment & Misc, Sundry, Holidays & Travel, Education, Eating Out
   - **Section: Assets** → Active Savings, Lifetime ISA, Stocks & Shares ISA, Dividend Portfolio
   - *(Grand Total: Total Expenditure — sum of all outflow sections)*

2. WHEN the canonical schema is changed THEN the system SHALL require only `src/categories.py` to be updated; all other modules SHALL reflect the change automatically.
3. WHERE items that cannot be matched are concerned, the system SHALL place them in an "Uncategorised" bucket that appears at the end of the CSV output.

---

### Requirement 7: Summarisation

**User Story:** As a user, I want subtotals per section and grand totals for income and expenditure so that I can understand my financial position at a glance.

#### Acceptance Criteria

1. WHEN amounts are summed THEN the system SHALL compute the total amount per category by summing all line item amounts assigned to that category.
2. WHEN section subtotals are computed THEN the system SHALL sum all category totals within each section to produce a section subtotal row.
3. WHEN grand totals are computed THEN the system SHALL compute:
   - **Total Income** as the sum of all inflow section subtotals (Regular Inflows + Irregular Inflows + Asset Liquidation).
   - **Total Expenditure** as the sum of all outflow section subtotals (Regular Outflows + Irregular Outflows + Assets).
4. IF a category has no matched items THEN the system SHALL include it in the output with a total amount of 0.
5. WHERE summarisation logic is concerned, it SHALL reside exclusively in `src/summariser.py`.
6. Section subtotals and grand totals SHALL be computed by the tool and SHALL NOT be read from the PDF.

---

### Requirement 8: CSV Output

**User Story:** As a user, I want a clean, well-structured CSV so that I can open it in a spreadsheet application or process it with other tools without manual cleanup.

#### Acceptance Criteria

1. WHEN the output CSV is written THEN it SHALL contain exactly three columns: `section`, `category`, `total_amount`.
2. WHEN rows are ordered THEN the system SHALL write them in the canonical section and category order defined in `src/categories.py`.
3. WHEN section subtotal rows are written THEN the system SHALL include them as distinct rows with the `category` field set to a subtotal label (e.g., `"Subtotal"`) and `section` set to the section name.
4. WHEN grand total rows are written THEN the system SHALL include `Total Income` and `Total Expenditure` as distinct rows after their respective groups.
5. WHEN Uncategorised items exist THEN the system SHALL include them as a final section at the end of the CSV.
6. WHERE CSV writing logic is concerned, it SHALL use Python's `csv` stdlib module and SHALL reside exclusively in `src/writer.py`.

---

### Requirement 9: Error Types and Handling

**User Story:** As a developer, I want well-defined custom error types so that errors from different pipeline stages are distinguishable and can be handled or reported precisely.

#### Acceptance Criteria

1. WHEN the PDF cannot be read or converted by either library THEN the system SHALL raise a `ConversionError`.
2. WHEN no line items are extracted from the Markdown THEN the system SHALL raise a `ParseError`.
3. WHERE custom error classes are defined, they SHALL reside exclusively in `src/errors.py`.
4. WHEN a `ConversionError` or `ParseError` propagates to `main.py` THEN the system SHALL catch it, print a human-readable message to stderr, and exit with a non-zero code.
5. WHEN an unmatched item is encountered THEN the system SHALL issue a warning (not raise an exception) and continue processing.

---

### Requirement 10: Module Structure and Separation of Concerns

**User Story:** As a developer, I want a clear module boundary for each pipeline stage so that individual components can be tested and modified in isolation.

#### Acceptance Criteria

1. WHERE source modules are located, they SHALL follow this structure:
   - `src/main.py` — CLI entry point; the only module that calls `sys.exit` or prints to stdout/stderr.
   - `src/pdf_converter.py` — PDF-to-Markdown conversion logic.
   - `src/parser.py` — Markdown-to-line-items parsing logic.
   - `src/categories.py` — Single source of truth for all section and category names.
   - `src/grouper.py` — All category matching and assignment logic.
   - `src/summariser.py` — Summarisation and totalling logic.
   - `src/writer.py` — CSV writing logic.
   - `src/errors.py` — Custom exception definitions.
2. No module SHALL import from `src/main.py`.
3. WHERE tests are located, they SHALL follow this structure:
   - `tests/test_parser.py` — Tests for `src/parser.py`.
   - `tests/test_grouper.py` — Tests for `src/grouper.py`.
   - `tests/test_summariser.py` — Tests for `src/summariser.py`.
4. WHERE the test framework is concerned, the system SHALL use `pytest`.

---

### Requirement 11: Non-Functional Constraints

**User Story:** As a developer, I want the tool to operate within defined technical boundaries so that it remains portable, auditable, and free of external dependencies.

#### Acceptance Criteria

1. WHEN the tool is executed THEN it SHALL require Python 3.8 or later.
2. WHEN processing a PDF THEN the system SHALL NOT make any network requests, access any external APIs, use any LLMs, open any GUI, or read from or write to any database.
3. WHEN performing category matching THEN the system SHALL NOT use any third-party fuzzy matching library; all matching SHALL be implemented in pure Python.
4. WHEN writing CSV output THEN the system SHALL use Python's `csv` stdlib module.
5. WHEN parsing CLI arguments THEN the system SHALL use Python's `argparse` stdlib module.
6. WHEN handling temporary files THEN the system SHALL use the system temp directory and SHALL clean up all temporary files upon completion or failure.
