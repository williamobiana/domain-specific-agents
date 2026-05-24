from dataclasses import dataclass
from typing import List

@dataclass
class Section:
    name: str
    categories: List[str]

# Canonical schema in defined order (6 sections, 21 categories total)
SCHEMA: List[Section] = [
    # Income sections (3 sections, 5 categories)
    Section(name="Regular Inflows", categories=["Salary"]),
    Section(name="Irregular Inflows", categories=["Carry Over", "Unexpected / Refund", "Loan"]),
    Section(name="Asset Liquidation", categories=["Savings", "Stocks & Shares"]),
    
    # Expense sections (3 sections, 16 categories)
    Section(name="Regular Outflows", categories=[
        "Rent",
        "Bill - Council Tax",
        "Bill - Electricity & Gas",
        "Bill - Phone & Internet",
        "Food Supplies",
        "Debt",
        "Car & Gas"
    ]),
    Section(name="Irregular Outflows", categories=[
        "Charity / Donations",
        "Gifts, Entertainment & Misc",
        "Sundry",
        "Holidays & Travel",
        "Education",
        "Eating Out"
    ]),
    Section(name="Assets", categories=[
        "Active Savings",
        "Lifetime ISA",
        "Stocks & Shares ISA",
        "Dividend Portfolio"
    ]),
]

# Section lists for grand total calculations
INCOME_SECTIONS: List[str] = ["Regular Inflows", "Irregular Inflows", "Asset Liquidation"]
OUTFLOW_SECTIONS: List[str] = ["Regular Outflows", "Irregular Outflows", "Assets"]

# Verify all sections are covered
assert set(INCOME_SECTIONS + OUTFLOW_SECTIONS) == {section.name for section in SCHEMA}
assert len(set(INCOME_SECTIONS) & set(OUTFLOW_SECTIONS)) == 0  # No overlap