# Requirements Document

## Introduction

The Monzo Expense Tool is a command-line application that transforms a Monzo personal-account statement PDF into one categorised monthly cash-flow CSV per calendar month covered by the statement. The tool parses raw transaction data, classifies each transaction against a user-maintained YAML rules file, groups transactions by calendar month, reconciles against the statement's reported totals, and emits CSVs that conform to a fixed personal-finance schema — complete with named sections, line-item subtotals, and grand totals. The tool targets a single end user running it locally against their own statements, removing the need for manual transaction classification.

This tool is a sibling of `lloyds-expense`. The two share intent and output schema shape but are deliberately separate codebases. Monzo statements have a fundamentally different format: direction is encoded in the sign of a single amount column (no separate money-in / money-out columns), there are no transaction-type codes, a single PDF may span multiple calendar months, descriptions frequently wrap across PDF rows, and Pot statement pages trail the personal-account section and must be ignored. These incompatibilities make a shared parser non-viable. Schema and writer logic are duplicated by design.

---

## Requirements

### Requirement 1: PDF Input Acceptance

**User Story:** As an account holder, I want to provide a single Monzo personal-account statement PDF to the tool so that it can process my transactions without requiring any format conversion on my part.

#### Acceptance Criteria

1. WHEN the user supplies a PDF file path as a positional argument THEN the system SHALL accept exactly one PDF file per invocation.
2. WHEN the supplied file does not exist or is not readable THEN the system SHALL exit with code 4 and display a descriptive error message via `rich`.
3. WHEN the supplied file is not a valid Monzo personal-account PDF THEN the system SHALL exit with code 3 and report a parse error.
4. WHEN more than one positional PDF argument is provided THEN the system SHALL exit with code 4 and inform the user that only one statement is accepted per run.
5. IF the PDF is password-protected or corrupt THEN the system SHALL exit with code 3 and display the underlying parse failure reason.
6. WHEN the supplied PDF is a Monzo Flex, joint-account, or business-account statement THEN the system SHALL exit with code 3; only Monzo personal-account statements are in scope.

---

### Requirement 2: Transaction Parsing

**User Story:** As an account holder, I want every transaction in my Monzo statement to be extracted with full fidelity, so that no data is lost or silently misread before classification.

#### Acceptance Criteria

1. WHEN a valid Monzo personal-account PDF is processed THEN the system SHALL extract each transaction's date, description, amount, direction, and running balance, returning them as a tuple of frozen `Transaction` dataclasses on a `Statement` object. `Transaction` SHALL NOT carry a `type_code` field — Monzo statements do not include transaction-type codes.
2. WHEN a transaction row carries a positive amount THEN the system SHALL record `direction` as `"in"` and `amount` as a positive `Decimal`.
3. WHEN a transaction row carries a negative amount THEN the system SHALL record `direction` as `"out"` and `amount` as a positive `Decimal`. Outflows SHALL NOT be stored as negative numbers; `direction` is the single source of truth for inflow versus outflow.
4. WHEN monetary values are parsed THEN the system SHALL use `decimal.Decimal` for all amounts, constructed from the cleaned string form. Floats SHALL NOT appear anywhere in the parsing pipeline.
5. WHEN amounts in the PDF contain thousand-separator commas THEN the system SHALL strip them before constructing the `Decimal`.
6. WHEN a transaction description wraps across multiple PDF rows — common for Faster Payments entries with `Reference: …` lines and for currency-conversion annotations — THEN the system SHALL re-join those continuation lines into a single `description` string, separated by a single space. The joining logic SHALL be contained entirely within `parser.py`.
7. WHEN the PDF contains Pot statement pages (pages describing Pot accounts rather than the main personal account) THEN the system SHALL detect and skip them entirely. No `Transaction` records SHALL be emitted from Pot pages. The personal-account section always precedes Pot pages.
8. WHEN transaction dates appear in the PDF THEN the system SHALL parse them using the four-digit year visible in the PDF; the parser SHALL NOT rely on the current system date to expand years.
9. WHEN the transaction table spans multiple pages of the personal-account section THEN the system SHALL concatenate rows into a single list preserving document order (top-to-bottom within a page, then page-by-page).
10. WHEN non-transaction content appears (e.g. column legends, summary rows, Pot page content) THEN the system SHALL ignore it and not emit `Transaction` records from it.
11. WHEN transactions are returned THEN the system SHALL preserve their document order. The parser SHALL NOT reorder by date, amount, or any other field.
12. WHEN the first page of the PDF contains period-level summary totals (`Total deposits`, `Total outgoings`) THEN the system SHALL extract them as `Decimal` values and store them on the `Statement` object.
13. WHEN the first page of the PDF contains opening and closing balance figures THEN the system SHALL extract them as `Decimal` values and store them on the `Statement` object.
14. IF the transaction table cannot be located in the personal-account section of the PDF THEN the system SHALL exit with code 3 and report the specific parse failure, including the page number where parsing failed if determinable.
15. IF the PDF parses but produces zero `Transaction` records THEN the parser SHALL still return a valid `Statement` object with an empty transactions list; zero-transaction handling defined in R9 then applies.

---

### Requirement 3: Rules File Loading and Validation

**User Story:** As an account holder, I want to maintain a YAML rules file that maps transaction descriptions to budget categories, so that I can control classification without modifying the tool's source code.

#### Acceptance Criteria

1. WHEN the `--rules` option is supplied THEN the system SHALL load the YAML rules file from the specified path using `PyYAML` (`yaml.safe_load`).
2. WHEN `--rules` is not supplied THEN the system SHALL look for a rules file at the default location `~/.config/monzo-expense/rules.yaml`; if neither is present, the system SHALL exit with code 4 and display a usage message.
3. WHEN the rules file is absent or unreadable THEN the system SHALL exit with code 4 and display a descriptive error message.
4. WHEN the rules file is loaded THEN the system SHALL validate that every rule has exactly one matcher: either `match` (a non-empty exact string) or `match_regex` (a compilable regular expression pattern). In the internal `Rule` representation, this SHALL be encoded as a tagged union (`ExactMatch | RegexMatch`), not as two nullable fields.
5. WHEN a rule entry contains a `type` field THEN the system SHALL exit with code 4 and display an error explaining that Monzo rules do not support type-code filtering. This field is valid in the Lloyds rules format but has no meaning for Monzo.
6. WHEN the rules file contains two or more rules whose matcher and `direction` fields are all identical (treating `None` and absent as equivalent, and comparing regex matchers by source string) THEN the system SHALL exit with code 4, list the duplicate rules by line number, and refuse to proceed.
7. WHEN a rule's `match_regex` value cannot be compiled as a Python regular expression THEN the system SHALL exit with code 4 and display the regex error position.
8. WHEN a rule specifies a `direction` field THEN the value MUST be `"in"` or `"out"`; any other value SHALL cause exit with code 4.
9. WHEN the YAML file's top-level structure is not a mapping containing a `rules` key whose value is a list THEN the system SHALL exit with code 4 with a descriptive error.
10. WHEN rules are returned from the loader THEN the list SHALL preserve the order of rules in the source YAML file, and each `Rule` SHALL carry the line number where it was defined for use in error messages.
11. WHEN a rule specifies a `category` that is not in the Monzo schema's closed enumeration THEN the system SHALL exit with code 4 and display the unknown category name.
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

1. WHEN all transactions have been classified THEN the system SHALL sum all classified money-in amounts across all months and compare the result to `Statement.total_deposits` using `Decimal` equality.
2. WHEN all transactions have been classified THEN the system SHALL sum all classified money-out amounts across all months and compare the result to `Statement.total_outgoings` using `Decimal` equality.
3. WHEN all transactions have been parsed THEN the system SHALL verify that `opening_balance + total_deposits - total_outgoings == closing_balance` using `Decimal` equality; failure indicates a parser fault and SHALL cause exit with code 3.
4. WHEN either the computed inflow total or the computed outflow total differs from the statement total by any amount THEN the system SHALL exit with code 2 and display the discrepancy (expected, actual, and difference) via `rich`.
5. WHEN reconciliation passes THEN the system SHALL proceed to CSV output without printing any reconciliation message.
6. WHERE reconciliation is concerned THEN no CLI flag SHALL bypass it.
7. WHEN reconciliation is performed THEN it SHALL operate over the entire statement period as a whole, not per-month. Monzo only prints period-level totals on page 1; per-month totals are not available in the PDF.

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

**User Story:** As an account holder, I want the tool to behave predictably even on a statement with no transactions, so that I get a usable CSV rather than a crash or a silent skip.

#### Acceptance Criteria

1. WHEN a parsed statement contains zero transactions AND `total_deposits` and `total_outgoings` are both `0.00` THEN the system SHALL emit a single CSV (for the statement's start month) with every schema row present, every value set to `0.00`, and exit with code 0.
2. WHEN a parsed statement contains zero transactions BUT `total_deposits` or `total_outgoings` is non-zero THEN the system SHALL exit with code 3 (parser fault — totals disagree with extracted rows).

---

### Requirement 10: CLI Interface

**User Story:** As an account holder, I want a simple command-line interface with clear options so that I can run the tool with minimal typing and understand available options from the help text.

#### Acceptance Criteria

1. WHEN the tool is invoked THEN the system SHALL accept the following signature: `monzo-expense <statement.pdf> [--rules <rules.yaml>] --out-dir <dir> [--report-unmatched <path>]`.
2. WHEN `--rules` is not supplied THEN the system SHALL fall back to `~/.config/monzo-expense/rules.yaml` as specified in R3.2.
3. WHEN `--out-dir` is not supplied THEN the system SHALL exit with code 4 and display a usage message.
4. WHEN `--help` is requested THEN the system SHALL display all options, defaults, and exit codes via `typer`.
5. WHEN the tool exits THEN the system SHALL use only the following exit codes: 0 (success), 1 (unmatched transactions), 2 (reconciliation mismatch), 3 (parse error), 4 (bad input).
6. WHERE console output is produced THEN the system SHALL use `rich` for all stderr messages, including errors and warnings, and reserve stdout for the list of written CSV file paths on success.

---

### Requirement 11: Module Boundaries

**User Story:** As a developer maintaining the tool, I want clearly separated modules with single responsibilities, so that each component can be tested and modified in isolation.

#### Acceptance Criteria

1. WHEN the codebase is structured THEN the system SHALL contain the following modules under `src/monzo_expense/`: `schema.py`, `errors.py`, `parser.py`, `rules.py`, `classifier.py`, `splitter.py`, `reconciler.py`, `writer.py`, and `cli.py`.
2. WHERE `cli.py` is concerned THEN it SHALL be the only module that accesses `sys.argv`, writes to stdout/stderr directly, or calls `sys.exit`.
3. WHERE `schema.py` is concerned THEN it SHALL define the closed enumeration of all valid categories (including `Main Account Inflow`) and the canonical CSV row order.
4. WHERE `errors.py` is concerned THEN it SHALL define a typed exception hierarchy (`StatementToCsvError`, `ParseError`, `RulesConfigError`, `UnmatchedTransactionsError`, `ReconciliationError`, `InputError`) used across all other modules.
5. WHERE `parser.py` is concerned THEN it SHALL accept a file path and return a typed `Statement` frozen dataclass containing `sort_code`, `account_number`, `period_start`, `period_end`, `opening_balance`, `closing_balance`, `total_deposits`, `total_outgoings`, and `transactions: tuple[Transaction, ...]`. `Transaction` SHALL have `date`, `description`, `amount: Decimal`, `direction`, and `running_balance`; it SHALL NOT have a `type_code` field.
6. WHERE `rules.py` is concerned THEN it SHALL accept a file path and return a validated ordered list of `Rule` objects, raising `RulesConfigError` for invalid content. `Rule` SHALL NOT have a `type_code` field.
7. WHERE `classifier.py` is concerned THEN it SHALL accept transactions and rules and return a `ClassificationResult` with no side effects.
8. WHERE `splitter.py` is concerned THEN it SHALL accept a `ClassificationResult` and return a `dict[YearMonth, ClassificationResult]` with no side effects.
9. WHERE `reconciler.py` is concerned THEN it SHALL accept the full `ClassificationResult` (all months combined) and `Statement` totals and return a `ReconciliationReport` without raising. The CLI decides whether to raise based on the report.
10. WHERE `writer.py` is concerned THEN it SHALL accept `dict[YearMonth, ClassificationResult]`, the `Statement`, and an output directory path, write the CSVs with no side effects beyond file I/O, and return the list of written paths in chronological order.
11. WHEN modules import from each other THEN `parser.py`, `rules.py`, `classifier.py`, `splitter.py`, `reconciler.py`, and `writer.py` SHALL import from `schema.py` and `errors.py` only; they SHALL NOT import from `cli.py` or from each other (except `schema.py` and `errors.py`). `cli.py` is the sole orchestrator.
12. WHEN `monzo_expense` needs a concept also present in `lloyds_expense` THEN the code SHALL be duplicated; cross-package imports between the two tools are forbidden.

---

### Requirement 12: Error Reporting Quality

**User Story:** As an account holder, I want error messages to be clear and actionable, so that I know exactly what went wrong and how to fix it.

#### Acceptance Criteria

1. WHEN any error occurs THEN the system SHALL display a human-readable message that identifies the problem, its location (file, page, or row where applicable), and the expected correct form.
2. WHEN unmatched transactions are reported THEN the system SHALL display each transaction's date, description, direction, and amount in a tabular format via `rich`.
3. WHEN a reconciliation mismatch is reported THEN the system SHALL display the statement total, the computed total, and the difference for both deposits and outgoings.
4. WHEN a rules validation error is reported THEN the system SHALL list each invalid rule by its line number in the YAML file and describe the nature of the violation.
5. WHEN the tool exits with a non-zero code THEN all error output SHALL have been written to stderr; stdout SHALL remain empty unless the tool succeeded (exit code 0) and printed written file paths.

---

### Requirement 13: Known Classification Rules (Seed Data)

**User Story:** As an account holder, I want an example rules file to ship with the tool covering known mappings for my account's recurring transactions, so that common transactions are classified correctly from the first run.

#### Acceptance Criteria

1. WHEN the example rules file (`examples/monzo_rules.example.yaml`) is shipped THEN it SHALL include a rule mapping `O Okwu-Boms (Faster Payments)` with `direction: in` to the category `Main Account Inflow`.
2. WHEN the example rules file is shipped THEN it SHALL include rules for all known food-supply counterparties: `W M MORRISONS DUMFRIES GBR`, `WM MORRISONS STORE DUMFRIES GBR`, `Lidl GB DUMFRIES GBR`, `TESCO STORES 2388 DUMFRIES GBR`, `MARKS&SPENCER PLC SACA DUMFRIES GBR`, and `POUNDLAND LTD - 2114 DUMFRIES GBR`, each mapped to the category `Food Supplies`.
3. WHEN the example rules file is shipped THEN it SHALL include rules for all known eating-out counterparties: `DGHB CATERING DUMFRIES GBR`, `MARCHBANK BAKERS THORNHILL DG3 GBR`, `La Dolce Vita Dumfries GBR`, `Enish Glasgow Glasgow GBR`, `PPOINT_*McEwans Premie Dumfries GBR`, `NYX*DCVendingLtd` (as a `match_regex` to cover location-suffix variants), and `DC7 VENDING LIMITED AYRSHIRE GBR`, each mapped to `Eating Out`.
4. WHEN the example rules file is shipped THEN it SHALL include rules for phone/internet bills: `Lebara Mobile Limited London GBR` and `THREE MOTO GLASGOW GBR`, both mapped to `Bill - Phone & Internet`.
5. WHEN the example rules file is shipped THEN it SHALL include rules for known Sundry counterparties: `RCGP (Direct Debit)`, `GENERAL MEDICAL C (Direct Debit)`, `MEDCOUNCIL/CONSEILMED OTTAWA CAN` (as `match_regex` to tolerate the variable CAD conversion suffix), `RP*My Local Surgery Lt Romsey GBR`, `DUMFRIES HOSPITALS LEA DUMFRIES GBR`, `SAVERS HEALTH & BEAUTY DUMFRIES GBR`, `SUPERDRUG STORES PLC DUMFRIES GBR`, `HOLLAND AND BARRETT DUMFRIES GBR`, `BOOTS 2265 LUTON GBR`, and `Ali Mohammad Almasri (Bank Transfer)`, all mapped to `Sundry`.
6. WHEN the example rules file is shipped THEN it SHALL include rules for known Holidays & Travel counterparties: `HOUSTONS MINI COACHES LOCKERBIE GBR`, `UBER *TRIP London GBR`, `UBER * PENDING London GBR`, `HARTHILL NORTH SF CONN SHOTTS LANARK GBR`, `ACA KIRKCALDY MG KIRKCALDY GBR`, `VF SERVICES (UK) LTD LONDON GBR`, and `SumUp *McLeans taxi Dumfries GBR`, all mapped to `Holidays & Travel`.
7. WHEN the example rules file is shipped THEN it SHALL include rules for Car & Gas: `Adamira Driving School (Faster Payments)`, `DVSA SWANSEA GBR`, and `HASTINGS DIRECT BEXHILL ON SE GBR`, all mapped to `Car & Gas`.
8. WHEN the example rules file is shipped THEN it SHALL include rules for Gifts/Entertainment/Misc: `AMAZON.CO.UK LONDON GBR`, `T K MAXX DUMFRIES GBR`, `BLUE INC - DUMFRIES DUMFRIES GBR`, and `Vinted Vilnius GBR`, mapped to `Gifts/Entertainment/Misc`.
9. WHEN the example rules file is shipped THEN it SHALL include a rule mapping `Somtochukwu Nchekwubechukwu Obiana (Faster Payments)` with `direction: in` to `Unexpected / Refund` and a separate rule for the same counterparty with `direction: out` to `Charity / Donations`.
10. WHEN the example rules file is shipped THEN it SHALL include a rule mapping `WWW.HL.CO.UK BRISTOL GBR` with `direction: in` to `Stocks & Shares` (Asset Liquidation) and a separate rule for the same counterparty with `direction: out` to `Stocks & Shares ISA` (Assets).
11. WHEN the example rules file is shipped THEN it SHALL include rules for known Assets outflows: `Transfer to Pot` mapped to `Active Savings`.
12. WHEN the example rules file is shipped THEN it SHALL NOT include a blanket catch-all for `Omasirichi Okwu-Boms (Faster Payments)` with `direction: out` — these are self-transfers back to the main account that require case-by-case rules based on context; a generic rule risks misclassifying genuine outflows.

---

### Requirement 14: Non-Functional — Code Quality

**User Story:** As a developer maintaining the tool, I want enforced code quality standards, so that the codebase remains readable and type-safe over time.

#### Acceptance Criteria

1. WHEN code is committed THEN the system SHALL pass `ruff` linting and formatting checks with no suppressed warnings.
2. WHEN code is committed THEN the system SHALL pass `mypy --strict` type checking with no ignored errors.
3. WHEN tests are run THEN the system SHALL achieve at least 90% line coverage on the non-CLI modules (`schema`, `errors`, `parser`, `rules`, `classifier`, `splitter`, `reconciler`, `writer`) using `pytest`.
4. WHEN the project is set up THEN all `monzo_expense` dependencies SHALL be declared in the existing `pyproject.toml` alongside `lloyds_expense`, managed with `uv`.
5. WHEN test fixtures are required THEN synthetic Monzo PDFs SHALL be generated by a script in `tests/monzo/fixtures/` using `reportlab`. The multi-month fixture SHALL cover at least two calendar months to exercise `splitter.py` and the multi-CSV writer path. Fixtures are checked in; tests SHALL NOT reach the network.
