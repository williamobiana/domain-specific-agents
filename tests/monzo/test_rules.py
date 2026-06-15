"""Tests for monzo_expense/rules.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from monzo_expense.errors import RulesConfigError
from monzo_expense.rules import ExactMatch, RegexMatch, Rule, load_rules
from monzo_expense.schema import Category


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_valid_exact_rule(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    direction: in
    category: Salary
""",
    )
    rules = load_rules(p)
    assert len(rules) == 1
    rule = rules[0]
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "SALARY PAYMENT"
    assert rule.direction == "in"
    assert rule.category == Category.SALARY


def test_valid_regex_rule(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match_regex: "^NYX\\\\*DCVendingLtd"
    category: "Eating Out"
""",
    )
    rules = load_rules(p)
    assert len(rules) == 1
    rule = rules[0]
    assert isinstance(rule.matcher, RegexMatch)
    assert rule.matcher.source == "^NYX\\*DCVendingLtd"


def test_rule_with_type_field_raises(tmp_path: Path) -> None:
    """A rule containing 'type' must raise RulesConfigError with Monzo context."""
    p = _write(
        tmp_path,
        """
rules:
  - match: SALARY
    type: BGC
    category: Salary
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(p)
    assert "type" in exc_info.value.message.lower()
    assert "monzo" in exc_info.value.message.lower()


def test_rule_has_no_type_code_attribute(tmp_path: Path) -> None:
    """Rule dataclass must not have a type_code attribute."""
    p = _write(tmp_path, "rules:\n  - match: FOOD\n    category: 'Food Supplies'\n")
    rules = load_rules(p)
    assert not hasattr(rules[0], "type_code")


def test_duplicate_rule_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match: FOOD
    category: "Food Supplies"
  - match: OTHER
    category: "Sundry"
  - match: FOOD
    category: "Gifts/Entertainment/Misc"
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(p)
    assert exc_info.value.violations


def test_unknown_category_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match: FOOD
    category: "Unknown Category XYZ"
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(p)
    assert "Unknown Category XYZ" in exc_info.value.message


def test_invalid_regex_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match_regex: "[invalid"
    category: "Sundry"
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(p)
    assert "[invalid" in exc_info.value.message


def test_missing_rules_key_raises(tmp_path: Path) -> None:
    p = _write(tmp_path, "not_rules:\n  - match: FOOD\n    category: 'Food Supplies'\n")
    with pytest.raises(RulesConfigError):
        load_rules(p)


def test_both_match_and_match_regex_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match: FOOD
    match_regex: "^FOOD"
    category: "Food Supplies"
""",
    )
    with pytest.raises(RulesConfigError):
        load_rules(p)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(tmp_path / "nonexistent.yaml")
    assert "not found" in exc_info.value.message.lower()


def test_exact_match_value_normalised(tmp_path: Path) -> None:
    """ExactMatch.value should be whitespace-collapsed and hyphen-normalised."""
    p = _write(
        tmp_path,
        "rules:\n  - match: \"  O Okwu–Boms  \"\n    category: 'Main Account Inflow'\n",
    )
    rules = load_rules(p)
    assert isinstance(rules[0].matcher, ExactMatch)
    # Unicode en-dash should be normalised to ASCII hyphen-minus
    assert "–" not in rules[0].matcher.value
    assert "-" in rules[0].matcher.value
    # Leading/trailing whitespace stripped
    assert not rules[0].matcher.value.startswith(" ")


def test_direction_in_and_out_accepted(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match: "WWW.HL.CO.UK BRISTOL GBR"
    direction: in
    category: "Stocks & Shares"
  - match: "WWW.HL.CO.UK BRISTOL GBR"
    direction: out
    category: "Stocks & Shares ISA"
""",
    )
    rules = load_rules(p)
    assert len(rules) == 2
    assert rules[0].direction == "in"
    assert rules[1].direction == "out"


def test_invalid_direction_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "rules:\n  - match: FOOD\n    direction: both\n    category: 'Food Supplies'\n",
    )
    with pytest.raises(RulesConfigError):
        load_rules(p)


def test_file_order_preserved(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match: ALPHA
    category: Salary
  - match: BETA
    category: Loan
  - match: GAMMA
    category: Rent
""",
    )
    rules = load_rules(p)
    assert [isinstance(r.matcher, ExactMatch) and r.matcher.value for r in rules] == [
        "ALPHA",
        "BETA",
        "GAMMA",
    ]


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    p = _write(tmp_path, "rules: [\n  unclosed bracket\n")
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(p)
    assert "parse error" in exc_info.value.message.lower()


def test_line_number_attached_to_rule(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
rules:
  - match: FOOD
    category: "Food Supplies"
""",
    )
    rules = load_rules(p)
    assert rules[0].line_number >= 1
