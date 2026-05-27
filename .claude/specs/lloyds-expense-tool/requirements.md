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

1. WHEN a valid Lloyds Classic PDF is processed THEN the system SHALL extract each transaction's date, description, type code, money-in amount, money-out amount, and running balance.
2. WHEN a transaction row in the PDF contains a money-in value THEN the system SHALL record a positive `Decimal` amount in the money-in field and leave money-out empty.
3. WHEN a transaction row in the PDF contains a money-out value THEN the system SHALL record a positive `Decimal` amount in the money-out field and leave money-in empty.
4. WHEN monetary values are parsed THEN the system SHALL use `decimal.Decimal` for all arithmetic to avoid floating-point rounding errors.
5. WHERE the transaction description spans multiple lines in the PDF THEN the system SHALL concatenate them into a single description string, preserving the original text.
6. WHEN parsing completes THEN the system SHALL also extract the statement's reported Money In total and Money Out total for use in reconciliation.
7. IF the transaction table cannot be located in the PDF THEN the system SHALL exit with code 3 and report the specific parse failure.

---

### Requirement 3: Rules File Loading and Validation

**User Story:** As an account holder, I want to maintain a YAML rules file that maps transaction descriptions to budget categories, so that I can control classification without modifying the tool's source code.

#### Acceptance Criteria

1. WHEN the `--rules` option is supplied THEN the system SHALL load the YAML rules file from the specified path using `ruamel.yaml`, preserving comments.
2. WHEN the rules file is absent or unreadable THEN the system SHALL exit with code 4 and display a descriptive error message.
3. WHEN the rules file is loaded THEN the system SHALL validate that every rule contains exactly one of `match` (exact string) or `match_regex` (regular expression pattern).
4. WHEN the rules file is loaded THEN the system SHALL validate that every rule's `category` value belongs to the closed schema enumeration defined in `schema.py`.
5. WHEN a rule contains an invalid `category` value THEN the system SHALL exit with code 4, list every offending rule, and refuse to proceed.
6. WHEN a rule specifies a `type` field THEN the system SHALL treat it as an optional Lloyds transaction-type code filter applied in addition to the description match.
7. WHEN a rule specifies a `direction` field THEN the system SHALL accept only `in` or `out`; any other value SHALL cause exit with code 4.
8. IF the rules file contains malformed YAML THEN the system SHALL exit with code 4 and display the YAML parse error location.

---

### Requirement 4: Two-Pass Transaction Classification

**User Story:** As an account holder, I want the tool to classify my transactions automatically using my rules file, so that each transaction is assigned to the correct budget category without manual intervention.

#### Acceptance Criteria

1. WHEN classifying each transaction THEN the system SHALL first attempt an exact case-sensitive match against all rules that use the `match` field.
2. WHEN no exact match is found THEN the system SHALL attempt a regex match against all rules that use the `match_regex` field, in the order they appear in the rules file.
3. WHEN a rule specifies both a description match and a `type` filter THEN the system SHALL only assign the rule if both the description and the transaction type match.
4. WHEN a rule specifies a `direction` filter THEN the system SHALL only assign the rule if the transaction's money direction matches.
5. WHEN a transaction matches exactly one rule THEN the system SHALL assign it to that rule's category.
6. WHEN a transaction matches more than one exact rule THEN the system SHALL assign it to the first matching rule in file order and SHALL NOT raise an error.
7. WHEN one or more transactions match no rule THEN the system SHALL collect all unmatched transactions and handle them according to the `--strict` setting.

---

### Requirement 5: Unmatched Transaction Handling

**User Story:** As an account holder, I want to be clearly informed about any transactions that could not be classified, so that I can extend my rules file and re-run the tool.

#### Acceptance Criteria

1. WHEN `--strict` is active (default) and at least one transaction is unmatched THEN the system SHALL exit with code 1 without producing any output CSV.
2. WHEN `--strict` is active and at least one transaction is unmatched THEN the system SHALL list every unmatched transaction (date, description, type, amount) to stderr via `rich`.
3. WHEN `--report-unmatched` is supplied THEN the system SHALL write a separate plain-text report of unmatched transactions to stdout regardless of `--strict` status.
4. WHEN all transactions are matched THEN the system SHALL NOT emit any unmatched-transaction warnings.
5. WHEN `--force` is supplied together with `--strict` THEN the system SHALL override strict mode, produce the output CSV, and still report unmatched transactions to stderr.

---

### Requirement 6: Reconciliation

**User Story:** As an account holder, I want the tool to verify that its computed totals match the statement's printed totals, so that I can trust the output is arithmetically correct to the penny.

#### Acceptance Criteria

1. WHEN all transactions have been classified THEN the system SHALL sum all classified money-in amounts and compare the result to the statement's reported Money In total.
2. WHEN all transactions have been classified THEN the system SHALL sum all classified money-out amounts and compare the result to the statement's reported Money Out total.
3. WHEN either computed total differs from the statement total by any amount THEN the system SHALL exit with code 2 and display the discrepancy (expected vs actual, and the difference) via `rich`.
4. WHEN reconciliation passes THEN the system SHALL proceed to CSV output without printing any reconciliation message.
5. IF `--force` is supplied and reconciliation fails THEN the system SHALL still exit with code 2; `--force` SHALL NOT bypass reconciliation errors.

---

### Requirement 7: CSV Output

**User Story:** As an account holder, I want the tool to produce a CSV that exactly matches my fixed budget schema, so that I can import it into my spreadsheet without any restructuring.

#### Acceptance Criteria

1. WHEN all transactions are classified and reconciliation passes THEN the system SHALL write a CSV to the path specified by `--out`.
2. WHEN the CSV is written THEN the system SHALL emit rows in the following fixed order, with no row omitted even if its value is zero:
   - Section header: Regular Inflows
   - Line items: Salary
   - Subtotal: Regular Inflows subtotal
   - Section header: Irregular Inflows
   - Line items: Carry Over, Unexpected / Refund, Loan
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
3. WHEN a category has no transactions in the statement THEN the system SHALL still emit its row with a value of `0.00`.
4. WHEN subtotals are computed THEN the system SHALL sum the `Decimal` values of all line items within the section.
5. WHEN grand totals are computed THEN the system SHALL sum the `Decimal` values of all section subtotals within the respective inflow or outflow group.
6. WHEN the `--out` file already exists THEN the system SHALL refuse to overwrite it unless `--force` is supplied.
7. WHEN `--force` is supplied and the output file already exists THEN the system SHALL overwrite the existing file silently.
8. WHEN the CSV is written THEN the system SHALL use the Python `csv` stdlib module and produce a file that is valid, unquoted where unnecessary, and UTF-8 encoded.

---

### Requirement 8: Determinism

**User Story:** As an account holder, I want every run with the same inputs to produce an identical output file, so that I can reliably diff outputs and trust that results are reproducible.

#### Acceptance Criteria

1. WHEN the tool is run twice with identical PDF, rules file, and CLI options THEN the system SHALL produce byte-identical CSV output on both runs.
2. WHEN transactions share the same date and category THEN the system SHALL order them consistently (e.g., in document order) to ensure deterministic output.
3. WHEN any source of non-determinism (e.g., dict iteration, timestamps) is present in the pipeline THEN the system SHALL eliminate it so that the output is stable across Python interpreter restarts.

---

### Requirement 9: CLI Interface

**User Story:** As an account holder, I want a simple command-line interface with clear options, so that I can run the tool with minimal typing and understand available options from the help text.

#### Acceptance Criteria

1. WHEN the tool is invoked THEN the system SHALL accept the following signature: `statement-to-csv <statement.pdf> --rules <rules.yaml> --out <budget.csv>`.
2. WHEN `--rules` is not supplied THEN the system SHALL exit with code 4 and display a usage message.
3. WHEN `--out` is not supplied THEN the system SHALL exit with code 4 and display a usage message.
4. WHEN `--strict` is not explicitly set THEN the system SHALL default to strict mode enabled.
5. WHEN `--help` is requested THEN the system SHALL display all options and exit codes via `typer`.
6. WHEN the tool exits THEN the system SHALL use only the following exit codes: 0 (success), 1 (unmatched transactions), 2 (reconciliation mismatch), 3 (parse error), 4 (bad input).
7. WHERE console output is produced THEN the system SHALL use `rich` for all stderr messages, including errors and warnings, and reserve stdout for any plain-text reports.

---

### Requirement 10: Module Boundaries

**User Story:** As a developer maintaining the tool, I want clearly separated modules with single responsibilities, so that each component can be tested and modified in isolation.

#### Acceptance Criteria

1. WHEN the codebase is structured THEN the system SHALL contain the following modules under `src/statement_to_csv/`: `schema.py`, `errors.py`, `parser.py`, `rules.py`, `classifier.py`, `reconciler.py`, `writer.py`, and `cli.py`.
2. WHERE `cli.py` is concerned THEN it SHALL be the only module that accesses `sys.argv`, writes to stdout/stderr directly, or calls `sys.exit`.
3. WHERE `schema.py` is concerned THEN it SHALL define a closed enumeration of all valid categories and the canonical CSV row order.
4. WHERE `errors.py` is concerned THEN it SHALL define a typed exception hierarchy used across all other modules.
5. WHERE `parser.py` is concerned THEN it SHALL accept a file path and return a list of typed `Transaction` dataclasses and the statement-level Money In / Money Out totals.
6. WHERE `rules.py` is concerned THEN it SHALL accept a file path and return a validated list of `Rule` objects, raising typed errors for invalid content.
7. WHERE `classifier.py` is concerned THEN it SHALL accept transactions and rules and return a `ClassificationResult` with no side effects.
8. WHERE `reconciler.py` is concerned THEN it SHALL accept a `ClassificationResult` and statement totals and return a pass/fail result with discrepancy details.
9. WHERE `writer.py` is concerned THEN it SHALL accept a `ClassificationResult` and an output path and write the CSV with no side effects beyond file I/O.

---

### Requirement 11: Error Reporting Quality

**User Story:** As an account holder, I want error messages to be clear and actionable, so that I know exactly what went wrong and how to fix it.

#### Acceptance Criteria

1. WHEN any error occurs THEN the system SHALL display a human-readable message that identifies the problem, its location (file, line, or row where applicable), and the expected correct form.
2. WHEN unmatched transactions are reported THEN the system SHALL display each transaction's date, description, type code, and amount in a tabular format via `rich`.
3. WHEN a reconciliation mismatch is reported THEN the system SHALL display the statement total, the computed total, and the difference in a clear format.
4. WHEN a rules validation error is reported THEN the system SHALL list each invalid rule by its position in the YAML file and the nature of the violation.
5. WHEN the tool exits with a non-zero code THEN the system SHALL have written all error output to stderr and nothing to stdout (except any explicit plain-text reports triggered by `--report-unmatched`).

---

### Requirement 12: Known Classification Rules (Seed Data)

**User Story:** As an account holder, I want the rules file to pre-populate with known mappings for my account's recurring transactions, so that common transactions are classified correctly from the first run.

#### Acceptance Criteria

1. WHEN the rules file is initialised THEN the system SHALL support a rule mapping descriptions matching `OMASIRICHI OKWU BO` or `OMASIRICHI OKWU-BO` with type `FPO` and direction `out` to the category `Food Supplies`.
2. WHEN the rules file is initialised THEN the system SHALL support a rule mapping the description `NATIONAL SERV M/W` with type `BGC` and direction `in` to the category `Salary`.
3. WHEN the rules file is initialised THEN the system SHALL support a rule mapping the description `HLAM REGULAR SAVIN` with type `DD` and direction `out` to the category `Active Savings`.
4. WHEN the rules file is initialised THEN the system SHALL support a rule mapping descriptions matching `Trading 212` with type `DEB` and direction `out` to one of `Stocks & Shares ISA` or `Dividend Portfolio`.
5. WHEN the rules file is initialised THEN the system SHALL support a regex rule mapping inbound FPI transactions whose description matches a personal-name pattern to the category `Carry Over` by default.

---

### Requirement 13: Non-Functional — Performance

**User Story:** As an account holder, I want the tool to complete quickly on a typical month's statement, so that I am not waiting an unreasonable amount of time for results.

#### Acceptance Criteria

1. WHEN processing a Lloyds Classic statement containing up to 200 transactions THEN the system SHALL complete within 10 seconds on a modern laptop with an SSD.
2. WHILE the tool is running THEN the system SHALL not hold more than 100 MB of memory beyond the PDF parsing library's own requirements.

---

### Requirement 14: Non-Functional — Code Quality

**User Story:** As a developer maintaining the tool, I want enforced code quality standards, so that the codebase remains readable and type-safe over time.

#### Acceptance Criteria

1. WHEN code is committed THEN the system SHALL pass `ruff` linting and formatting checks with no suppressed warnings.
2. WHEN code is committed THEN the system SHALL pass `mypy --strict` type checking with no ignored errors.
3. WHEN tests are run THEN the system SHALL achieve 100% coverage of the non-CLI modules (`schema`, `errors`, `parser`, `rules`, `classifier`, `reconciler`, `writer`) using `pytest`.
4. WHEN the project is set up THEN the system SHALL be managed with `uv` and declare all dependencies in a `pyproject.toml`.

---

### Requirement 15: Non-Functional — Security and Privacy

**User Story:** As an account holder, I want to be confident that the tool does not transmit or persist my financial data, so that my banking information stays on my own machine.

#### Acceptance Criteria

1. WHEN the tool processes a PDF THEN the system SHALL not make any network requests.
2. WHEN the tool runs THEN the system SHALL not write any data to locations other than the file specified by `--out` and any stderr/stdout console output.
3. WHEN the tool exits THEN the system SHALL not retain any in-memory state or write any temporary files that persist after the process terminates.
