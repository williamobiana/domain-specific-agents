from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    name: str
    categories: list[str]


SCHEMA: list[Section] = [
    Section(name="Regular Inflows", categories=["Salary"]),
    Section(name="Irregular Inflows", categories=["Carry Over", "Unexpected / Refund", "Loan"]),
    Section(name="Asset Liquidation", categories=["Savings", "Stocks & Shares"]),
    Section(name="Regular Outflows", categories=[
        "Rent", "Bill - Council Tax", "Bill - Electricity & Gas",
        "Bill - Phone & Internet", "Food Supplies", "Debt", "Car & Gas",
    ]),
    Section(name="Irregular Outflows", categories=[
        "Charity / Donations", "Gifts Entertainment & Misc",
        "Sundry", "Holidays & Travel", "Education", "Eating Out",
    ]),
    Section(name="Assets", categories=[
        "Active Savings", "Lifetime ISA", "Stocks & Shares ISA", "Dividend Portfolio",
    ]),
]

INCOME_SECTIONS: list[str] = ["Regular Inflows", "Irregular Inflows", "Asset Liquidation"]
OUTFLOW_SECTIONS: list[str] = ["Regular Outflows", "Irregular Outflows", "Assets"]
