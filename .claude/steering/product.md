# Steering: Bank Statement Expense Report CLI Tool

## 1. What This Tool Does

Transforms a **text-based bank statement PDF** into a structured CSV expense report by:
1. Extracting transactions (date, description, type, money in/out, balance)
2. Matching each transaction against user-defined rules in `rules.yml`
3. Summing matched amounts into a fixed 17-category hierarchy
4. Calculating section subtotals and two grand totals (Total Income, Total Expenditure)
5. Writing the CSV in strict row order and logging unmatched transactions

## 2. Non-Negotiable Constraints

- **CLI only** — no GUI, no web server, no interactive prompts during processing
- **Two required inputs only**: `statement.pdf` and `rules.yml` (all other arguments are optional with defaults)
- **Single Python script** — dependencies limited to `pdfplumber` and `pyyaml`
- **Process a 50-transaction statement in under 3 seconds**
- **CSV row order is fixed** — follow the exact category sequence in Section 4 below; never reorder
- **Missing categories output `0`** — never omit a row because there were no transactions for it

## 3. Spec Workflow Rules

This project uses **spec-driven development**. All feature work follows this pipeline:

```
spec-requirements → spec-design → spec-tasks → spec-impl → spec-test
```

- Sub-agents live in `.claude/agents/kfc/` — use the exact agent for each phase
- Spec documents are stored under `.claude/specs/{feature_name}/` (e.g. `.claude/specs/bank-statement-parser/requirements.md`)
- Feature names are always **kebab-case** (e.g. `bank-statement-parser`, not `BankStatementParser`)
- **Never skip phases** — do not write design before requirements are approved, do not write tasks before design is approved
- **Never create spec documents directly** — always use the appropriate sub-agent (`spec-requirements`, `spec-design`, `spec-tasks`)
- The main thread coordinates; sub-agents do the specific document work
- After any spec document is created or updated, **explicitly ask the user to approve it** before proceeding
- Requirements use **EARS format** — every acceptance criterion starts with `WHEN`, `IF`, `WHERE`, or `WHILE`, followed by `SHALL`
- Mermaid diagrams must not use parentheses in node text — use `W[Call provider.refresh]` not `W[Call provider.refresh()]`

## 4. Fixed Category Structure (CSV Row Order)

Implement and enforce this exact order. Never add, remove, or reorder rows.

**Inflows**
| Row | Category |
|-----|----------|
| 1 | Salary |
| 2 | **Total Regular Inflows** ← subtotal |
| 3 | Unexpected / Refund |
| 4 | Loan |
| 5 | **Total Irregular Inflows** ← subtotal |
| 6 | Savings |
| 7 | Stocks & Shares |
| 8 | **Total Asset Liquidation** ← subtotal |
| 9 | **Total Income** ← grand total (rows 2 + 5 + 8) |

**Outflows & Assets**
| Row | Category |
|-----|----------|
| 10 | Rent |
| 11 | Bill - Council Tax |
| 12 | Bill - Electricity & Gas |
| 13 | Bill - Phone & Internet |
| 14 | Food Supplies |
| 15 | Debt |
| 16 | Car & Gas |
| 17 | **Total Regular Outflows** ← subtotal |
| 18 | Charity / Donations |
| 19 | Gifts, Entertainment & Misc |
| 20 | Sundry |
| 21 | Holidays & Travel |
| 22 | Education |
| 23 | Eating Out |
| 24 | **Total Irregular Outflows** ← subtotal |
| 25 | Active Savings |
| 26 | Lifetime ISA |
| 27 | Stocks & Shares ISA |
| 28 | Dividend Portfolio |
| 29 | **Total Asset Expenditure** ← subtotal |
| 30 | **Total Expenditure** ← grand total (rows 17 + 24 + 29) |

## 5. Transaction Classification Rules

- Rules are matched **in order** — first match wins (never apply multiple rules to one transaction)
- Match is **case-insensitive** — `"SALARY"` matches `"salary"`, `"Salary"`, etc.
- A rule matches when **any listed keyword appears** in the description AND **the transaction type** is in the rule's `types` list
- If `types: []` and `keywords: []`, treat as a catch-all default (maps to Sundry)
- Unmatched transactions go to `unmapped.log` — never silently drop them

Example rule file structure (from `my_rules.yml`):
```yaml
rules:
  - category: "Salary"
    keywords: ["NATIONAL SERV", "SALARY", "WAGE", "PAYROLL"]
    types: ["FPI", "BGC"]

  - category: "Active Savings"
    keywords: ["HLAM REGULAR SAVIN", "REGULAR SAVER", "LLOYDS"]
    types: ["DD"]

  - category: "Sundry"
    keywords: []
    types: []
    default: true
```

## 6. Transaction Types Reference

| Type | Direction | Meaning |
|------|-----------|---------|
| FPI  | Money In  | Faster Payment In |
| BGC  | Money In  | Bank Giro Credit |
| FPO  | Money Out | Faster Payment Out |
| DD   | Money Out | Direct Debit |
| DEB  | Money Out | Debit Card |

`Money In` types contribute **positive** amounts to a category total. `Money Out` types contribute **negative** amounts.

## 7. CLI Interface

```bash
expense-parser statement.pdf --rules my_rules.yml --output report.csv
```

| Argument | Default |
|----------|---------|
| `input.pdf` | required |
| `--rules` / `-r` | `rules.yml` |
| `--output` / `-o` | `expense_report.csv` |
| `--unmapped-log` | `unmapped.log` |
| `--exclude-self-transfers` | `true` |
| `--strict` | `false` (fail if any transaction unmapped) |

The CLI must print a progress summary on completion:
```
Loading rules from my_rules.yml... done (12 rules).
Parsing PDF... found 42 transactions.
Classifying transactions...
  - Matched: 38 (90.5% of total value)
  - Unmapped: 4 (written to unmapped.log)
  - Self-transfers excluded: 3
Calculating subtotals... done.
CSV written to april_2026.csv
```

## 8. Error Handling

Emit clear, actionable error messages for these specific cases — no stack traces to the user:
- Missing `rules.yml` → `"Rules file not found: {path}"`
- Malformed PDF or no transactions extracted → `"No transactions found in {pdf}. Is this a text-based PDF?"`
- `--strict` mode with unmatched transactions → exit non-zero with count of unmapped transactions
