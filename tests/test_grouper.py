import pytest

from src.categories import SCHEMA
from src.grouper import (
    CategorisedItem,
    _exact_match,
    _fuzzy_match,
    _normalise,
    group_items,
    match_category,
)
from src.parser import ExpenseItem


class TestNormalise:
    def test_lowercase(self):
        assert _normalise("SALARY") == "salary"

    def test_collapse_whitespace(self):
        assert _normalise("  salary  ") == "salary"

    def test_strip_hyphen(self):
        assert _normalise("bill - council tax") == "bill council tax"

    def test_strip_slash(self):
        assert _normalise("unexpected / refund") == "unexpected refund"

    def test_strip_ampersand(self):
        assert _normalise("stocks & shares") == "stocks shares"

    def test_full_category_name(self):
        assert _normalise("Bill - Council Tax") == "bill council tax"

    def test_empty_string(self):
        assert _normalise("") == ""


class TestExactMatch:
    def test_salary_normalised(self):
        assert _exact_match("salary") == ("Regular Inflows", "Salary")

    def test_rent_normalised(self):
        assert _exact_match("rent") == ("Regular Outflows", "Rent")

    def test_no_match(self):
        assert _exact_match("completely unknown xyz") is None

    def test_empty_normalised(self):
        assert _exact_match("") is None


class TestFuzzyMatch:
    def test_reordered_tokens(self):
        # "council tax bill" matches "Bill - Council Tax" (normalised: "bill council tax")
        result = _fuzzy_match("council tax bill")
        assert result == ("Regular Outflows", "Bill - Council Tax")

    def test_no_match_on_unknown(self):
        assert _fuzzy_match("completely unknown xyz abc") is None

    def test_empty_tokens_no_match(self):
        assert _fuzzy_match("") is None

    def test_substring_containment(self):
        # "council" is a substring of norm_cat "bill council tax" (1/3 tokens < 50%, so
        # only the substring check triggers — not the token overlap check)
        result = _fuzzy_match("council")
        assert result == ("Regular Outflows", "Bill - Council Tax")

    def test_higher_ratio_wins_tie(self):
        # "savings" matches "Savings" (100%) over "Active Savings" (50%)
        result = _fuzzy_match("savings")
        assert result == ("Asset Liquidation", "Savings")


class TestMatchCategory:
    def test_exact_salary(self):
        assert match_category("Salary") == ("Regular Inflows", "Salary")

    @pytest.mark.parametrize("category_name,section_name", [
        (cat, section.name)
        for section in SCHEMA
        for cat in section.categories
    ])
    def test_all_schema_categories_exact_text(self, category_name, section_name):
        assert match_category(category_name) == (section_name, category_name)

    def test_case_insensitive_lower(self):
        assert match_category("salary") == ("Regular Inflows", "Salary")

    def test_case_insensitive_upper(self):
        assert match_category("SALARY") == ("Regular Inflows", "Salary")

    def test_whitespace_padded_with_punctuation(self):
        assert match_category("  bill - council tax  ") == ("Regular Outflows", "Bill - Council Tax")

    def test_fuzzy_partial_match_reordered(self):
        assert match_category("council tax bill") == ("Regular Outflows", "Bill - Council Tax")

    def test_unknown_returns_none(self):
        assert match_category("completely unknown xyz abc") is None

    def test_empty_string_returns_none(self):
        assert match_category("") is None

    def test_case_insensitive_loan(self):
        assert match_category("LOAN") == ("Irregular Inflows", "Loan")

    def test_case_insensitive_rent(self):
        assert match_category("rent") == ("Regular Outflows", "Rent")

    def test_fuzzy_savings_matches_savings_not_active_savings(self):
        # "Savings" (100% ratio) beats "Active Savings" (50% ratio)
        assert match_category("my savings") == ("Asset Liquidation", "Savings")


class TestGroupItems:
    def test_matched_item_in_first_list(self):
        items = [ExpenseItem(raw_text="Salary", amount=3500.0)]
        categorised, unmatched = group_items(items)
        assert len(categorised) == 1
        assert categorised[0].section == "Regular Inflows"
        assert categorised[0].category == "Salary"
        assert categorised[0].amount == 3500.0

    def test_unmatched_item_in_second_list(self):
        items = [ExpenseItem(raw_text="completely unknown xyz", amount=100.0)]
        categorised, unmatched = group_items(items)
        assert len(unmatched) == 1
        assert unmatched[0].raw_text == "completely unknown xyz"

    def test_unmatched_assigned_uncategorised_in_first_list(self):
        items = [ExpenseItem(raw_text="completely unknown xyz", amount=100.0)]
        categorised, unmatched = group_items(items)
        assert len(categorised) == 1
        assert categorised[0].section == "Uncategorised"
        assert categorised[0].category == "Uncategorised"

    def test_unmatched_amount_preserved_in_first_list(self):
        items = [ExpenseItem(raw_text="completely unknown xyz", amount=42.5)]
        categorised, _ = group_items(items)
        assert categorised[0].amount == 42.5

    def test_mixed_matched_and_unmatched(self):
        items = [
            ExpenseItem(raw_text="Salary", amount=3500.0),
            ExpenseItem(raw_text="completely unknown xyz", amount=100.0),
            ExpenseItem(raw_text="Rent", amount=900.0),
        ]
        categorised, unmatched = group_items(items)
        assert len(categorised) == 3
        assert len(unmatched) == 1
        assert categorised[0].category == "Salary"
        assert categorised[1].category == "Uncategorised"
        assert categorised[2].category == "Rent"

    def test_empty_items_list(self):
        categorised, unmatched = group_items([])
        assert categorised == []
        assert unmatched == []

    def test_all_matched_no_unmatched(self):
        items = [
            ExpenseItem(raw_text="Salary", amount=3500.0),
            ExpenseItem(raw_text="Rent", amount=900.0),
        ]
        categorised, unmatched = group_items(items)
        assert unmatched == []
        assert len(categorised) == 2

    def test_amounts_preserved_for_matched(self):
        items = [ExpenseItem(raw_text="Salary", amount=3500.0)]
        categorised, _ = group_items(items)
        assert categorised[0].amount == 3500.0

    def test_returns_categorised_item_instances(self):
        items = [ExpenseItem(raw_text="Salary", amount=3500.0)]
        categorised, _ = group_items(items)
        assert isinstance(categorised[0], CategorisedItem)

    def test_unmatched_returns_expense_item_instances(self):
        items = [ExpenseItem(raw_text="unknown xyz", amount=50.0)]
        _, unmatched = group_items(items)
        assert isinstance(unmatched[0], ExpenseItem)

    def test_multiple_unmatched_items(self):
        items = [
            ExpenseItem(raw_text="alien xyz 1", amount=10.0),
            ExpenseItem(raw_text="alien xyz 2", amount=20.0),
        ]
        categorised, unmatched = group_items(items)
        assert len(unmatched) == 2
        assert len(categorised) == 2
        assert all(c.section == "Uncategorised" for c in categorised)
