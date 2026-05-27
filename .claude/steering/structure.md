# Project Structure

## Top-level layout

```
.
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── .gitignore
├── src/
│   └── lloyds-expense/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── schema.py
│       ├── parser.py
│       ├── rules.py
│       ├── classifier.py
│       ├── reconciler.py
│       ├── writer.py
│       └── errors.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── statement_minimal.pdf
│   │   ├── statement_full.pdf
│   │   └── rules_example.yaml
│   ├── test_parser.py
│   ├── test_rules.py
│   ├── test_classifier.py
│   ├── test_reconciler.py
│   ├── test_writer.py
│   └── test_cli.py
└── examples/
    ├── rules.example.yaml
    └── sample_output.csv
```

## `src/` layout

A `src/`-layout project (not flat). This forces tests to import the installed package rather than picking up the working-tree directory by accident, and matches the modern Python packaging norm.

## Module responsibilities

Each module has one job. Modules import downward in this list — never upward, never sideways across peers when it can be avoided.

### `schema.py` — the source of truth for the budget shape
- Defines the closed enumeration of sections and categories.
- Declares the output row order (the canonical schema spelled out in `product.md`).
- Exposes helpers: "which section does this category belong to?", "iterate all rows in display order".
- Pure data and pure functions. No I/O. No dependencies on other project modules.
- Everything else in the codebase references categories *through this module* — no string literals for category names anywhere else.

### `errors.py` — exception hierarchy
- `StatementToCsvError` (base)
- `ParseError`, `RulesConfigError`, `UnmatchedTransactionsError`, `ReconciliationError`, `InputError`
- No logic, no imports beyond stdlib.

### `parser.py` — PDF → typed transactions
- Single public function: `parse_statement(path: Path) -> Statement`.
- `Statement` is a frozen dataclass holding: account metadata (sort code, account number, period), `money_in_total`, `money_out_total`, `opening_balance`, `closing_balance`, and `list[Transaction]`.
- `Transaction` is a frozen dataclass: `date`, `description`, `type_code`, `amount: Decimal`, `direction: Literal["in", "out"]`, `running_balance: Decimal`.
- Uses `pdfplumber`. All Lloyds-specific layout assumptions live here and nowhere else.
- Raises `ParseError` on anything unexpected.

### `rules.py` — YAML → rule objects
- Loads, validates, and compiles the rules file into an ordered list of `Rule` objects.
- Validates every `category` against `schema.py` at load time — unknown categories raise `RulesConfigError` immediately.
- Compiles regex rules once, at load time.
- No matching logic — that's `classifier.py`'s job.

### `classifier.py` — transactions × rules → categorised transactions
- Single public function: `classify(transactions, rules) -> ClassificationResult`.
- `ClassificationResult` holds the matched transactions (each tagged with its `(section, category)`) and the unmatched list.
- First-match-wins, in rules-file order.
- Pure function. No I/O.

### `reconciler.py` — sanity check against the statement
- Sums classified inflows and outflows in `Decimal`.
- Compares to `Statement.money_in_total` and `Statement.money_out_total`.
- Returns a `ReconciliationReport` (ok or mismatched, with the diffs). Does not raise — the caller decides what to do.

### `writer.py` — categorised data → CSV
- Single public function: `write_csv(result: ClassificationResult, out: Path) -> None`.
- Iterates `schema.py`'s canonical row order, summing matched transactions per category.
- Emits section headers, line items, subtotals, and grand totals — every row, every time, zero-filled where empty.
- Deterministic output: fixed column order, fixed line endings, fixed decimal formatting.

### `cli.py` — the only place that touches argv, stdout, stderr, or sys.exit
- `typer` app with one command.
- Wires parser → rules → classifier → reconciler → writer.
- Catches every `StatementToCsvError` subclass and maps it to the documented exit codes with `rich`-formatted output.
- Library modules never call `print`. The CLI is the only "outer edge."

### `__main__.py`
- Two lines: import the typer app and call it. Enables `python -m statement_to_csv`.

## Test layout

- One test module per source module, plus `test_cli.py` for end-to-end invocations.
- `conftest.py` provides shared fixtures: a parsed sample `Statement`, a loaded rules set, a `tmp_path`-based output directory.
- `fixtures/` holds redacted real-shape PDFs and a representative `rules.yaml`. Fixtures are checked in; tests must not reach the network.
- End-to-end tests in `test_cli.py` invoke the CLI via `typer.testing.CliRunner` and assert on exit code, stdout, stderr, and the byte content of the generated CSV.
- Golden-file testing for `writer.py`: a known input produces a CSV that matches a committed expected file byte-for-byte. Regenerating the golden file is a deliberate, reviewed action.

## Conventions

- **Type hints everywhere.** Public functions have full signatures; internal helpers too. `mypy --strict` is the gate.
- **Dataclasses are `frozen=True`** by default. Mutation is opt-in and rare.
- **No module-level state** other than constants. No singletons, no globals, no caches.
- **Paths are `pathlib.Path`**, never `str`, from the CLI boundary inward.
- **Money is `Decimal`**, from parser to writer. The only `float` allowed in the codebase is one that comes from a third-party library, and it's converted immediately.
- **One public function per module** where practical. If a module grows a second one, that's a signal it might want splitting.
- **Imports**: stdlib first, third-party second, project last. Ruff enforces the order.

## Where things go when in doubt

| If you're adding… | It lives in… |
|---|---|
| A new budget category | `schema.py` (and `examples/rules.example.yaml`) |
| A new way to match a rule (e.g. amount ranges) | `rules.py` for the spec, `classifier.py` for the match logic |
| A change to the PDF layout assumptions | `parser.py` only |
| A new exit code or user-facing message | `cli.py` and `errors.py` |
| A new output column or row | `schema.py` (declaration) + `writer.py` (emission) |
| Anything that calls `print` | `cli.py` — or it's wrong |