# Product Overview

## What this is

A command-line tool that converts a Lloyds Bank UK personal account statement (PDF) into a categorised monthly cash-flow CSV. The output mirrors a fixed personal-finance schema with named sections, line-item subtotals, and grand totals for income and expenditure.

## Problem

Lloyds statements list transactions in chronological order with terse descriptions (e.g. `OMASIRICHI OKWU BO`, `HLAM REGULAR SAVIN`, `NATIONAL SERV M/W`). Producing a monthly budget from a raw statement means manually classifying every line against a personal taxonomy — salary vs refund, rent vs council tax, savings transfer vs spending. Doing this by hand each month is slow and error-prone, and the totals never reconcile on the first pass.

The tool removes the manual classification step. The user supplies one statement PDF and gets back a CSV laid out in their personal budget schema, with subtotals and grand totals computed, ready to paste into a tracking spreadsheet.

## Who it's for

A single end user — the account holder — running it on their own machine against their own statements. Not multi-tenant, not a service, no shared state.

## What it does (in scope)

- Accept exactly one Lloyds Classic statement PDF per invocation.
- Parse the transaction table, preserving date, description, type, money-in, money-out, and balance.
- Classify each transaction against a user-maintained YAML rules file mapping descriptions (and transaction types) to schema categories.
- Emit a CSV that matches the budget schema exactly: every section header, every line item, every subtotal, and both grand totals are present, even if a category has zero activity in that month.
- Surface unclassified transactions clearly so the user can extend the rules file and re-run.
- Reconcile: the sum of all classified amounts must equal the statement's reported Money In and Money Out totals. Any mismatch is reported.

## What it does not do (out of scope)

- No multi-statement, multi-month, or batched processing. One PDF in, one CSV out.
- No banks other than Lloyds, no statement formats other than the Classic personal-account layout.
- No interactive classification, no LLM-assisted categorisation, no learning loop. Rules are explicit and user-edited.
- No GUI, no web interface, no cloud sync.
- No financial advice, forecasting, or budget recommendations — purely a transformation tool.
- No persistence between runs beyond the rules file the user maintains.

## Schema produced

The output CSV always contains these rows in this order, regardless of whether any given category had activity:

**Inflows**
- Regular Inflows: Salary → subtotal
- Irregular Inflows: Unexpected / Refund, Loan → subtotal
- Asset Liquidation: Savings, Stocks & Shares → subtotal
- **Total Income** (grand total)

**Outflows**
- Regular Outflows: Rent, Bill - Council Tax, Bill - Electricity & Gas, Bill - Phone & Internet, Food Supplies, Debt, Car & Gas → subtotal
- Irregular Outflows: Charity / Donations, Gifts/Entertainment/Misc, Sundry, Holidays & Travel, Education, Eating Out → subtotal
- Assets: Active Savings, Lifetime ISA, Stocks & Shares ISA, Dividend Portfolio → subtotal
- **Total Expenditure** (grand total)

## Success criteria

1. Running the tool against a Lloyds statement PDF produces a CSV in the schema above with no manual post-editing required, provided every transaction matches a rule.
2. When transactions don't match a rule, the tool exits non-zero, lists the unmatched lines, and produces no partial CSV — the user knows exactly what to add to the rules file.
3. Computed totals reconcile to the Money In / Money Out figures printed on the statement, to the penny.
4. A second run with the same inputs produces a byte-identical CSV (deterministic).

## Domain notes — known classifications for this account

These are the user's standing classifications for recurring counterparties on their statement. They are documented here so the intent is captured in steering rather than hidden inside the rules file. The rules file is the implementation; this section is the truth the rules file must encode.

- **`OMASIRICHI OKWU BO` / `OMASIRICHI OKWU-BO`** (FPO, money out) → **Food Supplies**. These are the user's own self-transfers and are by far the most frequent line on the statement. The two punctuation variants must both match.
- **`NATIONAL SERV M/W`** (BGC, money in) → **Salary**.
- **`HLAM REGULAR SAVIN`** (DD, money out) → **Active Savings**. Multiple entries per month, treated as savings rather than expenditure.
- **`Trading 212`** (DEB, money out) → **Stocks & Shares ISA** (or Dividend Portfolio, user-specified per rule).
- **`LLOYDS BANK PLC`** (DD, money out) — needs case-by-case rules; could be a credit-card bill (Debt) or a fee. Not safely auto-classifiable from description alone.
- **Money in from `OMASIRICHI OKWU BO` / `SOMTOCHUKWU NCHEKW` / similar personal-name FPIs** → **Unexpected / Refund** by default (self-transfers returning, or transfers from known contacts). Genuine refunds belong in **Unexpected / Refund** and should be added as more specific rules when they occur.

This list will grow. New counterparties added to the user's life mean new rules; the steering doc is updated when the *intent* changes (e.g. "Trading 212 is now my dividend portfolio, not my ISA"), not when a new one-off transaction appears.
