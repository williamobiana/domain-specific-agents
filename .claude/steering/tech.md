---
name: tech
description: Technology choices and coding conventions for the expense summary CLI tool. All implementation must follow these decisions.
---

## Language

Python 3.8+

## Dependencies

| Purpose | Library | Notes |
|---|---|---|
| PDF → text | `pdfplumber` | Preferred — better table and layout extraction than PyPDF2 |
| Markdown output | plain string formatting | The `.md` is an intermediate only, not a deliverable |
| CSV writing | `csv` (stdlib) | No third-party library needed |
| CLI args | `argparse` (stdlib) | No Click or Typer — keep dependencies minimal |
| Testing | `pytest` | Standard, no extras required |

> If `pdfplumber` cannot extract usable text from a given PDF, fall back to `pdfminer.six`. Document the fallback in a comment.

## Category matching strategy

Matching in `grouper.py` works in two passes:

> NOTE: The source PDF contains no explicit labeled fields — only item description text and an amount. All matching must therefore operate on the parsed item text/description (and optionally the amount) only.

1. **Exact match** — normalise both the parsed item text and the canonical category name (lowercase, collapse whitespace, strip punctuation) and compare directly.
2. **Fuzzy match** — if exact match fails, use a simple substring or token overlap check. Do not use a third-party fuzzy library; keep it in plain Python.

If neither pass produces a match, assign the item to `"Uncategorised"` and emit a warning. The match function must accept an item text string (the parsed description) and return a `(section, category)` tuple or `None`.

```python
# grouper.py — canonical signature
def match_category(item_text: str) -> tuple[str, str] | None:
    """Return (section_name, category_name) or None if no match found.
    `item_text` is the parsed description extracted from the PDF (there are no explicit labels)."""
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

- Unit tests for `parser`, `grouper`, `summariser`
- `test_grouper.py` must cover:
  - Exact label matches for every category in the schema
  - Case-insensitive and whitespace-variant matches
  - An unrecognised label returning `None`
- `test_summariser.py` must verify section subtotals and both grand totals (`Total Income`, `Total Expenditure`)
- Use small fixture strings/objects — no real PDFs in tests
- Test the unhappy path: malformed input, zero rows, amounts that cannot be parsed

## What to avoid

- Do not infer or invent new categories — the schema in `categories.py` is fixed
- Do not use LLMs or external APIs for parsing or matching
- Do not use pandas — `csv` stdlib is sufficient
- Do not add a database or any persistence beyond the output CSV
- Do not create a `setup.py` or packaging infrastructure unless explicitly requested
