# Requirements Document

## Introduction

The Revolut Expense Tool is a command-line application that transforms a Revolut GBP personal-account statement PDF into one categorised monthly cash-flow CSV per calendar month covered by the statement. The tool parses raw transaction data, classifies each transaction against a user-maintained YAML rules file, groups transactions by calendar month, reconciles against the statement's reported totals, and emits CSVs that conform to a fixed schema — complete with named sections, line-item subtotals, and grand totals. The tool targets a single end user running it locally against their own statements, removing the need for manual transaction classification.

This tool is a sibling of `lloyds-expense` and `monzo-expense`. All three share intent and output schema shape but are deliberately separate codebases. Revolut statements have their own format quirks: direction is encoded by which of two amount columns (`Money out`, `Money in`) the value appears in (like Lloyds, unlike Monzo's signed single column); there are no transaction-type codes (like Monzo, unlike Lloyds); a single PDF may span multiple calendar months (like Monzo, unlike Lloyds); dates use long-form English (`Apr 1, 2026`, unlike Lloyds' `DD MMM YY` and Monzo's `DD/MM/YYYY`); transaction descriptions wrap across multiple PDF rows in distinctive ways (`To:` / `From:`, `Card:`, `Reference:`, `Revolut Rate …`, `Fee:`); and the statement contains two non-cash-flow sections — **Pending** (before the main transactions table) and **Reverted** (after the main transactions table) — that must both be excluded. The Balance summary on page 1 prints opening balance, closing balance, total money in, and total money out explicitly, which is more than Monzo prints but the same shape as Lloyds' per-statement totals. These incompatibilities make a shared parser non-viable. Schema and writer logic are duplicated by design.

The `revolut_expense.schema` is identical in shape to `monzo_expense.schema` — both include the `MAIN_ACCOUNT_INFLOW` category in Irregular Inflows.

---

## Requirements

### Requirement 1: PDF Input Acceptance

**User Story:** As an account holder, I want to provide a single Revolut account statement PDF to the tool so that it can process my transactions without requiring any format conversion on my part.

#### Acceptance Criteria

1. WHEN the user supplies a PDF file path as a positional argument THEN the system SHALL accept exactly one PDF file per invocation.
2. WHEN the supplied file does not exist or is not readable THEN the system SHALL exit with code 4 and display a descriptive error message via `rich`.
3. WHEN the supplied file is not a valid Revolut GBP personal-account PDF THEN the system SHALL exit with code 3 and report a parse error.
4. WHEN more than one positional PDF argument is provided THEN the system SHALL exit with code 4 and inform the user that only one statement is accepted per run.
5. IF the PDF is password-protected or corrupt THEN the system SHALL exit with code 3 and display the underlying parse failure reason.
6. WHEN the PDF's "Balance summary" indicates a non-GBP product (or no product line) THEN the system SHALL exit with code 3 — only the GBP personal-account statement format is supported.

---

### Requirement 2: Transaction Parsing

**User Story:** As an account holder, I want every completed transaction in the statement to be extracted with full fidelity, so that no data is lost or silently misread before classification.

#### Acceptance Criteria

1. WHEN a valid Revolut GBP account PDF is processed THEN the system SHALL extract each transaction's date, description, amount, direction, and running balance, returning them as a tuple of frozen `Transaction` dataclasses on a `Statement` object. `Transaction` SHALL NOT carry a `type_code` field — Revolut statements do not include transaction-type codes.
2. WHEN a transaction row has a value in the `Money in` column THEN the system SHALL record `direction` as `"in"` and `amount` as a positive `Decimal`.
3. WHEN a transaction row has a value in the `Money out` column THEN the system SHALL record `direction` as `"out"` and `amount` as a positive `Decimal`. Outflows SHALL NOT be stored as negative numbers; `direction` is the single source of truth for inflow versus outflow.
4. WHEN a row has values in both the `Money out` and `Money in` columns THEN the system SHALL raise `ParseError` — this is a parser fault, not a legitimate data condition.
5. WHEN monetary values are parsed THEN the system SHALL use `decimal.Decimal` for all amounts, constructed from the cleaned string form (leading `£` stripped, thousand-separator commas stripped). Floats SHALL NOT appear anywhere in the parsing pipeline.
6. WHEN a transaction description wraps across multiple PDF rows THEN the system SHALL re-join those continuation rows into a single `description` string. The recognised continuation-row patterns are:
   - `To: <merchant or counterparty>` (card payments and outbound transfers)
   - `From: <counterparty, account number>` (inbound transfers)
   - `Card: 535456******1161` or any `Card: ` line (card-funded transactions)
   - `Reference: <text>` (Faster Payments references)
   - `Revolut Rate £1.00 = <rate> <CCY> (ECB rate* £1.00 = <rate> <CCY>)` followed by `<amount> <CCY>` (foreign-currency conversion lines)
   - `Fee: £<amount>` and the line beneath it carrying a converted-amount restatement (FX fees on currency conversions)
   The joining logic SHALL be contained entirely within `parser.py`. The joined description is a single string with continuation segments separated by a single space.
7. WHEN a `Fee: £X.XX` continuation line is encountered THEN the system SHALL absorb it into the parent transaction's joined description and SHALL NOT emit a separate `Transaction` for the fee. The fee amount is already included in the parent row's printed `Money out` value.
8. WHEN the PDF contains a section beginning `"Pending from <start> to <end>"` THEN the system SHALL detect that section and skip every row within it. Pending rows are not completed transactions and SHALL NOT be emitted as `Transaction` records.
9. WHEN the PDF contains a section beginning `"Reverted from <start> to <end>"` THEN the system SHALL detect that section and skip every row within it. Reverted rows have been undone by the bank and SHALL NOT be emitted as `Transaction` records; including them would double-count against the statement's reported totals.
10. WHEN identifying section boundaries THEN the system SHALL recognise `"Pending from"`, `"Account transactions from"`, and `"Reverted from"` as the three section header phrases. Only rows under `"Account transactions from"` SHALL be emitted as `Transaction` records.
11. WHEN transaction dates appear in the PDF THEN the system SHALL parse them as `MMM D, YYYY` (e.g. `Apr 1, 2026`, `May 24, 2026`) using `datetime.strptime(date_str, "%b %d, %Y")`; the parser SHALL NOT rely on the current system date to expand years — the year is always explicit in Revolut PDFs.
12. WHEN the transaction table spans multiple pages THEN the system SHALL concatenate rows into a single list preserving document order (top-to-bottom within a page, then page-by-page).
13. WHEN non-transaction content appears (column headers, page headers, footer disclaimers, "Page N of M" markers, the QR-code legal box) THEN the system SHALL ignore it and not emit `Transaction` records from it.
14. WHEN transactions are returned THEN the system SHALL preserve their document order. The parser SHALL NOT reorder by date, amount, or any other field.
15. WHEN the "Balance summary" block on page 1 is parsed THEN the system SHALL extract `Opening balance`, `Money out` (total), `Money in` (total), and `Closing balance` as `Decimal` values and store them on the `Statement` object as `opening_balance`, `total_money_out`, `total_money_in`, and `closing_balance`. The summary row labelled `"Account (E-Money)"` is the source of these values — the `"Total"` row exists too but for a single-product statement it carries identical figures.
16. WHEN the statement period appears on page 1 THEN the system SHALL extract the start and end dates from the `"Account transactions from <start> to <end>"` header (long-form English: `April 1, 2026 to May 24, 2026`), parse them, and store them as `period_start` and `period_end` on the `Statement` object.
17. WHEN account metadata (sort code, account number, IBAN, BIC) appears on page 1 THEN the system SHALL extract these and store them on the `Statement` object. They are not required for processing but are useful for debugging and for human verification when comparing CSVs to source.
18. IF the transaction table cannot be located in the PDF THEN the system SHALL exit with code 3 and report the specific parse failure, including the page number where parsing failed if determinable.
19. IF the PDF parses but produces zero `Transaction` records THEN the parser SHALL still return a valid `Statement` object with an empty transactions tuple; zero-transaction handling defined in R9 then applies.

---

### Requirement 3: Rules File Loading and Validation

**User Story:** As an account holder, I want to maintain a YAML rules file that maps transaction descriptions to budget categories, so that I can control classification without modifying the tool's source code.

#### Acceptance Criteria

1. WHEN the `--rules` option is supplied THEN the system SHALL load the YAML rules file from the specified path using `PyYAML` (`yaml.safe_load`).
2. WHEN `--rules` is not supplied THEN the system SHALL first look for a rules file at the project-local location `rules/revolut_rules.yaml` (relative to the working directory), then fall back to `~/.config/revolut-expense/rules.yaml`; if neither is present, the system SHALL exit with code 4 and display a usage message listing both paths.
3. WHEN the rules file is absent or unreadable THEN the system SHALL exit with code 4 and display a descriptive error message.
4. WHEN the rules file is loaded THEN the system SHALL validate that every rule has exactly one matcher: either `match` (a non-empty exact string) or `match_regex` (a compilable regular expression pattern). In the internal `Rule` representation, this SHALL be encoded as a tagged union (`ExactMatch | RegexMatch`), not as two nullable fields.
5. WHEN a rule entry contains a `type` field THEN the system SHALL exit with code 4 and display an error explaining that Revolut rules do not support type-code filtering. This field is valid in the Lloyds rules format but has no meaning for Revolut.
6. WHEN the rules file contains two or more rules whose matcher and `direction` fields are all identical (treating `None` and absent as equivalent, and comparing regex matchers by source string) THEN the system SHALL exit with code 4, list the duplicate rules by line number, and refuse to proceed.
7. WHEN a rule's `match_regex` value cannot be compiled as a Python regular expression THEN the system SHALL exit with code 4 and display the regex error position.
8. WHEN a rule specifies a `direction` field THEN the value MUST be `"in"` or `"out"`; any other value SHALL cause exit with code 4.
9. WHEN the YAML file's top-level structure is not a mapping containing a `rules` key whose value is a list THEN the system SHALL exit with code 4 with a descriptive error.
10. WHEN rules are returned from the loader THEN the list SHALL preserve the order of rules in the source YAML file, and each `Rule` SHALL carry the line number where it was defined for use in error messages.
11. WHEN a rule specifies a `category` that is not in the Revolut schema's closed enumeration THEN the system SHALL exit with code 4 and display the unknown category name.
12. IF the rules file contains malformed YAML THEN the system SHALL exit with code 4 and display the YAML parse error location.

---

### Requirement 4: Transaction Classification

**User Story:** As an account holder, I want the tool to classify my transactions automatically using my rules file, so that each transaction is assigned to the correct budget category without manual intervention.

#### Acceptance Criteria

1. WHEN comparing transaction descriptions to rules THEN the system SHALL apply the following normalisation to both sides before comparison: trim leading and trailing whitespace, collapse internal whitespace runs to a single space, and treat all variants of the Unicode hyphen/dash as equivalent to ASCII hyphen-minus.
2. WHEN classifying each transaction THEN the system SHALL first attempt a normalised exact match against all rules that use the `match` field, in rules-file order.
3. WHEN no exact match is found THEN the system SHALL attempt a regex match against all rules that use the `match_regex` field, in the order they appear in the rules file. Regex matching is applied against the normalised description.
4. WHEN a rule specifies a `direction` filter THEN the system SHALL only assign the rule if the transaction's direction matches.
5. WHEN a transaction matches exactly one rule THEN the system SHALL assign it to that rule's category.
6. WHEN one or more transactions match no rule THEN the system SHALL collect all unmatched transactions and handle them according to Requirement 5.

> **Note on multiple matches:** R3.6 makes duplicate rules a load-time error, so classification never has to choose between two rules with identical matcher and direction. For regex rules, first-in-file-order wins; the user is responsible for ordering them appropriately.

---

### Requirement 5: Unmatched Transaction Handling

**User Story:** As an account holder, I want to be clearly informed about any transactions that could not be classified, so that I can extend my rules file and re-run the tool.

#### Acceptance Criteria

1. WHEN at least one transaction is unmatched THEN the system SHALL exit with code 1 without producing any output CSVs. This behaviour is non-bypassable; there is no flag to suppress it.
2. WHEN at least one transaction is unmatched THEN the system SHALL list every unmatched transaction (date, description, amount, direction) to stderr via `rich` in a tabular format.
3. WHEN `--report-unmatched <path>` is supplied AND at least one transaction is unmatched THEN the system SHALL additionally write a plain-text report of unmatched transactions to the specified path before exiting with code 1.
4. WHEN all transactions are matched THEN the system SHALL NOT emit any unmatched-transaction warnings, and `--report-unmatched` (if supplied) SHALL have no effect.

---

### Requirement 6: Calendar Month Splitting

**User Story:** As an account holder, I want one CSV per calendar month covered by my statement, so that each file maps cleanly to one row in my monthly budget spreadsheet.

#### Acceptance Criteria

1. WHEN all transactions have been classified THEN the system SHALL group them by `(year, month)` of their transaction date into a `dict[YearMonth, ClassificationResult]`, where `YearMonth` is a `(int, int)` named tuple.
2. WHEN grouping transactions THEN the system SHALL preserve document order within each month's group.
3. WHEN the statement covers only a single calendar month THEN the system SHALL produce a dict with exactly one entry.
4. WHEN the statement spans two or more calendar months THEN the system SHALL produce one dict entry per month, with no transactions appearing in more than one month's group.
5. WHEN a classified transaction's date falls outside the statement's `period_start` to `period_end` range THEN the system SHALL raise a `ParseError`; this indicates a parser fault.
6. WHEN the splitter runs THEN it SHALL be a pure function with no I/O and no side effects.

---

### Requirement 7: Reconciliation

**User Story:** As an account holder, I want the tool to verify that its computed totals match the statement's printed totals, so that I can trust the output is arithmetically correct to the penny.

#### Acceptance Criteria

1. WHEN all transactions have been classified THEN the system SHALL sum all classified money-in amounts across all months and compare the result to `Statement.total_money_in` using `Decimal` equality.
2. WHEN all transactions have been classified THEN the system SHALL sum all classified money-out amounts across all months and compare the result to `Statement.total_money_out` using `Decimal` equality.
3. WHEN all transactions have been parsed THEN the system SHALL verify that `opening_balance + total_money_in - total_money_out == closing_balance` using `Decimal` equality; failure indicates a parser fault and SHALL cause exit with code 3.
4. WHEN either the computed inflow total or the computed outflow total differs from the statement total by any amount THEN the system SHALL exit with code 2 and display the discrepancy (expected, actual, and difference) via `rich`.
5. WHEN reconciliation passes THEN the system SHALL proceed to CSV output without printing any reconciliation message.
6. WHERE reconciliation is concerned THEN no CLI flag SHALL bypass it.
7. WHEN reconciliation is performed THEN it SHALL operate over the entire statement period as a whole, not per-month. Revolut prints period-level totals only; per-month totals are not available in the PDF.
8. WHEN Pending or Reverted rows exist in the PDF THEN they SHALL NOT contribute to the reconciliation sum. The Balance summary totals on page 1 already exclude Pending and Reverted figures.

---

### Requirement 8: CSV Output

**User Story:** As an account holder, I want the tool to produce one CSV per month that exactly matches my fixed budget schema, so that I can import each file into my spreadsheet without any restructuring.

#### Acceptance Criteria

1. WHEN all transactions are classified, split by month, and reconciliation passes THEN the system SHALL write one CSV file per calendar month to the directory specified by `--out-dir`.
2. WHEN naming output files THEN the system SHALL use the pattern `<YYYY-MM>.csv` (e.g. `2026-04.csv`) for each month. If two statements covering overlapping months are processed in the same directory, the later run SHALL overwrite silently; output is regenerable from the PDF and rules file.
3. WHEN the `--out-dir` directory does not exist THEN the system SHALL create it (including any missing parent directories).
4. WHEN a CSV is written THEN the system SHALL prepend a metadata header recording the statement period (start date and end date of the full statement, not just the month) before the schema rows.
5. WHEN a CSV is written THEN the system SHALL emit schema rows in the following fixed order, with no row omitted even if its value is zero:
   - Section header: Regular Inflows
   - Line items: Salary
   - Subtotal: Regular Inflows subtotal
   - Section header: Irregular Inflows
   - Line items: Unexpected / Refund, Loan, Main Account Inflow
   - Subtotal: Irregular Inflows subtotal
   - Section header: Asset Liquidation
   - Line items: Savings, Stocks & Shares
   - Subtotal: Asset Liquidation subtotal
   - Grand total row: Total Income
   - Section header: Regular Outflows
   - Line items: Rent, Bill - Council Tax, Bill - Electricity & Gas, Bill - Phone & Internet, Food Supplies, Debt, Car & Gas
   - Subtotal: Regular Outflows subtotal
   - Section header: Irregular Outflows
   - Line items: Charity / Donations, Gifts/Entertainment/Misc, Sundry, Holidays & Travel, Education, Eating Out
   - Subtotal: Irregular Outflows subtotal
   - Section header: Assets
   - Line items: Active Savings, Lifetime ISA, Stocks & Shares ISA, Dividend Portfolio
   - Subtotal: Assets subtotal
   - Grand total row: Total Expenditure
   - Balance row: Balance (Total Income − Total Expenditure)
6. WHEN a category has no transactions in a given month THEN the system SHALL still emit its row with a value of `0.00`.
7. WHEN subtotals are computed THEN the system SHALL sum the `Decimal` values of all line items within the section, quantized to two decimal places.
8. WHEN grand totals are computed THEN the system SHALL sum the `Decimal` values of all section subtotals within the respective inflow or outflow group.
9. WHEN the CSV is written THEN the system SHALL use the Python `csv` stdlib module with `csv.QUOTE_MINIMAL`, UTF-8 encoding, and `\n` line endings.
10. WHEN the system writes multiple CSVs THEN the system SHALL write them in chronological month order and SHALL report each written file path to stdout via `rich` upon success.

---

### Requirement 9: Zero-Transaction Statements

**User Story:** As an account holder, I want the tool to behave predictably even on a statement with no completed transactions, so that I get a usable CSV rather than a crash or a silent skip.

#### Acceptance Criteria

1. WHEN a parsed statement contains zero transactions AND `total_money_in` and `total_money_out` are both `0.00` THEN the system SHALL emit a single CSV (for the statement's start month) with every schema row present, every value set to `0.00`, and exit with code 0.
2. WHEN a parsed statement contains zero transactions BUT `total_money_in` or `total_money_out` is non-zero THEN the system SHALL exit with code 3 (parser fault — totals disagree with extracted rows).
3. WHEN a parsed statement contains only Pending and/or Reverted rows (no completed transactions) AND `total_money_in` and `total_money_out` are both `0.00` THEN R9.1 applies — Pending and Reverted are excluded from both the transaction count and the totals.

---

### Requirement 10: CLI Interface

**User Story:** As an account holder, I want a simple command-line interface with clear options so that I can run the tool with minimal typing and understand available options from the help text.

#### Acceptance Criteria

1. WHEN the tool is invoked THEN the system SHALL accept the following signature: `revolut-expense <statement.pdf> [--rules <rules.yaml>] --out-dir <dir> [--report-unmatched <path>]`.
2. WHEN `--rules` is not supplied THEN the system SHALL use the default rules resolution order defined in R3.2.
3. WHEN `--out-dir` is not supplied THEN the system SHALL default to `./output` (a directory named `output` in the current working directory) and create it if absent.
4. WHEN `--help` is requested THEN the system SHALL display all options, defaults, and exit codes via `typer`.
5. WHEN the tool exits THEN the system SHALL use only the following exit codes: 0 (success), 1 (unmatched transactions), 2 (reconciliation mismatch), 3 (parse error), 4 (bad input).
6. WHERE console output is produced THEN the system SHALL use `rich` for all stderr messages, including errors and warnings, and reserve stdout for the list of written CSV file paths on success.

---

### Requirement 11: Module Boundaries

**User Story:** As a developer maintaining the tool, I want clearly separated modules with single responsibilities, so that each component can be tested and modified in isolation.

#### Acceptance Criteria

1. WHEN the codebase is structured THEN the system SHALL contain the following modules under `src/revolut_expense/`: `schema.py`, `errors.py`, `parser.py`, `rules.py`, `classifier.py`, `splitter.py`, `reconciler.py`, `writer.py`, and `cli.py`.
2. WHERE `cli.py` is concerned THEN it SHALL be the only module that accesses `sys.argv`, writes to stdout/stderr directly, or calls `sys.exit`.
3. WHERE `schema.py` is concerned THEN it SHALL define the closed enumeration of all valid categories (including `Main Account Inflow`) and the canonical CSV row order. It SHALL be structurally identical to `monzo_expense/schema.py`.
4. WHERE `errors.py` is concerned THEN it SHALL define a typed exception hierarchy (`StatementToCsvError`, `ParseError`, `RulesConfigError`, `UnmatchedTransactionsError`, `ReconciliationError`, `InputError`) used across all other modules.
5. WHERE `parser.py` is concerned THEN it SHALL accept a file path and return a typed `Statement` frozen dataclass containing `sort_code`, `account_number`, `iban`, `bic`, `period_start`, `period_end`, `opening_balance`, `closing_balance`, `total_money_in`, `total_money_out`, and `transactions: tuple[Transaction, ...]`. `Transaction` SHALL have `date`, `description`, `amount: Decimal`, `direction`, and `running_balance`; it SHALL NOT have a `type_code` field.
6. WHERE `rules.py` is concerned THEN it SHALL accept a file path and return a validated ordered list of `Rule` objects, raising `RulesConfigError` for invalid content. `Rule` SHALL NOT have a `type_code` field.
7. WHERE `classifier.py` is concerned THEN it SHALL accept transactions and rules and return a `ClassificationResult` with no side effects.
8. WHERE `splitter.py` is concerned THEN it SHALL accept a `ClassificationResult` and return a `dict[YearMonth, ClassificationResult]` with no side effects.
9. WHERE `reconciler.py` is concerned THEN it SHALL accept the full `ClassificationResult` (all months combined) and `Statement` totals and return a `ReconciliationReport` without raising for inflow/outflow mismatches. The CLI decides whether to raise based on the report. The balance-arithmetic check (R7.3) raises `ParseError` directly because it indicates a parser fault, not a user-correctable condition.
10. WHERE `writer.py` is concerned THEN it SHALL accept `dict[YearMonth, ClassificationResult]`, the `Statement`, and an output directory path, write the CSVs with no side effects beyond file I/O, and return the list of written paths in chronological order.
11. WHEN modules import from each other THEN `parser.py`, `rules.py`, `classifier.py`, `splitter.py`, `reconciler.py`, and `writer.py` SHALL import from `schema.py` and `errors.py` only; they SHALL NOT import from `cli.py` or from each other (except `schema.py` and `errors.py`). `cli.py` is the sole orchestrator.
12. WHEN `revolut_expense` needs a concept also present in `monzo_expense` or `lloyds_expense` THEN the code SHALL be duplicated; cross-package imports between the three tools are forbidden.

---

### Requirement 12: Error Reporting Quality

**User Story:** As an account holder, I want error messages to be clear and actionable, so that I know exactly what went wrong and how to fix it.

#### Acceptance Criteria

1. WHEN any error occurs THEN the system SHALL display a human-readable message that identifies the problem, its location (file, page, or row where applicable), and the expected correct form.
2. WHEN unmatched transactions are reported THEN the system SHALL display each transaction's date, description, direction, and amount in a tabular format via `rich`.
3. WHEN a reconciliation mismatch is reported THEN the system SHALL display the statement total, the computed total, and the difference for both money-in and money-out.
4. WHEN a rules validation error is reported THEN the system SHALL list each invalid rule by its line number in the YAML file and describe the nature of the violation.
5. WHEN the tool exits with a non-zero code THEN all error output SHALL have been written to stderr; stdout SHALL remain empty unless the tool succeeded (exit code 0) and printed written file paths.

---

### Requirement 13: Known Classification Rules (Live Rules File)

**User Story:** As an account holder, I want the live rules file to cover all known mappings for my account's recurring transactions, so that common transactions are classified correctly from the first run.

The live rules file lives at `rules/revolut_rules.yaml` in the project root (the project-local default discovered by the CLI). The rules below correspond to the counterparties documented in `product.md` under "Domain notes — known classifications for the Revolut account".

#### Acceptance Criteria

1. WHEN the rules file is loaded THEN it SHALL include rules mapping the main-account top-up counterparty to `Main Account Inflow`: `match_regex: "^Payment from O OKWU-BOMS"` with `direction: in`, and `match_regex: "^Payment from OMASIRICHI OKWU BOMS"` with `direction: in` (uppercase variant). The Reference text (`BORROWED`, `BORROW OOO`, `BORROW DEFINITELY`, `No more borrow`, `NO MORE BORROW`, `Contribution`, or absent) is irrelevant — all variants map to the same category.
2. WHEN the rules file is loaded THEN it SHALL include `match_regex: "^Payment from NATWEST HRPS PAYRO"` with `direction: in` mapped to `Salary`.
3. WHEN the rules file is loaded THEN it SHALL include `match_regex: "^Payment from ACTIVE SAVINGS CASH HUB"` with `direction: in` mapped to `Savings` (Asset Liquidation) — Hargreaves Lansdown Active Savings cash hub paying funds back to Revolut.
4. WHEN the rules file is loaded THEN it SHALL include rules for the user's self-transfers to the main Lloyds account: `match_regex: "^To Omasirichi Okwu.Boms"` with `direction: out` mapped to `Charity / Donations` (the `.` covers both space and hyphen variants between `Okwu` and `Boms`), and `match_regex: "^To Somtochukwu Nchekwubechukwu Obiana"` with `direction: out` mapped to `Charity / Donations`.
5. WHEN the rules file is loaded THEN it SHALL include rules for phone/internet bills: `match_regex: "^Lebara"` mapped to `Bill - Phone & Internet`.
6. WHEN the rules file is loaded THEN it SHALL include rules for known Food Supplies counterparties: `match_regex: "^Morrisons "`, `match_regex: "^Tesco "`, `match_regex: "^Lidl"`, `match_regex: "^ALDI"`, `match_regex: "^Aldi"`, `match_regex: "^Marks & Spencer"`, `match_regex: "^Poundland"`, `match_regex: "^Iceland"`, `match_regex: "^Albaraka Halal"`, `match_regex: "^SPAR"`, `match_regex: "^KeyStore"`, `match_regex: "^Fruits Roots"` — all mapped to `Food Supplies`. Regex anchors (`^`) are used because Revolut descriptions begin with the merchant short-name and continue into `To: <address>` continuation segments after join.
7. WHEN the rules file is loaded THEN it SHALL include rules for known Eating Out counterparties: `match_regex: "^Dghb Catering"`, `match_regex: "^Greggs"`, `match_regex: "^Costa Coffee"`, `match_regex: "^Starbucks"`, `match_regex: "^Enish Glasgow"`, `match_regex: "^The Corner Eatery"`, `match_regex: "^Top Stop Take Away"`, `match_regex: "^Embankment Cafe"`, `match_regex: "^Shanghai Shanghai"`, `match_regex: "^Indian Greedy Coo"`, `match_regex: "^The Flavour Hi"`, `match_regex: "^Royal Outpost"`, `match_regex: "^Premier"` (the merchant short-name for `Ppoint_*mcewans Premie`) — all mapped to `Eating Out`. Note: in real Revolut PDFs the primary row description for this merchant is `The Flavour Hi`; the `Sumup *the Flavour Hi` text appears only in the `To:` continuation row and is not what the regex matches against.
8. WHEN the rules file is loaded THEN it SHALL include rules for Holidays & Travel: `match_regex: "^Trainline"`, `match_regex: "^Travelodge"`, `match_regex: "^Bee Network"`, `match_regex: "^Metrolink"`, `match_regex: "^Manchester Central"`, `match_regex: "^Euro Car Parks"`, `match_regex: "^TransferGo"`, `match_regex: "^The Halston"` — all mapped to `Holidays & Travel`. Note: the `Manchester Central` rule already covers the merchant whose `To:` continuation contains `Sumup *manchester Cen` — no separate `^Sumup \\*manchester` rule is needed or included.
9. WHEN the rules file is loaded THEN it SHALL include rules for Car & Gas: `match_regex: "^Shell"`, `match_regex: "^Halfords"`, `match_regex: "^Focus Motor Store"` — all mapped to `Car & Gas`.
10. WHEN the rules file is loaded THEN it SHALL include rules for Sundry: `match_regex: "^Medcouncil"`, `match_regex: "^Holland & Barrett"`, `match_regex: "^Superdrug"`, `match_regex: "^Savers"`, `match_regex: "^Merlin Office"`, `match_regex: "^British Heart Foundation"`, `match_regex: "^Anthropic"`, `match_regex: "^Fonetech"` — all mapped to `Sundry`. The `Anthropic` regex covers both the `Anthropic, San Francisco, CA` and `Claude.ai Subscription, San Francisco, CA` description variants because the prefix is the same after merchant-name extraction.
11. WHEN the rules file is loaded THEN it SHALL include rules for Gifts/Entertainment/Misc: `match_regex: "^The Range"`, `match_regex: "^A1 Trading"`, `match_regex: "^Vue"` (covers both `Vue` and `Vue Cinemas`), `match_regex: "^Boom Battle Bar"`, `match_regex: "^Steam"`, `match_regex: "^The Stove Network"` — all mapped to `Gifts/Entertainment/Misc`.
12. WHEN the rules file is loaded THEN it SHALL include rules for personal-name outbound Faster Payments treated as `Charity / Donations` by default: `match_regex: "^To ER Li"`, `match_regex: "^To Williams Obiegbu"`, `match_regex: "^To JOHN ADEBOLA SAMUEL"`, `match_regex: "^To QUEEN IME OKPONGETE"`, `match_regex: "^Transfer to Annabel Aigbodion"`, `match_regex: "^Transfer to Hersh Hamad"` — all with `direction: out` mapped to `Charity / Donations`.
13. WHEN the rules file is loaded THEN it SHALL include `match_regex: "^Hargreaves Lansdown"` with `direction: out` mapped to `Stocks & Shares ISA` (Hargreaves Lansdown card-funded ISA contributions; note the merchant short-name `Hargreaves Lansdown` differs from the Monzo equivalent `WWW.HL.CO.UK BRISTOL GBR` because Revolut and Monzo print the same merchant differently).

---

### Requirement 14: Non-Functional — Code Quality

**User Story:** As a developer maintaining the tool, I want enforced code quality standards, so that the codebase remains readable and type-safe over time.

#### Acceptance Criteria

1. WHEN code is committed THEN the system SHALL pass `ruff` linting and formatting checks with no suppressed warnings.
2. WHEN code is committed THEN the system SHALL pass `mypy --strict` type checking with no ignored errors.
3. WHEN tests are run THEN the system SHALL achieve at least 90% line coverage on the non-CLI modules (`schema`, `errors`, `parser`, `rules`, `classifier`, `splitter`, `reconciler`, `writer`) using `pytest`.
4. WHEN the project is set up THEN all `revolut_expense` dependencies SHALL be declared in the existing `pyproject.toml` alongside `lloyds_expense` and `monzo_expense`, managed with `uv`. A `[project.scripts]` entry `revolut-expense = "revolut_expense.cli:app"` SHALL be added, and `src/revolut_expense` SHALL be added to `[tool.hatch.build.targets.wheel].packages`. `src/revolut_expense/cli.py` SHALL be added to the `[tool.coverage.run] omit` list alongside the existing Lloyds and Monzo CLI omissions.
5. WHEN test fixtures are required THEN synthetic Revolut PDFs SHALL be generated by a script in `tests/revolut/fixtures/` using `reportlab`. The multi-month fixture SHALL cover at least two calendar months to exercise `splitter.py` and the multi-CSV writer path. A dedicated `statement_with_pending_and_reverted.pdf` fixture SHALL contain at least one Pending row and at least one Reverted row, and tests SHALL assert that those rows are excluded from `Transaction` extraction, from reconciliation, and from CSV output. Fixtures are checked in; tests SHALL NOT reach the network.
