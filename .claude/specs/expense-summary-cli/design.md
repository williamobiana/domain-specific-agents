# Design Document — expense-summary-cli

## Overview

`expense-summary` is a single-command CLI tool that converts a personal PDF expense report into a
structured CSV file. The tool operates entirely offline (no network, no LLMs, no GUI, no database)
and passes data through a fixed, linear pipeline:

```
PDF file → Markdown string → list[ExpenseItem] → list[CategorisedItem] → list[SectionSummary] → CSV file
```

Every pipeline stage maps to exactly one source module. All category and section names are defined
in one place (`categories.py`) and are never duplicated. The tool exits cleanly with a human-readable
message on any expected failure.

---

## Architecture Design

### System Architecture Diagram

```mermaid
graph TB
    CLI[CLI — main.py\nargparse: input_pdf, output_csv]
    VAL[Input Validation\nmain.py]
    CONV[pdf_converter.py\npdfplumber primary\npdfminer.six fallback]
    TEMP[Temp .md file\nsystem temp dir]
    PARSE[parser.py\nMarkdown → list of ExpenseItem]
    GROUP[grouper.py\nExpenseItem → CategorisedItem\ntwo-pass matching]
    SUM[summariser.py\nCategorisedItem → SectionSummary\nsubtotals + grand totals]
    WRITE[writer.py\nSectionSummary → CSV]
    CAT[categories.py\nSingle source of truth\nSCHEMA, INCOME_SECTIONS\nOUTFLOW_SECTIONS]
    ERR[errors.py\nConversionError\nParseError\nGroupingError]
    WARN[stderr warnings\nunmatched items]
    OUT[output.csv]

    CLI --> VAL
    VAL --> CONV
    CONV --> TEMP
    TEMP --> PARSE
    PARSE --> GROUP
    GROUP --> SUM
    SUM --> WRITE
    WRITE --> OUT

    CAT --> GROUP
    CAT --> SUM
    CAT --> WRITE
    ERR --> CONV
    ERR --> PARSE
    ERR --> GROUP
    GROUP --> WARN
```

### Data Flow Diagram

```mermaid
graph LR
    A[PDF path\nstring] --> B[pdf_converter\nconvert_pdf]
    B --> C[Markdown string]
    C --> D[parser\nparse_items]
    D --> E[list of ExpenseItem\nraw_text: str\namount: float]
    E --> F[grouper\ngroup_items]
    F --> G[list of CategorisedItem\nsection: str\ncategory: str\namount: float]
    F --> W[stderr warnings\nuncategorised items]
    G --> H[summariser\nsummarise]
    H --> I[list of SectionSummary\nsection: str\ncategories: list of CategoryTotal\nsubtotal: float]
    I --> J[writer\nwrite_csv]
    J --> K[CSV file]
```

---

## Component Design

### main.py — CLI Entry Point

Responsibilities:
- Parse exactly two positional CLI arguments (`input_pdf`, `output_csv`) via `argparse`
- Validate input path (exists, `.pdf` extension) and output path (writable location)
- Call `run_pipeline(input_path, output_path)` which orchestrates all stages
- Catch `ConversionError`, `ParseError`, `GroupingError` and print human-readable messages to stderr
- Emit unmatched-item warnings to stderr (received from `grouper` via return value)
- Be the only module that calls `sys.exit` or writes to stdout/stderr

Interfaces:

```python
def validate_paths(input_path: str, output_path: str) -> None:
    """Raise SystemExit with a descriptive message if either path is invalid."""

def run_pipeline(input_path: str, output_path: str) -> None:
    """Orchestrate the full conversion pipeline. Raises ConversionError, ParseError,
    or GroupingError on failure."""

def main() -> None:
    """CLI entry point: parse args, validate, run pipeline, handle errors."""
```

Dependencies: `pdf_converter`, `parser`, `grouper`, `summariser`, `writer`, `errors`

---

### pdf_converter.py — PDF to Markdown Conversion

Responsibilities:
- Accept a PDF file path and return a Markdown-formatted string
- Attempt text extraction with `pdfplumber` first; fall back to `pdfminer.six` if the result is
  empty or unusable
- Write the Markdown string to a temporary file in the system temp directory
- Return the temp file path so the caller can read and then delete it
- Raise `ConversionError` if both libraries fail

Interfaces:

```python
def convert_pdf(pdf_path: str) -> str:
    """Extract text from PDF and return as a Markdown string.
    Raises ConversionError if neither pdfplumber nor pdfminer.six produces usable text."""

def _extract_with_pdfplumber(pdf_path: str) -> str | None:
    """Return text extracted by pdfplumber, or None if extraction yields no usable content."""

def _extract_with_pdfminer(pdf_path: str) -> str | None:
    """Return text extracted by pdfminer.six (fallback), or None on failure."""

def _write_temp_markdown(content: str) -> str:
    """Write content to a temp file; return the temp file path."""
```

Dependencies: `pdfplumber`, `pdfminer.six`, `tempfile` (stdlib), `errors`

Temp-file lifecycle note: `main.py` wraps `run_pipeline` in a `try/finally` that deletes the temp
file regardless of success or failure. `pdf_converter` creates the file and returns its path;
cleanup responsibility sits with the caller (`main.py`).

---

### parser.py — Markdown to ExpenseItem List

Responsibilities:
- Accept a Markdown string (read from the temp file)
- Scan each line for a recognisable expense pattern: a description text and a numeric amount
- Return a `list[ExpenseItem]`
- Raise `ParseError` if no items are found after scanning all lines
- Skip lines that do not match (no error on individual skipped lines)
- Handle common numeric formats: commas as thousands separators, leading currency symbols
  (`£`, `$`, `€`), optional whitespace between symbol and digits

Interfaces:

```python
def parse_items(markdown_text: str) -> list[ExpenseItem]:
    """Parse a Markdown string into a list of ExpenseItem objects.
    Raises ParseError if the result is empty."""

def _parse_line(line: str) -> ExpenseItem | None:
    """Attempt to extract a description and amount from a single line.
    Returns None if the line does not match the expected pattern."""

def _normalise_amount(raw: str) -> float:
    """Strip currency symbols and commas, then convert to float.
    Raises ValueError on unparseable input (caller skips the line)."""
```

Dependencies: `re` (stdlib), `errors`

Line pattern strategy: a line is considered an expense line if it contains a non-empty text token
followed (or preceded) by a numeric amount string matching the pattern
`[£$€]?\s*[\d,]+(\.\d{1,2})?`. The description is everything on the line that is not the amount
token, stripped of leading/trailing whitespace.

---

### categories.py — Canonical Schema

Responsibilities:
- Define the single source of truth for all section names, category names, and their order
- Export `SCHEMA`, `INCOME_SECTIONS`, `OUTFLOW_SECTIONS`, and the `Section` dataclass
- Never contain business logic; only data declarations

Data declarations:

```python
@dataclass(frozen=True)
class Section:
    name: str
    categories: list[str]

SCHEMA: list[Section] = [
    Section(name="Regular Inflows",    categories=["Salary"]),
    Section(name="Irregular Inflows",  categories=["Carry Over", "Unexpected / Refund", "Loan"]),
    Section(name="Asset Liquidation",  categories=["Savings", "Stocks & Shares"]),
    Section(name="Regular Outflows",   categories=[
        "Rent", "Bill - Council Tax", "Bill - Electricity & Gas",
        "Bill - Phone & Internet", "Food Supplies", "Debt", "Car & Gas",
    ]),
    Section(name="Irregular Outflows", categories=[
        "Charity / Donations", "Gifts Entertainment & Misc",
        "Sundry", "Holidays & Travel", "Education", "Eating Out",
    ]),
    Section(name="Assets", categories=[
        "Active Savings", "Lifetime ISA", "Stocks & Shares ISA", "Dividend Portfolio",
    ]),
]

INCOME_SECTIONS:  list[str] = ["Regular Inflows", "Irregular Inflows", "Asset Liquidation"]
OUTFLOW_SECTIONS: list[str] = ["Regular Outflows", "Irregular Outflows", "Assets"]
```

Dependencies: none (zero imports)

---

### grouper.py — Category Matching and Assignment

Responsibilities:
- Accept `list[ExpenseItem]` and return `list[CategorisedItem]`
- Run two-pass matching per item (exact then fuzzy) on `item.raw_text` only
- Assign unmatched items to section `"Uncategorised"`, category `"Uncategorised"`
- Collect all unmatched items and return them alongside the matched list so `main.py` can emit warnings
- Never import from `main.py`; never print to stdout/stderr directly

Interfaces:

```python
def group_items(
    items: list[ExpenseItem],
) -> tuple[list[CategorisedItem], list[ExpenseItem]]:
    """Match each ExpenseItem to a (section, category) pair.
    Returns (matched_items, unmatched_items).
    Unmatched items are assigned to "Uncategorised"; the second element
    lets the caller emit warnings without grouper touching stderr."""

def match_category(item_text: str) -> tuple[str, str] | None:
    """Return (section_name, category_name) or None if no match found.
    Pass 1: exact normalised match. Pass 2: fuzzy token/substring match."""

def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation."""

def _exact_match(normalised_text: str) -> tuple[str, str] | None:
    """Compare normalised item text against each normalised category name."""

def _fuzzy_match(normalised_text: str) -> tuple[str, str] | None:
    """Token overlap and substring heuristics — pure Python, no third-party libs."""
```

Dependencies: `categories`, `errors`

Two-pass matching detail:

Pass 1 — Exact match:
- Normalise item text: `_normalise(item.raw_text)`
- For each `Section` in `SCHEMA`, normalise each category name with the same function
- If normalised item text == normalised category name → match

Pass 2 — Fuzzy match (only reached if pass 1 finds nothing):
- Split normalised item text into tokens (whitespace split)
- For each category name, split its normalised form into tokens
- If token set overlap >= 1 AND the overlapping token(s) account for ≥ 50% of the category's
  tokens → match
- Additionally, if the full normalised category name is a substring of the normalised item text
  (or vice versa) → match
- Tie-break: prefer the category with the highest token overlap ratio; if equal, prefer the
  category that appears earlier in `SCHEMA`

---

### summariser.py — Totalling and Grand Totals

Responsibilities:
- Accept `list[CategorisedItem]` and return `list[SectionSummary]`
- Produce one `SectionSummary` per section in `SCHEMA` order, including sections with zero items
- Within each summary, produce one `CategoryTotal` per category in that section's canonical order,
  defaulting to `0.0` for categories with no matched items
- Compute `subtotal` as the sum of all `CategoryTotal.total` values in that section
- Append an additional `SectionSummary` for `"Uncategorised"` if any uncategorised items exist
- Compute grand totals (`Total Income`, `Total Expenditure`) as sums of section subtotals per
  `INCOME_SECTIONS` / `OUTFLOW_SECTIONS`

Interfaces:

```python
def summarise(items: list[CategorisedItem]) -> list[SectionSummary]:
    """Aggregate CategorisedItems into SectionSummary objects in canonical order.
    Always includes every category from SCHEMA (zero-filled when no items match)."""

def compute_grand_totals(
    summaries: list[SectionSummary],
) -> tuple[float, float]:
    """Return (total_income, total_expenditure) by summing the relevant section subtotals."""

def _build_category_totals(
    section_name: str,
    items: list[CategorisedItem],
) -> list[CategoryTotal]:
    """Return one CategoryTotal per category in the section, in canonical order."""
```

Dependencies: `categories`

---

### writer.py — CSV Output

Responsibilities:
- Accept `list[SectionSummary]`, `float` (total income), `float` (total expenditure), and an
  output file path
- Write a UTF-8 CSV with header `section,category,total_amount`
- For each `SectionSummary`, write category rows then the section subtotal row
- After all income sections, write the `Total Income` grand total row (empty section column)
- After all outflow sections, write the `Total Expenditure` grand total row (empty section column)
- If an `"Uncategorised"` summary exists, append it at the end, after the grand totals
- Format all amounts to exactly 2 decimal places
- Use `csv.writer` from stdlib only

Interfaces:

```python
def write_csv(
    summaries: list[SectionSummary],
    total_income: float,
    total_expenditure: float,
    output_path: str,
) -> None:
    """Write the full CSV to output_path. Raises OSError on write failure."""

def _write_section(
    writer: csv.writer,
    summary: SectionSummary,
) -> None:
    """Write category rows and the subtotal row for one section."""

def _fmt(amount: float) -> str:
    """Format a float to a 2-decimal-place string."""
```

Dependencies: `csv` (stdlib), `categories`

---

### errors.py — Custom Exceptions

```python
class ConversionError(Exception):
    """Raised by pdf_converter when neither PDF library can extract usable text."""

class ParseError(Exception):
    """Raised by parser when no ExpenseItem objects are found in the Markdown."""

class GroupingError(Exception):
    """Raised by grouper for a structural/programming error (not for unmatched items)."""
```

Note: unmatched items are not exceptional — they are returned as the second element of
`group_items` and result in stderr warnings from `main.py`, not exceptions.

---

## Data Model

### Core Data Structures

```python
# categories.py
@dataclass(frozen=True)
class Section:
    name: str
    categories: list[str]

# parser.py
@dataclass
class ExpenseItem:
    raw_text: str   # description extracted from PDF (no explicit labels)
    amount: float

# grouper.py
@dataclass
class CategorisedItem:
    section: str    # e.g. "Regular Inflows"
    category: str   # e.g. "Salary" — always a value from SCHEMA or "Uncategorised"
    amount: float

# summariser.py
@dataclass
class CategoryTotal:
    category: str
    total: float

@dataclass
class SectionSummary:
    section: str
    categories: list[CategoryTotal]
    subtotal: float
```

### Data Model Diagram

```mermaid
classDiagram
    class Section {
        +str name
        +list~str~ categories
    }

    class ExpenseItem {
        +str raw_text
        +float amount
    }

    class CategorisedItem {
        +str section
        +str category
        +float amount
    }

    class CategoryTotal {
        +str category
        +float total
    }

    class SectionSummary {
        +str section
        +list~CategoryTotal~ categories
        +float subtotal
    }

    Section "1" --> "many" CategorisedItem : defines valid values for
    CategorisedItem "many" --> "1" SectionSummary : aggregated into
    SectionSummary "1" *-- "many" CategoryTotal : contains
```

---

## Business Process

### Process 1: Full Pipeline Execution

```mermaid
flowchart TD
    START[User invokes\nexpense-summary input.pdf output.csv]
    VALID{Paths valid?}
    EXIT_VAL[Print error to stderr\nsys.exit non-zero]
    CONV[pdf_converter.convert_pdf\nAttempt pdfplumber extraction]
    PLUMB_OK{pdfplumber\nproduced text?}
    MINER[Fallback:\npdfminer extraction]
    MINER_OK{pdfminer\nproduced text?}
    CONV_ERR[Raise ConversionError]
    TEMP[Write Markdown to\nsystem temp file]
    PARSE[parser.parse_items\nScan Markdown lines]
    ITEMS_OK{Items found?}
    PARSE_ERR[Raise ParseError]
    GROUP[grouper.group_items\nTwo-pass match per item]
    SUM[summariser.summarise\nBuild SectionSummary list]
    GRAND[summariser.compute_grand_totals]
    WRITE[writer.write_csv\nWrite output CSV]
    WARN{Any unmatched\nitems?}
    WARN_OUT[Print warnings to stderr]
    CLEANUP[Delete temp .md file\nalways runs via finally]
    SUCCESS[sys.exit 0]
    ERR_CATCH[Catch ConversionError\nParseError\nGroupingError\nPrint message to stderr\nsys.exit non-zero]

    START --> VALID
    VALID -->|No| EXIT_VAL
    VALID -->|Yes| CONV
    CONV --> PLUMB_OK
    PLUMB_OK -->|Yes| TEMP
    PLUMB_OK -->|No| MINER
    MINER --> MINER_OK
    MINER_OK -->|Yes| TEMP
    MINER_OK -->|No| CONV_ERR
    CONV_ERR --> ERR_CATCH
    TEMP --> PARSE
    PARSE --> ITEMS_OK
    ITEMS_OK -->|No| PARSE_ERR
    PARSE_ERR --> ERR_CATCH
    ITEMS_OK -->|Yes| GROUP
    GROUP --> SUM
    SUM --> GRAND
    GRAND --> WRITE
    WRITE --> WARN
    WARN -->|Yes| WARN_OUT
    WARN_OUT --> CLEANUP
    WARN -->|No| CLEANUP
    CLEANUP --> SUCCESS
    ERR_CATCH --> CLEANUP
```

### Process 2: Two-Pass Category Matching (per item)

```mermaid
flowchart TD
    ITEM[ExpenseItem.raw_text]
    NORM[_normalise: lowercase\ncollapse whitespace\nstrip punctuation]
    EXACT[Pass 1: exact_match\nCompare normalised text\nagainst normalised\ncategory names in SCHEMA]
    EXACT_OK{Match found?}
    FUZZY[Pass 2: fuzzy_match\nToken overlap\nSubstring containment]
    FUZZY_OK{Match found?}
    MATCH[Return tuple\nsection_name category_name]
    UNCAT[Return None\nCaller assigns Uncategorised\nCollects for warning]

    ITEM --> NORM
    NORM --> EXACT
    EXACT --> EXACT_OK
    EXACT_OK -->|Yes| MATCH
    EXACT_OK -->|No| FUZZY
    FUZZY --> FUZZY_OK
    FUZZY_OK -->|Yes| MATCH
    FUZZY_OK -->|No| UNCAT
```

### Process 3: CSV Row Emission Order

```mermaid
flowchart TD
    H[Write header row\nsection,category,total_amount]
    RI[Section: Regular Inflows\nOne row per category\n+ subtotal row]
    II[Section: Irregular Inflows\nOne row per category\n+ subtotal row]
    AL[Section: Asset Liquidation\nOne row per category\n+ subtotal row]
    TI[Grand total row\nempty section\nTotal Income]
    RO[Section: Regular Outflows\nOne row per category\n+ subtotal row]
    IO[Section: Irregular Outflows\nOne row per category\n+ subtotal row]
    AS[Section: Assets\nOne row per category\n+ subtotal row]
    TE[Grand total row\nempty section\nTotal Expenditure]
    UC{Uncategorised\nitems exist?}
    UCR[Section: Uncategorised\nOne row per item]
    DONE[File closed]

    H --> RI --> II --> AL --> TI
    TI --> RO --> IO --> AS --> TE
    TE --> UC
    UC -->|Yes| UCR --> DONE
    UC -->|No| DONE
```

### Process 4: Temp File Lifecycle

```mermaid
flowchart TD
    A[main.py calls run_pipeline]
    B[pdf_converter creates temp .md file\ntempfile.mkstemp in sys temp dir]
    C[temp file path stored in variable]
    D{Pipeline succeeds\nor fails?}
    E[finally block executes\nos.unlink on temp path\nif file exists]
    F[No leftover files]

    A --> B --> C --> D
    D -->|either| E --> F
```

---

## Error Handling Strategy

### Error Taxonomy

| Error type | Raised in | Caught in | User message |
|---|---|---|---|
| `SystemExit` (invalid paths) | `main.py` | `main.py` | Descriptive path error to stderr |
| `ConversionError` | `pdf_converter.py` | `main.py` | "Could not convert PDF: {detail}" |
| `ParseError` | `parser.py` | `main.py` | "Could not parse expenses: {detail}" |
| `GroupingError` | `grouper.py` | `main.py` | "Could not group expenses: {detail}" |
| Unmatched items (warning) | `grouper.py` (returned) | `main.py` | Printed to stderr; tool continues |
| `OSError` on CSV write | `writer.py` | `main.py` | Propagates as unhandled; wraps in message |

### Principles

- No raw Python tracebacks are shown to the user under normal operation.
- Only `main.py` writes to stdout or stderr and calls `sys.exit`.
- Unmatched items never cause a crash; they are collected, returned, and reported as warnings:

```
Warning: 2 item(s) could not be matched to a known category:
  - "Misc refund" (£12.50)
  - "TfL" (£4.80)
```

- Temp file cleanup is unconditional: wrapped in a `try/finally` in `run_pipeline` so cleanup runs
  even when an exception propagates.
- If the output CSV path is not writable, the error is detected during input validation (before any
  processing starts), not at write time.

---

## Testing Strategy

### Test Coverage Map

| Test file | Module under test | Key scenarios |
|---|---|---|
| `test_parser.py` | `parser.py` | Valid lines, skipped non-matching lines, currency symbols, commas in amounts, zero-item input raises `ParseError`, malformed amounts skipped |
| `test_grouper.py` | `grouper.py` | Exact match for every category in `SCHEMA`, case-insensitive variants, whitespace variants, unrecognised text returns `None`, fuzzy match on partial tokens |
| `test_summariser.py` | `summariser.py` | Per-category totals, section subtotals, `Total Income` grand total, `Total Expenditure` grand total, zero-filled categories when no items present |

### Design Decisions for Testability

- `parse_items` accepts a plain string — no file I/O needed in tests.
- `group_items` accepts `list[ExpenseItem]` — no PDF or Markdown needed in tests.
- `match_category` is a standalone pure function — trivially unit-testable.
- `summarise` accepts `list[CategorisedItem]` — fully in-memory.
- No global mutable state in any module.
- Tests use small, hand-authored fixture strings and dataclass instances; no real PDFs.

### Test Fixtures Pattern

```python
# test_parser.py
SAMPLE_MD = """\
Salary £3,500.00
Rent 900.00
Unknown item £12.50
not a valid line
"""

def test_parse_items_returns_expected_count():
    items = parse_items(SAMPLE_MD)
    assert len(items) == 3  # "not a valid line" skipped

def test_parse_items_raises_on_empty():
    with pytest.raises(ParseError):
        parse_items("no amounts here\nanother blank line")
```

```python
# test_grouper.py
def test_exact_match_salary():
    assert match_category("Salary") == ("Regular Inflows", "Salary")

def test_exact_match_case_insensitive():
    assert match_category("salary") == ("Regular Inflows", "Salary")

def test_unrecognised_returns_none():
    assert match_category("completely unknown xyz") is None
```

```python
# test_summariser.py
def test_section_subtotal():
    items = [
        CategorisedItem("Regular Inflows", "Salary", 3500.00),
        CategorisedItem("Regular Inflows", "Salary", 200.00),
    ]
    summaries = summarise(items)
    ri = next(s for s in summaries if s.section == "Regular Inflows")
    assert ri.subtotal == 3700.00

def test_grand_totals():
    # ... build items across income and outflow sections
    _, total_income, total_expenditure = summarise(items), *compute_grand_totals(summaries)
    assert total_income == expected_income
    assert total_expenditure == expected_expenditure
```

---

## Design Decisions and Rationale

| Decision | Rationale |
|---|---|
| `pdfplumber` as primary, `pdfminer.six` as fallback | `pdfplumber` offers better layout and table extraction; `pdfminer.six` provides a lower-level fallback when the higher-level lib fails on unusual PDFs |
| Intermediate Markdown string (not parsed directly from PDF objects) | Decouples the PDF extraction step from parsing; the parser can be tested with plain strings; switching PDF libraries does not affect downstream modules |
| Temp file deleted in `finally` block | Guarantees cleanup on both success and failure paths without relying on context managers across module boundaries |
| Two-pass matching (exact then fuzzy) in `grouper.py` | Exact matching is deterministic and O(n) in category count; fuzzy matching only runs when exact fails, keeping the common case fast and predictable |
| `categories.py` with zero imports | Makes it safe for all other modules to import from it without circular dependency risk |
| Unmatched items returned, not raised | Keeps the tool useful even with partial coverage; the user sees a warning and still receives a CSV for the matched items |
| Categories zero-filled when missing | Ensures the CSV always has a consistent, comparable structure across monthly reports |
| `csv` stdlib only | Avoids pandas as a dependency; the output format is simple enough for stdlib |
| Functions capped at ~30 lines | Keeps each function independently testable and readable without scrolling |
