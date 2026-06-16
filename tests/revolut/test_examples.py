"""Tests for the live rules/revolut_rules.yaml file."""

from __future__ import annotations

from pathlib import Path

from revolut_expense.rules import ExactMatch, RegexMatch, load_rules
from revolut_expense.schema import Category

RULES_PATH = Path(__file__).parent.parent.parent / "rules" / "revolut_rules.yaml"


def test_rules_file_loads_without_error() -> None:
    rules = load_rules(RULES_PATH)
    assert len(rules) > 0


def test_payment_from_o_okwu_boms_rule_present() -> None:
    rules = load_rules(RULES_PATH)
    matching = [
        r
        for r in rules
        if isinstance(r.matcher, RegexMatch)
        and r.matcher.source == "^Payment from O OKWU-BOMS"
        and r.direction == "in"
        and r.category == Category.MAIN_ACCOUNT_INFLOW
    ]
    assert len(matching) == 1


def test_natwest_salary_rule_present() -> None:
    rules = load_rules(RULES_PATH)
    matching = [
        r
        for r in rules
        if isinstance(r.matcher, RegexMatch)
        and r.matcher.source == "^Payment from NATWEST HRPS PAYRO"
        and r.category == Category.SALARY
    ]
    assert len(matching) == 1


def test_hargreaves_lansdown_isa_rule() -> None:
    rules = load_rules(RULES_PATH)
    matching = [
        r
        for r in rules
        if isinstance(r.matcher, RegexMatch)
        and r.matcher.source == "^Hargreaves Lansdown"
        and r.direction == "out"
        and r.category == Category.STOCKS_SHARES_ISA
    ]
    assert len(matching) == 1


def test_no_rule_has_type_field() -> None:
    rules = load_rules(RULES_PATH)
    for rule in rules:
        assert not hasattr(rule, "type")


def test_all_regex_patterns_compile() -> None:
    import re

    rules = load_rules(RULES_PATH)
    for rule in rules:
        if isinstance(rule.matcher, RegexMatch):
            assert re.compile(rule.matcher.source) is not None


def test_self_transfer_rules_present() -> None:
    rules = load_rules(RULES_PATH)
    okwu_boms = [
        r
        for r in rules
        if isinstance(r.matcher, RegexMatch)
        and r.matcher.source == "^To Omasirichi Okwu.Boms"
        and r.direction == "out"
        and r.category == Category.CHARITY_DONATIONS
    ]
    assert len(okwu_boms) == 1

    somto = [
        r
        for r in rules
        if isinstance(r.matcher, RegexMatch)
        and r.matcher.source == "^To Somtochukwu Nchekwubechukwu Obiana"
        and r.direction == "out"
        and r.category == Category.CHARITY_DONATIONS
    ]
    assert len(somto) == 1


def test_active_savings_rule_present() -> None:
    rules = load_rules(RULES_PATH)
    matching = [
        r
        for r in rules
        if isinstance(r.matcher, RegexMatch)
        and r.matcher.source == "^Payment from ACTIVE SAVINGS CASH HUB"
        and r.direction == "in"
        and r.category == Category.SAVINGS
    ]
    assert len(matching) == 1
