"""Budget shape definition: category and section enumerations."""

import enum


class Category(enum.Enum):
    """All leaf budget categories used in the fixed CSV schema."""

    # Regular Inflows
    SALARY = "Salary"
    
    # Irregular Inflows
    UNEXPECTED_REFUND = "Unexpected / Refund"
    LOAN = "Loan"
    
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
