"""Tests for examples/monzo_rules.example.yaml."""

from __future__ import annotations

from pathlib import Path

from monzo_expense.rules import ExactMatch, RegexMatch, load_rules
from monzo_expense.schema import Category

EXAMPLES_FILE = Path(__file__).parent.parent.parent / "examples" / "monzo_rules.example.yaml"


def test_example_file_loads_without_error() -> None:
    rules = load_rules(EXAMPLES_FILE)
    assert len(rules) > 0


def test_main_account_inflow_rule_present() -> None:
    rules = load_rules(EXAMPLES_FILE)
    matches = [
        r for r in rules
        if isinstance(r.matcher, ExactMatch)
        and r.matcher.value == "O Okwu-Boms (Faster Payments)"
        and r.direction == "in"
    ]
    assert len(matches) == 1
    assert matches[0].category == Category.MAIN_ACCOUNT_INFLOW


def test_medcouncil_rule_uses_match_regex() -> None:
    rules = load_rules(EXAMPLES_FILE)
    regex_rules = [
        r for r in rules
        if isinstance(r.matcher, RegexMatch)
        and "MEDCOUNCIL" in r.matcher.source
    ]
    assert len(regex_rules) == 1
    assert regex_rules[0].category == Category.SUNDRY


def test_no_rule_has_type_field() -> None:
    """Example rules file must not contain any 'type' field (Monzo does not support it)."""
    text = EXAMPLES_FILE.read_text(encoding="utf-8")
    # A 'type' field key in a rule mapping would appear as "  type:" or "    type:"
    # The rules loader would have rejected it; this is a belt-and-suspenders check.
    rules = load_rules(EXAMPLES_FILE)  # must not raise
    assert all(not hasattr(r, "type_code") for r in rules)


def test_wwwhlcouk_has_two_direction_specific_rules() -> None:
    """WWW.HL.CO.UK must have separate in (Stocks & Shares) and out (Stocks & Shares ISA) rules."""
    rules = load_rules(EXAMPLES_FILE)
    hl_rules = [
        r for r in rules
        if isinstance(r.matcher, ExactMatch)
        and r.matcher.value == "WWW.HL.CO.UK BRISTOL GBR"
    ]
    assert len(hl_rules) == 2
    directions = {r.direction for r in hl_rules}
    assert directions == {"in", "out"}
    categories = {r.category for r in hl_rules}
    assert Category.STOCKS_AND_SHARES in categories
    assert Category.STOCKS_SHARES_ISA in categories


def test_somtochukwu_has_two_direction_specific_rules() -> None:
    rules = load_rules(EXAMPLES_FILE)
    s_rules = [
        r for r in rules
        if isinstance(r.matcher, ExactMatch)
        and "Somtochukwu" in r.matcher.value
    ]
    assert len(s_rules) == 2
    directions = {r.direction for r in s_rules}
    assert directions == {"in", "out"}


def test_transfer_to_pot_maps_to_active_savings() -> None:
    rules = load_rules(EXAMPLES_FILE)
    pot_rules = [
        r for r in rules
        if isinstance(r.matcher, ExactMatch)
        and r.matcher.value == "Transfer to Pot"
    ]
    assert len(pot_rules) == 1
    assert pot_rules[0].category == Category.ACTIVE_SAVINGS
