# Steering: Technology Decisions

## Language & Runtime

- **Python 3.8+** — f-strings, `match`/`case`, and `argparse` with `BooleanOptionalAction` are all available
- No virtual environment is prescribed; `requirements.txt` is the only dependency manifest

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pdfplumber` | latest stable | Extract text and table data from text-based PDFs |
| `pyyaml` | latest stable | Parse `rules.yml` |

No other third-party packages. Standard library covers everything else:
- `argparse` — CLI argument parsing
- `csv` — CSV output via `csv.writer`
- `sys` — `sys.exit()` for error cases
- `re` — case-insensitive keyword matching if needed
- `pathlib` — file path handling (prefer over `os.path`)

## PDF Extraction with `pdfplumber`

Open statements with `pdfplumber.open(path)` and iterate pages. Transactions are expected in a consistent table layout — extract with `page.extract_table()`, not `page.extract_text()`. Each row maps directly to the transaction dict defined in `structure.md`.

```python
import pdfplumber

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        table = page.extract_table()
        # table is a list of lists; row[0]=date, row[1]=description, etc.
```

## Rules Loading with `pyyaml`

Load with `yaml.safe_load()` — never `yaml.load()` (unsafe).

```python
import yaml

with open(rules_path) as f:
    config = yaml.safe_load(f)
rules = config["rules"]  # list of dicts
```

## CSV Output

Use `csv.writer` with default dialect. The header row is `["Category", "Amount"]`. All amount values are formatted to two decimal places as strings before writing — do not rely on `csv.writer` for float formatting.

```python
import csv

with open(output_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Category", "Amount"])
    for label, value in rows:
        writer.writerow([label, f"{value:.2f}"])
```

## CLI with `argparse`

Use a single `ArgumentParser`. Boolean flags use `BooleanOptionalAction` so users can pass `--no-exclude-self-transfers` to disable defaults.

```python
import argparse

parser = argparse.ArgumentParser(prog="expense-parser")
parser.add_argument("input", metavar="input.pdf")
parser.add_argument("--rules", "-r", default="rules.yml")
parser.add_argument("--output", "-o", default="expense_report.csv")
parser.add_argument("--unmapped-log", default="unmapped.log")
parser.add_argument("--exclude-self-transfers", action=argparse.BooleanOptionalAction, default=True)
parser.add_argument("--strict", action="store_true", default=False)
```

## Error Handling

Use `sys.exit(message)` for all user-facing errors — this prints the message to stderr and exits with code 1 without a traceback. Never `raise` to the top level.

```python
import sys

if not Path(rules_path).exists():
    sys.exit(f"Rules file not found: {rules_path}")
```

## Testing

- **`pytest`** — test runner (dev dependency only, not in `requirements.txt`)
- One test file per component matching the layout in `structure.md`:
  - `tests/test_extractor.py` — mock `pdfplumber.open` or use `tests/fixtures/sample.pdf`
  - `tests/test_classifier.py` — pure unit tests; no file I/O
  - `tests/test_report.py` — assert exact row order and subtotal calculations against known inputs
- Tests must not write to disk; use `tmp_path` (pytest fixture) for any output file assertions

## What to Avoid

- `yaml.load()` — use `yaml.safe_load()` only
- `os.path` — use `pathlib.Path` instead
- `print()` for errors — use `sys.exit(message)` for errors, `print()` only for the progress summary
- Splitting logic across multiple `.py` files — everything stays in `expense_parser.py`
- Pinning dependency versions in `requirements.txt` — list package names only
