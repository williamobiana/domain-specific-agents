"""Budget shape definition: category and section enumerations."""

import enum
from dataclasses import dataclass
from typing import Literal


class Category(enum.Enum):
    """All leaf budget categories used in the fixed CSV schema."""

    # Regular Inflows
    SALARY = "Salary"

    # Irregular Inflows
    UNEXPECTED_REFUND = "Unexpected / Refund"
    LOAN = "Loan"
    MAIN_ACCOUNT_INFLOW = "Main Account Inflow"

    # Asset Liquidation
    SAVINGS = "Savings"
    STOCKS_AND_SHARES = "Stocks & Shares"

    # Regular Outflows
    RENT = "Rent"
    BILL_COUNCIL_TAX = "Bill - Council Tax"
    BILL_ELECTRICITY_GAS = "Bill - Electricity & Gas"
    BILL_PHONE_INTERNET = "Bill - Phone & Internet"
    FOOD_SUPPLIES = "Food Supplies"
    DEBT = "Debt"
    CAR_AND_GAS = "Car & Gas"

    # Irregular Outflows
    CHARITY_DONATIONS = "Charity / Donations"
    GIFTS_ENTERTAINMENT_MISC = "Gifts/Entertainment/Misc"
    SUNDRY = "Sundry"
    HOLIDAYS_TRAVEL = "Holidays & Travel"
    EDUCATION = "Education"
    EATING_OUT = "Eating Out"

    # Assets
    ACTIVE_SAVINGS = "Active Savings"
    LIFETIME_ISA = "Lifetime ISA"
    STOCKS_SHARES_ISA = "Stocks & Shares ISA"
    DIVIDEND_PORTFOLIO = "Dividend Portfolio"


class Section(enum.Enum):
    """Top-level sections grouping categories in the fixed CSV schema."""

    REGULAR_INFLOWS = "Regular Inflows"
    IRREGULAR_INFLOWS = "Irregular Inflows"
    ASSET_LIQUIDATION = "Asset Liquidation"
    REGULAR_OUTFLOWS = "Regular Outflows"
    IRREGULAR_OUTFLOWS = "Irregular Outflows"
    ASSETS = "Assets"


@dataclass(frozen=True)
class SchemaRow:
    """One row in the fixed CSV output schema."""

    kind: Literal["section_header", "line_item", "subtotal", "grand_total", "balance"]
    section: Section | None
    category: Category | None
    label: str
    group: Literal["income", "expenditure"] | None


_SECTION_CATEGORY_MAP: dict[Category, Section] = {
    Category.SALARY: Section.REGULAR_INFLOWS,
    Category.UNEXPECTED_REFUND: Section.IRREGULAR_INFLOWS,
    Category.LOAN: Section.IRREGULAR_INFLOWS,
    Category.MAIN_ACCOUNT_INFLOW: Section.IRREGULAR_INFLOWS,
    Category.SAVINGS: Section.ASSET_LIQUIDATION,
    Category.STOCKS_AND_SHARES: Section.ASSET_LIQUIDATION,
    Category.RENT: Section.REGULAR_OUTFLOWS,
    Category.BILL_COUNCIL_TAX: Section.REGULAR_OUTFLOWS,
    Category.BILL_ELECTRICITY_GAS: Section.REGULAR_OUTFLOWS,
    Category.BILL_PHONE_INTERNET: Section.REGULAR_OUTFLOWS,
    Category.FOOD_SUPPLIES: Section.REGULAR_OUTFLOWS,
    Category.DEBT: Section.REGULAR_OUTFLOWS,
    Category.CAR_AND_GAS: Section.REGULAR_OUTFLOWS,
    Category.CHARITY_DONATIONS: Section.IRREGULAR_OUTFLOWS,
    Category.GIFTS_ENTERTAINMENT_MISC: Section.IRREGULAR_OUTFLOWS,
    Category.SUNDRY: Section.IRREGULAR_OUTFLOWS,
    Category.HOLIDAYS_TRAVEL: Section.IRREGULAR_OUTFLOWS,
    Category.EDUCATION: Section.IRREGULAR_OUTFLOWS,
    Category.EATING_OUT: Section.IRREGULAR_OUTFLOWS,
    Category.ACTIVE_SAVINGS: Section.ASSETS,
    Category.LIFETIME_ISA: Section.ASSETS,
    Category.STOCKS_SHARES_ISA: Section.ASSETS,
    Category.DIVIDEND_PORTFOLIO: Section.ASSETS,
}


def category_display_name(category: Category) -> str:
    """Return the human-readable display name for a category."""
    return category.value


def section_for_category(category: Category) -> Section:
    """Return the section that owns the given category."""
    return _SECTION_CATEGORY_MAP[category]


def _li(category: Category) -> SchemaRow:
    return SchemaRow(
        kind="line_item",
        section=_SECTION_CATEGORY_MAP[category],
        category=category,
        label=category.value,
        group=None,
    )


SCHEMA_ORDER: list[SchemaRow] = [
    # Regular Inflows
    SchemaRow(
        kind="section_header",
        section=Section.REGULAR_INFLOWS,
        category=None,
        label="Regular Inflows",
        group="income",
    ),
    _li(Category.SALARY),
    SchemaRow(
        kind="subtotal",
        section=Section.REGULAR_INFLOWS,
        category=None,
        label="Regular Inflows subtotal",
        group="income",
    ),
    # Irregular Inflows
    SchemaRow(
        kind="section_header",
        section=Section.IRREGULAR_INFLOWS,
        category=None,
        label="Irregular Inflows",
        group="income",
    ),
    _li(Category.UNEXPECTED_REFUND),
    _li(Category.LOAN),
    _li(Category.MAIN_ACCOUNT_INFLOW),
    SchemaRow(
        kind="subtotal",
        section=Section.IRREGULAR_INFLOWS,
        category=None,
        label="Irregular Inflows subtotal",
        group="income",
    ),
    # Asset Liquidation
    SchemaRow(
        kind="section_header",
        section=Section.ASSET_LIQUIDATION,
        category=None,
        label="Asset Liquidation",
        group="income",
    ),
    _li(Category.SAVINGS),
    _li(Category.STOCKS_AND_SHARES),
    SchemaRow(
        kind="subtotal",
        section=Section.ASSET_LIQUIDATION,
        category=None,
        label="Asset Liquidation subtotal",
        group="income",
    ),
    SchemaRow(
        kind="grand_total",
        section=None,
        category=None,
        label="Total Income",
        group="income",
    ),
    # Regular Outflows
    SchemaRow(
        kind="section_header",
        section=Section.REGULAR_OUTFLOWS,
        category=None,
        label="Regular Outflows",
        group="expenditure",
    ),
    _li(Category.RENT),
    _li(Category.BILL_COUNCIL_TAX),
    _li(Category.BILL_ELECTRICITY_GAS),
    _li(Category.BILL_PHONE_INTERNET),
    _li(Category.FOOD_SUPPLIES),
    _li(Category.DEBT),
    _li(Category.CAR_AND_GAS),
    SchemaRow(
        kind="subtotal",
        section=Section.REGULAR_OUTFLOWS,
        category=None,
        label="Regular Outflows subtotal",
        group="expenditure",
    ),
    # Irregular Outflows
    SchemaRow(
        kind="section_header",
        section=Section.IRREGULAR_OUTFLOWS,
        category=None,
        label="Irregular Outflows",
        group="expenditure",
    ),
    _li(Category.CHARITY_DONATIONS),
    _li(Category.GIFTS_ENTERTAINMENT_MISC),
    _li(Category.SUNDRY),
    _li(Category.HOLIDAYS_TRAVEL),
    _li(Category.EDUCATION),
    _li(Category.EATING_OUT),
    SchemaRow(
        kind="subtotal",
        section=Section.IRREGULAR_OUTFLOWS,
        category=None,
        label="Irregular Outflows subtotal",
        group="expenditure",
    ),
    # Assets
    SchemaRow(
        kind="section_header",
        section=Section.ASSETS,
        category=None,
        label="Assets",
        group="expenditure",
    ),
    _li(Category.ACTIVE_SAVINGS),
    _li(Category.LIFETIME_ISA),
    _li(Category.STOCKS_SHARES_ISA),
    _li(Category.DIVIDEND_PORTFOLIO),
    SchemaRow(
        kind="subtotal",
        section=Section.ASSETS,
        category=None,
        label="Assets subtotal",
        group="expenditure",
    ),
    SchemaRow(
        kind="grand_total",
        section=None,
        category=None,
        label="Total Expenditure",
        group="expenditure",
    ),
    SchemaRow(
        kind="balance",
        section=None,
        category=None,
        label="Balance",
        group=None,
    ),
]
