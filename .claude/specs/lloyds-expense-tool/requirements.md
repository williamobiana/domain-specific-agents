# Requirements Document

## Introduction

The Lloyds Expense Tool is a command-line application that transforms a Lloyds Bank UK Classic personal account statement (PDF) into a categorised monthly cash-flow CSV. The tool parses raw transaction data, classifies each transaction against a user-maintained YAML rules file, and emits a CSV that conforms to a fixed personal-finance schema — complete with named sections, line-item subtotals, and grand totals. The tool targets a single end user running it locally against their own statements, removing the need for manual transaction classification.

---

## Requirements

### Requirement 1: PDF Input Acceptance

**User Story:** As an account holder, I want to provide a single Lloyds Classic statement PDF to the tool, so that it can process my transactions without requiring any format conversion on my part.

#### Acceptance Criteria

1. WHEN the user supplies a PDF file path as a positional argument THEN the system SHALL accept exactly one PDF file per invocation.
2. WHEN the supplied file does not exist or is not readable THEN the system SHALL exit with code 4 and display a descriptive error message via `rich`.
3. WHEN the supplied file is not a valid Lloyds Classic personal-account PDF THEN the system SHALL exit with code 3 and report a parse error.
4. WHEN more than one positional PDF argument is provided THEN the system SHALL exit with code 4 and inform the user that only one statement is accepted per run.
5. IF the PDF is password-protected or corrupt THEN the system SHALL exit with code 3 and display the underlying parse failure reason.

---

### Requirement 2: Transaction Parsing

**User Story:** As an account holder, I want every transaction in the statement to be extracted with full fidelity, so that no data is lost or silently misread before classification.

#### Acceptance Criteria

1. WHEN a valid Lloyds Classic PDF is processed THEN the system SHALL extract each transaction's date, description, type code, amount, direction, and running balance, returning them as a list of frozen Transaction dataclasses on a Statement object.
2. WHEN a transaction row in the PDF contains a money-in value THEN the system SHALL record amount as a positive `Decimal` and direction as "in".
3. WHEN a transaction row in the PDF contains a money-out value THEN the system SHALL record amount as a positive `Decimal` and direction as "out". Outflows SHALL NOT be stored as negative numbers; direction is the single source of truth for inflow versus outflow.
4. WHEN monetary values are parsed THEN the system SHALL use `decimal.Decimal` for all amounts, constructed via Decimal(str(...)) from the cleaned string form. Floats SHALL NOT appear anywhere in the parsing pipeline.
5. WHEN amounts in the PDF contain thousand-separator commas (e.g., "1,000.00") THEN the system SHALL strip them before constructing the Decimal.
6. WHEN transaction dates appear in the PDF with a two-digit year (e.g., "01 Apr 26") THEN the system SHALL expand the year using the four-digit year present in the statement period extracted under R2.6. Two-digit-year expansion SHALL NOT use the current system date.
7. WHEN the transaction table spans multiple pages THEN the system SHALL concatenate rows into a single list preserving document order (top-to-bottom within a page, then page-by-page).
8. WHEN non-transaction tabular content appears in the PDF (such as the transaction-type-code legend on the final page) THEN the system SHALL ignore it and not emit Transaction records from it.
9. WHEN descriptions are truncated by the bank in the PDF (visible as cut-off names, e.g., "SOMTOCHUKWU NCHEKW") THEN the system SHALL store the truncated form verbatim. Rules in the YAML file are expected to match against the truncated string as it appears in the statement, not the original full name.
10. WHEN transactions are returned THEN the system SHALL preserve their document order (the order they appear in the PDF). The parser SHALL NOT reorder by date, amount, or any other field.
11. IF the transaction table cannot be located in the PDF THEN the system SHALL exit with code 3 and report the specific parse failure, including the page number where parsing failed if determinable.
12. IF the PDF parses but produces zero Transaction records THEN the parser SHALL still return a valid Statement object with an empty transactions list; the zero-transaction handling defined in R8 then applies.

---

### Requirement 3: Rules File Loading and Validation

**User Story:** As an account holder, I want to maintain a YAML rules file that maps transaction descriptions to budget categories, so that I can control classification without modifying the tool's source code.

#### Acceptance Criteria

1. WHEN the `--rules` option is supplied THEN the system SHALL load the YAML rules file from the specified path using `PyYAML` (`yaml.safe_load`). Comment preservation is not required because the tool never writes to the rules file — the user is the sole editor.
2. WHEN `--rules` is not supplied THEN the system SHALL look for a rules file at the default location `~/.config/lloyds-expense/rules.yaml`; if neither is present, the system SHALL exit with code 4 and display a usage message.
3. WHEN the rules file is absent or unreadable THEN the system SHALL exit with code 4 and display a descriptive error message.
4. WHEN the rules file is loaded THEN the system SHALL validate that every rule has exactly one matcher: either `match` (a non-empty exact string) or `match_regex` (a compilable regular expression pattern). In the internal `Rule` representation, this SHALL be encoded as a tagged union (`ExactMatch | RegexMatch`), not as two nullable fields.
5. WHEN the rules file contains two or more rules whose matcher, `type`, and `direction` fields are all identical (treating `None` and absent as equivalent, and comparing regex matchers by source string) THEN the system SHALL exit with code 4, list the duplicate rules by line number, and refuse to proceed.
6. WHEN a rule specifies a `type` field THEN the system SHALL validate it against the closed set of known Lloyds type codes (FPO, FPI, DD, DEB, BGC, BP, CHG, CHQ, COR, CPT, DEP, FEE, MPI, MPO, PAY, SO, TFR). Unknown type codes SHALL cause exit with code 4.
7. WHEN a rule's `match_regex` value cannot be compiled as a Python regular expression THEN the system SHALL exit with code 4 and display the regex error position.
8. WHEN the YAML file's top-level structure is not a mapping containing a `rules` key whose value is a list THEN the system SHALL exit with code 4 with a descriptive error.
9. WHEN rules are returned from the loader THEN the list SHALL preserve the order of rules in the source YAML file, and each `Rule` SHALL carry the line number where it was defined for use in error messages.
10. IF the rules file contains malformed YAML THEN the system SHALL exit with code 4 and display the YAML parse error location.

---

### Requirement 4: Transaction Classification

**User Story:** As an account holder, I want the tool to classify my transactions automatically using my rules file, so that each transaction is assigned to the correct budget category without manual intervention.

#### Acceptance Criteria

1. WHEN comparing transaction descriptions to rules THEN the system SHALL apply the following normalisation to both sides before comparison: trim leading and trailing whitespace, collapse internal whitespace runs to a single space, and treat all variants of the hyphen-minus character as equivalent.
2. WHEN classifying each transaction THEN the system SHALL first attempt a normalised exact match against all rules that use the `match` field.
3. WHEN no exact match is found THEN the system SHALL attempt a regex match against all rules that use the `match_regex` field, in the order they appear in the rules file. Regex matching is applied against the normalised description.
4. WHEN a rule specifies a `type` filter THEN the system SHALL only assign the rule if the transaction's type code matches.
5. WHEN a rule specifies a `direction` filter THEN the system SHALL only assign the rule if the transaction's money direction matches.
6. WHEN a transaction matches exactly one rule THEN the system SHALL assign it to that rule's category.
7. WHEN one or more transactions match no rule THEN the system SHALL collect all unmatched transactions and handle them according to Requirement 5.

> **Note on duplicate exact matches:** R3.6 makes duplicate exact rules a load-time error, so classification never has to choose between two identical exact matches. For regex rules, first-in-file-order wins; the user is responsible for ordering them.

---

### Requirement 5: Unmatched Transaction Handling

**User Story:** As an account holder, I want to be clearly informed about any transactions that could not be classified, so that I can extend my rules file and re-run the tool.

#### Acceptance Criteria

1. WHEN at least one transaction is unmatched THEN the system SHALL exit with code 1 without producing any output CSV. This behaviour is non-bypassable; there is no flag to suppress it.
2. WHEN at least one transaction is unmatched THEN the system SHALL list every unmatched transaction (date, description, type, amount, direction) to stderr via `rich` in a tabular format.
3. WHEN `--report-unmatched <path>` is supplied AND at least one transaction is unmatched THEN the system SHALL additionally write a plain-text report of unmatched transactions to the specified path before exiting with code 1.
4. WHEN all transactions are matched THEN the system SHALL NOT emit any unmatched-transaction warnings, and `--report-unmatched` (if supplied) SHALL have no effect.

---

### Requirement 6: Reconciliation

**User Story:** As an account holder, I want the tool to verify that its computed totals match the statement's printed totals, so that I can trust the output is arithmetically correct to the penny.

#### Acceptance Criteria

1. WHEN all transactions have been classified THEN the system SHALL sum all classified money-in amounts and compare the result to the statement's reported Money In total.
2. WHEN all transactions have been classified THEN the system SHALL sum all classified money-out amounts and compare the result to the statement's reported Money Out total.
3. WHEN all transactions have been parsed THEN the system SHALL verify that `opening_balance + money_in_total - money_out_total == closing_balance` using `Decimal` equality; failure indicates a parser fault and SHALL exit with code 3.
4. WHEN either computed inflow or outflow total differs from the statement total by any amount THEN the system SHALL exit with code 2 and display the discrepancy (expected, actual, and difference) via `rich`.
5. WHEN reconciliation passes THEN the system SHALL proceed to CSV output without printing any reconciliation message.
6. WHERE reconciliation is concerned THEN no CLI flag SHALL bypass it.

---

### Requirement 7: CSV Output

**User Story:** As an account holder, I want the tool to produce a CSV that exactly matches my fixed budget schema, so that I can import it into my spreadsheet without any restructuring.

#### Acceptance Criteria

1. WHEN all transactions are classified and reconciliation passes THEN the system SHALL write a CSV to the path specified by `--out`.
2. WHEN the CSV is written THEN the system SHALL prepend a metadata header recording the statement period (start date and end date), before the schema rows.
3. WHEN the CSV is written THEN the system SHALL emit schema rows in the following fixed order, with no row omitted even if its value is zero:
   - Section header: Regular Inflows
   - Line items: Salary
   - Subtotal: Regular Inflows subtotal
   - Section header: Irregular Inflows
   - Line items: Unexpected / Refund, Loan
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
4. WHEN a category has no transactions in the statement THEN the system SHALL still emit its row with a value of `0.00`.
5. WHEN subtotals are computed THEN the system SHALL sum the `Decimal` values of all line items within the section, quantized to two decimal places.
6. WHEN grand totals are computed THEN the system SHALL sum the `Decimal` values of all section subtotals within the respective inflow or outflow group.
7. WHEN the `--out` file already exists THEN the system SHALL overwrite it silently. The output CSV is a pure function of the PDF and the rules file and is therefore regenerable; users who want versioned outputs SHALL use period-stamped filenames (e.g., `budget-2026-04.csv`) or store outputs under version control.
8. WHEN the CSV is written THEN the system SHALL use the Python `csv` stdlib module with `csv.QUOTE_MINIMAL`, UTF-8 encoding, and `\n` line endings.

---

### Requirement 8: Zero-Transaction Statements

**User Story:** As an account holder, I want the tool to behave predictably even on a statement with no transactions, so that I get a usable CSV rather than a crash or a silent skip.

#### Acceptance Criteria

1. WHEN a parsed statement contains zero transactions AND the statement's reported Money In and Money Out totals are both `0.00` THEN the system SHALL emit a CSV with every schema row present, every value set to `0.00`, and exit with code 0.
2. WHEN a parsed statement contains zero transactions BUT the statement's reported Money In or Money Out total is non-zero THEN the system SHALL exit with code 3 (parser fault — totals disagree with extracted rows).

---

### Requirement 9: Determinism

**User Story:** As an account holder, I want every run with the same inputs to produce an identical output file, so that I can reliably diff outputs and trust that results are reproducible.

#### Acceptance Criteria

1. WHEN the tool is run twice with identical PDF, rules file, and CLI options THEN the system SHALL produce byte-identical CSV output on both runs.
2. WHEN transactions share the same date and category THEN the system SHALL order them in document order to ensure deterministic output.
3. WHEN any source of non-determinism (e.g., dict iteration, timestamps, hostnames) is present in the pipeline THEN the system SHALL eliminate it so that the output is stable across Python interpreter restarts and across machines.

---

### Requirement 10: CLI Interface

**User Story:** As an account holder, I want a simple command-line interface with clear options, so that I can run the tool with minimal typing and understand available options from the help text.

#### Acceptance Criteria

1. WHEN the tool is invoked THEN the system SHALL accept the following signature: `lloyds-expense <statement.pdf> [--rules <rules.yaml>] --out <budget.csv> [--report-unmatched <path>]`.
2. WHEN `--rules` is not supplied THEN the system SHALL fall back to `~/.config/lloyds-expense/rules.yaml` as specified in R3.2.
3. WHEN `--out` is not supplied THEN the system SHALL exit with code 4 and display a usage message.
4. WHEN `--help` is requested THEN the system SHALL display all options, defaults, and exit codes via `typer`.
5. WHEN the tool exits THEN the system SHALL use only the following exit codes: 0 (success), 1 (unmatched transactions), 2 (reconciliation mismatch), 3 (parse error), 4 (bad input).
6. WHERE console output is produced THEN the system SHALL use `rich` for all stderr messages, including errors and warnings, and reserve stdout for any explicit plain-text reports.

---

### Requirement 11: Module Boundaries

**User Story:** As a developer maintaining the tool, I want clearly separated modules with single responsibilities, so that each component can be tested and modified in isolation.

#### Acceptance Criteria

1. WHEN the codebase is structured THEN the system SHALL contain the following modules under `src/statement_to_csv/`: `schema.py`, `errors.py`, `parser.py`, `rules.py`, `classifier.py`, `reconciler.py`, `writer.py`, and `cli.py`.
2. WHERE `cli.py` is concerned THEN it SHALL be the only module that accesses `sys.argv`, writes to stdout/stderr directly, or calls `sys.exit`.
3. WHERE `schema.py` is concerned THEN it SHALL define a closed enumeration of all valid categories and the canonical CSV row order.
4. WHERE `errors.py` is concerned THEN it SHALL define a typed exception hierarchy used across all other modules.
5. WHERE `parser.py` is concerned THEN it SHALL accept a file path and return a typed `Statement` dataclass containing transactions, statement period, opening/closing balances, and Money In / Money Out totals.
6. WHERE `rules.py` is concerned THEN it SHALL accept a file path and return a validated list of `Rule` objects, raising typed errors for invalid content.
7. WHERE `classifier.py` is concerned THEN it SHALL accept transactions and rules and return a `ClassificationResult` with no side effects.
8. WHERE `reconciler.py` is concerned THEN it SHALL accept a `ClassificationResult` and statement totals and return a pass/fail result with discrepancy details.
9. WHERE `writer.py` is concerned THEN it SHALL accept a `ClassificationResult`, statement metadata, and an output path, and write the CSV with no side effects beyond file I/O.

---

### Requirement 12: Error Reporting Quality

**User Story:** As an account holder, I want error messages to be clear and actionable, so that I know exactly what went wrong and how to fix it.

#### Acceptance Criteria

1. WHEN any error occurs THEN the system SHALL display a human-readable message that identifies the problem, its location (file, line, or row where applicable), and the expected correct form.
2. WHEN unmatched transactions are reported THEN the system SHALL display each transaction's date, description, type code, direction, and amount in a tabular format via `rich`.
3. WHEN a reconciliation mismatch is reported THEN the system SHALL display the statement total, the computed total, and the difference in a clear format.
4. WHEN a rules validation error is reported THEN the system SHALL list each invalid rule by its position in the YAML file and the nature of the violation.
5. WHEN the tool exits with a non-zero code THEN the system SHALL have written all error output to stderr; stdout SHALL remain empty unless `--report-unmatched` produced a file (in which case stdout is still untouched — the report is a file, not piped output).

---

### Requirement 13: Known Classification Rules (Seed Data)

**User Story:** As an account holder, I want an example rules file to ship with the tool covering known mappings for my account's recurring transactions, so that common transactions are classified correctly from the first run.

#### Acceptance Criteria

1. WHEN the example rules file (`examples/rules.example.yaml`) is shipped THEN it SHALL include a rule mapping the description `OMASIRICHI OKWU BO` with type `FPO` and direction `out` to the category `Food Supplies`. The description normalisation defined in R4.1 ensures the hyphenated variant `OMASIRICHI OKWU-BO` matches the same rule.
2. WHEN the example rules file is shipped THEN it SHALL include a rule mapping the description `NATIONAL SERV M/W` with type `BGC` and direction `in` to the category `Salary`.
3. WHEN the example rules file is shipped THEN it SHALL include a rule mapping the description `HLAM REGULAR SAVIN` with type `DD` and direction `out` to the category `Active Savings`.
4. WHEN the example rules file is shipped THEN it SHALL include a rule mapping the description `Trading 212` with type `DEB` and direction `out` to the category `Stocks & Shares ISA`. The user can override this to `Dividend Portfolio` in their own rules file if appropriate.
5. WHEN the example rules file is shipped THEN it SHALL NOT include a generic personal-name regex rule for inbound FPIs. Such matches risk classifying salary, refunds, and one-off transfers identically. The user is expected to add specific rules per known counterparty.

---

### Requirement 14: Non-Functional — Code Quality

**User Story:** As a developer maintaining the tool, I want enforced code quality standards, so that the codebase remains readable and type-safe over time.

#### Acceptance Criteria

1. WHEN code is committed THEN the system SHALL pass `ruff` linting and formatting checks with no suppressed warnings.
2. WHEN code is committed THEN the system SHALL pass `mypy --strict` type checking with no ignored errors.
3. WHEN tests are run THEN the system SHALL achieve at least 90% line coverage on the non-CLI modules (`schema`, `errors`, `parser`, `rules`, `classifier`, `reconciler`, `writer`) using `pytest`.
4. WHEN the project is set up THEN the system SHALL be managed with `uv` and declare all dependencies in a `pyproject.toml`.

---

### Requirement 15: Non-Functional — Security and Privacy

**User Story:** As an account holder, I want to be confident that the tool does not transmit or persist my financial data, so that my banking information stays on my own machine.

#### Acceptance Criteria

1. WHEN the tool processes a PDF THEN the system SHALL not make any network requests.
2. WHEN the tool runs THEN the system SHALL not write any data to locations other than the file specified by `--out`, the file specified by `--report-unmatched` (if supplied), and any stderr/stdout console output.
3. WHEN the tool exits THEN the system SHALL not leave any temporary files on disk.

