"""Tests for rules.py — load_rules, ExactMatch, RegexMatch, Rule validation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from lloyds_expense.errors import RulesConfigError
from lloyds_expense.rules import ExactMatch, RegexMatch, load_rules
from lloyds_expense.schema import Category

# ---------------------------------------------------------------------------
# Helper: write a temporary rules file and return its path
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, content: str) -> Path:
    """Write *content* to a temporary rules.yaml and return the path."""
    p = tmp_path / "rules.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Case 1: Valid file with exact match rule
# ---------------------------------------------------------------------------


def test_valid_exact_rule(tmp_path: Path) -> None:
    """Valid file with one exact match rule returns a list with one Rule."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    type: BGC
    direction: in
    category: Salary
""",
    )
    rules = load_rules(rules_file)

    assert len(rules) == 1
    rule = rules[0]
    assert isinstance(rule.matcher, ExactMatch)
    assert rule.matcher.value == "SALARY PAYMENT"
    assert rule.type_code == "BGC"
    assert rule.direction == "in"
    assert rule.category == Category.SALARY


def test_valid_exact_rule_file_order_preserved(tmp_path: Path) -> None:
    """Rules are returned in the same order as they appear in the YAML file."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: HLAM REGULAR SAVIN
    type: DD
    direction: out
    category: Active Savings
  - match: SALARY PAYMENT
    type: BGC
    direction: in
    category: Salary
""",
    )
    rules = load_rules(rules_file)

    assert len(rules) == 2
    assert isinstance(rules[0].matcher, ExactMatch)
    assert rules[0].matcher.value == "HLAM REGULAR SAVIN"
    assert rules[0].category == Category.ACTIVE_SAVINGS
    assert isinstance(rules[1].matcher, ExactMatch)
    assert rules[1].matcher.value == "SALARY PAYMENT"
    assert rules[1].category == Category.SALARY


# ---------------------------------------------------------------------------
# Case 2: Valid file with regex rule
# ---------------------------------------------------------------------------


def test_valid_regex_rule(tmp_path: Path) -> None:
    """Valid file with one regex rule returns a RegexMatch with compiled pattern and source."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match_regex: "^AMAZON"
    category: Food Supplies
""",
    )
    rules = load_rules(rules_file)

    assert len(rules) == 1
    rule = rules[0]
    assert isinstance(rule.matcher, RegexMatch)
    assert rule.matcher.source == "^AMAZON"
    assert isinstance(rule.matcher.pattern, re.Pattern)
    assert rule.matcher.pattern.pattern == "^AMAZON"
    assert rule.category == Category.FOOD_SUPPLIES


def test_valid_regex_rule_pattern_is_compiled(tmp_path: Path) -> None:
    """The compiled pattern in RegexMatch actually matches strings as expected."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match_regex: "^FOOD.*"
    category: Food Supplies
""",
    )
    rules = load_rules(rules_file)
    matcher = rules[0].matcher
    assert isinstance(matcher, RegexMatch)
    assert matcher.pattern.match("FOOD STORE")
    assert not matcher.pattern.match("NOT FOOD")


# ---------------------------------------------------------------------------
# Case 3: Duplicate exact rule raises RulesConfigError listing both line numbers
# ---------------------------------------------------------------------------


def test_duplicate_exact_rule_raises(tmp_path: Path) -> None:
    """Two identical exact-match rules (same matcher, type, direction) raise RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    type: BGC
    direction: in
    category: Salary
  - match: SALARY PAYMENT
    type: BGC
    direction: in
    category: Salary
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    err = exc_info.value
    # The error message or violations must reference both duplicated rules (by line number).
    # Actual line numbers depend on how many leading blank lines the YAML AST counts, so
    # we just verify that two distinct line numbers appear somewhere in the reported text.
    full_text = str(err.message) + " ".join(err.violations)
    # Extract all integers from the text; there must be at least two distinct ones.
    import re as _re

    found_numbers = list(map(int, _re.findall(r"\d+", full_text)))
    assert len(found_numbers) >= 2, f"Expected two line numbers in: {full_text!r}"
    assert len(set(found_numbers)) >= 2, f"Expected distinct line numbers in: {full_text!r}"


def test_duplicate_exact_rule_violations_list_populated(tmp_path: Path) -> None:
    """RulesConfigError for duplicates populates the violations list."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: HLAM REGULAR SAVIN
    type: DD
    direction: out
    category: Active Savings
  - match: HLAM REGULAR SAVIN
    type: DD
    direction: out
    category: Active Savings
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert len(exc_info.value.violations) >= 1


# ---------------------------------------------------------------------------
# Case 4: Duplicate regex rule (same source string) raises RulesConfigError
# ---------------------------------------------------------------------------


def test_duplicate_regex_rule_raises(tmp_path: Path) -> None:
    """Two regex rules with the same source string, type, and direction raise RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match_regex: "^PAYPAL"
    category: Sundry
  - match_regex: "^PAYPAL"
    category: Gifts/Entertainment/Misc
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert exc_info.value.violations


# ---------------------------------------------------------------------------
# Case 5: Unknown category raises RulesConfigError
# ---------------------------------------------------------------------------


def test_unknown_category_raises(tmp_path: Path) -> None:
    """A rule referencing a category not in the Category enum raises RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SOME DESCRIPTION
    category: Nonexistent Category
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert "Nonexistent Category" in exc_info.value.message


# ---------------------------------------------------------------------------
# Case 6: Invalid regex raises RulesConfigError with pattern source info
# ---------------------------------------------------------------------------


def test_invalid_regex_raises(tmp_path: Path) -> None:
    """An uncompilable regex pattern raises RulesConfigError mentioning the pattern source."""
    bad_pattern = "[unclosed"
    rules_file = _write(
        tmp_path,
        f"""
rules:
  - match_regex: "{bad_pattern}"
    category: Sundry
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert bad_pattern in exc_info.value.message


# ---------------------------------------------------------------------------
# Case 7: Missing 'rules' key raises RulesConfigError
# ---------------------------------------------------------------------------


def test_missing_rules_key_raises(tmp_path: Path) -> None:
    """A YAML file without a top-level 'rules' key raises RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
categories:
  - Salary
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert "rules" in exc_info.value.message.lower()


def test_rules_value_not_a_list_raises(tmp_path: Path) -> None:
    """A 'rules' key whose value is not a list raises RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules: not-a-list
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert "rules" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# Case 8: Both 'match' and 'match_regex' present raises RulesConfigError
# ---------------------------------------------------------------------------


def test_both_match_and_match_regex_raises(tmp_path: Path) -> None:
    """A rule entry that specifies both 'match' and 'match_regex' raises RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    match_regex: "^SALARY"
    category: Salary
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    msg = exc_info.value.message.lower()
    assert "match" in msg


# ---------------------------------------------------------------------------
# Case 9: ExactMatch.value is normalised at load time
# ---------------------------------------------------------------------------


def test_exact_match_value_whitespace_collapsed(tmp_path: Path) -> None:
    """ExactMatch.value has internal whitespace runs collapsed to a single space."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: "SALARY   PAYMENT"
    category: Salary
""",
    )
    rules = load_rules(rules_file)
    assert isinstance(rules[0].matcher, ExactMatch)
    assert rules[0].matcher.value == "SALARY PAYMENT"


def test_exact_match_value_leading_trailing_whitespace_stripped(tmp_path: Path) -> None:
    """ExactMatch.value has leading and trailing whitespace stripped."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: "  SALARY PAYMENT  "
    category: Salary
""",
    )
    rules = load_rules(rules_file)
    assert isinstance(rules[0].matcher, ExactMatch)
    assert rules[0].matcher.value == "SALARY PAYMENT"


def test_exact_match_value_hyphen_variants_normalised(tmp_path: Path) -> None:
    """ExactMatch.value has Unicode hyphen variants replaced with ASCII hyphen-minus."""
    # U+2013 EN DASH used in the match string
    rules_file = _write(
        tmp_path,
        'rules:\n  - match: "OKWU\u2013BO"\n    category: Food Supplies\n',
    )
    rules = load_rules(rules_file)
    assert isinstance(rules[0].matcher, ExactMatch)
    # U+2013 should be replaced with ASCII hyphen-minus (U+002D)
    assert rules[0].matcher.value == "OKWU-BO"


# ---------------------------------------------------------------------------
# Case 10: Unknown type code raises RulesConfigError
# ---------------------------------------------------------------------------


def test_unknown_type_code_raises(tmp_path: Path) -> None:
    """A rule with an unrecognised type code raises RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    type: XYZ
    category: Salary
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert "XYZ" in exc_info.value.message


# ---------------------------------------------------------------------------
# Case 11: Valid type code is accepted without error
# ---------------------------------------------------------------------------


def test_valid_type_code_fpo_accepted(tmp_path: Path) -> None:
    """A rule with a known type code 'FPO' is accepted without raising."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: OMASIRICHI OKWU BO
    type: FPO
    direction: out
    category: Food Supplies
""",
    )
    rules = load_rules(rules_file)
    assert len(rules) == 1
    assert rules[0].type_code == "FPO"


def test_valid_type_codes_all_accepted(tmp_path: Path) -> None:
    """All known Lloyds type codes can be used in rules without error."""
    from lloyds_expense.rules import KNOWN_TYPE_CODES

    for code in sorted(KNOWN_TYPE_CODES):
        rules_file = _write(
            tmp_path,
            f"""
rules:
  - match: SOME DESCRIPTION {code}
    type: {code}
    category: Salary
""",
        )
        rules = load_rules(rules_file)
        assert rules[0].type_code == code


# ---------------------------------------------------------------------------
# Case 12: YAML parse error raises RulesConfigError
# ---------------------------------------------------------------------------


def test_yaml_parse_error_raises(tmp_path: Path) -> None:
    """Malformed YAML content raises RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: OK
    category: Salary
  : broken: yaml: {{{
""",
    )
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(rules_file)

    assert "yaml" in exc_info.value.message.lower() or exc_info.value.line_number is not None


# ---------------------------------------------------------------------------
# Case 13: Non-existent file raises RulesConfigError
# ---------------------------------------------------------------------------


def test_nonexistent_file_raises(tmp_path: Path) -> None:
    """Passing a path to a file that does not exist raises RulesConfigError."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(RulesConfigError) as exc_info:
        load_rules(missing)

    assert "not found" in exc_info.value.message.lower() or str(missing) in exc_info.value.message


# ---------------------------------------------------------------------------
# Case 14: Empty rules list returns an empty list (no error)
# ---------------------------------------------------------------------------


def test_empty_rules_list_returns_empty(tmp_path: Path) -> None:
    """A file with 'rules: []' returns an empty list without raising."""
    rules_file = _write(
        tmp_path,
        """
rules: []
""",
    )
    rules = load_rules(rules_file)
    assert rules == []


# ---------------------------------------------------------------------------
# Case 15: direction filter loaded correctly
# ---------------------------------------------------------------------------


def test_direction_in_loaded(tmp_path: Path) -> None:
    """A rule with 'direction: in' has direction set to 'in'."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: NATIONAL SERV M/W
    type: BGC
    direction: in
    category: Salary
""",
    )
    rules = load_rules(rules_file)
    assert rules[0].direction == "in"


def test_direction_out_loaded(tmp_path: Path) -> None:
    """A rule with 'direction: out' has direction set to 'out'."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: HLAM REGULAR SAVIN
    type: DD
    direction: out
    category: Active Savings
""",
    )
    rules = load_rules(rules_file)
    assert rules[0].direction == "out"


def test_direction_absent_is_none(tmp_path: Path) -> None:
    """A rule with no 'direction' field has direction set to None."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SOME TRANSACTION
    category: Sundry
""",
    )
    rules = load_rules(rules_file)
    assert rules[0].direction is None


# ---------------------------------------------------------------------------
# Case 16: line_number attribute is populated on each Rule (>= 1)
# ---------------------------------------------------------------------------


def test_line_number_populated_single_rule(tmp_path: Path) -> None:
    """Each Rule carries a line_number attribute >= 1."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    type: BGC
    direction: in
    category: Salary
""",
    )
    rules = load_rules(rules_file)
    assert rules[0].line_number >= 1


def test_line_numbers_populated_multiple_rules(tmp_path: Path) -> None:
    """All rules in a multi-rule file have line_number >= 1, and they differ."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: HLAM REGULAR SAVIN
    type: DD
    direction: out
    category: Active Savings
  - match: SALARY PAYMENT
    type: BGC
    direction: in
    category: Salary
  - match_regex: "^TRADING 212"
    type: DEB
    direction: out
    category: Stocks & Shares ISA
""",
    )
    rules = load_rules(rules_file)
    assert len(rules) == 3
    for rule in rules:
        assert rule.line_number >= 1
    # Line numbers should be distinct and in ascending order
    line_numbers = [r.line_number for r in rules]
    assert line_numbers == sorted(set(line_numbers))


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_type_code_absent_is_none(tmp_path: Path) -> None:
    """A rule with no 'type' field has type_code set to None."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SOME DESCRIPTION
    category: Salary
""",
    )
    rules = load_rules(rules_file)
    assert rules[0].type_code is None


def test_rule_dataclass_is_frozen(tmp_path: Path) -> None:
    """Rule instances are frozen dataclasses and cannot be mutated."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    category: Salary
""",
    )
    rules = load_rules(rules_file)
    with pytest.raises((AttributeError, TypeError)):
        rules[0].type_code = "BGC"  # type: ignore[misc]


def test_exact_match_dataclass_is_frozen(tmp_path: Path) -> None:
    """ExactMatch instances are frozen dataclasses and cannot be mutated."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: SALARY PAYMENT
    category: Salary
""",
    )
    rules = load_rules(rules_file)
    matcher = rules[0].matcher
    assert isinstance(matcher, ExactMatch)
    with pytest.raises((AttributeError, TypeError)):
        matcher.value = "OTHER"  # type: ignore[misc]


def test_regex_match_dataclass_is_frozen(tmp_path: Path) -> None:
    """RegexMatch instances are frozen dataclasses and cannot be mutated."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match_regex: "^AMAZON"
    category: Food Supplies
""",
    )
    rules = load_rules(rules_file)
    matcher = rules[0].matcher
    assert isinstance(matcher, RegexMatch)
    with pytest.raises((AttributeError, TypeError)):
        matcher.source = "other"  # type: ignore[misc]


def test_duplicate_differs_by_direction_not_duplicate(tmp_path: Path) -> None:
    """Two rules with same matcher and type but different directions are NOT duplicates."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: TRANSFER
    type: TFR
    direction: in
    category: Savings
  - match: TRANSFER
    type: TFR
    direction: out
    category: Active Savings
""",
    )
    # Should not raise — direction differs, so not duplicates
    rules = load_rules(rules_file)
    assert len(rules) == 2


def test_duplicate_differs_by_type_not_duplicate(tmp_path: Path) -> None:
    """Two rules with same matcher and direction but different type codes are NOT duplicates."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - match: PAYEE NAME
    type: FPO
    direction: out
    category: Food Supplies
  - match: PAYEE NAME
    type: DEB
    direction: out
    category: Eating Out
""",
    )
    # Should not raise — type code differs, so not duplicates
    rules = load_rules(rules_file)
    assert len(rules) == 2


def test_neither_match_nor_match_regex_raises(tmp_path: Path) -> None:
    """A rule entry with neither 'match' nor 'match_regex' raises RulesConfigError."""
    rules_file = _write(
        tmp_path,
        """
rules:
  - category: Salary
    type: BGC
""",
    )
    with pytest.raises(RulesConfigError):
        load_rules(rules_file)


def test_regex_source_stored_verbatim(tmp_path: Path) -> None:
    """RegexMatch.source stores the original pattern string, not the compiled repr."""
    # Use a plain pattern with no YAML-special backslash sequences so that
    # YAML parses it unambiguously regardless of quoting style.
    pattern = "^AMAZON[0-9]+"
    rules_file = _write(
        tmp_path,
        f"""
rules:
  - match_regex: "{pattern}"
    category: Food Supplies
""",
    )
    rules = load_rules(rules_file)
    matcher = rules[0].matcher
    assert isinstance(matcher, RegexMatch)
    assert matcher.source == pattern
