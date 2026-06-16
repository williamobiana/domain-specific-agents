# bank-expense-tools

Three CLI tools that parse UK personal bank statement PDFs and produce categorised monthly cash-flow CSVs:

- **`lloyds-expense`** — Lloyds Bank Classic personal account → one CSV per run
- **`monzo-expense`** — Monzo personal account → one CSV per calendar month covered by the statement
- **`revolut-expense`** — Revolut GBP personal account → one CSV per calendar month covered by the statement

All tools share the same budget schema and the same pipeline: parse → classify → reconcile → write. They are separate codebases because each bank's PDF has an incompatible format.

## Installation

Requires Python 3.11+. Install with [uv](https://github.com/astral-sh/uv):

```sh
uv sync
```

---

## lloyds-expense

### How it works

1. **Parse** — extracts metadata and transactions from the PDF using `pdfplumber`. Handles both structured table extraction and Lloyds' garbled accessibility-overlay text format.
2. **Load rules** — reads a YAML file mapping transaction descriptions and type codes to budget categories.
3. **Classify** — two-pass exact-then-regex matching. Any unmatched transactions abort the run.
4. **Reconcile** — verifies classified totals equal the statement's Money In / Money Out figures.
5. **Write** — emits a single fixed-schema CSV.

### Usage

```sh
uv run lloyds-expense <statement.pdf>
```

| Option | Default | Description |
|---|---|---|
| `--rules` | `rules/rules.yaml` | Path to YAML rules file |
| `--out` | `<pdf-stem>.csv` in current directory | Output CSV path |
| `--report-unmatched` | — | Write unmatched transactions to this file |

### Rules file

Rules live in `rules/rules.yaml`. Each rule maps a transaction to a budget category:

```yaml
rules:
  - match: NATIONAL SERV M/W   # exact description match
    type: BGC                   # Lloyds type code (optional)
    direction: in               # "in" or "out" (optional)
    category: Salary

  - match_regex: "^AMAZON.*"   # regex match (alternative to match)
    direction: out
    category: Gifts/Entertainment/Misc
```

**Fields:**

- `match` — exact description string (whitespace-normalised, Unicode hyphens collapsed to ASCII)
- `match_regex` — regular expression applied against the normalised description
- `type` — Lloyds type code filter; one of `BGC`, `DD`, `DEB`, `FPI`, `FPO`, `BP`, `CHG`, `CHQ`, `COR`, `CPT`, `DEP`, `FEE`, `MPI`, `MPO`, `PAY`, `SO`, `TFR`
- `direction` — `in` or `out`
- `category` — must be one of the supported budget categories

---

## monzo-expense

### How it works

1. **Parse** — extracts metadata and transactions from the PDF using word-position extraction (`pdfplumber`). Monzo PDFs have no structured table borders, so column layout is inferred from x-coordinates. Handles multi-line descriptions, Pot pages (ignored), and multi-month statements.
2. **Load rules** — reads a YAML file mapping transaction descriptions to budget categories. No type code field (Monzo statements carry no transaction-type codes).
3. **Classify** — two-pass exact-then-regex matching. Any unmatched transactions abort the run.
4. **Split** — groups transactions by calendar month.
5. **Reconcile** — verifies classified totals equal the statement's Total deposits / Total outgoings figures.
6. **Write** — emits one CSV per calendar month (e.g. `monzo-2026-04.csv`, `monzo-2026-05.csv`).

### Usage

```sh
uv run monzo-expense <statement.pdf>
```

| Option | Default | Description |
|---|---|---|
| `--rules` | `rules/monzo_rules.yaml` | Path to YAML rules file |
| `--out-dir` | `./output` | Directory to write CSVs into |
| `--report-unmatched` | — | Write unmatched transactions to this file |

### Rules file

Rules live in `rules/monzo_rules.yaml`. Monzo rules do **not** support a `type` field:

```yaml
rules:
  - match: "O Okwu-Boms (Faster Payments)"
    direction: in
    category: "Main Account Inflow"

  - match_regex: "^Adamira Driving School"   # covers "Reference: ..." suffixes
    direction: out
    category: "Car & Gas"
```

**Fields:**

- `match` — exact description string
- `match_regex` — regular expression applied against the normalised description
- `direction` — `in` or `out` (optional)
- `category` — must be one of the supported budget categories

When a new statement produces unmatched transactions, add rules for the new descriptions and re-run.

---

## revolut-expense

### How it works

1. **Parse** — extracts metadata and transactions from the PDF using word-position extraction (`pdfplumber`). Revolut PDFs have no structured table borders, so column layout is inferred from x-coordinates. Handles multi-line descriptions (`To:`, `From:`, `Card:`, `Reference:`, `Revolut Rate`, `Fee:` continuation rows), Pending and Reverted sections (both excluded), and multi-month statements.
2. **Load rules** — reads a YAML file mapping transaction descriptions to budget categories. No `type` field (Revolut statements carry no transaction-type codes).
3. **Classify** — two-pass exact-then-regex matching. Any unmatched transactions abort the run.
4. **Split** — groups transactions by calendar month.
5. **Reconcile** — verifies classified totals equal the statement's Money in / Money out figures from the Balance summary on page 1.
6. **Write** — emits one CSV per calendar month (e.g. `revolut-2026-04.csv`, `revolut-2026-05.csv`).

### Usage

```sh
uv run revolut-expense <statement.pdf>
```

| Option | Default | Description |
|---|---|---|
| `--rules` | `rules/revolut_rules.yaml` | Path to YAML rules file |
| `--out-dir` | `./output` | Directory to write CSVs into |
| `--report-unmatched` | — | Write unmatched transactions to this file |

### Rules file

Rules live in `rules/revolut_rules.yaml`. Revolut rules do **not** support a `type` field. Descriptions are matched against the merchant short-name that begins the primary transaction row — `To:` / `From:` / `Card:` continuation text is joined onto the description but regex anchors (`^`) target the leading short-name:

```yaml
rules:
  - match_regex: "^Payment from NATWEST HRPS PAYRO"
    direction: in
    category: "Salary"

  - match_regex: "^Morrisons "   # trailing space avoids matching "Morrisons Metro" etc.
    category: "Food Supplies"

  - match_regex: "^Hargreaves Lansdown"
    direction: out
    category: "Stocks & Shares ISA"
```

**Fields:**

- `match` — exact description string
- `match_regex` — regular expression applied against the normalised description
- `direction` — `in` or `out` (optional)
- `category` — must be one of the supported budget categories

When a new statement produces unmatched transactions, add rules for the new descriptions and re-run.

---

## Budget schema

All tools produce CSVs with this fixed row order. Every category is always present, with `0.00` for months with no activity.

| Section | Categories |
|---|---|
| Regular Inflows | Salary |
| Irregular Inflows | Unexpected / Refund, Loan, Main Account Inflow *(Monzo only)* |
| Asset Liquidation | Savings, Stocks & Shares |
| **Total Income** | |
| Regular Outflows | Rent, Bill - Council Tax, Bill - Electricity & Gas, Bill - Phone & Internet, Food Supplies, Debt, Car & Gas |
| Irregular Outflows | Charity / Donations, Gifts/Entertainment/Misc, Sundry, Holidays & Travel, Education, Eating Out |
| Assets | Active Savings, Lifetime ISA, Stocks & Shares ISA, Dividend Portfolio |
| **Total Expenditure** | |
| **Balance** | Total Income − Total Expenditure for the period |

The **Balance** row is the period net cash flow, not the account closing balance. To get the closing balance, add the opening balance to the Balance value.

---

## Exit codes

All tools use the same exit codes:

| Code | Meaning |
|---|---|
| `0` | Success — CSV(s) written |
| `1` | One or more unmatched transactions — no CSV written |
| `2` | Reconciliation mismatch — no CSV written |
| `3` | PDF parse failure |
| `4` | Bad input (missing file, bad rules config) |

---

## Development

```sh
# Run all tests (requires 90% coverage on non-CLI modules)
uv run pytest

# Run tests for one tool only
uv run pytest tests/lloyds/
uv run pytest tests/monzo/
uv run pytest tests/revolut/

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src
```

Test fixtures (synthetic PDFs) are generated by `tests/fixtures/create_fixtures.py`, `tests/monzo/fixtures/create_fixtures.py`, and `tests/revolut/fixtures/create_fixtures.py` using `reportlab`.
