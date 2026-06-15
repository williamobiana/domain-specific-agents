# Project Structure

This repository hosts two sibling packages, one per supported bank: `lloyds_expense` and `monzo_expense`. They share intent and schema shape but are deliberately separate codebases — different parsers, different rules-file dialects, different CLIs. Common concepts (the budget schema, the writer's row order) are duplicated between them by design; forcing premature sharing would couple the two banks' quirks together.

## Top-level layout

```
.
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── .gitignore
├── src/
│   ├── lloyds_expense/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── schema.py
│   │   ├── parser.py
│   │   ├── rules.py
│   │   ├── classifier.py
│   │   ├── reconciler.py
│   │   ├── writer.py
│   │   └── errors.py
│   └── monzo_expense/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── schema.py
│       ├── parser.py
│       ├── rules.py
│       ├── classifier.py
│       ├── splitter.py        # NEW — Monzo-only, groups transactions by calendar month
│       ├── reconciler.py
│       ├── writer.py
│       └── errors.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── lloyds/
│   │   ├── fixtures/
│   │   │   ├── statement_minimal.pdf
│   │   │   ├── statement_full.pdf
│   │   │   └── rules_example.yaml
│   │   ├── test_parser.py
│   │   ├── test_rules.py
│   │   ├── test_classifier.py
│   │   ├── test_reconciler.py
│   │   ├── test_writer.py
│   │   └── test_cli.py
│   └── monzo/
│       ├── fixtures/
│       │   ├── statement_minimal.pdf
│       │   ├── statement_multi_month.pdf
│       │   └── rules_example.yaml
│       ├── test_parser.py
│       ├── test_rules.py
│       ├── test_classifier.py
│       ├── test_splitter.py
│       ├── test_reconciler.py
│       ├── test_writer.py
│       └── test_cli.py
└── examples/
    ├── lloyds_rules.example.yaml
    ├── lloyds_sample_output.csv
    ├── monzo_rules.example.yaml
    └── monzo_sample_output.csv
```

## `src/` layout

A `src/`-layout project (not flat). Each bank gets its own subpackage. Tests import installed packages, never the working tree.

The two packages have **no cross-imports**. If `monzo_expense` needs something from `lloyds_expense`, that's a signal the shared concept should be extracted into a third package (`bank_expense_core` or similar) — but until there's a third bank, the duplication is cheaper than the abstraction.

## Module responsibilities — `lloyds_expense`

See the original module responsibilities documented earlier in this section (unchanged). Briefly: `schema.py` is the source of truth for budget shape; `parser.py` extracts transactions from a Lloyds Classic PDF; `rules.py` loads and validates YAML rules with type-code support; `classifier.py` runs two-pass exact-then-regex matching; `reconciler.py` checks classified totals against the statement's Money In / Money Out; `writer.py` emits a single CSV; `cli.py` orchestrates and is the only I/O boundary.

## Module responsibilities — `monzo_expense`

Each module has one job. Modules import downward in this list — never upward, never sideways across peers when it can be avoided.

### `schema.py` — the source of truth for the budget shape
- Defines the closed enumeration of sections and categories.
- Declares the output row order (the canonical schema spelled out in `monzo_expense/product.md`).
- **Adds `MAIN_ACCOUNT_INFLOW` to the Irregular Inflows section** — the only schema difference from `lloyds_expense`.
- Exposes helpers: "which section does this category belong to?", "iterate all rows in display order".
- Pure data and pure functions. No I/O. No dependencies on other project modules.

### `errors.py` — exception hierarchy
- `StatementToCsvError` (base)
- `ParseError`, `RulesConfigError`, `UnmatchedTransactionsError`, `ReconciliationError`, `InputError`
- Mirror of `lloyds_expense/errors.py`. No logic, no imports beyond stdlib.

### `parser.py` — PDF → typed transactions
- Single public function: `parse_statement(path: Path) -> Statement`.
- `Statement` is a frozen dataclass holding: account metadata (sort code, account number, period start/end), `total_deposits`, `total_outgoings`, `opening_balance`, `closing_balance`, and `list[Transaction]`.
- `Transaction` is a frozen dataclass: `date`, `description`, `amount: Decimal`, `direction: Literal["in", "out"]`, `running_balance: Decimal`. **No `type_code` field** — Monzo statements do not carry transaction-type codes.
- Re-joins description lines that wrap across multiple PDF rows (common for Faster Payments entries with `Reference: …` and for currency-conversion lines).
- Ignores Pot statement pages — these appear after the personal-account section and are not part of the cash-flow view.
- Uses `pdfplumber`. All Monzo-specific layout assumptions live here and nowhere else.
- Raises `ParseError` on anything unexpected.

### `rules.py` — YAML → rule objects
- Loads, validates, and compiles the rules file into an ordered list of `Rule` objects.
- Validates every `category` against `schema.py` at load time — unknown categories raise `RulesConfigError` immediately.
- Compiles regex rules once, at load time.
- **No `type_code` field** in the rule schema (Monzo has no type codes). Fields are: `match` | `match_regex`, optional `direction`, required `category`.
- No matching logic — that's `classifier.py`'s job.

### `classifier.py` — transactions × rules → categorised transactions
- Single public function: `classify(transactions, rules) -> ClassificationResult`.
- `ClassificationResult` holds the matched transactions (each tagged with its category) and the unmatched list.
- First-match-wins, in rules-file order. Two-pass: exact matches before regex matches.
- Pure function. No I/O.

### `splitter.py` — calendar-month grouping (Monzo-only)
- Single public function: `split_by_month(result: ClassificationResult) -> dict[YearMonth, ClassificationResult]`.
- Groups classified transactions by `(year, month)` of their transaction date.
- Each output `ClassificationResult` preserves document order within its month.
- Pure function. No I/O.

### `reconciler.py` — sanity check against the statement
- Sums classified inflows and outflows across **all months combined** in `Decimal`.
- Compares to `Statement.total_deposits` and `Statement.total_outgoings` (the period grand totals from page 1).
- Returns a `ReconciliationReport` (ok or mismatched, with the diffs). Does not raise — the caller decides.
- Reconciliation is period-level, not per-month, because Monzo only prints period totals.

### `writer.py` — categorised data → CSVs (plural)
- Single public function: `write_csvs(by_month: dict[YearMonth, ClassificationResult], statement: Statement, out_dir: Path) -> list[Path]`.
- For each month, writes one CSV named `<account>_<YYYY-MM>.csv` (or just `<YYYY-MM>.csv` if account info is sensitive).
- Iterates `schema.py`'s canonical row order, summing matched transactions per category for that month.
- Emits section headers, line items, subtotals, and grand totals — every row, every time, zero-filled where empty.
- Deterministic output: fixed column order, fixed line endings, fixed decimal formatting, fixed file ordering.
- Returns the list of files written, in chronological order, for the CLI to display.

### `cli.py` — the only place that touches argv, stdout, stderr, or sys.exit
- `typer` app with one command.
- Wires parser → rules → classifier → splitter → reconciler → writer.
- Catches every `StatementToCsvError` subclass and maps it to the documented exit codes with `rich`-formatted output.
- Library modules never call `print`. The CLI is the only "outer edge."
- Uses `--out-dir` (not `--out`) because Monzo produces multiple files.

### `__main__.py`
- Two lines: import the typer app and call it. Enables `python -m monzo_expense`.

## Test layout

- One test module per source module, plus `test_cli.py` for end-to-end invocations, **per package**.
- `conftest.py` (top-level) provides shared fixtures usable by either bank's tests.
- Bank-specific fixtures live under `tests/<bank>/fixtures/`. Fixtures are checked in; tests must not reach the network.
- End-to-end tests invoke the CLI via `typer.testing.CliRunner` and assert on exit code, stdout, stderr, and the byte content of generated CSVs.
- Golden-file testing for `writer.py`: known inputs produce CSVs that match committed expected files byte-for-byte. Regenerating golden files is a deliberate, reviewed action.
- The Monzo multi-month fixture must cover at least two calendar months to exercise `splitter.py` and the multi-CSV writer behaviour.

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
| A new budget category | `<bank>/schema.py` (and the example rules file) |
| A new way to match a rule (e.g. amount ranges) | `<bank>/rules.py` for the spec, `<bank>/classifier.py` for the match logic |
| A change to the PDF layout assumptions | `<bank>/parser.py` only |
| A change to how months are grouped | `monzo_expense/splitter.py` only |
| A new exit code or user-facing message | `<bank>/cli.py` and `<bank>/errors.py` |
| A new output column or row | `<bank>/schema.py` (declaration) + `<bank>/writer.py` (emission) |
| Anything that calls `print` | `<bank>/cli.py` — or it's wrong |
| Logic that would be shared between Lloyds and Monzo | Stop. Duplicate it. Revisit only when a third bank arrives. |