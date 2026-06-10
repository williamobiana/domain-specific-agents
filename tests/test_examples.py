"""Seed-data tests for rules/rules.yaml (Task 10, R12.x)."""

from __future__ import annotations

from pathlib import Path

from lloyds_expense.rules import ExactMatch, RegexMatch, Rule, load_rules
from lloyds_expense.schema import Category

# Path is relative to the project root where pytest is invoked.
RULES_FILE = Path("rules/rules.yaml")


def test_rules_file_exists() -> None:
    """The rules file must be present in the repository."""
    assert RULES_FILE.exists()


def test_rules_loads_twelve_rules() -> None:
    """The rules file must contain exactly 12 rules."""
    rules = load_rules(RULES_FILE)
    assert len(rules) == 12


def test_food_supplies_rule() -> None:
    """OMASIRICHI OKWU BO / FPO / out → Food Supplies."""
    rules = load_rules(RULES_FILE)
    rule = next(
        r for r in rules
        if isinstance(r.matcher, ExactMatch)
        and r.matcher.value == "OMASIRICHI OKWU BO"
        and r.direction == "out"
    )
    assert rule.type_code == "FPO"
    assert rule.category == Category.FOOD_SUPPLIES


def test_food_supplies_hyphen_rule() -> None:
    """OMASIRICHI OKWU-BO / FPO / out → Food Supplies (hyphen variant)."""
    rules = load_rules(RULES_FILE)
    rule = next(
        r for r in rules
        if isinstance(r.matcher, ExactMatch) and r.matcher.value == "OMASIRICHI OKWU-BO"
    )
    assert rule.type_code == "FPO"
    assert rule.direction == "out"
    assert rule.category == Category.FOOD_SUPPLIES


def test_salary_rule() -> None:
    """NATIONAL SERV M/W / BGC / in → Salary."""
    rules = load_rules(RULES_FILE)
    rule = next(r for r in rules if r.category == Category.SALARY)
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "NATIONAL SERV M/W"
    assert rule.type_code == "BGC"
    assert rule.direction == "in"


def test_active_savings_rule() -> None:
    """HLAM REGULAR SAVIN / DD / out → Active Savings."""
    rules = load_rules(RULES_FILE)
    rule = next(r for r in rules if r.category == Category.ACTIVE_SAVINGS)
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "HLAM REGULAR SAVIN"
    assert rule.type_code == "DD"
    assert rule.direction == "out"


def test_stocks_shares_isa_rule() -> None:
    """Trading 212 / DEB / out → Stocks & Shares ISA."""
    rules = load_rules(RULES_FILE)
    rule = next(r for r in rules if r.category == Category.STOCKS_SHARES_ISA)
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "Trading 212"
    assert rule.type_code == "DEB"
    assert rule.direction == "out"


def test_debt_rule() -> None:
    """LLOYDS BANK PLC / DD / out → Debt."""
    rules = load_rules(RULES_FILE)
    rule = next(r for r in rules if r.category == Category.DEBT)
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "LLOYDS BANK PLC"
    assert rule.type_code == "DD"
    assert rule.direction == "out"


def test_charity_rules() -> None:
    """GRACE AKANNI, SOMTOCHUKWU NCHEKW (out), MAUTON TOLULOPE HU → Charity / Donations."""
    rules = load_rules(RULES_FILE)
    charity_out = [
        r for r in rules
        if r.category == Category.CHARITY_DONATIONS and r.direction == "out"
    ]
    names = {r.matcher.value for r in charity_out if isinstance(r.matcher, ExactMatch)}
    assert names == {"GRACE AKANNI", "SOMTOCHUKWU NCHEKW", "MAUTON TOLULOPE HU", "ABDULAKEEM SOLIHU"}


def test_unexpected_refund_rules() -> None:
    """OMASIRICHI OKWU BO and SOMTOCHUKWU NCHEKW (FPI / in) → Unexpected / Refund."""
    rules = load_rules(RULES_FILE)
    refund_in = [
        r for r in rules
        if r.category == Category.UNEXPECTED_REFUND and r.direction == "in"
    ]
    names = {r.matcher.value for r in refund_in if isinstance(r.matcher, ExactMatch)}
    assert names == {"OMASIRICHI OKWU BO", "SOMTOCHUKWU NCHEKW"}


def test_no_fpi_regex_rule() -> None:
    """The rules file must NOT include a generic FPI regex rule."""
    rules = load_rules(RULES_FILE)
    fpi_regex_rules = [
        r for r in rules if isinstance(r.matcher, RegexMatch) and r.type_code == "FPI"
    ]
    assert len(fpi_regex_rules) == 0


def test_all_matchers_are_exact_match() -> None:
    """All rules use exact matching, not regex."""
    rules = load_rules(RULES_FILE)
    for rule in rules:
        assert isinstance(rule.matcher, ExactMatch), (
            f"Expected ExactMatch for rule at line {rule.line_number}, "
            f"got {type(rule.matcher).__name__}"
        )
