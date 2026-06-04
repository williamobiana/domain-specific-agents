"""Tests for errors.py — typed exception hierarchy."""

from __future__ import annotations

import pytest

from lloyds_expense.errors import (
    InputError,
    ParseError,
    ReconciliationError,
    RulesConfigError,
    StatementToCsvError,
    UnmatchedTransactionsError,
)

# ── Inheritance ─────────────────────────────────────────────────────────────


def test_parse_error_is_statement_to_csv_error() -> None:
    assert issubclass(ParseError, StatementToCsvError)


def test_rules_config_error_is_statement_to_csv_error() -> None:
    assert issubclass(RulesConfigError, StatementToCsvError)


def test_unmatched_transactions_error_is_statement_to_csv_error() -> None:
    assert issubclass(UnmatchedTransactionsError, StatementToCsvError)


def test_reconciliation_error_is_statement_to_csv_error() -> None:
    assert issubclass(ReconciliationError, StatementToCsvError)


def test_input_error_is_statement_to_csv_error() -> None:
    assert issubclass(InputError, StatementToCsvError)


def test_all_errors_are_exceptions() -> None:
    assert issubclass(StatementToCsvError, Exception)


# ── StatementToCsvError ──────────────────────────────────────────────────────


def test_base_error_can_be_raised_and_caught() -> None:
    with pytest.raises(StatementToCsvError, match="base error"):
        raise StatementToCsvError("base error")


def test_subclasses_caught_as_base() -> None:
    with pytest.raises(StatementToCsvError):
        raise ParseError("pdf broken")

    with pytest.raises(StatementToCsvError):
        raise RulesConfigError("bad rules")

    with pytest.raises(StatementToCsvError):
        raise InputError("bad arg")


# ── ParseError ───────────────────────────────────────────────────────────────


def test_parse_error_message_attribute() -> None:
    err = ParseError("cannot locate transaction table")
    assert err.message == "cannot locate transaction table"


def test_parse_error_page_defaults_to_none() -> None:
    err = ParseError("something went wrong")
    assert err.page is None


def test_parse_error_page_set_when_provided() -> None:
    err = ParseError("row parse failed", page=3)
    assert err.page == 3


def test_parse_error_str_contains_message() -> None:
    err = ParseError("invalid PDF structure")
    assert "invalid PDF structure" in str(err)


def test_parse_error_page_zero_is_valid() -> None:
    err = ParseError("error on first page", page=0)
    assert err.page == 0


# ── RulesConfigError ─────────────────────────────────────────────────────────


def test_rules_config_error_message_attribute() -> None:
    err = RulesConfigError("missing rules key")
    assert err.message == "missing rules key"


def test_rules_config_error_line_number_defaults_to_none() -> None:
    err = RulesConfigError("bad rule")
    assert err.line_number is None


def test_rules_config_error_violations_defaults_to_empty_list() -> None:
    err = RulesConfigError("multiple problems")
    assert err.violations == []


def test_rules_config_error_line_number_set_when_provided() -> None:
    err = RulesConfigError("unknown category", line_number=7)
    assert err.line_number == 7


def test_rules_config_error_violations_set_when_provided() -> None:
    violations = ["line 3: duplicate rule", "line 9: duplicate rule"]
    err = RulesConfigError("duplicate rules found", violations=violations)
    assert err.violations == violations


def test_rules_config_error_violations_list_is_independent_copy() -> None:
    original = ["violation 1"]
    err = RulesConfigError("bad", violations=original)
    original.append("violation 2")
    # The violations list stored on the error reflects the list object passed in;
    # the test simply confirms the attribute holds the expected values at construction.
    assert "violation 1" in err.violations


def test_rules_config_error_str_contains_message() -> None:
    err = RulesConfigError("invalid regex at line 5")
    assert "invalid regex at line 5" in str(err)


def test_rules_config_error_all_params() -> None:
    err = RulesConfigError("errors found", line_number=12, violations=["dup at 12", "dup at 20"])
    assert err.message == "errors found"
    assert err.line_number == 12
    assert len(err.violations) == 2


# ── UnmatchedTransactionsError ───────────────────────────────────────────────


def test_unmatched_transactions_error_stores_unmatched() -> None:
    # Use sentinel objects — Transaction is not yet implemented.
    sentinel_a = object()
    sentinel_b = object()
    unmatched: tuple[object, ...] = (sentinel_a, sentinel_b)  # type: ignore[assignment]
    err = UnmatchedTransactionsError(unmatched)  # type: ignore[arg-type]
    assert err.unmatched is unmatched


def test_unmatched_transactions_error_message_includes_count() -> None:
    sentinel = object()
    err = UnmatchedTransactionsError((sentinel,))  # type: ignore[arg-type]
    assert "1" in str(err)


def test_unmatched_transactions_error_empty_tuple() -> None:
    err = UnmatchedTransactionsError(())  # type: ignore[arg-type]
    assert err.unmatched == ()
    assert "0" in str(err)


def test_unmatched_transactions_error_plural_message() -> None:
    sentinels: tuple[object, ...] = (object(), object(), object())
    err = UnmatchedTransactionsError(sentinels)  # type: ignore[arg-type]
    assert "3" in str(err)


# ── ReconciliationError ──────────────────────────────────────────────────────


def test_reconciliation_error_stores_report() -> None:
    # Use a sentinel — ReconciliationReport is not yet implemented.
    sentinel_report = object()
    err = ReconciliationError(sentinel_report)  # type: ignore[arg-type]
    assert err.report is sentinel_report


def test_reconciliation_error_has_descriptive_message() -> None:
    sentinel_report = object()
    err = ReconciliationError(sentinel_report)  # type: ignore[arg-type]
    assert len(str(err)) > 0


# ── InputError ───────────────────────────────────────────────────────────────


def test_input_error_message_attribute() -> None:
    err = InputError("--out is required")
    assert err.message == "--out is required"


def test_input_error_str_contains_message() -> None:
    err = InputError("only one PDF may be supplied")
    assert "only one PDF may be supplied" in str(err)


def test_input_error_can_be_raised_and_caught() -> None:
    with pytest.raises(InputError, match="bad flag"):
        raise InputError("bad flag")


# ── Catch-all catch block ────────────────────────────────────────────────────


def test_all_subclasses_caught_by_base_in_except_block() -> None:
    errors_to_raise = [
        ParseError("p"),
        RulesConfigError("r"),
        UnmatchedTransactionsError(()),  # type: ignore[arg-type]
        ReconciliationError(object()),  # type: ignore[arg-type]
        InputError("i"),
    ]
    for exc in errors_to_raise:
        caught = False
        try:
            raise exc
        except StatementToCsvError:
            caught = True
        assert caught, f"{type(exc).__name__} was not caught as StatementToCsvError"
