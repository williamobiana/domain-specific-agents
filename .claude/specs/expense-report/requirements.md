# Expense Summary — Requirements

## Introduction
A local CLI tool that converts a personal bank/expense PDF into a canonical CSV summarising income and expenditure by fixed sections and categories. The tool must be deterministic, testable, and run on Linux with Python 3.11+. The canonical schema and ordering are fixed and authoritative.

## Requirements

### Requirement 1 — CLI entrypoint
**User Story:** As a user, I want a single command-line entrypoint so that I can convert a PDF to a CSV in one step.

#### Acceptance Criteria
1. WHEN the user runs the tool with two positional arguments THEN the system SHALL accept `expense-summary input.pdf output.csv` and run the pipeline.
2. IF the input file is missing OR the extension is not `.pdf` THEN the system SHALL exit non‑zero and print a clear error message.
3. WHEN the pipeline completes successfully THEN the system SHALL exit 0.

### Requirement 2 — PDF → Markdown conversion
**User Story:** As a user, I want the tool to extract all textual content and numeric values from the PDF so that later stages can parse expense lines.

#### Acceptance Criteria
1. WHEN provided a readable PDF THEN the system SHALL produce an intermediate Markdown/plain-text string containing the extracted text.
2. IF `pdfplumber` fails to yield usable text THEN the system SHALL fall back to `pdfminer.six` (documented in code comments).
3. IF conversion fails THEN the system SHALL raise a ConversionError that `main.py` handles and reports.

### Requirement 3 — Parse expense line items
**User Story:** As a user, I want the tool to detect expense lines and amounts so that items can be categorised and summed.

#### Acceptance Criteria
1. WHEN presented with the extracted markdown/text THEN the parser SHALL return a list of ExpenseItem(dataclass with raw_text and amount).
2. IF no expense rows are found THEN the parser SHALL raise a ParseError.
3. IF any line has an unparseable amount THEN the parser SHALL raise a ParseError for that input (tests must cover malformed rows).

### Requirement 4 — Canonical categories schema
**User Story:** As a developer, I want a single authoritative declaration of sections and categories so that CSV order and grouping are deterministic.

#### Acceptance Criteria
1. WHERE category and section names are needed THEN the system SHALL import them only from `categories.py` (SCHEMA, INCOME_SECTIONS, OUTFLOW_SECTIONS).
2. IF any module requires a category name THEN it SHALL never hard‑code strings that duplicate `categories.py`.

### Requirement 5 — Matching and grouping
**User Story:** As a user, I want parsed items mapped to canonical categories using deterministic heuristics so that grouping is reproducible and testable.

#### Acceptance Criteria
1. WHEN grouping items THEN `grouper.py` SHALL expose `match_category(item_text: str) -> tuple[str, str] | None`.
2. WHEN matching THEN the system SHALL perform:
   - Exact pass: normalise (lowercase, collapse whitespace, strip punctuation) and compare.
   - Fuzzy pass: plain‑Python substring/token overlap fallback (no 3rd‑party fuzzy libs).
3. IF no match is found THEN `match_category` SHALL return None and `group_items` SHALL assign the item to "Uncategorised" and emit a warning (not an exception).
4. IF grouping fails due to schema issues THEN grouper SHALL raise GroupingError.

### Requirement 6 — Summarise and totals
**User Story:** As a user, I want per-category totals, section subtotals, and grand totals so that financial summaries are clear.

#### Acceptance Criteria
1. WHEN given a list of CategorisedItem THEN `summariser.summarise` SHALL return SectionSummary objects ordered by SCHEMA with CategoryTotal entries and a numeric subtotal for each section.
2. WHEN summarising THEN the system SHALL compute two grand totals: Total Income (sum of income sections) and Total Expenditure (sum of outflow sections).
3. WHEN written to CSV THEN amounts SHALL be formatted to two decimal places.

### Requirement 7 — CSV writing and ordering
**User Story:** As a user, I want a canonical CSV file so that downstream tools can rely on consistent order and layout.

#### Acceptance Criteria
1. WHEN writing output THEN `writer.write_csv` SHALL produce `section,category,total_amount` header.
2. FOR each section in SCHEMA THEN the CSV SHALL list each category row, followed by a `Total <Section Name>` subtotal row (section column repeated).
3. AFTER sections THEN the CSV SHALL include two grand total rows with an empty section column: `,Total Income,<amt>` and `,Total Expenditure,<amt>`.
4. WHEN writing fails (e.g., permission denied) THEN the system SHALL exit non‑zero with a clear error.

### Requirement 8 — Error handling and warnings
**User Story:** As a user, I want clear, human-readable errors and non-fatal warnings so I can act on problems without reading tracebacks.

#### Acceptance Criteria
1. WHEN a module raises ConversionError, ParseError, or GroupingError THEN `main.py` SHALL catch it and exit with a short, user-friendly message (no raw traceback).
2. WHEN items are unmatched THEN `main.py` SHALL print a final warning block to stderr listing unmatched items and amounts in the specified format.
3. WHILE running THEN the tool SHALL not print internal stack traces by default.

### Requirement 9 — Testing and quality
**User Story:** As a developer, I want unit tests that validate parser, grouper, and summariser behaviour so the tool is maintainable and correct.

#### Acceptance Criteria
1. WHEN running tests THEN the project SHALL use pytest with tests for:
   - parser: happy path, malformed rows, zero rows, bad amounts (ParseError).
   - grouper: exact matches for every category in SCHEMA, case/whitespace variants, and an unrecognised label returning None.
   - summariser: per-category totals, section subtotals, and both grand totals.
2. IF tests run locally THEN they SHALL be fast and not depend on real PDFs (use fixture strings/objects).
3. WHEN installing dependencies THEN `requirements.txt` SHALL include pdfplumber, pdfminer.six, pytest.

### Requirement 10 — Non‑functional constraints
**User Story:** As a system administrator, I want predictable, local execution so operations comply with privacy and offline requirements.

#### Acceptance Criteria
1. WHEN running the tool THEN it SHALL run fully locally with no network calls.
2. IF intermediate files are required THEN they SHALL be written to the system temp directory or kept in-memory and be clearly documented.
3. THE codebase SHALL use type hints, dataclasses, no global mutable state, and avoid pandas and external fuzzy libraries.

## Acceptance / Success Criteria
- The CLI completes and produces a CSV matching the canonical schema and order.
- Section subtotals and grand totals match computed sums from parsed data.
- Tests pass with pytest.
- Warnings for unmatched items are printed, but processing completes.
