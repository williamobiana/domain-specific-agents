---
name: tech
description: Technology choices and coding conventions for the expense summary CLI tool. All implementation must follow these decisions.
---

## Language

Python 3.8+

## Dependencies

| Purpose | Library | Notes |
|---|---|---|
| PDF → Word | `pdf2docx` | Primary converter; preserves table structure from bank statements |
| Word reading | `python-docx` | Reads the `.docx` intermediate to extract tables and paragraphs |
| CSV writing | `csv` (stdlib) | No third-party library needed |
| CLI args | `argparse` (stdlib) | No Click or Typer — keep dependencies minimal |
| Testing | `pytest` | Standard, no extras required |

> If `pdf2docx` fails to convert or produces an empty document, raise `ConversionError`. No text-extraction fallback — the `.docx` is the single intermediate format.

## Category matching strategy

Matching in `grouper.py` works in three passes, using both description text and transaction direction:

> NOTE: The source PDF contains no explicit labeled fields — only item description text, an amount, and a direction (Money In / Money Out). Matching operates on the description text; direction is used to bias toward income vs outflow sections.

1. **Exact match** — normalise both the parsed item text and the canonical category name (lowercase, collapse whitespace, strip punctuation) and compare directly.
2. **Keyword match** — check the normalised text against a table of common bank description patterns (e.g. `"regular sav"` → Active Savings, `"trading 212"` → Stocks & Shares ISA). Pure Python; no third-party library.
3. **Fuzzy match** — if exact and keyword match both fail, use a substring or token overlap check, biased toward income sections for `direction='in'` and outflow sections for `direction='out'`. Pure Python only.

If no pass produces a match, assign the item to `"Uncategorised"` and emit a warning. The match function accepts the description text and an optional direction:

```python
# grouper.py — canonical signature
def match_category(item_text: str, direction: str = 'out') -> tuple[str, str] | None:
    """Return (section_name, category_name) or None if no match found."""
```

Category names are imported from `categories.py` — never hard-coded in `grouper.py` logic.

## Coding conventions

- Type hints on all function signatures
- Dataclasses for structured data (see `structure.md`)
- Raise custom exceptions (`ParseError`, `ConversionError`, `GroupingError`) rather than returning `None` or bare strings for error states
- `main.py` catches all custom exceptions and prints a clean message — no raw tracebacks shown to the user
- Functions stay small: if a function exceeds ~30 lines, split it
- No global mutable state

## Error handling pattern

```python
# Custom exceptions live in src/errors.py
class ConversionError(Exception): pass
class ParseError(Exception): pass
class GroupingError(Exception): pass
```

Each module raises its own exception type. `main.py` catches them all:

```python
try:
    run_pipeline(input_path, output_path)
except ConversionError as e:
    sys.exit(f"Could not convert PDF: {e}")
except ParseError as e:
    sys.exit(f"Could not parse expenses: {e}")
except GroupingError as e:
    sys.exit(f"Could not group expenses: {e}")
```

Unmatched categories are warnings, not exceptions — the tool continues and notes them at the end:
```
Warning: 2 item(s) could not be matched to a known category and were skipped:
  - "Misc refund" (£12.50)
  - "TfL" (£4.80)
```

## Testing expectations

- Unit tests for `pdf_converter`, `parser`, `grouper`, `summariser`
- `test_pdf_converter.py` must cover conversion success/failure paths (mock pdf2docx)
- `test_parser.py` must cover:
  - Table-based extraction from a .docx with a transactions table (Money In / Money Out columns)
  - Paragraph-based extraction from a .docx with plain text expense lines
  - `ParseError` raised when the document has no usable expense items
- `test_grouper.py` must cover:
  - Exact label matches for every category in the schema
  - Case-insensitive and whitespace-variant matches
  - Keyword matches (e.g. "HLAM REGULAR SAVIN" → Active Savings)
  - Direction-biased matching: `direction='in'` prefers income sections
  - An unrecognised label returning `None`
- `test_summariser.py` must verify section subtotals and both grand totals (`Total Income`, `Total Expenditure`)
- Use small in-memory `.docx` objects (built with python-docx) as fixtures — no real PDFs
- Test the unhappy path: empty document, zero rows, amounts that cannot be parsed

## What to avoid

- Do not infer or invent new categories — the schema in `categories.py` is fixed
- Do not use LLMs or external APIs for parsing or matching
- Do not use pandas — `csv` stdlib is sufficient
- Do not add a database or any persistence beyond the output CSV
- Do not create a `setup.py` or packaging infrastructure unless explicitly requested
- Do not use pdfplumber or pdfminer.six — pdf2docx is the single PDF conversion library
