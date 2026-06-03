"""Tests for schema.py — Category/Section enums, SchemaRow, and SCHEMA_ORDER."""

import pytest

from lloyds_expense.schema import (
    SCHEMA_ORDER,
    Category,
    SchemaRow,
    Section,
    category_display_name,
    section_for_category,
)


def test_category_count() -> None:
    assert len(Category) == 22


def test_section_count() -> None:
    assert len(Section) == 6


# ── Category member values ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("member", "display_name"),
    [
        (Category.SALARY, "Salary"),
        (Category.UNEXPECTED_REFUND, "Unexpected / Refund"),
        (Category.LOAN, "Loan"),
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


# ── Section member values ───────────────────────────────────────────────────


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


def test_category_lookup_by_value() -> None:
    assert Category("Salary") is Category.SALARY
    assert Category("Stocks & Shares ISA") is Category.STOCKS_SHARES_ISA


def test_section_lookup_by_value() -> None:
    assert Section("Regular Inflows") is Section.REGULAR_INFLOWS
    assert Section("Assets") is Section.ASSETS


def test_category_members_are_unique() -> None:
    values = [c.value for c in Category]
    assert len(values) == len(set(values))


def test_section_members_are_unique() -> None:
    values = [s.value for s in Section]
    assert len(values) == len(set(values))


# ── SchemaRow dataclass ─────────────────────────────────────────────────────


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


def test_schema_row_fields() -> None:
    row = SchemaRow(
        kind="section_header",
        section=Section.REGULAR_INFLOWS,
        category=None,
        label="Regular Inflows",
        group="income",
    )
    assert row.kind == "section_header"
    assert row.section is Section.REGULAR_INFLOWS
    assert row.category is None
    assert row.label == "Regular Inflows"
    assert row.group == "income"


# ── SCHEMA_ORDER constant ───────────────────────────────────────────────────


def test_schema_order_length() -> None:
    # 6 section headers + 22 line items + 6 subtotals + 2 grand totals = 36
    assert len(SCHEMA_ORDER) == 36


def test_schema_order_line_item_count() -> None:
    line_items = [row for row in SCHEMA_ORDER if row.kind == "line_item"]
    assert len(line_items) == 22


def test_schema_order_section_header_count() -> None:
    headers = [row for row in SCHEMA_ORDER if row.kind == "section_header"]
    assert len(headers) == 6


def test_schema_order_subtotal_count() -> None:
    subtotals = [row for row in SCHEMA_ORDER if row.kind == "subtotal"]
    assert len(subtotals) == 6


def test_schema_order_grand_total_count() -> None:
    grand_totals = [row for row in SCHEMA_ORDER if row.kind == "grand_total"]
    assert len(grand_totals) == 2


def test_every_category_appears_exactly_once_as_line_item() -> None:
    line_item_categories = [row.category for row in SCHEMA_ORDER if row.kind == "line_item"]
    assert len(line_item_categories) == len(Category)
    assert set(line_item_categories) == set(Category)


def test_group_on_section_headers() -> None:
    income_sections = {
        Section.REGULAR_INFLOWS,
        Section.IRREGULAR_INFLOWS,
        Section.ASSET_LIQUIDATION,
    }
    expenditure_sections = {Section.REGULAR_OUTFLOWS, Section.IRREGULAR_OUTFLOWS, Section.ASSETS}
    for row in SCHEMA_ORDER:
        if row.kind == "section_header":
            assert row.section is not None
            if row.section in income_sections:
                assert row.group == "income", f"{row.section} header should have group='income'"
            elif row.section in expenditure_sections:
                assert row.group == "expenditure", (
                    f"{row.section} header should have group='expenditure'"
                )


def test_group_on_subtotals() -> None:
    income_sections = {
        Section.REGULAR_INFLOWS,
        Section.IRREGULAR_INFLOWS,
        Section.ASSET_LIQUIDATION,
    }
    for row in SCHEMA_ORDER:
        if row.kind == "subtotal":
            assert row.section is not None
            expected = "income" if row.section in income_sections else "expenditure"
            assert row.group == expected, (
                f"subtotal for {row.section} should have group='{expected}'"
            )


def test_group_on_grand_totals() -> None:
    grand_totals = [row for row in SCHEMA_ORDER if row.kind == "grand_total"]
    assert grand_totals[0].label == "Total Income"
    assert grand_totals[0].group == "income"
    assert grand_totals[1].label == "Total Expenditure"
    assert grand_totals[1].group == "expenditure"


def test_line_items_have_no_group() -> None:
    for row in SCHEMA_ORDER:
        if row.kind == "line_item":
            assert row.group is None, f"line_item {row.label} should have group=None"


def test_schema_order_fixed_sequence() -> None:
    labels = [row.label for row in SCHEMA_ORDER]
    assert labels[0] == "Regular Inflows"
    assert labels[1] == "Salary"
    assert labels[2] == "Regular Inflows subtotal"
    assert labels[11] == "Total Income"
    assert labels[-1] == "Total Expenditure"
    assert labels[-2] == "Assets subtotal"


# ── Helper functions ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (Category.SALARY, "Salary"),
        (Category.FOOD_SUPPLIES, "Food Supplies"),
        (Category.STOCKS_SHARES_ISA, "Stocks & Shares ISA"),
        (Category.GIFTS_ENTERTAINMENT_MISC, "Gifts/Entertainment/Misc"),
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
        (Category.SAVINGS, Section.ASSET_LIQUIDATION),
        (Category.STOCKS_AND_SHARES, Section.ASSET_LIQUIDATION),
        (Category.RENT, Section.REGULAR_OUTFLOWS),
        (Category.BILL_COUNCIL_TAX, Section.REGULAR_OUTFLOWS),
        (Category.BILL_ELECTRICITY_GAS, Section.REGULAR_OUTFLOWS),
        (Category.BILL_PHONE_INTERNET, Section.REGULAR_OUTFLOWS),
        (Category.FOOD_SUPPLIES, Section.REGULAR_OUTFLOWS),
        (Category.DEBT, Section.REGULAR_OUTFLOWS),
        (Category.CAR_AND_GAS, Section.REGULAR_OUTFLOWS),
        (Category.CHARITY_DONATIONS, Section.IRREGULAR_OUTFLOWS),
        (Category.GIFTS_ENTERTAINMENT_MISC, Section.IRREGULAR_OUTFLOWS),
        (Category.SUNDRY, Section.IRREGULAR_OUTFLOWS),
        (Category.HOLIDAYS_TRAVEL, Section.IRREGULAR_OUTFLOWS),
        (Category.EDUCATION, Section.IRREGULAR_OUTFLOWS),
        (Category.EATING_OUT, Section.IRREGULAR_OUTFLOWS),
        (Category.ACTIVE_SAVINGS, Section.ASSETS),
        (Category.LIFETIME_ISA, Section.ASSETS),
        (Category.STOCKS_SHARES_ISA, Section.ASSETS),
        (Category.DIVIDEND_PORTFOLIO, Section.ASSETS),
    ],
)
def test_section_for_category(category: Category, expected_section: Section) -> None:
    assert section_for_category(category) is expected_section


def test_section_for_every_category_is_defined() -> None:
    for category in Category:
        section = section_for_category(category)
        assert isinstance(section, Section)
