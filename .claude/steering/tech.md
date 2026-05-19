---
description: Technology choices and coding conventions for the expense summary CLI tool. All implementation must follow these decisions.
---

## Language

Python 3.11+

## Dependencies

| Purpose | Library | Notes |
|---|---|---|
| PDF → text | `pdfplumber` | Preferred over PyPDF2 — better table and layout extraction |
| Markdown output | `markdownify` or plain string formatting | Keep it simple; the `.md` is an intermediate, not a deliverable |
| CSV writing | `csv` (stdlib) | No third-party library needed |
| CLI args | `argparse` (stdlib) | No Click or Typer — keep dependencies minimal |
| Testing | `pytest` | Standard, no extras required |

> If `pdfplumber` cannot extract usable text from a given PDF, fall back to `pdfminer.six`. Document the fallback in a comment.

## Coding conventions

- Type hints on all function signatures
- Dataclasses for structured data (see `structure.md`)
- Raise custom exceptions (`ParseError`, `ConversionError`) rather than returning `None` or bare strings for error states
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
```

## Testing expectations

- Unit tests for `parser`, `grouper`, `summariser`
- Use small fixture strings/objects — no real PDFs in tests
- Test the unhappy path: malformed input, zero rows, amounts that cannot be parsed

## What to avoid

- Do not use LLMs or external APIs for parsing or grouping
- Do not use pandas — `csv` stdlib is sufficient
- Do not add a database or any persistence beyond the output CSV
- Do not create a `setup.py` or packaging infrastructure unless explicitly requested