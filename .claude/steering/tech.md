# Technical Stack

## Language and runtime

- **Python 3.11+**. Pinned via `.python-version` and declared in `pyproject.toml`. 3.11 is the floor because of `tomllib` in stdlib and improved error messages; nothing in the design needs anything newer.
- **No async.** This is a synchronous, single-file, single-process tool. Adding async would buy nothing and cost clarity.

## Dependency management

- **`uv`** for dependency resolution, virtualenv management, and execution. Lockfile committed (`uv.lock`).
- `pyproject.toml` is the single source of truth for project metadata, dependencies, dev dependencies, and tool config (ruff, pytest, mypy).
- No `requirements.txt`, no `setup.py`, no `setup.cfg`.

## Core libraries

| Concern | Library | Why |
|---|---|---|
| PDF text extraction | **`pdfplumber`** | Best-in-class for tabular PDFs; preserves column structure that Lloyds statements rely on. Avoids the fragile text-positioning gymnastics that `pypdf` / `pdfminer.six` force on you for tables. |
| CLI argument parsing | **`typer`** | Type-hint-driven, generates `--help` automatically, plays well with `rich` for error output. Standard library `argparse` would also work but typer is lower-friction for the size of this tool. |
| YAML rules file | **`PyYAML`** (`yaml.safe_load`) | The rules file is read-only from the tool's perspective — the user is the sole editor. Comment-preserving round-trip libraries like `ruamel.yaml` solve a problem the tool doesn't have. If a future feature ever writes back to the rules file (e.g., an interactive rule builder), swap the dependency then. |
| Decimal money | **`decimal.Decimal`** (stdlib) | Floats are banned for any monetary value. All amounts parsed as `Decimal`, all arithmetic in `Decimal`, all output formatted from `Decimal`. |
| CSV output | **`csv`** (stdlib) | Output is a fixed, simple shape; no need for pandas. |
| Console output / errors | **`rich`** | Coloured unmatched-transaction reports and reconciliation diffs read far better than plain text when the user is fixing their rules file. |

Explicitly **not** used:
- **pandas** — overkill for this volume and shape of data; pulls a heavy dependency for what `csv` + `Decimal` does in a few dozen lines.
- **pydantic** — the domain model is small enough that `@dataclass(frozen=True)` is clearer and zero-cost.
- **regex** library — stdlib `re` is sufficient.

## Tooling

- **`ruff`** for linting and formatting (replaces black, isort, flake8). Config in `pyproject.toml`.
- **`mypy --strict`** for type checking. The codebase is fully typed; CI fails on any new untyped function.
- **`pytest`** for tests, with `pytest-cov` for coverage. Coverage floor: 90% on non-CLI modules.

## CLI shape

```
lloyds-expense <statement.pdf> --rules rules.yaml --out budget.csv
```

- `<statement.pdf>` — required positional, path to one Lloyds Classic PDF.
- `--rules` — required, path to the YAML rules file.
- `--out` — required, destination CSV path. Refuses to overwrite unless `--force`.
- `--strict` (default on) — exit non-zero on any unmatched transaction; do not write CSV.
- `--report-unmatched` — write a separate file listing unmatched transactions for easy rule authoring.
- Exit codes: `0` success, `1` unmatched transactions, `2` reconciliation mismatch, `3` parse error, `4` bad input (missing file, malformed YAML, etc).

## Rules file format

YAML, hand-edited. Two-pass matching: exact description match first, then regex fallback. Each rule maps to a `(section, category)` pair drawn from a closed enumeration defined in the schema module — the rules engine refuses to load a rule referencing an unknown category, so typos in the YAML fail loudly at startup, not silently at classification time.

```yaml
rules:
  - match: "NATIONAL SERV M/W"
    type: "BGC"
    category: "Salary"

  - match_regex: "^OMASIRICHI OKWU"
    direction: out
    category: "Food Supplies"

  - match: "HLAM REGULAR SAVIN"
    type: "DD"
    category: "Active Savings"
```

Rule fields:
- `match` (exact) or `match_regex` (pattern) — exactly one required.
- `type` (optional) — restrict to a Lloyds transaction-type code (FPO, FPI, DD, DEB, BGC, etc).
- `direction` (optional) — `in` or `out`; restricts to money-in or money-out rows.
- `category` (required) — must be one of the schema's leaf categories.

First matching rule wins. Order matters and is the user's responsibility.

## Money handling rules

- Parse all amounts via `Decimal(str(value))` from the extracted string, never via `float`.
- Quantize to 2 decimal places at the boundary (input parse, output write), never in the middle.
- Reconciliation: `sum(classified inflows) == statement.money_in` and `sum(classified outflows) == statement.money_out`, exact `Decimal` equality. No epsilon comparisons.

## Determinism

- Section and category order is fixed in code (an `Enum` declared in display order), not derived from rules-file order or input order.
- CSV is written with `\n` line endings (`newline=""` + explicit `\n`) and a fixed column order.
- No timestamps, no machine identifiers, no random IDs in output.

## Error model

A single exception hierarchy rooted at `StatementToCsvError`, with subclasses for parse errors, unmatched transactions, reconciliation failures, and config errors. The CLI layer is the only place that catches these and maps them to exit codes and `rich`-formatted user messages. Library code raises; it does not print.

## Platforms

- Primary: Linux.
- No platform-specific code paths; everything goes through `pathlib`.
