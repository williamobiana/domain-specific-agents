# Product Brief: Bank Statement to Expense Report CLI Tool

## 1. Executive Summary
A command-line interface (CLI) tool that transforms **raw bank statement PDFs** into a structured expense report CSV. The tool extracts transactions, applies user‑defined classification rules (keywords + transaction types), groups them into a fixed category hierarchy, calculates section subtotals and grand totals, and exports a strictly formatted CSV.

## 2. Problem Statement
Bank statements do not contain expense categories like "Rent" or "Salary" — only payer/payee names, transaction types (FPI, FPO, DD, DEB, etc.), and amounts. Manually categorising hundreds of transactions is tedious and error‑prone.

Users need a tool that:
- Extracts transactions from a PDF bank statement.
- Applies **custom rules** to map each transaction to a predefined category.
- Groups categories into sections (Regular Inflows, Irregular Outflows, Assets, etc.).
- Calculates section subtotals and grand totals (Total Income, Total Expenditure).
- Exports a standardised CSV for financial analysis.

## 3. Target Users
- Individuals tracking personal finances from bank statements.

## 4. Core Requirements

### 4.1 Inputs
| Input | Description |
|-------|-------------|
| `statement.pdf` | Bank statement PDF (text‑based, not scanned). |
| `rules.yml` | User‑defined mapping from transaction patterns to categories. |

### 4.2 Output
- A single CSV file with the **exact category order** defined below.
- Missing categories = `0`.
- Section subtotals and grand totals automatically calculated.

### 4.3 Fixed Category Structure (CSV Output Order)
**Inflows**
- Section: Regular Inflows
  - Salary
  - Total Regular Inflows ← subtotal
- Section: Irregular Inflows
  - Unexpected / Refund
  - Loan
  - Total Irregular Inflows ← subtotal
- Section: Asset Liquidation
  - Savings
  - Stocks & Shares
  - Total Asset Liquidation ← subtotal
- **Total Income** ← grand total of all inflow sections

**Outflows & Assets**
- Section: Regular Outflows
  - Rent
  - Bill - Council Tax
  - Bill - Electricity & Gas
  - Bill - Phone & Internet
  - Food Supplies
  - Debt
  - Car & Gas
  - Total Regular Outflows ← subtotal
- Section: Irregular Outflows
  - Charity / Donations
  - Gifts, Entertainment & Misc
  - Sundry
  - Holidays & Travel
  - Education
  - Eating Out
  - Total Irregular Outflows ← subtotal
- Section: Assets
  - Active Savings
  - Lifetime ISA
  - Stocks & Shares ISA
  - Dividend Portfolio
  - Total Asset Expenditure ← subtotal
- **Total Expenditure** ← grand total of all outflow sections

### 4.4 Functional Requirements

| ID | Description |
|----|-------------|
| FR-01 | Extract transactions from PDF: date, description, type (e.g., FPI, FPO, DD, DEB), money in, money out, balance. |
| FR-02 | Load user‑defined mapping rules from a config file (`rules.yml`). |
| FR-03 | Apply rules to each transaction: match by **keywords** (case‑insensitive) and/or **transaction type**. |
| FR-04 | Each rule maps to one of the 17 categories (Salary, Rent, Active Savings, etc.). |
| FR-05 | If multiple rules match, use the first match (priority order = rule order in file). |
| FR-06 | If no rule matches, flag transaction as `unmapped` and optionally skip or assign to "Sundry". |
| FR-07 | Sum all amounts per category. `Money In` (FPI, BGC, etc.) = positive contribution; `Money Out` (FPO, DEB, DD) = negative. |
| FR-08 | Calculate section subtotals by summing their child categories. |
| FR-09 | Calculate `Total Income` = sum(Regular Inflows + Irregular Inflows + Asset Liquidation). |
| FR-10 | Calculate `Total Expenditure` = sum(Regular Outflows + Irregular Outflows + Assets). |
| FR-11 | **Self‑transfer detection** : track transactions where description matches account holder name and type as food supplies. |
| FR-12 | Generate CSV with exact row order from section 4.3. |
| FR-13 | Write unmapped transactions to a separate log file for user review. |

### 4.5 Non-Functional Requirements
- **CLI‑first:** No GUI; all operations via terminal.
- **Performance:** Process a typical 3‑page statement with 50+ transactions in < 3 seconds.
- **Portable:** Single Python script with `pdfplumber` and `pyyaml` as dependencies.
- **Error handling:** Clear error messages for missing rules file, malformed PDF, or zero transactions found.

## 5. User Interface (CLI)

### Basic usage
```bash
expense-parser statement.pdf --rules my_rules.yml --output report.csv
```

### Full options

| Argument                   | Description                                                 | Default                 |
| --------                   | -------                                                     | -------                 |
| `input.pdf`                | Bank statement PDF                                          | required                |
| `--rules`, `-r`            | Path to mapping rules file (YAML or CSV)                    | `rules.yml`             |
| `--output`, `-o`           | Output CSV path                                             | `expense_report.csv`    |
| `--unmapped-log`           | Write unmapped transactions to this file                    | `unmapped.log`          |
| `--exclude-self-transfers` | Ignore transactions where description matches account holder| `true`                  | 
| `--strict`                 | Fail if any transaction remains unmapped                    | `false`                 |
| `--version`                | Show version                                                |  —                      |

		

### Example session
```bash

$ expense-parser Statement_2026_4.pdf --rules my_rules.yml --output april_2026.csv

Loading rules from my_rules.yml... done (12 rules).
Parsing PDF... found 42 transactions.
Classifying transactions...
  - Matched: 38 (90.5% of total value)
  - Unmapped: 4 (written to unmapped.log)
  - Self-transfers excluded: 3
Calculating subtotals... done.
CSV written to april_2026.csv

Unmapped transactions (4):
  - 07 Apr 26 | GRACE AKANNI | FPO | €500.00
  - 14 Apr 26 | MAUTON TOLLUOPE HU | FPO | €200.00
  - (review unmapped.log for details)
```

## 6. Rules File Format (Example)
```
# my_rules.yml
rules:
  - category: "Salary"
    keywords: ["NATIONAL SERV", "SALARY", "WAGE", "PAYROLL"]
    types: ["FPI", "BGC"]
    
  - category: "Active Savings"
    keywords: ["HLAM REGULAR SAVIN", "REGULAR SAVER", "LLOYDS"]
    types: ["DD"]
    
  - category: "Stocks & Shares ISA"
    keywords: ["TRADING 212", "VANGUARD", "HARGREAVES"]
    types: ["DEB"]
    
  - category: "Gifts, Entertainment & Misc"
    keywords: ["SOMTOCHUKWU NCHEKW"]
    types: ["FPO"]
    
  - category: "Sundry"
    keywords: []  # catch-all for unmatched
    types: []
    default: true
```

## 7. Glossary
| Term           | Definition                                                      |
|----------------|------------------------------------------------------------------|
| FPI            | Faster Payment In (money received)                               |
| FPO            | Faster Payment Out (money sent)                                  |
| DD             | Direct Debit                                                    |
| DEB            | Debit Card transaction                                          |
| BGC            | Bank Giro Credit                                                |
| Self-transfer  | Moving money between own accounts (excluded from totals)         |
| Rule           | A combination of keywords and transaction types that maps to a category |
| Unmapped       | A transaction that matched no rule                              |
| Section        | A group of related categories (e.g., Regular Outflows)           |
| Subtotal       | Sum of all categories within a section                          |
