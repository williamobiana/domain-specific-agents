# Requirements Document

## Introduction

The bank-statement-parser is a CLI tool written as a single Python script that transforms a text-based bank statement PDF into a structured CSV expense report. It extracts transactions from the PDF, classifies each transaction using user-defined rules supplied in a YAML file, aggregates matched amounts into a fixed 17-category hierarchy, and writes the result as a CSV in a strict 30-row sequence. Unmatched transactions are logged to a separate file rather than silently discarded. The tool is designed to run non-interactively, accepting only two required inputs (a PDF file and a rules file), with all other behaviour controlled by optional arguments with sensible defaults.

---

## Requirements

### Requirement 1 — CLI Interface and Argument Parsing

**User Story:** As a user, I want to invoke the tool from the command line with a PDF and a rules file so that I can generate an expense report without writing any code or using a GUI.

#### Acceptance Criteria

1. WHEN the user runs `expense-parser <input.pdf>` without any optional flags THEN the system SHALL accept the positional argument as the path to the PDF to process.
2. WHEN the user supplies `--rules` or `-r` followed by a file path THEN the system SHALL use that file as the rules source; otherwise the system SHALL default to `rules.yml` in the current working directory.
3. WHEN the user supplies `--output` or `-o` followed by a file path THEN the system SHALL write the CSV report to that path; otherwise the system SHALL default to `expense_report.csv`.
4. WHEN the user supplies `--unmapped-log` followed by a file path THEN the system SHALL write unmatched transactions to that path; otherwise the system SHALL default to `unmapped.log`.
5. WHEN the user supplies `--exclude-self-transfers` THEN the system SHALL honour the boolean value provided; IF the flag is omitted THEN the system SHALL default to `true` and exclude self-transfer transactions from processing.
6. WHEN the user supplies `--strict` THEN the system SHALL enable strict mode; IF the flag is omitted THEN the system SHALL default to `false` and run in non-strict mode.
7. WHEN the user provides an unrecognised argument THEN the system SHALL print a usage message to stderr and exit with a non-zero code.
8. WHERE argument parsing is implemented THEN the system SHALL use Python's `argparse` module exclusively and SHALL NOT use interactive prompts during processing.

---

### Requirement 2 — PDF Transaction Extraction

**User Story:** As a user, I want the tool to reliably extract every transaction row from my bank statement PDF so that no transaction is silently missed.

#### Acceptance Criteria

1. WHEN the tool opens a PDF file THEN the system SHALL use `pdfplumber` and call `page.extract_table()` on each page to retrieve tabular data.
2. WHEN transaction rows are extracted THEN the system SHALL parse the following fields for each row: date, description, transaction type, money-in amount, money-out amount, and running balance.
3. WHEN a transaction type is encountered THEN the system SHALL recognise the following types: `FPI` (Faster Payment In), `BGC` (Bank Giro Credit), `FPO` (Faster Payment Out), `DD` (Direct Debit), and `DEB` (Debit Card).
4. WHEN the PDF file cannot be opened or parsed THEN the system SHALL print the message `No transactions found in {pdf}. Is this a text-based PDF?` to stderr and exit with a non-zero code, without printing a stack trace.
5. WHEN no transaction rows are found after parsing all pages THEN the system SHALL print the message `No transactions found in {pdf}. Is this a text-based PDF?` to stderr and exit with a non-zero code.
6. WHEN `--exclude-self-transfers` is true THEN the system SHALL identify and exclude any transaction that represents a transfer between accounts belonging to the same holder before classification.
7. WHILE extracting transactions THEN the system SHALL process a PDF containing 50 transactions in under 3 seconds on a standard development machine.

---

### Requirement 3 — Rules File Loading and Validation

**User Story:** As a user, I want to define my own classification rules in a YAML file so that the tool maps transactions to categories according to my personal conventions.

#### Acceptance Criteria

1. WHEN the tool loads the rules file THEN the system SHALL use `yaml.safe_load()` exclusively and SHALL NOT use `yaml.load()` without a Loader.
2. WHEN the rules file path does not exist THEN the system SHALL print the message `Rules file not found: {path}` to stderr and exit with a non-zero code, without printing a stack trace.
3. WHEN the rules file is present but contains invalid YAML THEN the system SHALL print a descriptive error message to stderr and exit with a non-zero code.
4. WHEN a rule entry has `types: []` AND `keywords: []` THEN the system SHALL treat that rule as a catch-all default that maps unmatched transactions to the `Sundry` category.
5. WHEN multiple rules are defined THEN the system SHALL evaluate them in the order they appear in the file, and the first matching rule SHALL win; subsequent rules for the same transaction SHALL NOT be evaluated.

---

### Requirement 4 — Transaction Classification

**User Story:** As a user, I want each extracted transaction to be assigned to exactly one category so that totals are accurate and nothing is double-counted.

#### Acceptance Criteria

1. WHEN classifying a transaction THEN the system SHALL check whether any keyword in a rule's `keywords` list appears in the transaction's description using a case-insensitive substring match.
2. WHEN a keyword match is found THEN the system SHALL also verify that the transaction's type is present in the rule's `types` list before considering the rule a match.
3. WHEN a rule matches a transaction THEN the system SHALL assign the transaction to the category specified by that rule and SHALL stop evaluating further rules.
4. WHEN no rule matches a transaction AND a catch-all rule exists THEN the system SHALL assign the transaction to `Sundry`.
5. WHEN no rule matches a transaction AND no catch-all rule exists THEN the system SHALL write the transaction to the unmapped log file and SHALL NOT include it in any category total.
6. WHEN a transaction is classified THEN the system SHALL assign it to exactly one category and SHALL NOT count it in more than one category's total.

---

### Requirement 5 — Amount Aggregation and Category Hierarchy

**User Story:** As a user, I want transaction amounts summed into the fixed category hierarchy so that I can see both individual category totals and meaningful subtotals at a glance.

#### Acceptance Criteria

1. WHEN aggregating amounts THEN the system SHALL sum the relevant amount field (money-in for inflow categories, money-out for outflow categories) for all transactions assigned to each category.
2. WHEN a category has no transactions assigned to it THEN the system SHALL output `0` for that category's amount and SHALL NOT omit the row from the CSV.
3. WHEN computing subtotals THEN the system SHALL sum the leaf category amounts within each section as defined in the fixed hierarchy below:
   - `Total Regular Inflows` = Salary
   - `Total Irregular Inflows` = Unexpected/Refund + Loan
   - `Total Asset Liquidation` = Savings + Stocks & Shares (inflow)
   - `Total Regular Outflows` = Rent + Bill - Council Tax + Bill - Electricity & Gas + Bill - Phone & Internet + Food Supplies + Debt + Car & Gas
   - `Total Irregular Outflows` = Charity/Donations + Gifts/Entertainment & Misc + Sundry + Holidays & Travel + Education + Eating Out
   - `Total Asset Expenditure` = Active Savings + Lifetime ISA + Stocks & Shares ISA + Dividend Portfolio
4. WHEN computing grand totals THEN the system SHALL calculate:
   - `Total Income` = Total Regular Inflows + Total Irregular Inflows + Total Asset Liquidation
   - `Total Expenditure` = Total Regular Outflows + Total Irregular Outflows + Total Asset Expenditure

---

### Requirement 6 — CSV Output with Fixed Row Order

**User Story:** As a user, I want the CSV report to always follow the same row sequence so that I can use it as a drop-in input for a spreadsheet template without reformatting.

#### Acceptance Criteria

1. WHEN writing the CSV file THEN the system SHALL use Python's `csv` module and SHALL write rows in the following fixed sequence, with no deviations:
   1. Salary
   2. Total Regular Inflows
   3. Unexpected/Refund
   4. Loan
   5. Total Irregular Inflows
   6. Savings
   7. Stocks & Shares
   8. Total Asset Liquidation
   9. Total Income
   10. Rent
   11. Bill - Council Tax
   12. Bill - Electricity & Gas
   13. Bill - Phone & Internet
   14. Food Supplies
   15. Debt
   16. Car & Gas
   17. Total Regular Outflows
   18. Charity/Donations
   19. Gifts/Entertainment & Misc
   20. Sundry
   21. Holidays & Travel
   22. Education
   23. Eating Out
   24. Total Irregular Outflows
   25. Active Savings
   26. Lifetime ISA
   27. Stocks & Shares ISA
   28. Dividend Portfolio
   29. Total Asset Expenditure
   30. Total Expenditure
2. WHEN a category has no transactions THEN the system SHALL still write its row with a value of `0`; the row SHALL NOT be omitted.
3. WHEN the output file path already exists THEN the system SHALL overwrite it without prompting.
4. IF the output directory does not exist THEN the system SHALL create it before writing the file.
5. WHERE the CSV is written THEN each row SHALL contain at minimum the category name and its calculated amount.

---

### Requirement 7 — Unmapped Transaction Logging

**User Story:** As a user, I want every unmatched transaction recorded in a log file so that I can review and add new rules without losing visibility of uncategorised spending.

#### Acceptance Criteria

1. WHEN a transaction is not matched by any rule THEN the system SHALL append a record of that transaction to the unmapped log file.
2. WHEN writing to the unmapped log THEN the system SHALL include at minimum the transaction date, description, type, and amount.
3. WHEN no transactions are unmatched THEN the system SHALL write an empty unmapped log file or omit the file entirely, but SHALL NOT raise an error.
4. WHEN `--strict` mode is enabled AND one or more transactions are unmatched THEN the system SHALL exit with a non-zero exit code after processing completes.
5. WHEN `--strict` mode is enabled AND transactions are unmatched THEN the system SHALL print to stderr the count of unmatched transactions before exiting.
6. WHEN `--strict` mode is disabled AND transactions are unmatched THEN the system SHALL complete normally and write unmatched transactions to the log without exiting with an error.

---

### Requirement 8 — Progress Summary Output

**User Story:** As a user, I want a brief summary printed to the terminal after each run so that I can confirm the tool processed the expected number of transactions.

#### Acceptance Criteria

1. WHEN processing completes successfully THEN the system SHALL print a progress summary to stdout.
2. WHEN printing the summary THEN the system SHALL include the total number of transactions extracted, the number of transactions successfully classified, and the number of unmatched transactions.
3. WHEN printing the summary THEN the system SHALL include the output CSV path and the unmapped log path.
4. WHEN `--strict` mode is active and unmatched transactions exist THEN the system SHALL still print the summary before exiting with a non-zero code.

---

### Requirement 9 — Error Handling and Exit Behaviour

**User Story:** As a user, I want clear, human-readable error messages without Python stack traces so that I can diagnose problems quickly without needing to read source code.

#### Acceptance Criteria

1. WHEN the rules file is not found THEN the system SHALL print `Rules file not found: {path}` to stderr and exit with a non-zero code, and SHALL NOT print a Python traceback.
2. WHEN the PDF cannot be parsed or yields no transactions THEN the system SHALL print `No transactions found in {pdf}. Is this a text-based PDF?` to stderr and exit with a non-zero code, and SHALL NOT print a Python traceback.
3. WHEN any other unrecoverable error occurs THEN the system SHALL print a descriptive, user-friendly message to stderr and exit with a non-zero code, and SHALL NOT expose internal stack traces to the user.
4. WHEN processing succeeds THEN the system SHALL exit with code `0`.
5. WHEN `--strict` mode is active and unmatched transactions exist THEN the system SHALL exit with a non-zero code.

---

### Requirement 10 — Technology Stack and Dependency Constraints

**User Story:** As a developer, I want the tool implemented as a single Python script with minimal dependencies so that it is easy to install and audit.

#### Acceptance Criteria

1. WHEN the tool is implemented THEN it SHALL be a single Python script requiring Python 3.8 or higher.
2. WHERE external libraries are used THEN the system SHALL use only `pdfplumber` for PDF extraction and `pyyaml` for YAML parsing as third-party dependencies.
3. WHERE standard library modules are needed THEN the system SHALL use `argparse` for argument parsing, `csv` for CSV writing, `pathlib` for file path handling, and `sys` for exit codes.
4. IF any dependency outside of `pdfplumber`, `pyyaml`, and the Python standard library is introduced THEN the system SHALL be considered non-compliant with this requirement.
5. WHEN the script is run THEN it SHALL NOT start a web server, SHALL NOT open a GUI, and SHALL NOT require interactive input during processing.

---

### Requirement 11 — Non-Functional Requirements

**User Story:** As a user, I want the tool to be fast, reliable, and predictable so that it can be incorporated into regular personal finance workflows.

#### Acceptance Criteria

1. WHEN processing a PDF containing 50 transactions THEN the system SHALL complete the full pipeline (extract, classify, aggregate, write) in under 3 seconds.
2. WHEN the same PDF and rules file are provided on repeated runs THEN the system SHALL produce byte-for-byte identical CSV output, ensuring deterministic behaviour.
3. WHEN the rules file contains a large number of rules THEN the system SHALL still classify all transactions correctly by evaluating rules in declaration order.
4. WHILE running THEN the system SHALL NOT modify the input PDF or the rules file.
5. WHEN the CSV output is written THEN the system SHALL always produce exactly 30 data rows in the fixed category sequence, regardless of how many transactions were present in the PDF.
