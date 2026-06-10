"""Tests for monzo_expense/schema.py."""

import pytest

from monzo_expense.schema import (
    SCHEMA_ORDER,
    Category,
    SchemaRow,
    Section,
    category_display_name,
    section_for_category,
)


def test_category_count() -> None:
    assert len(Category) == 23


def test_section_count() -> None:
    assert len(Section) == 6


def test_main_account_inflow_present() -> None:
    assert Category.MAIN_ACCOUNT_INFLOW in Category
    assert Category.MAIN_ACCOUNT_INFLOW.value == "Main Account Inflow"


def test_main_account_inflow_maps_to_irregular_inflows() -> None:
    assert section_for_category(Category.MAIN_ACCOUNT_INFLOW) is Section.IRREGULAR_INFLOWS


@pytest.mark.parametrize(
    ("member", "display_name"),
    [
        (Category.SALARY, "Salary"),
        (Category.UNEXPECTED_REFUND, "Unexpected / Refund"),
        (Category.LOAN, "Loan"),
        (Category.MAIN_ACCOUNT_INFLOW, "Main Account Inflow"),
        (Category.SAVINGS, "Savings"),
        (Category.STOCKS_AND_SHARES, "Stocks & Shares"),
        (Category.RENT, "Rent"),
        (Category.BILL_COUNCIL_TAX, "Bill - Council Tax"),
        (Category.BILL_ELECTRICITY_GAS, "Bill - Electricity & Gas"),
        (Category.BILL_PHONE_INTERNET, "Bill - Phone & Internet"),
        (Category.FOOD_SUPPLIES, "Food Supplies"),
        (Category.DEBT, "Debt"),
        (Category.CAR_AND_GAS, "Car & Gas"),
        (Category.CHARITY_DONATIONS, "Charity / Donations"),
        (Category.GIFTS_ENTERTAINMENT_MISC, "Gifts/Entertainment/Misc"),
        (Category.SUNDRY, "Sundry"),
        (Category.HOLIDAYS_TRAVEL, "Holidays & Travel"),
        (Category.EDUCATION, "Education"),
        (Category.EATING_OUT, "Eating Out"),
        (Category.ACTIVE_SAVINGS, "Active Savings"),
        (Category.LIFETIME_ISA, "Lifetime ISA"),
        (Category.STOCKS_SHARES_ISA, "Stocks & Shares ISA"),
        (Category.DIVIDEND_PORTFOLIO, "Dividend Portfolio"),
    ],
)
def test_category_display_names(member: Category, display_name: str) -> None:
    assert member.value == display_name


@pytest.mark.parametrize(
    ("member", "display_name"),
    [
        (Section.REGULAR_INFLOWS, "Regular Inflows"),
        (Section.IRREGULAR_INFLOWS, "Irregular Inflows"),
        (Section.ASSET_LIQUIDATION, "Asset Liquidation"),
        (Section.REGULAR_OUTFLOWS, "Regular Outflows"),
        (Section.IRREGULAR_OUTFLOWS, "Irregular Outflows"),
        (Section.ASSETS, "Assets"),
    ],
)
def test_section_display_names(member: Section, display_name: str) -> None:
    assert member.value == display_name


def test_schema_order_length() -> None:
    # 6 section headers + 23 line items + 6 subtotals + 2 grand totals + 1 balance = 38
    assert len(SCHEMA_ORDER) == 38


def test_schema_order_line_item_count() -> None:
    line_items = [row for row in SCHEMA_ORDER if row.kind == "line_item"]
    assert len(line_items) == 23


def test_schema_order_section_header_count() -> None:
    assert len([row for row in SCHEMA_ORDER if row.kind == "section_header"]) == 6


def test_schema_order_subtotal_count() -> None:
    assert len([row for row in SCHEMA_ORDER if row.kind == "subtotal"]) == 6


def test_schema_order_grand_total_count() -> None:
    assert len([row for row in SCHEMA_ORDER if row.kind == "grand_total"]) == 2


def test_schema_order_balance_row_is_last() -> None:
    assert SCHEMA_ORDER[-1].kind == "balance"


def test_every_category_appears_exactly_once_as_line_item() -> None:
    line_item_categories = [row.category for row in SCHEMA_ORDER if row.kind == "line_item"]
    assert len(line_item_categories) == len(Category)
    assert set(line_item_categories) == set(Category)


def test_main_account_inflow_in_schema_order() -> None:
    line_item_categories = [row.category for row in SCHEMA_ORDER if row.kind == "line_item"]
    assert Category.MAIN_ACCOUNT_INFLOW in line_item_categories


def test_main_account_inflow_after_loan_in_irregular_inflows() -> None:
    """MAIN_ACCOUNT_INFLOW must appear immediately after LOAN in SCHEMA_ORDER."""
    labels = [row.label for row in SCHEMA_ORDER]
    loan_idx = labels.index("Loan")
    mai_idx = labels.index("Main Account Inflow")
    assert mai_idx == loan_idx + 1


def test_group_on_section_headers() -> None:
    income_sections = {Section.REGULAR_INFLOWS, Section.IRREGULAR_INFLOWS, Section.ASSET_LIQUIDATION}
    expenditure_sections = {Section.REGULAR_OUTFLOWS, Section.IRREGULAR_OUTFLOWS, Section.ASSETS}
    for row in SCHEMA_ORDER:
        if row.kind == "section_header":
            assert row.section is not None
            if row.section in income_sections:
                assert row.group == "income"
            elif row.section in expenditure_sections:
                assert row.group == "expenditure"


def test_group_on_subtotals() -> None:
    income_sections = {Section.REGULAR_INFLOWS, Section.IRREGULAR_INFLOWS, Section.ASSET_LIQUIDATION}
    for row in SCHEMA_ORDER:
        if row.kind == "subtotal":
            assert row.section is not None
            expected = "income" if row.section in income_sections else "expenditure"
            assert row.group == expected


def test_group_on_grand_totals() -> None:
    grand_totals = [row for row in SCHEMA_ORDER if row.kind == "grand_total"]
    assert grand_totals[0].label == "Total Income"
    assert grand_totals[0].group == "income"
    assert grand_totals[1].label == "Total Expenditure"
    assert grand_totals[1].group == "expenditure"


def test_line_items_have_no_group() -> None:
    for row in SCHEMA_ORDER:
        if row.kind == "line_item":
            assert row.group is None


def test_schema_row_is_frozen() -> None:
    row = SchemaRow(
        kind="line_item",
        section=Section.ASSETS,
        category=Category.ACTIVE_SAVINGS,
        label="Active Savings",
        group=None,
    )
    with pytest.raises(AttributeError):
        row.label = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (Category.SALARY, "Salary"),
        (Category.MAIN_ACCOUNT_INFLOW, "Main Account Inflow"),
        (Category.FOOD_SUPPLIES, "Food Supplies"),
    ],
)
def test_category_display_name(category: Category, expected: str) -> None:
    assert category_display_name(category) == expected


@pytest.mark.parametrize(
    ("category", "expected_section"),
    [
        (Category.SALARY, Section.REGULAR_INFLOWS),
        (Category.UNEXPECTED_REFUND, Section.IRREGULAR_INFLOWS),
        (Category.LOAN, Section.IRREGULAR_INFLOWS),
        (Category.MAIN_ACCOUNT_INFLOW, Section.IRREGULAR_INFLOWS),
        (Category.SAVINGS, Section.ASSET_LIQUIDATION),
        (Category.STOCKS_AND_SHARES, Section.ASSET_LIQUIDATION),
        (Category.RENT, Section.REGULAR_OUTFLOWS),
        (Category.FOOD_SUPPLIES, Section.REGULAR_OUTFLOWS),
        (Category.CHARITY_DONATIONS, Section.IRREGULAR_OUTFLOWS),
        (Category.EATING_OUT, Section.IRREGULAR_OUTFLOWS),
        (Category.ACTIVE_SAVINGS, Section.ASSETS),
        (Category.STOCKS_SHARES_ISA, Section.ASSETS),
    ],
)
def test_section_for_category(category: Category, expected_section: Section) -> None:
    assert section_for_category(category) is expected_section


def test_section_for_every_category_is_defined() -> None:
    for category in Category:
        section = section_for_category(category)
        assert isinstance(section, Section)
