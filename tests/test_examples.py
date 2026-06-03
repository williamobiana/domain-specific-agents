"""Seed-data tests for examples/rules.example.yaml (Task 10, R12.x)."""

from __future__ import annotations

from pathlib import Path

from lloyds_expense.rules import ExactMatch, RegexMatch, Rule, load_rules
from lloyds_expense.schema import Category

# Path is relative to the project root where pytest is invoked.
EXAMPLES_RULES = Path("examples/rules.example.yaml")


def test_example_rules_file_exists() -> None:
    """The example rules file must be present in the repository."""
    assert EXAMPLES_RULES.exists()


def test_example_rules_loads_four_rules() -> None:
    """The example file must contain exactly 4 rules (R12.1-R12.4)."""
    rules = load_rules(EXAMPLES_RULES)
    assert len(rules) == 4


def test_food_supplies_rule() -> None:
    """R12.1: OMASIRICHI OKWU BO / FPO / out → Food Supplies."""
    rules = load_rules(EXAMPLES_RULES)
    rule: Rule = rules[0]
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "OMASIRICHI OKWU BO"
    assert rule.type_code == "FPO"
    assert rule.direction == "out"
    assert rule.category == Category.FOOD_SUPPLIES


def test_salary_rule() -> None:
    """R12.2: NATIONAL SERV M/W / BGC / in → Salary."""
    rules = load_rules(EXAMPLES_RULES)
    rule: Rule = rules[1]
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "NATIONAL SERV M/W"
    assert rule.type_code == "BGC"
    assert rule.direction == "in"
    assert rule.category == Category.SALARY


def test_active_savings_rule() -> None:
    """R12.3: HLAM REGULAR SAVIN / DD / out → Active Savings."""
    rules = load_rules(EXAMPLES_RULES)
    rule: Rule = rules[2]
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "HLAM REGULAR SAVIN"
    assert rule.type_code == "DD"
    assert rule.direction == "out"
    assert rule.category == Category.ACTIVE_SAVINGS


def test_stocks_shares_isa_rule() -> None:
    """R12.4: Trading 212 / DEB / out → Stocks & Shares ISA."""
    rules = load_rules(EXAMPLES_RULES)
    rule: Rule = rules[3]
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "Trading 212"
    assert rule.type_code == "DEB"
    assert rule.direction == "out"
    assert rule.category == Category.STOCKS_SHARES_ISA


def test_no_fpi_regex_rule() -> None:
    """R12.5: The example file must NOT include a generic FPI regex rule."""
    rules = load_rules(EXAMPLES_RULES)
    fpi_regex_rules = [
        r for r in rules if isinstance(r.matcher, RegexMatch) and r.type_code == "FPI"
    ]
    assert len(fpi_regex_rules) == 0


def test_all_matchers_are_exact_match() -> None:
    """All 4 example rules use exact matching, not regex (no generic patterns)."""
    rules = load_rules(EXAMPLES_RULES)
    for rule in rules:
        assert isinstance(rule.matcher, ExactMatch), (
            f"Expected ExactMatch for rule at line {rule.line_number}, "
            f"got {type(rule.matcher).__name__}"
        )


def test_food_supplies_rule_value_normalised() -> None:
    """R12.1: ExactMatch.value is stored in normalised form at load time."""
    rules = load_rules(EXAMPLES_RULES)
    food_rule = next(r for r in rules if r.category == Category.FOOD_SUPPLIES)
    # The YAML value "OMASIRICHI OKWU BO" has no leading/trailing whitespace,
    # no Unicode hyphens, and no repeated spaces — normalisation is a no-op.
    assert food_rule.matcher.value == "OMASIRICHI OKWU BO"
