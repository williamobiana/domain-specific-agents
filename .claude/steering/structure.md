---
description: File and module structure for the expense summary CLI tool. All code must follow this layout.
---

## Structure

```
expense-summary/
├── src/
│   ├── main.py          # Entry point — parses CLI args, calls pipeline, handles top-level errors
│   ├── pdf_converter.py # PDF → Markdown conversion
│   ├── parser.py        # Markdown → list of raw expense line items
│   ├── grouper.py       # Groups expense items by name — ALL grouping logic lives here
│   ├── summariser.py    # Sums amounts per group → list of (group_name, total)
│   └── writer.py        # Writes the final CSV
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
| `pdf_converter.py` | Accept a PDF path, return a Markdown string |
| `parser.py` | Accept a Markdown string, return a list of `ExpenseItem` objects |
| `grouper.py` | Accept a list of `ExpenseItem`, return a list of `GroupedExpense` — **the only place grouping logic lives** |
| `summariser.py` | Accept a list of `GroupedExpense`, return `(group_name, total)` pairs |
| `writer.py` | Accept `(group_name, total)` pairs and an output path, write the CSV |

## Data types

```python
# parser.py
@dataclass
class ExpenseItem:
    raw_label: str   # original text from the report
    amount: float    # parsed numeric value

# grouper.py
@dataclass
class GroupedExpense:
    group_name: str
    items: list[ExpenseItem]
```

## Rules

- Each module does one thing. Do not let grouping logic bleed into `parser.py` or `summariser.py`.
- `main.py` is the only module that prints to stdout/stderr or calls `sys.exit`.
- No module imports from `main.py`.
- Tests cover `parser`, `grouper`, and `summariser` independently.
- Intermediate `.md` file (if written to disk) goes in the system temp directory, not alongside the input file.
