# Product Overview

## What this is

A set of command-line tools that convert UK personal-account bank statements (PDF) into categorised monthly cash-flow CSVs. The output mirrors a fixed personal-finance schema with named sections, line-item subtotals, and grand totals for income and expenditure.

Three banks are supported, each as its own tool:

- **`lloyds-expense`** — one Lloyds Classic statement PDF → one CSV.
- **`monzo-expense`** — one Monzo personal-account statement PDF → one CSV **per calendar month** covered by the statement.
- **`revolut-expense`** — one Revolut GBP personal-account statement PDF → one CSV **per calendar month** covered by the statement.

The tools share intent and schema shape but are deliberately separate codebases under `src/lloyds_expense/`, `src/monzo_expense/`, and `src/revolut_expense/`. The three banks have incompatible statement formats:

- **Lloyds** has transaction-type codes (FPO, DD, BGC, etc.) and separate money-in / money-out columns; one statement covers one period that always falls within a single billing month.
- **Monzo** encodes direction in the sign of a single amount column, has no type codes, spans multiple months per PDF, and includes Pot statement pages that must be ignored.
- **Revolut** has separate money-in / money-out columns (like Lloyds) and a running-balance column, but no transaction-type codes (like Monzo), spans multiple months per PDF (like Monzo), uses long-form English dates (`Apr 1, 2026`), and prefixes its transaction stream with a "Pending" section and trails it with a "Reverted" section — both of which must be excluded from the cash-flow view. Most transactions also carry a `Card: 535456******1161` continuation line and many carry currency-conversion or reference continuation lines.

Forcing one parser to cover all three would compromise each. Schema and writer logic are duplicated by design; sharing comes only if a fourth bank arrives that justifies the abstraction.

## Problem

Bank statements list transactions in chronological order with terse or noisy descriptions (`OMASIRICHI OKWU BO`, `HLAM REGULAR SAVIN`, `DGHB CATERING DUMFRIES GBR`, `MEDCOUNCIL/CONSEILMED OTTAWA CAN Amount: CAD -335.00. Exchange rate: 1.833105.`, `Payment from ACTIVE SAVINGS CASH HUB`). Producing a monthly budget from a raw statement means manually classifying every line against a personal taxonomy — salary vs refund, rent vs council tax, savings transfer vs spending, internal top-up vs genuine income. Doing this by hand each month is slow and error-prone, and the totals never reconcile on the first pass.

The tools remove the manual classification step. The user supplies one statement PDF and gets back CSVs laid out in their personal budget schema, with subtotals and grand totals computed, ready to paste into a tracking spreadsheet.

## Who it's for

A single end user — the account holder — running it on their own machine against their own statements. Not multi-tenant, not a service, no shared state.

## What it does (in scope)

- Accept exactly one statement PDF per invocation, from the bank that matches the tool being run.
- Parse the transaction table, preserving date, description, signed amount, and direction. Lloyds additionally preserves the transaction-type code (FPO, DD, BGC, etc.); Monzo and Revolut have no such codes.
- For Monzo and Revolut, re-join descriptions that wrap across multiple PDF rows (Faster Payments references, currency-conversion notes, `To:` / `From:` lines, `Card:` lines, `Fee:` lines).
- For Monzo, ignore Pot statement pages — they appear after the personal-account section and are not part of the cash-flow view. The pot deposits are already captured as `Transfer to Pot` rows in the main account stream.
- For Revolut, ignore the **Pending** section (transactions not yet settled, listed before the main account-transactions table) and the **Reverted** section (transactions that were reversed, listed after the main table). Only the rows under "Account transactions from … to …" are part of the cash-flow view.
- Classify each transaction against a user-maintained YAML rules file mapping descriptions (and, for Lloyds, transaction types) to schema categories.
- Emit CSV(s) that match the budget schema exactly: every section header, every line item, every subtotal, and both grand totals are present, even if a category has zero activity. Lloyds produces one CSV per run; Monzo and Revolut each produce one CSV per calendar month covered by the statement.
- Surface unclassified transactions clearly so the user can extend the rules file and re-run.
- Reconcile: the sum of all classified amounts must equal the statement's reported totals. For Lloyds, that's the per-statement Money In / Money Out figures. For Monzo, that's the period-level `Total deposits` / `Total outgoings` on page 1, summed across all months. For Revolut, that's the period-level `Money in` / `Money out` figures in the Balance summary on page 1, summed across all months. Any mismatch is reported.

## What it does not do (out of scope)

- No multi-statement, multi-PDF, or batched processing. One PDF in, per invocation.
- No banks other than Lloyds (Classic personal account), Monzo (personal account), and Revolut (GBP personal account). Joint accounts, business accounts, Monzo Flex statements, and Revolut multi-currency / non-GBP statements are not in scope.
- No auto-detection of bank from the PDF — the user picks the right tool.
- No interactive classification, no LLM-assisted categorisation, no learning loop. Rules are explicit and user-edited.
- No GUI, no web interface, no cloud sync.
- No financial advice, forecasting, or budget recommendations — purely a transformation tool.
- No persistence between runs beyond the rules file the user maintains.
- No reconciliation of Monzo Pot statement pages against the main account `Transfer to Pot` rows. Pot flows are captured via those rows only.
- No inclusion of Revolut's Pending or Reverted sections in the cash-flow output. Pending lines are not yet completed transactions; Reverted lines have already been undone and would double-count if included.

## Schema produced

Each output CSV contains these rows in this order, regardless of whether any given category had activity:

**Inflows**
- Regular Inflows: Salary → subtotal
- Irregular Inflows: Unexpected / Refund, Loan, *Main Account Inflow (Monzo and Revolut only)* → subtotal
- Asset Liquidation: Savings, Stocks & Shares → subtotal
- **Total Income** (grand total)

**Outflows**
- Regular Outflows: Rent, Bill - Council Tax, Bill - Electricity & Gas, Bill - Phone & Internet, Food Supplies, Debt, Car & Gas → subtotal
- Irregular Outflows: Charity / Donations, Gifts/Entertainment/Misc, Sundry, Holidays & Travel, Education, Eating Out → subtotal
- Assets: Active Savings, Lifetime ISA, Stocks & Shares ISA, Dividend Portfolio → subtotal
- **Total Expenditure** (grand total)
- Balance (Total Income − Total Expenditure)

All three tools share this schema except for one addition: `Main Account Inflow` in the Irregular Inflows section, present for Monzo and Revolut but not for Lloyds. See "Schema deviations" below.

## Success criteria

1. Running any of the tools against a matching statement PDF produces CSV(s) in the schema above with no manual post-editing required, provided every transaction matches a rule.
2. When transactions don't match a rule, the tool exits non-zero, lists the unmatched lines, and produces no partial output — the user knows exactly what to add to the rules file.
3. Computed totals reconcile to the statement's reported figures to the penny.
4. A second run with the same inputs produces byte-identical output (deterministic).

## Schema deviations from the common schema

The Monzo and Revolut tools each add one category that does not exist in the Lloyds tool:

- **`Main Account Inflow`** (Irregular Inflows section, Monzo and Revolut only). Both Monzo and Revolut are used as secondary spending accounts topped up frequently from the user's main Lloyds account. These top-ups appear in the Monzo statement as positive Faster Payments from `O Okwu-Boms`, and in the Revolut statement as `Payment from O OKWU-BOMS` (often with reference text such as `BORROWED`, `BORROW OOO`, `BORROW DEFINITELY`, `No more borrow`, `NO MORE BORROW`, or `Contribution`). They are not income in any economic sense — they are internal transfers — but the schema is a closed enumeration with no "internal transfer" category, and they must land somewhere to make reconciliation arithmetic balance. Capturing them in a dedicated category keeps the Irregular Inflows subtotal meaningful (genuine refunds and loans stay separate). The Lloyds schema does not include this category because Lloyds is the user's main account — there is no equivalent inbound top-up pattern.

All other sections and categories are identical across all three tools.

## Domain notes — known classifications for the Lloyds account

These are the user's standing classifications for recurring counterparties on their Lloyds statement. They are documented here so the intent is captured in steering rather than hidden inside the rules file. The rules file is the implementation; this section is the truth the rules file must encode.

- **`OMASIRICHI OKWU BO` / `OMASIRICHI OKWU-BO`** (FPO, money out) → **Food Supplies**. These are the user's own self-transfers and are by far the most frequent line on the statement. The two punctuation variants must both match.
- **`NATIONAL SERV M/W`** (BGC, money in) → **Salary**.
- **`HLAM REGULAR SAVIN`** (DD, money out) → **Active Savings**. Multiple entries per month, treated as savings rather than expenditure.
- **`Trading 212`** (DEB, money out) → **Stocks & Shares ISA** (or Dividend Portfolio, user-specified per rule).
- **`LLOYDS BANK PLC`** (DD, money out) — needs case-by-case rules; could be a credit-card bill (Debt) or a fee. Not safely auto-classifiable from description alone.
- **Money in from `OMASIRICHI OKWU BO` / `SOMTOCHUKWU NCHEKW` / similar personal-name FPIs** → **Unexpected / Refund** by default (self-transfers returning, or transfers from known contacts). Genuine refunds belong in **Unexpected / Refund** and should be added as more specific rules when they occur.

## Domain notes — known classifications for the Monzo account

The user's standing classifications for recurring counterparties on the Monzo account. Note that Monzo rules cannot filter by transaction-type code; matching uses description and direction only.

### Inflows

- **`O Okwu-Boms (Faster Payments)`** (money in) → **Main Account Inflow**. The user's own top-ups from their main account. By far the most frequent inflow line. *Not* Unexpected/Refund — distinct from the Lloyds counterpart of the same name because the direction of flow is reversed (this is money landing in Monzo from Lloyds).
- **`Somtochukwu Nchekwubechukwu Obiana (Faster Payments)`** (money in, often with reference "Sent from Revolut") → **Unexpected / Refund**. Transfers from a known contact.
- **`WWW.HL.CO.UK BRISTOL GBR`** (money in) → **Stocks & Shares** (Asset Liquidation). Hargreaves Lansdown ISA withdrawals.

### Outflows — Bills

- **`Lebara Mobile Limited London GBR`** → **Bill - Phone & Internet**.
- **`THREE MOTO GLASGOW GBR`** → **Bill - Phone & Internet**.

### Outflows — Food Supplies

- **`W M MORRISONS DUMFRIES GBR`**, **`WM MORRISONS STORE DUMFRIES GBR`** → **Food Supplies**.
- **`Lidl GB DUMFRIES GBR`** → **Food Supplies**.
- **`TESCO STORES 2388 DUMFRIES GBR`** → **Food Supplies**.
- **`MARKS&SPENCER PLC SACA DUMFRIES GBR`** → **Food Supplies** (typically grocery; override per-rule if needed).
- **`POUNDLAND LTD - 2114 DUMFRIES GBR`** → **Food Supplies** (treat as grocery by default).

### Outflows — Eating Out

- **`DGHB CATERING DUMFRIES GBR`** → **Eating Out**. The most frequent outflow, multiple entries per day.
- **`MARCHBANK BAKERS THORNHILL DG3 GBR`** → **Eating Out**.
- **`La Dolce Vita Dumfries GBR`** → **Eating Out**.
- **`Enish Glasgow Glasgow GBR`** → **Eating Out**.
- **`PPOINT_*McEwans Premie Dumfries GBR`** → **Eating Out**.
- **`NYX*DCVendingLtd`** (Kilmarnock/Reading variants) → **Eating Out** (vending).
- **`DC7 VENDING LIMITED AYRSHIRE GBR`** → **Eating Out** (vending).

### Outflows — Sundry (catch-all for professional/medical fees and miscellaneous)

- **`RCGP (Direct Debit)`** → **Sundry**. Royal College of General Practitioners membership.
- **`GENERAL MEDICAL C (Direct Debit)`** → **Sundry**. General Medical Council registration.
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

### Outflows — Gifts/Entertainment/Misc

- **`AMAZON.CO.UK LONDON GBR`** → **Gifts/Entertainment/Misc**.
- **`T K MAXX DUMFRIES GBR`** → **Gifts/Entertainment/Misc**.
- **`BLUE INC - DUMFRIES DUMFRIES GBR`** → **Gifts/Entertainment/Misc**.
- **`Vinted Vilnius GBR`** → **Gifts/Entertainment/Misc** (refunds also classified here).

### Outflows — Charity / Donations

- **`Somtochukwu Nchekwubechukwu Obiana (Faster Payments)`** (money out) → **Charity / Donations**. Same counterparty as the inflow rule above, distinguished by `direction: out`.
- **`Omasirichi Okwu-Boms (Faster Payments)`** (money out) — needs case-by-case rules; self-transfers out to the main account. Not safely auto-classifiable.

### Outflows — Assets

- **`Transfer to Pot`** → **Active Savings**. Daily pot deposits (1p savings challenge etc.).
- **`WWW.HL.CO.UK BRISTOL GBR`** (money out) → **Stocks & Shares ISA**. Hargreaves Lansdown ISA contributions.

## Domain notes — known classifications for the Revolut account

The user's standing classifications for recurring counterparties on the Revolut GBP account. Like Monzo, Revolut has no transaction-type codes; matching uses description and direction only. Revolut descriptions are typically the merchant short-name (`Morrisons`, `Tesco`, `Hargreaves Lansdown`) with a continuation row beneath giving `To: <merchant address>, <location>` and `Card: 535456******1161`. The parser joins the merchant name and the `To:` / `From:` line into a single description; rules match against the joined form, which is the long-form merchant string used below.

### Inflows

- **`Payment from O OKWU-BOMS`** (money in, any reference — `BORROWED`, `BORROW OOO`, `BORROW DEFINITELY`, `No more borrow`, `NO MORE BORROW`, `Contribution`, or none) → **Main Account Inflow**. Top-ups from the user's main Lloyds account. By far the most frequent inflow line. Mirrors the Monzo `O Okwu-Boms (Faster Payments)` inflow.
- **`Payment from OMASIRICHI OKWU BOMS`** (money in) → **Main Account Inflow**. Uppercase variant of the same counterparty, seen occasionally.
- **`Payment from NATWEST HRPS PAYRO`** (money in, reference like `C1018215131/01`) → **Salary**. NatWest-routed HR Payroll deposit.
- **`Payment from ACTIVE SAVINGS CASH HUB`** (money in, reference `SOW...`) → **Savings** (Asset Liquidation). Hargreaves Lansdown Active Savings cash hub paying funds back to Revolut. Treated as drawing down from an interest-bearing savings buffer, not as income.

### Outflows — Internal transfers / Charity / Donations

- **`To Omasirichi Okwu-Boms`** / **`To Omasirichi Okwu Boms`** (money out, Faster Payments) → **Charity / Donations**. Self-transfers back to the user's main Lloyds account. Same convention as the Monzo `Omasirichi Okwu-Boms (Faster Payments)` outflow.
- **`To Somtochukwu Nchekwubechukwu Obiana`** (money out, Faster Payments) → **Charity / Donations**. Self-transfers to a secondary personal account. Same direction-disambiguation pattern as Monzo.

### Outflows — Bills

- **`Lebara mobile`** / **`Lebara Mobile Limited London GBR`** → **Bill - Phone & Internet**.

### Outflows — Food Supplies

- **`Morrisons`** (any `Wm Morrisons Store, Dumfries` / `Morr Dumfries, Dumfries` / `Morrisons Dumfries - 1, Dumfries, SCT` variant) → **Food Supplies**.
- **`Tesco`** (any `Tesco Stores 2388, Dumfries` / `Tesco Stores 5969, Dumfries` / `Tesco Pfs 5452, Heathhall` variant) → **Food Supplies**. Includes the `Pfs` (petrol filling station) variant by default; override per-rule if treating petrol separately.
- **`Lidl`** (`Lidl Gb, Dumfries` / `Lidl Gb Dumfries, Lidl Gb Dumfr, GBR`) → **Food Supplies**.
- **`ALDI`** / **`Aldi`** (`Aldi Stores, Dumfries` / `Aldi, Dumfries, SCT`) → **Food Supplies**.
- **`Marks & Spencer`** (`Marks&spencer Plc Saca, Dumfries`) → **Food Supplies** (typically grocery; override per-rule if needed).
- **`Poundland`** (`Poundland Ltd - 2114, Dumfries`) → **Food Supplies**.
- **`Iceland`** (`Iceland, Dumfries`) → **Food Supplies**.
- **`Albaraka Halal`** (`Albaraka Halal, Dumfries, GBR`) → **Food Supplies**.
- **`SPAR Food & Fuel`** / **`KeyStore`** / **`Fruits Roots`** → **Food Supplies**.

### Outflows — Eating Out

- **`Dghb Catering`** (`Dghb Catering, Dumfries`) → **Eating Out**.
- **`Greggs`** (`Greggs Plc, Dumfries`) → **Eating Out**.
- **`Costa Coffee`** (any `Costa Coffee 43011492, Manchester` / `Costa Coffee 43011529, Carlisle` / `Costa Coffee 43010497, Dumfries` variant) → **Eating Out**.
- **`Starbucks`** → **Eating Out**.
- **`Enish Glasgow`** → **Eating Out**.
- **`The Halston`** (`The Halston Aparthotel, Carlisle`) → **Eating Out** if a small amount, **Holidays & Travel** if a room charge — needs per-rule disambiguation, often by amount; default to **Eating Out** as the most common pattern.
- **`The Corner Eatery And`** / **`Top Stop Take Away`** / **`Embankment Cafe Co.`** / **`Shanghai Shanghai Oriental Buffet`** / **`Indian Greedy Coo`** / **`Sumup *the Flavour Hi`** / **`Royal Outpost`** → **Eating Out**.
- **`Ppoint_*mcewans Premie`** (the "Premier" merchant line) → **Eating Out**.

### Outflows — Holidays & Travel

- **`Trainline`** (`Trainline, +443332022222, GBR`) → **Holidays & Travel**.
- **`Travelodge`** / **`Travelodge by Wyndham`** (`Travelodg Travelodge G, Thame` / `Manchester`) → **Holidays & Travel**.
- **`Bee Network`** / **`Metrolink`** / **`Manchester Central`** / **`Sumup *manchester Cen, Manchester`** → **Holidays & Travel**.
- **`Euro Car Parks`** (`Euro Car Parks Ltd, Glasgow`) → **Holidays & Travel**.
- **`TransferGo`** (`Transfergo, London`) → **Holidays & Travel** by user convention (remittances treated under travel for budget purposes; override per-rule if user changes mind).

### Outflows — Car & Gas

- **`Shell`** (`Shell 9 St Michaels St, Dumfries` / `Shell Collin 568, Dumfries`) → **Car & Gas**. Fuel.
- **`Halfords`** (`Halfords 0847, Dumfries West`) → **Car & Gas**. Motor parts.
- **`Focus Motor Store Ltd`** (`Focus Motor Store Ltd, Dumfries`) → **Car & Gas**.
- **`Fonetech`** (`Fonetech, Dumfries, GBR`) — needs case-by-case rules; usually phone repair, classify per-incident.

### Outflows — Sundry

- **`Medcouncil`** (`Medcouncil, Ottawa, ON`, with CAD currency-conversion continuation line and sometimes a `Fee: £X.XX` line) → **Sundry**. Canadian Medical Council fee.
- **`Holland & Barrett`** (`Holland & Barrett, Dumfries`) → **Sundry**.
- **`Superdrug`** (`Superdrug Stores Plc, Dumfries`) → **Sundry**.
- **`Savers`** (`Savers Health & Beauty, Dumfries`) → **Sundry**.
- **`Merlin Office`** (`Merlin Office, Dumfries, GBR`) → **Sundry**.
- **`British Heart Foundation`** → **Sundry** (or **Charity / Donations** by user preference).
- **`Anthropic`** (`Anthropic, San Francisco, CA` and `Claude.ai Subscription, San Francisco, CA`) → **Sundry**. Claude subscription, may appear as a USD-converted line.

### Outflows — Gifts/Entertainment/Misc

- **`The Range`** (`The Range, Dumfries`) → **Gifts/Entertainment/Misc**.
- **`A1 Trading`** (`A1 Trading, 7703789578, GA`, USD-converted) → **Gifts/Entertainment/Misc**.
- **`Vue`** / **`Vue Cinemas`** / **`Boom Battle Bar Glasgo`** / **`Steam`** (`Steamgames.com ..., Hamburg, DEU`) → **Gifts/Entertainment/Misc**.
- **`The Stove Network`** (`The Stove Network, Dumfries Dg1, SCT`) → **Gifts/Entertainment/Misc**.

### Outflows — Charity / Donations (Revolut-specific small-value transfers)

- **`To ER Li`** / **`To Williams Obiegbu`** / **`To JOHN ADEBOLA SAMUEL`** / **`To QUEEN IME OKPONGETE`** / **`Transfer to Annabel Aigbodion`** / **`Transfer to Hersh Hamad`** → **Charity / Donations** by default (transfers to other individuals). User may override per-rule.

### Outflows — Assets

- **`Hargreaves Lansdown`** (`Www.hl.co.uk, Bristol, LND`) → **Stocks & Shares ISA**. ISA contributions. May appear multiple times on the same day (chunked transfers).

---

All classification lists will grow. New counterparties added to the user's life mean new rules. The steering doc is updated when the *intent* changes (e.g. "Trading 212 is now my dividend portfolio, not my ISA", "M&S is now treats, not groceries", or "TransferGo should be Charity, not Holidays & Travel"), not when a one-off transaction appears.
