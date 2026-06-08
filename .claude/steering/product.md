# Product Overview — Monzo Expense Tool

## What this is

A command-line tool that converts a Monzo UK personal-account statement (PDF) into one categorised monthly cash-flow CSV **per calendar month** covered by the statement. Each CSV mirrors a fixed personal-finance schema with named sections, line-item subtotals, and grand totals for income and expenditure.

This is a sibling package to `lloyds_expense`. The two tools share intent and schema shape but are deliberately separate codebases — Monzo statements have no transaction-type codes, encode direction in the sign of the amount, span multiple months per PDF, and include Monzo-specific concepts like Pots. Forcing one parser to cover both banks would compromise both.

## Problem

Monzo statements list transactions across a multi-month period in chronological order with descriptions that include merchant names, locations, currency conversion notes, Faster Payments references, and pot transfer markers (e.g. `DGHB CATERING DUMFRIES GBR`, `O Okwu-Boms (Faster Payments)`, `Transfer to Pot -1.07`, `MEDCOUNCIL/CONSEILMED OTTAWA CAN Amount: CAD -335.00. Exchange rate: 1.833105.`). Building a monthly budget from this means manually splitting the period into months, classifying every line against a personal taxonomy, and reconciling totals — slow and error-prone.

The tool removes the manual work. One Monzo PDF in, one CSV per month out, each in the user's budget schema, with subtotals and grand totals computed.

## Who it's for

A single end user — the account holder — running it on their own machine against their own statements. Not multi-tenant, not a service, no shared state.

## What it does (in scope)

- Accept exactly one Monzo personal-account statement PDF per invocation.
- Parse the transaction table, preserving date, description (re-joined across wrapped lines), signed amount, and derived direction (`in` if positive, `out` if negative).
- Ignore Pot statement pages — they appear after the main personal-account pages and are not part of the monthly cash-flow view. The pot deposits are already captured as `Transfer to Pot` rows in the main account stream and classified there.
- Split the transactions into calendar months based on the transaction date.
- Classify each transaction against a user-maintained YAML rules file mapping descriptions to schema categories.
- For each calendar month covered by the statement, emit a CSV that matches the budget schema exactly: every section header, every line item, every subtotal, and both grand totals present, even if a category has zero activity in that month.
- Surface unclassified transactions clearly so the user can extend the rules file and re-run.
- Reconcile: the sum of all classified amounts across **all months** must equal the statement's reported `Total deposits` and `Total outgoings` figures from page 1. Any mismatch is reported.

## What it does not do (out of scope)

- No banks other than Monzo, no statement formats other than the personal-account layout. Joint accounts, business accounts, and Monzo Flex statements are not in scope.
- No interactive classification, no LLM-assisted categorisation, no learning loop. Rules are explicit and user-edited.
- No GUI, no web interface, no cloud sync.
- No financial advice, forecasting, or budget recommendations — purely a transformation tool.
- No persistence between runs beyond the rules file the user maintains.
- No reconciliation of internal pot balances against the pot statement pages. Pot flows are captured via the `Transfer to Pot` rows only.
- No handling of currency-conversion lines as a separate concept — they appear with the GBP-equivalent amount and are classified by description like any other transaction.

## Schema produced

Each output CSV contains these rows in this order, regardless of whether any given category had activity that month:

**Inflows**
- Regular Inflows: Salary → subtotal
- Irregular Inflows: Unexpected / Refund, Loan, Main Account Inflow → subtotal
- Asset Liquidation: Savings, Stocks & Shares → subtotal
- **Total Income** (grand total)

**Outflows**
- Regular Outflows: Rent, Bill - Council Tax, Bill - Electricity & Gas, Bill - Phone & Internet, Food Supplies, Debt, Car & Gas → subtotal
- Irregular Outflows: Charity / Donations, Gifts, Entertainment & Misc, Sundry, Holidays & Travel, Education, Eating Out → subtotal
- Assets: Active Savings, Lifetime ISA, Stocks & Shares ISA, Dividend Portfolio → subtotal
- **Total Expenditure** (grand total)
- Balance (Total Income − Total Expenditure)

The schema differs from the Lloyds tool's schema in one place: **Irregular Inflows** has an additional `Main Account Inflow` category (see "Schema deviations" below).

## Success criteria

1. Running the tool against a Monzo statement PDF produces one CSV per calendar month in the statement period, each in the schema above, with no manual post-editing required, provided every transaction matches a rule.
2. When transactions don't match a rule, the tool exits non-zero, lists the unmatched lines, and produces no partial CSVs — the user knows exactly what to add to the rules file.
3. Computed totals reconcile to the `Total deposits` / `Total outgoings` figures printed on page 1 of the statement, to the penny, summed across all months.
4. A second run with the same inputs produces byte-identical CSVs (deterministic).

## Schema deviations from the Lloyds tool

The Monzo schema adds one category that does not exist in the Lloyds tool:

- **`Main Account Inflow`** (Irregular Inflows section). Monzo is used as a secondary spending account topped up frequently from the user's main account. These top-ups appear in the statement as positive Faster Payments from `O Okwu-Boms`. They are not income in any economic sense — they are internal transfers — but the schema is a closed enumeration with no "internal transfer" category, and they must land somewhere to make reconciliation arithmetic balance. Capturing them in a dedicated category keeps the Irregular Inflows subtotal meaningful (genuine refunds and loans stay separate) and lets the user subtract Main Account Inflow from Total Income mentally when comparing to the Lloyds budget.

All other sections and categories are identical to the Lloyds schema.

## Domain notes — known classifications for this account

The user's standing classifications for recurring counterparties on this account. These are the truth the rules file must encode.

### Inflows

- **`O Okwu-Boms (Faster Payments)`** (money in) → **Main Account Inflow**. The user's own top-ups from their main account. By far the most frequent inflow line. *Not* Unexpected/Refund.
- **`Somtochukwu Nchekwubechukwu Obiana (Faster Payments)`** (money in, often with reference "Sent from Revolut") → **Unexpected / Refund**. Transfers from a known contact, sometimes labelled "Lunch Money" or similar.
- **`WWW.HL.CO.UK BRISTOL GBR`** (money in) → **Stocks & Shares** (Asset Liquidation). Hargreaves Lansdown ISA withdrawals.

### Outflows — Bills and Regular

- **`Lebara Mobile Limited London GBR`** → **Bill - Phone & Internet**. Monthly mobile bill.
- **`THREE MOTO GLASGOW GBR`** → **Bill - Phone & Internet**. Mobile top-ups.

### Outflows — Food Supplies

- **`W M MORRISONS DUMFRIES GBR`**, **`WM MORRISONS STORE DUMFRIES GBR`** → **Food Supplies**.
- **`Lidl GB DUMFRIES GBR`** → **Food Supplies**.
- **`TESCO STORES 2388 DUMFRIES GBR`** → **Food Supplies**.
- **`MARKS&SPENCER PLC SACA DUMFRIES GBR`** → **Food Supplies** (typically grocery, override per-rule if needed).
- **`POUNDLAND LTD - 2114 DUMFRIES GBR`** → **Food Supplies** (treat as grocery by default).

### Outflows — Eating Out

- **`DGHB CATERING DUMFRIES GBR`** → **Eating Out**. By far the most frequent outflow, multiple entries per day.
- **`MARCHBANK BAKERS THORNHILL DG3 GBR`** → **Eating Out**.
- **`La Dolce Vita Dumfries GBR`** → **Eating Out**.
- **`Enish Glasgow Glasgow GBR`** → **Eating Out**.
- **`PPOINT_*McEwans Premie Dumfries GBR`** → **Eating Out**.
- **`NYX*DCVendingLtd`** (Kilmarnock/Reading variants) → **Eating Out** (vending machines).
- **`DC7 VENDING LIMITED AYRSHIRE GBR`** → **Eating Out** (vending machines).

### Outflows — Sundry (catch-all for professional fees and miscellaneous)

- **`RCGP (Direct Debit)`** → **Sundry**. Royal College of General Practitioners membership fee.
- **`GENERAL MEDICAL C (Direct Debit)`** → **Sundry**. General Medical Council registration fee.
- **`MEDCOUNCIL/CONSEILMED OTTAWA CAN`** → **Sundry**. Canadian Medical Council fee (appears with CAD conversion line).
- **`RP*My Local Surgery Lt Romsey GBR`** → **Sundry**. Medical professional fees.
- **`DUMFRIES HOSPITALS LEA DUMFRIES GBR`** → **Sundry**.
- **`SAVERS HEALTH & BEAUTY DUMFRIES GBR`** → **Sundry**.
- **`SUPERDRUG STORES PLC DUMFRIES GBR`** → **Sundry**.
- **`HOLLAND AND BARRETT DUMFRIES GBR`** → **Sundry**.
- **`BOOTS 2265 LUTON GBR`** → **Sundry**.
- **`Ali Mohammad Almasri (Bank Transfer)`** → **Sundry** (housemate/bill split).

### Outflows — Holidays & Travel

- **`HOUSTONS MINI COACHES LOCKERBIE GBR`** → **Holidays & Travel**.
- **`UBER *TRIP London GBR`**, **`UBER * PENDING London GBR`** → **Holidays & Travel**.
- **`HARTHILL NORTH SF CONN SHOTTS LANARK GBR`** → **Holidays & Travel** (motorway services).
- **`ACA KIRKCALDY MG KIRKCALDY GBR`** → **Holidays & Travel**.
- **`VF SERVICES (UK) LTD LONDON GBR`** → **Holidays & Travel**.
- **`SumUp *McLeans taxi Dumfries GBR`** → **Holidays & Travel**.

### Outflows — Car & Gas

- **`Adamira Driving School (Faster Payments)`** → **Car & Gas**. Recurring driving lessons.
- **`DVSA SWANSEA GBR`** → **Car & Gas**. Driving test fees.
- **`HASTINGS DIRECT BEXHILL ON SE GBR`** → **Car & Gas**. Car insurance.

### Outflows — Gifts, Entertainment & Misc

- **`AMAZON.CO.UK LONDON GBR`** → **Gifts, Entertainment & Misc**.
- **`T K MAXX DUMFRIES GBR`** → **Gifts, Entertainment & Misc**.
- **`BLUE INC - DUMFRIES DUMFRIES GBR`** → **Gifts, Entertainment & Misc**.
- **`Vinted Vilnius GBR`** → **Gifts, Entertainment & Misc** (clothes resale; refunds also classified here).

### Outflows — Charity / Donations

- **`Somtochukwu Nchekwubechukwu Obiana (Faster Payments)`** (money out) → **Charity / Donations**. (Same counterparty as the inflow rule above, but distinguished by `direction: out`.)
- **`Omasirichi Okwu-Boms (Faster Payments)`** (money out) → needs case-by-case rules; self-transfers out to the main account. Not safely auto-classifiable; consider **Charity / Donations** or a dedicated rule per use case.

### Outflows — Assets

- **`Transfer to Pot`** → **Active Savings**. Daily pot deposits (1p savings challenge etc.).
- **`WWW.HL.CO.UK BRISTOL GBR`** (money out) → **Stocks & Shares ISA**. Hargreaves Lansdown ISA contributions.

This list will grow. The steering doc is updated when the *intent* changes (e.g. "M&S is now an Eating Out treat, not groceries"), not when a new one-off transaction appears.
