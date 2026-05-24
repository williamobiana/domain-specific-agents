---
name: structure
description: File and module structure for the expense summary CLI tool. All code must follow this layout.
---

## Structure

```
expense-summary/
├── src/
│   ├── main.py          # Entry point — parses CLI args, calls pipeline, handles top-level errors
│   ├── pdf_converter.py # PDF → Markdown conversion
│   ├── parser.py        # Markdown → list of raw ExpenseItem objects
│   ├── categories.py    # Canonical category/section schema — the single source of truth for all category names
│   ├── grouper.py       # Maps ExpenseItems to known categories — ALL matching logic lives here
│   ├── summariser.py    # Sums amounts per category, computes section subtotals and grand totals
│   └── writer.py        # Writes the final CSV in canonical section order
├── tests/
│   ├── test_parser.py
│   ├── test_grouper.py
│   └── test_summariser.py
├── requirements.txt
└── README.md
```

## Module responsibilities

| Module | Single responsibility |
|---|---|
| `main.py` | CLI wiring only — no business logic |
| `pdf_converter.py` | Accept a PDF path, convert it to a `.docx` via `pdf2docx`, return the temp `.docx` file path |
| `parser.py` | Accept a `.docx` file path, extract expense items from Word tables (bank statements) or paragraphs (plain-text reports), return a list of `ExpenseItem` objects with description, amount, and direction |
| `categories.py` | Declare the canonical schema (sections, category names, order) — **nothing else imports this definition from anywhere else** |
| `grouper.py` | Accept a list of `ExpenseItem`, return a list of `CategorisedItem` — **the only place category-matching logic lives**, uses item direction to bias section selection |
| `summariser.py` | Accept a list of `CategorisedItem`, return `SectionSummary` objects with per-category totals, section subtotals, and grand totals |
| `writer.py` | Accept a list of `SectionSummary` and an output path, write the CSV in canonical order |

## Data types

```python
# categories.py — canonical schema, imported by grouper and writer
SCHEMA: list[Section] = [
    Section(name="Regular Inflows", categories=[
        "Salary",
    ]),
    Section(name="Irregular Inflows", categories=[
        "Carry Over",
        "Unexpected / Refund",
        "Loan",
    ]),
    Section(name="Asset Liquidation", categories=[
        "Savings",
        "Stocks & Shares",
    ]),
    # ... and so on for outflow sections
]

INCOME_SECTIONS  = ["Regular Inflows", "Irregular Inflows", "Asset Liquidation"]
OUTFLOW_SECTIONS = ["Regular Outflows", "Irregular Outflows", "Assets"]

# parser.py
@dataclass
class ExpenseItem:
    raw_text: str    # parsed item description text from the report (no labelled fields)
    amount: float    # parsed numeric value
    direction: str   # 'in' (Money In / credit) or 'out' (Money Out / debit); default 'out'

# grouper.py
@dataclass
class CategorisedItem:
    section: str          # e.g. "Regular Inflows"
    category: str         # e.g. "Salary" — must be a value from SCHEMA
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
    subtotal: float          # sum of all category totals in this section
```

## CSV output format

```
section,category,total_amount
Regular Inflows,Salary,3500.00
Regular Inflows,Total Regular Inflows,3500.00
Irregular Inflows,Carry Over,200.00
...
,Total Income,3700.00
Regular Outflows,Rent,900.00
...
,Total Expenditure,2400.00
```

- Section subtotal rows repeat the section name and use `Total <Section Name>` as the category.
- Grand total rows (`Total Income`, `Total Expenditure`) have an empty section column.
- All amounts formatted to 2 decimal places.

## Rules

- `categories.py` is the single source of truth for category and section names. No other module hard-codes a category string.
- Grouping/matching logic lives only in `grouper.py`. Never in `parser.py`, `summariser.py`, or `writer.py`.
- `main.py` is the only module that prints to stdout/stderr or calls `sys.exit`.
- No module imports from `main.py`.
- Tests cover `parser`, `grouper`, and `summariser` independently.
- Intermediate `.docx` file goes in the system temp directory, not alongside the input file.
- If a parsed item does not match any known category, `grouper.py` raises a warning (logged to stderr via `main.py`) and assigns it to an `"Uncategorised"` bucket — it does not crash.
