"""Tests for schema.py — Category and Section enumerations (Task 2.1)."""

import pytest

from lloyds_expense.schema import Category, Section


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
